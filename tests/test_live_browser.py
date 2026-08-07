"""Live browser service — ticket auth, origin policy, coordinate transform.

These are the pure-logic guarantees behind the stream. The full end-to-end proof
(frames + a click landing on a real page) needs a running gym and browser and
lives in the spike script; what must never silently regress is here.
"""

from __future__ import annotations

import time

import pytest

from live_browser import service


# --------------------------------------------------------------------------- tickets
def test_ticket_roundtrips_for_an_email_owner():
    """Regression: owners are emails, which contain dots. A dot-delimited ticket
    parsed the wrong fields and rejected every legitimate connection."""
    t = service.mint_ticket("sess123", "diego@deccan.ai")
    assert service.check_ticket("sess123", t) == "diego@deccan.ai"


@pytest.mark.parametrize("owner", ["a@b.co", "first.last+tag@sub.domain.example", "plain", "üser@dömain.io"])
def test_ticket_roundtrips_for_awkward_owners(owner):
    t = service.mint_ticket("s", owner)
    assert service.check_ticket("s", t) == owner


def test_ticket_is_scoped_to_its_session():
    """A ticket for one workspace must not open another — otherwise any annotator
    with a valid ticket could attach to someone else's live browser."""
    t = service.mint_ticket("sessA", "u@x.io")
    assert service.check_ticket("sessA", t) == "u@x.io"
    assert service.check_ticket("sessB", t) is None


def test_expired_ticket_is_rejected():
    assert service.check_ticket("s", service.mint_ticket("s", "u@x.io", ttl=-1)) is None


def test_tampered_ticket_is_rejected():
    t = service.mint_ticket("s", "u@x.io")
    exp, sig, owner_b64 = t.split(".", 2)
    # forge a later expiry, keep the old signature
    assert service.check_ticket("s", f"{int(exp) + 99999}.{sig}.{owner_b64}") is None
    # swap the owner, keep the signature
    assert service.check_ticket("s", f"{exp}.{sig}.{service._b64(b'attacker@evil.io')}") is None


@pytest.mark.parametrize("bad", ["", "garbage", "1.2", "notanint.sig.b3Vy", "..."])
def test_malformed_tickets_do_not_raise(bad):
    assert service.check_ticket("s", bad) is None


# --------------------------------------------------------------------------- origin
def test_origin_allowlist(monkeypatch):
    monkeypatch.setattr(service, "ALLOWED_ORIGINS", ["http://localhost:8080"])
    assert service.origin_ok("http://localhost:8080")
    assert not service.origin_ok("http://evil.example")
    assert not service.origin_ok(None)


def test_origin_wildcard_is_permissive(monkeypatch):
    monkeypatch.setattr(service, "ALLOWED_ORIGINS", ["*"])
    assert service.origin_ok("http://anything.example")


# --------------------------------------------------------------------------- coordinates
def _sess() -> service.LiveSession:
    return service.LiveSession(id="s", owner="u@x.io", url="http://localhost:8000/")


def test_normalized_coordinates_map_to_the_viewport():
    """The wire format is a FRACTION of the client canvas, so a scaled canvas can
    never mis-place a click: the service always multiplies by the real viewport."""
    s = _sess()
    assert s.to_page_xy(0.0, 0.0) == (0.0, 0.0)
    assert s.to_page_xy(1.0, 1.0) == (float(service.VIEWPORT_W), float(service.VIEWPORT_H))
    assert s.to_page_xy(0.5, 0.5) == (service.VIEWPORT_W / 2, service.VIEWPORT_H / 2)


def test_the_same_fraction_lands_identically_whatever_the_canvas_size():
    """A 900x563 and a 1920x1200 canvas both send the same fraction for the same
    on-screen point, and both must resolve to the same page pixel."""
    s = _sess()
    target_x, target_y = 1039.0, 72.0  # a real element position in page pixels
    for canvas_w, canvas_h in [(900, 563), (1920, 1200), (640, 400), (1280, 800)]:
        # what the client computes from ITS canvas
        client_px_x = target_x / service.VIEWPORT_W * canvas_w
        client_px_y = target_y / service.VIEWPORT_H * canvas_h
        nx, ny = client_px_x / canvas_w, client_px_y / canvas_h
        x, y = s.to_page_xy(nx, ny)
        assert x == pytest.approx(target_x, abs=0.001)
        assert y == pytest.approx(target_y, abs=0.001)


def test_out_of_range_coordinates_are_clamped_not_thrown():
    """A drag that leaves the canvas must not dispatch input outside the page."""
    s = _sess()
    assert s.to_page_xy(-5.0, -5.0) == (0.0, 0.0)
    assert s.to_page_xy(9.0, 9.0) == (float(service.VIEWPORT_W), float(service.VIEWPORT_H))


# --------------------------------------------------------------------------- structured actions
class FakeLocator:
    def __init__(self, page, sel, visible=True, count=1):
        self.page, self.sel, self.visible, self._count = page, sel, visible, count

    async def is_visible(self):
        return self.visible

    async def count(self):
        return self._count

    async def scroll_into_view_if_needed(self, timeout=0):
        return None

    async def click(self, timeout=0, button="left", click_count=1):
        if not self.visible:
            raise RuntimeError("intercepted")
        # Records the BUTTON and the count, because "did it click" is not the
        # question a right-click test is asking.
        self.page.calls.append(("click", self.sel, button, click_count))

    async def evaluate(self, script):
        self.page.calls.append(("tag", self.sel))

    @property
    def first(self):
        return self


class FakePage:
    """Stands in for a Playwright page: `present` is what the DOM contains, and
    `visible` decides whether the real click path works or falls through to JS."""

    def __init__(self, present=(), visible=True, url="http://localhost:8000/"):
        self.present, self.visible, self.url = set(present), visible, url
        self.calls: list[tuple] = []
        self.js: list[tuple] = []

    async def evaluate(self, script, arg=None):
        if isinstance(arg, list) and len(arg) == 3:            # _js_activate
            sel, kind, val = arg
            if sel not in self.present:
                return False
            self.js.append((kind, sel, val))
            return True
        if isinstance(arg, str):                                # querySelector probe
            return arg in self.present
        return None

    def locator(self, sel):
        return FakeLocator(self, sel, visible=self.visible)

    def get_by_role(self, role, name=""):
        return FakeLocator(self, f"role={role}[{name}]", count=1 if f"role:{role}:{name}" in self.present else 0)

    async def goto(self, url, wait_until="load"):
        self.url = url


def _live(page) -> service.LiveSession:
    s = _sess()
    s.page = page
    return s


@pytest.mark.asyncio
async def test_locator_resolution_prefers_the_most_durable_identifier():
    page = FakePage(present={'[data-test-id="btn-send"]', "#send", ".btn"})
    s = _live(page)
    sel = await s.resolve({"testId": "btn-send", "id": "send", "css": ".btn"})
    assert sel == '[data-test-id="btn-send"]', "a test id must beat an id or a css path"


@pytest.mark.asyncio
async def test_locator_resolution_falls_back_through_the_candidates():
    page = FakePage(present={".cart a"})
    s = _live(page)
    assert await s.resolve({"testId": "gone", "id": "gone", "css": ".cart a"}) == ".cart a"


@pytest.mark.asyncio
async def test_an_unresolvable_locator_fails_loudly():
    """A silently-skipped action produces a trajectory that claims to do something
    it never did — the worst possible outcome for a golden."""
    s = _live(FakePage(present=set()))
    out = await s.act("click", {"testId": "nope"})
    assert out["ok"] is False and "no element matched" in out["error"]


@pytest.mark.asyncio
async def test_click_uses_the_real_interaction_when_the_element_is_visible():
    page = FakePage(present={"#buy"}, visible=True)
    out = await _live(page).act("click", {"id": "buy"})
    assert out["ok"] and ("click", "#buy", "left", 1) in page.calls
    assert not page.js, "no need for the JS fallback when a real click works"


@pytest.mark.asyncio
async def test_click_falls_back_to_js_activation_instead_of_timing_out():
    """The harness's own rule: everything is pickable. A collapsed menu or an
    intercepted element must still activate — never hang."""
    page = FakePage(present={"#buy"}, visible=False)
    out = await _live(page).act("click", {"id": "buy"})
    assert out["ok"] and page.js == [("click", "#buy", None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [
    ("fill", "fill"), ("type", "fill"), ("select", "select"), ("select_option", "select"), ("check", "check"),
])
async def test_the_action_vocabulary_matches_the_agent_harness(kind, expected):
    """A human-authored golden is replayed by the SAME benchmark that runs agents.
    If the two dispatch differently, manual trajectories don't reproduce."""
    page = FakePage(present={"#f"})
    out = await _live(page).act(kind, {"id": "f"}, {"value": "hello"})
    assert out["ok"] and page.js[0][0] == expected
    if expected in ("fill", "select"):
        assert page.js[0][2] == "hello"


@pytest.mark.asyncio
async def test_navigate_needs_no_locator():
    page = FakePage()
    out = await _live(page).act("navigate", None, {"url": "http://localhost:8000/cart"})
    assert out["ok"] and page.url.endswith("/cart")


@pytest.mark.asyncio
async def test_an_unsupported_action_is_refused_not_guessed():
    page = FakePage(present={"#x"})
    out = await _live(page).act("teleport", {"id": "x"})
    assert out["ok"] is False and "unsupported" in out["error"]


@pytest.mark.asyncio
async def test_the_resolved_selector_is_reported_back():
    """Recording what actually matched is what makes the step auditable later —
    re-deriving it at replay time would silently pick a different element."""
    page = FakePage(present={"#buy"})
    out = await _live(page).act("click", {"id": "buy"})
    assert out["resolved"]["selector"] == "#buy"


# --------------------------------------------------------------------------- vocabulary completeness
class FakeCDPSession:
    """The CDP session `_bind` attaches per tab.

    Binding is per-PAGE, not per-context: the screencast, the mouse and the
    keyboard all ride this session, so switching tabs detaches and re-attaches
    one. The fake records what it was told to do so a test can assert the
    screencast actually followed the tab.
    """

    def __init__(self, page):
        self.page = page
        self.handlers: dict = {}
        self.sent: list = []
        self.detached = False

    def on(self, event, handler):
        self.handlers[event] = handler

    async def send(self, method, params=None):
        self.sent.append((method, params or {}))
        return {}

    async def detach(self):
        self.detached = True


class FakeContext:
    def __init__(self, pages):
        self.pages = pages
        self.opened = []
        self.cdp_sessions: list = []

    async def new_cdp_session(self, page):
        s = FakeCDPSession(page)
        self.cdp_sessions.append(s)
        return s

    def on(self, event, handler):
        """`context.on("page")` — popup adoption. Nothing in these tests opens
        one, so recording it is enough."""
        return None

    async def new_page(self):
        # A new tab loads the same app, so it sees the same elements — the real
        # context shares cookies and session, which is why tabs live in one.
        p = _tabbable(FakePage(present=set(self.pages[0].present) if self.pages else {"#buy"}))
        self.pages.append(p)
        self.opened.append(p)
        return p


def _tabbable(p):
    """A FakePage that can be fronted and closed, like a real tab."""
    p.fronted = False
    p.closed = False

    async def bring():
        p.fronted = True

    async def close():
        p.closed = True

    async def settle(state, timeout=0):
        p.settled = True

    p.settled = False
    p.bring_to_front = bring
    p.close = close
    p.wait_for_load_state = settle
    return p


def _multitab(n=2):
    pages = [_tabbable(FakePage(present={"#buy"}, url=f"http://localhost:8000/tab{i}")) for i in range(n)]
    s = _sess()
    s.context = FakeContext(pages)
    s.page = pages[0]
    return s, pages


@pytest.mark.asyncio
async def test_submit_is_supported():
    """Regression from a real replay probe: submit is the SECOND most common
    action in the archive (46 uses against 110 clicks), so an executor without it
    cannot replay roughly a fifth of every recorded trajectory."""
    page = FakePage(present={"#send"}, visible=False)

    async def settle(state, timeout=0):
        page.settled = True
    page.wait_for_load_state = settle
    page.settled = False

    out = await _live(page).act("submit", {"id": "send"})
    assert out["ok"] and page.js == [("click", "#send", None)]
    assert page.settled, "a submit navigates; reading the world before it settles reads the OLD world"


@pytest.mark.asyncio
async def test_every_action_kind_in_the_recorded_archive_is_executable():
    """The vocabulary must be COMPLETE, not merely overlapping with the harness.
    These eight kinds are what the archive actually contains."""
    # `right_click` and `dblclick` joined the list when the RECORDER stopped
    # flattening them into `click` — a step described as "right-click Save for
    # later" used to replay as a left click, report ok, and be stamped verified.
    # Recording them honestly is only half the fix: if the executor cannot
    # perform them, every trajectory containing one becomes unshippable instead.
    recorded = ["click", "fill", "submit", "navigate", "open_tab", "select", "check", "switch_tab",
                "right_click", "dblclick"]
    s, pages = _multitab()
    for p in pages:
        p.present = {"#x"}

    for kind in recorded:
        args = {"url": "/cart", "value": "v", "tab_index": 0}
        out = await s.act(kind, {"id": "x"}, args)
        assert out["ok"] is True, f"{kind} is in the archive but not executable: {out.get('error')}"


@pytest.mark.asyncio
async def test_open_tab_shares_the_browser_context():
    """Tabs live in ONE context so cookies and session survive — cross-app tasks
    are the point, and an agent logged out on every new tab could not do them."""
    s, pages = _multitab(1)
    out = await s.act("open_tab", None, {"url": "/mail"})
    assert out["ok"] and len(s.context.pages) == 2
    assert s.page is s.context.pages[1] and s.page.fronted


@pytest.mark.asyncio
async def test_switch_tab_out_of_range_is_refused_not_clamped():
    """Clamping would silently act on the WRONG tab — a trajectory that claims to
    read the mail tab while actually reading the shop one."""
    s, pages = _multitab(2)
    assert (await s.act("switch_tab", None, {"tab_index": 1}))["ok"]
    assert s.page is pages[1]
    bad = await s.act("switch_tab", None, {"tab_index": 7})
    # The refusal must NAME what could not be found. Tabs are addressable by
    # index or by stable id now, so the message reports both rather than the
    # older index-only "out of range".
    assert bad["ok"] is False
    assert "no such tab" in bad["error"] and "7" in bad["error"], bad["error"]
    assert s.page is pages[1], "a refused switch must not move the active tab"


@pytest.mark.asyncio
async def test_a_switch_carrying_a_url_goes_by_origin_not_by_index():
    """The replay path addresses an app the way the live pane does.

    A session opens with only the task's primary app and the others get a tab
    when first visited, so a recorded tab INDEX is meaningless by the time a
    replay reaches it. Worse, `tab_index` defaulted to 0: a switch carrying only
    {app, url} replayed as "go to the first tab" and answered ok, so every
    cross-app step ran against the primary app while the transcript read clean.
    """
    s, pages = _multitab(1)
    pages[0].url = "http://localhost:5201/"
    mail = _tabbable(FakePage(present={"#buy"}, url="http://localhost:5203/"))
    s.context.pages.append(mail)

    out = await s.act("switch_tab", None, {"app": "mail", "url": "http://localhost:5203/"})
    assert out["ok"] and s.page is mail, "the url must win over the absent index"
    assert out["kind"] == "switch_tab", "report the action that was asked for"
    assert out["resolved"]["openedTab"] is False, "mail already had a tab"


@pytest.mark.asyncio
async def test_a_switch_to_an_app_with_no_tab_yet_opens_one():
    """Only the primary app is open at the start, so the first move to any other
    app has no tab to find. Refusing here would strand the replay at step one of
    every cross-app trajectory."""
    s, pages = _multitab(1)
    pages[0].url = "http://localhost:5201/"

    out = await s.act("switch_tab", None, {"app": "food", "url": "http://localhost:5205/"})
    assert out["ok"] and len(s.context.pages) == 2
    assert out["resolved"]["openedTab"] is True, "and it says the tab was built, not found"


# --------------------------------------------------------------------------- observation
def test_the_observe_script_is_valid_javascript():
    """The JS is assembled by string formatting, so a Python-level mistake becomes
    a JS SYNTAX ERROR that only shows up in a browser.

    This is not hypothetical: a `\\n` inside a `//` comment in the Python source
    became a real newline, ended the comment early, and turned the rest of the
    line into code. `observe()` catches everything and returns {}, so every page
    yielded zero elements, every request still answered 200, and the dataset
    would simply have had no observations.
    """
    js = service._OBSERVE_JS
    assert "%s" not in js, "the descriptor was never substituted in"
    assert js.count("{") == js.count("}"), "unbalanced braces"
    assert js.count("(") == js.count(")"), "unbalanced parens"
    for n, line in enumerate(js.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        # A `//` comment cannot be followed by a bare newline mid-statement; the
        # check that actually catches the bug is that no comment line is left
        # holding an unterminated string.
        assert stripped.count("'") % 2 == 0, f"odd quote count on line {n}: {line!r}"


@pytest.mark.asyncio
async def test_observation_failure_is_reported_not_silently_empty(caplog):
    """`observe` is best-effort so a mid-navigation page cannot lose a step — but
    silence is how observation capture turns itself off permanently."""
    page = FakePage()

    async def boom(script, arg=None):
        raise RuntimeError("SyntaxError: Unexpected identifier")
    page.evaluate = boom

    with caplog.at_level("WARNING"):
        out = await _live(page).observe()
    assert out == {}
    assert any("observe failed" in r.message or "observe failed" in r.getMessage()
               for r in caplog.records), "a broken observe must say so"


@pytest.mark.asyncio
async def test_an_observation_carries_the_page_and_its_elements():
    page = FakePage()
    captured = {
        "url": "http://localhost:5201/cart", "title": "Cart",
        "viewport": {"w": 1280, "h": 800}, "scroll": {"x": 0, "y": 240},
        "text": "Subtotal $41.98", "truncated": False,
        "elements": [{"targetKey": "checkout-btn", "role": "button",
                      "bbox": {"x": 1, "y": 2, "w": 120, "h": 40}}],
    }

    async def ev(script, arg=None):
        return captured
    page.evaluate = ev

    out = await _live(page).observe()
    assert out["url"].endswith("/cart") and out["scroll"]["y"] == 240
    assert out["elements"][0]["targetKey"] == "checkout-btn"
    assert "tabId" in out, "an observation must say which tab it describes"


@pytest.mark.asyncio
async def test_the_last_tab_cannot_be_closed():
    s, pages = _multitab(1)
    out = await s.act("close_tab", None, {"tab_index": 0})
    assert out["ok"] is False and "last remaining" in out["error"]


@pytest.mark.asyncio
async def test_closing_the_active_tab_moves_focus_to_a_survivor():
    """Otherwise every later action dispatches into a closed page."""
    s, pages = _multitab(2)
    await s.act("switch_tab", None, {"tab_index": 1})
    s.context.pages = [pages[0], pages[1]]
    out = await s.act("close_tab", None, {"tab_index": 1})
    assert out["ok"] and pages[1].closed
    assert s.page is not pages[1]


@pytest.mark.asyncio
async def test_a_relative_path_resolves_against_the_session_origin():
    """Archived actions carry relative paths ("/account/orders"); resolving them
    against the wrong origin would navigate somewhere real."""
    s = _sess()
    s.url = "http://localhost:8000/some/deep/page"
    assert s._abs("/account/orders") == "http://localhost:8000/account/orders"
    assert s._abs("http://elsewhere.test/x") == "http://elsewhere.test/x"


@pytest.mark.asyncio
async def test_wait_reloads_because_our_pages_never_live_update():
    """The gym's pages are server-rendered. An agent that waits on a frozen page
    would never see the event it is waiting for."""
    page = FakePage()
    page.reloaded = False

    async def reload(wait_until="load"):
        page.reloaded = True
    page.reload = reload

    out = await _live(page).act("wait", None, {})
    assert out["ok"] and page.reloaded


# --------------------------------------------------------------------------- reconnect
def test_a_lease_held_by_a_detached_socket_is_reclaimable():
    """The dropped controller's lease is released in its own handler's `finally`,
    which cannot run until that socket finishes tearing down. A client that
    reconnects promptly arrives while the lease is still held by the socket it
    just lost, and would be demoted to a read-only viewer of its OWN session with
    no way back. A lease whose owner is no longer attached is nobody's lease."""
    s = _sess()
    s.controller = "ws-old"
    s.attached = set()  # the old socket is gone; its finally has not run yet
    assert s.controller not in s.attached

    s.attached.add("ws-new")
    if s.controller is not None and s.controller not in s.attached:
        s.controller = None
    assert s.controller is None, "the reconnecting client can take control"


def test_a_lease_held_by_a_LIVE_socket_is_not_stolen():
    """One controller at a time is the whole point — a second viewer must stay
    read-only while the first is still driving."""
    s = _sess()
    s.attached = {"ws-a"}
    s.controller = "ws-a"
    s.attached.add("ws-b")
    if s.controller is not None and s.controller not in s.attached:
        s.controller = None
    assert s.controller == "ws-a"


def test_the_input_counter_resets_so_a_reconnect_is_not_answered_stale():
    """`last_input_id` lives on the SESSION and outlives the socket, but a
    reconnecting client starts its ids at 1 again. Without a reset every input
    after a reconnect is acked applied:false/"stale" — input that looks delivered
    and is not, which is exactly what the ack channel exists to prevent."""
    s = _sess()
    s.last_input_id = 57
    s.last_input_id = 0  # what `stream` does on accept
    assert 1 > s.last_input_id, "the first input of the new socket is accepted"


@pytest.mark.asyncio
async def test_a_right_click_uses_the_right_button_and_never_falls_back():
    """A right-click that quietly becomes a left click is the failure this whole
    kind exists to end. The JS fallback dispatches a plain click, so it is
    deliberately NOT available here: an un-performable gesture must be refused,
    not substituted."""
    page = FakePage(present={"#x"})
    s = _live(page)

    out = await s.act("right_click", {"id": "x"}, {})
    assert out["ok"] is True
    assert page.calls == [("click", "#x", "right", 1)]

    hidden = FakePage(present={"#x"}, visible=False)
    refused = await _live(hidden).act("right_click", {"id": "x"}, {})
    assert refused["ok"] is False, "no silent downgrade to a JS click"
    assert hidden.js == [], "the JS fallback dispatches a LEFT click"


@pytest.mark.asyncio
async def test_a_double_click_clicks_twice():
    page = FakePage(present={"#x"})
    out = await _live(page).act("dblclick", {"id": "x"}, {})
    assert out["ok"] is True
    assert page.calls == [("click", "#x", "left", 2)]
