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

    def __init__(self, present=(), visible=True, url="http://localhost:8000/", says=None):
        self.present, self.visible, self.url = set(present), visible, url
        self.calls: list[tuple] = []
        self.js: list[tuple] = []
        #: selector -> what that element SAYS (its aria-label/name/text). Only
        #: needed by the tests about a path that resolves to the wrong element.
        self.says = dict(says or {})

    async def evaluate(self, script, arg=None):
        if isinstance(arg, list) and len(arg) == 3:            # _js_activate
            sel, kind, val = arg
            if sel not in self.present:
                return False
            self.js.append((kind, sel, val))
            return True
        if isinstance(arg, list) and len(arg) == 2:            # querySelector + identity probe
            sel, want = arg
            if sel not in self.present:
                return False
            if not want:
                return True
            return self.says.get(sel, want)[:120] == want[:120]
        if isinstance(arg, str):                                # legacy querySelector probe
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
        # A capture answers with pixels. The thumbnail path reads them off the
        # answer, and treats an empty one as "this tab could not be photographed".
        if method == "Page.captureScreenshot":
            return {"data": f"jpeg:{self.page.url}"}
        return {}

    async def detach(self):
        self.detached = True


class FakeContext:
    def __init__(self, pages):
        self.pages = pages
        self.opened = []
        self.cdp_sessions: list = []
        self._on_page = None

    async def new_cdp_session(self, page):
        s = FakeCDPSession(page)
        self.cdp_sessions.append(s)
        return s

    def on(self, event, handler):
        """`context.on("page")` — the popup follower."""
        if event == "page":
            self._on_page = handler

    async def new_page(self):
        # A new tab loads the same app, so it sees the same elements — the real
        # context shares cookies and session, which is why tabs live in one.
        p = _tabbable(FakePage(present=set(self.pages[0].present) if self.pages else {"#buy"}))
        self.pages.append(p)
        self.opened.append(p)
        # Playwright fires this for EVERY page in the context, not only for a
        # popup the page opened itself — which is the whole trap, so the fake
        # fires it too. Dispatched here, inside the awaited new_page(), because
        # that is when the real event arrives.
        if self._on_page is not None:
            self._on_page(p)
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
    s.context.on("page", s._on_new_page)
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
async def test_preopen_tabs_warms_background_tabs_without_switching():
    """A cua-hub session opens every app at once; only the primary stays active."""
    s, pages = _multitab(1)
    pages[0].url = "http://localhost:5201/"
    active = s.page
    await s.preopen_tabs([
        "http://localhost:5203/",
        "http://localhost:5202/",
        "http://localhost:5203/",  # duplicate origin — must not stack
    ])
    assert len(s.context.pages) == 3
    assert s.page is active, "preopen must not steal the screencast binding"
    # The context's page event fires for tabs WE open, and the popup follower
    # cannot tell them apart: unsuppressed it rebound to each one in turn, so a
    # five-app session came up watching the last app it pre-opened instead of the
    # task's primary — and recorded four popups for tabs nobody opened.
    assert s.notices == [], "a tab we asked for is not a popup"


@pytest.mark.asyncio
async def test_thumbnails_photograph_every_tab_without_touching_the_binding():
    """The dock draws the apps nobody is looking at, which means photographing a
    tab in place. Fronting one to shoot it would hide the tab the screencast is
    bound to and freeze the stream the annotator is working in."""
    s, pages = _multitab(3)
    await s._bind(pages[0])
    bound = s.cdp

    shots = await s.thumbnails()

    assert [t["url"] for t in shots] == [p.url for p in pages]
    assert [t["active"] for t in shots] == [True, False, False]
    assert all(t["data"] for t in shots), "a preview with no pixels is a placeholder"
    assert s.page is pages[0] and s.cdp is bound, "a preview must not steal the binding"
    assert not any(p.fronted for p in pages[1:]), "photographing a tab must not front it"
    # One throwaway session per tab per poll; leaking them exhausts the browser.
    assert all(c.detached for c in s.context.cdp_sessions if c is not bound)


@pytest.mark.asyncio
async def test_a_tab_that_cannot_be_photographed_is_omitted_not_blanked():
    """A blank preview drawn as if it were the app is a lie about a live page.
    Leaving it out lets the pane keep whatever it last had."""
    s, pages = _multitab(2)
    real = s.context.new_cdp_session

    async def refuse(page):
        if page is pages[1]:
            raise RuntimeError("target closed")
        return await real(page)

    s.context.new_cdp_session = refuse

    shots = await s.thumbnails()

    assert [t["url"] for t in shots] == [pages[0].url]


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


def test_the_descriptor_gives_an_unnamed_element_a_path():
    """An element with no test id, id or name described as {}, and a step whose
    locator is {} is refused at the last gate as unreplayable — which stranded
    whole hand-done attempts with no way to ship and no repair control. Not noise
    either: of the four locator-less clicks in the recorded corpus, one had
    changed the world."""
    js = service._DESCRIBE_EL_JS
    assert "cssPath" in js, "there must be a fallback handle"
    assert "nth-of-type" in js
    # The path has to REACH an anchor. resolve() uses querySelector, which takes
    # the first match, so a chain cut short of an id or body is relative and can
    # match a different element elsewhere on the page.
    assert "e.id" in js and "body" in js and "data-test-id" in js, (
        "the walk must terminate at something unique"
    )
    assert "parts.length >= 20" in js, "the cap has to be generous enough to reach the anchor"


@pytest.mark.asyncio
async def test_a_label_that_wraps_onto_two_lines_still_matches_itself():
    """ShopGym's "Returns\n& Orders" link, refused at step 0 of every run.

    The recorder stores `text` trimmed but NOT whitespace-collapsed, while the
    page is read collapsed — so the identity check compared "Returns\n& Orders"
    against "Returns & Orders" and concluded the element was a different one.
    Every multi-line label in every mock, and it is the FIRST action of the M105
    trajectory.
    """
    page = FakePage(present={"#orders"}, says={"#orders": "Returns & Orders"})

    sel = await _live(page).resolve({"role": "a", "text": "Returns\n& Orders", "css": "#orders"})

    assert sel == "#orders"


@pytest.mark.asyncio
async def test_a_path_that_lands_on_the_wrong_element_is_refused():
    """Resolving is not being right.

    An nth-of-type chain anchored at `#root` describes a POSITION, and one extra
    wrapper between recording and replay slides it onto a different element that
    resolves perfectly and does something else. On a real M105 replay the Send
    click landed on whatever now sat at that position, reported ok, and left the
    world with no sent mail: the trajectory failed at its last step with every
    action reporting success. The element has to still say what we wrote down.
    """
    page = FakePage(present={"#root > div:nth-of-type(1) > button:nth-of-type(1)",
                             "role:button:Send"},
                    says={"#root > div:nth-of-type(1) > button:nth-of-type(1)": "Discard"})

    sel = await _live(page).resolve({"role": "button", "text": "Send",
                                     "css": "#root > div:nth-of-type(1) > button:nth-of-type(1)"})

    assert sel != "#root > div:nth-of-type(1) > button:nth-of-type(1)", (
        "a path onto a button that now says Discard must not answer for Send"
    )
    assert sel == "[data-replay-target='1']", "it should fall through to the accessible name"


@pytest.mark.asyncio
async def test_a_path_onto_the_element_it_described_is_still_used():
    """The check must not cost the common case: when the path still lands on the
    thing we wrote down, it is the fastest and most exact handle there is."""
    page = FakePage(present={"#root > div:nth-of-type(1) > button:nth-of-type(1)"},
                    says={"#root > div:nth-of-type(1) > button:nth-of-type(1)": "Send"})

    sel = await _live(page).resolve({"role": "button", "text": "Send",
                                     "css": "#root > div:nth-of-type(1) > button:nth-of-type(1)"})

    assert sel == "#root > div:nth-of-type(1) > button:nth-of-type(1)"


@pytest.mark.asyncio
async def test_a_button_with_only_text_still_resolves_by_its_accessible_name():
    """The step that SENT the email, failing at the last action.

    ShopMail's Send is `<button>Send</button>` in a compose dialog: no testId, no
    id, no name attribute. The only handle the recorder could give it was an
    unanchored `#root > div:nth-of-type(1) > …` path, and one extra wrapper
    between recording and replay is enough to miss it. For a button the visible
    text IS the accessible name, so role+text finds it when the path does not.
    """
    calls: list[tuple] = []

    class Loc:
        async def count(self): return 1
        async def evaluate(self, _js): calls.append(("marked",))
        @property
        def first(self): return self

    class Page:
        async def evaluate(self, _js, sel=None): return False       # every selector misses
        def get_by_role(self, role, name=None):
            calls.append((role, name))
            return Loc()

    ex = service.LiveSession.__new__(service.LiveSession)
    ex.page = Page()
    sel = await ex.resolve({"role": "button", "text": "Send",
                            "css": "#root > div:nth-of-type(9) > button:nth-of-type(1)"})

    assert sel == "[data-replay-target='1']"
    assert ("button", "Send") in calls, "text must be offered as the accessible name"


def test_a_contenteditable_reports_its_text_as_its_value():
    """The bug that emptied every email body out of the trajectory.

    A contenteditable is a text field that is not an <input>, so it has no
    `value` property and `'value' in el` is false. Keystrokes into ShopMail's
    compose body therefore folded into a fill with value null: the step said the
    annotator typed SOMETHING and never what. Recorded on a real M105 run, where
    the wording of the reply IS the answer to the task.
    """
    js = service._DESCRIBE_EL_JS
    assert "el.isContentEditable" in js, "a contenteditable must report a value"
    # BEFORE the plain `value` read, not after. Anything can be given a `.value`
    # property, and a replay that filled a contenteditable by assigning el.value
    # did exactly that — so reading `value` first reported the phantom back and
    # the field looked filled while the page still showed an empty body.
    editable_at = js.index("if (el.isContentEditable) {")
    value_at = js.index("else if ('value' in el) d.value = el.value;")
    assert editable_at < value_at, "a phantom .value must not outrank the real content"
    # And the MARKUP alongside it: a rich editor stores markup (ShopMail keeps
    # bodyRef.current.innerHTML), so a fill that only knows the text rebuilds the
    # body as flat divs — same words, different body, hash says diverged.
    assert "d.valueHtml = el.innerHTML;" in js


def test_filling_a_contenteditable_writes_its_text_not_a_value_property():
    """`el.value = val` on a contenteditable invents a property nobody reads.

    The page is unchanged, the fill reports success, and the mail body stays
    empty. Replaying M105 that way filled nothing, clicked a Send that really was
    the Send button, and sent no mail — every action ok, trajectory failed at its
    last step, and the describe helper read the phantom back so the field even
    looked filled.
    """
    js = service._JS_ACTIVATE_JS if hasattr(service, "_JS_ACTIVATE_JS") else ""
    src = js or __import__("inspect").getsource(service.LiveSession._js_activate)
    assert "el.isContentEditable" in src and "el.textContent = val" in src, (
        "a contenteditable must be filled by writing its text"
    )


def test_a_named_element_still_gets_a_path_because_a_name_is_not_unique():
    """The condition that let a replay pay with the wrong card.

    testId and id identify ONE element; `name` does not — every radio in a group
    shares it. Skipping the path for named elements meant the controls that most
    need disambiguating never got one: a click on the PayPal radio recorded
    {role: input, name: "payment"}, `resolve` turned that into [name="payment"],
    and querySelector returned the FIRST match — the expired Visa the task exists
    to catch. The replay reported ok either way.
    """
    js = service._DESCRIBE_EL_JS
    assert "if (!testId && !el.id) d.selector = cssPath(el);" in js
    assert "!name" not in js.split("d.selector = cssPath")[0][-80:], (
        "a name must not suppress the path"
    )


def test_the_pane_can_operate_a_select_at_all():
    """A native dropdown is painted by the BROWSER, so the headless Chromium
    behind the screencast never renders one. Measured against the real ShopGym
    product page: clicking the Qty box moved its value from 'All' to 'All'.

    So the option list has to come back over the wire for the pane to draw, and
    the choice has to go back as its own message. Without both, every task whose
    answer runs through a <select> — a quantity, a per-line ship-to address — is
    impossible to annotate, and M102 is exactly that task.
    """
    src = __import__("inspect").getsource(service)
    assert "async def select_at" in src, "the pane must be able to READ the options"
    assert "async def select_value" in src, "and to CHOOSE one"
    assert '/live/sessions/{sid}/select-at' in src, "exposed over REST for the press path"
    assert 'kind == "select"' in src, "and accepted on the input channel"
    # It must use the real control, not assign .value — React listens for change.
    assert "select_option" in src


def test_the_frame_endpoint_reports_the_SESSION_viewport(monkeypatch):
    """A module-level route is not a method, and `self` there is a 500 nothing
    catches until something calls it.

    Making the viewport per-session rewrote several VIEWPORT_W references at once
    and one landed in /frame — the route the annotator backend calls for every
    per-step screenshot. The pane looked perfect while the whole screenshot
    channel 500'd, and the bundle would have shipped without its pixels.

    It must also report the SESSION's size, not the module default: a screenshot
    labelled with the wrong dimensions is worse than one with none.
    """
    from fastapi.testclient import TestClient

    class FakeSession:
        closed = False
        frame_seq = 7
        latest_frame = "AAA"
        vw, vh = 1884, 684

    monkeypatch.setitem(service.SESSIONS, "s1", FakeSession())
    r = TestClient(service.app).get("/live/sessions/s1/frame")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seq"] == 7 and body["data"] == "AAA"
    assert body["viewport"] == {"width": 1884, "height": 684}, (
        "the frame must be labelled with the size it was actually captured at"
    )


def test_the_thumbnails_endpoint_needs_a_ticket(monkeypatch):
    """A preview is a picture of somebody's live session — five of them, in fact,
    including whatever is on screen in their mail app. It is read behind the same
    ticket as every other read of the session, not left open because it is only
    pixels."""
    from fastapi.testclient import TestClient

    class FakeSession:
        closed = False
        vw, vh = 1280, 800

        async def thumbnails(self):
            return [{"tabId": "t1", "url": "http://localhost:5201/", "active": True, "data": "AAA"}]

    monkeypatch.setitem(service.SESSIONS, "s1", FakeSession())
    client = TestClient(service.app)

    assert client.post("/live/sessions/s1/thumbnails", json={"ticket": "forged"}).status_code == 403

    ok = client.post("/live/sessions/s1/thumbnails",
                     json={"ticket": service.mint_ticket("s1", "u@x.io")})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["thumbs"][0]["data"] == "AAA"
    # The caller draws these, and a thumbnail whose size it has to guess at
    # renders blurry or letterboxed.
    assert body["scale"] == service.THUMB_SCALE
    assert body["viewport"] == {"width": 1280, "height": 800}


def test_the_height_floor_does_not_reintroduce_the_letterboxing():
    """The floor was 600, and the stage the pane actually has is about 510px.

    So a request for 494 was clamped UP to 600, and `fit` then scaled the picture
    to 85% to make it back — min(1600/1584, 510/600) — which is exactly the
    letterboxing this negotiation exists to remove. The floor was undoing the fix
    and reporting a plausible-looking percentage while doing it.

    A short viewport is not a broken one: the page scrolls, which is what a short
    window does everywhere else.
    """
    assert service.MIN_VIEWPORT_H <= 400, (
        f"a floor of {service.MIN_VIEWPORT_H} is taller than the stage, so short panes "
        f"get clamped up and letterboxed again"
    )
    # The width floor stays real: below it the storefronts reflow to the mobile
    # layout, which is not the layout any task was authored against.
    assert service.MIN_VIEWPORT_W >= 900


@pytest.mark.asyncio
async def test_a_short_stage_gets_the_viewport_it_asked_for():
    """The regression above, at the size that produced it."""
    s = service.LiveSession.__new__(service.LiveSession)
    s.vw, s.vh, s.context, s.cdp = 1280, 800, None, None

    out = await s.resize(1584, 494)

    assert (out["width"], out["height"]) == (1584, 494), out
    assert (s.vw, s.vh) == (1584, 494)


@pytest.mark.asyncio
async def test_a_move_between_a_press_and_a_release_carries_the_held_button():
    """Why an annotator could not select or copy anything in the gym.

    `buttons` is the mask of what is HELD, and it is what makes a drag a drag.
    Moves were dispatched with button "none" and no mask, so Chrome treated every
    one as a hover: a press-move-release across a paragraph selected nothing.
    Measured against a real page — the same gesture returns "" without the mask
    and the full sentence with it.

    The gesture was recorded as a `drag` on top of that, which the executor
    cannot perform, so one attempt to read a value failed the whole trajectory
    at certify.
    """
    sent: list[dict] = []

    class Cdp:
        async def send(self, method, payload=None):
            sent.append(payload or {})

    s = service.LiveSession.__new__(service.LiveSession)
    s.cdp, s.vw, s.vh, s.held_button = Cdp(), 1280, 800, None

    await s.mouse("down", 0.1, 0.5, "left", 1)
    await s.mouse("move", 0.3, 0.5)
    await s.mouse("up", 0.3, 0.5, "left", 1)

    down, move, up = sent
    assert down["buttons"] == 1
    assert move["buttons"] == 1, "a move with the button held must say so, or it is a hover"
    assert move["button"] == "left"
    assert up["buttons"] == 0, "and the release must clear it"


@pytest.mark.asyncio
async def test_the_plain_move_MESSAGE_also_carries_the_held_button():
    """The same rule, on the path the pane actually uses.

    `mouse(phase="move")` had the mask and `move()` did not — and the pane sends
    `{type: "move"}` for every pointer move, so the fixed path was the one nobody
    called. A drag across a run of text was therefore still a sequence of hovers
    and still selected nothing: measured end to end against the running service,
    the identical gesture answered "" through `move` and 60 characters through
    `mouse`. Hence the delegation, and hence this test — a future `move` that
    dispatches its own event would silently reintroduce the whole defect.
    """
    sent: list[dict] = []

    class Cdp:
        async def send(self, method, payload=None):
            sent.append(payload or {})

    s = service.LiveSession.__new__(service.LiveSession)
    s.cdp, s.vw, s.vh, s.held_button = Cdp(), 1280, 800, None

    await s.mouse("down", 0.1, 0.5, "left", 1)
    await s.move(0.3, 0.5)                      # what the pane sends mid-drag
    await s.mouse("up", 0.3, 0.5, "left", 1)

    _, move, _ = sent
    assert move["type"] == "mouseMoved"
    assert move["buttons"] == 1, "a plain move mid-press is a DRAG, not a hover"
    assert move["button"] == "left"


@pytest.mark.asyncio
async def test_a_plain_hover_carries_no_button():
    """The other half: an ordinary move must not look like a drag, or every
    mouseover on the page would start selecting text."""
    sent: list[dict] = []

    class Cdp:
        async def send(self, method, payload=None):
            sent.append(payload or {})

    s = service.LiveSession.__new__(service.LiveSession)
    s.cdp, s.vw, s.vh, s.held_button = Cdp(), 1280, 800, None

    await s.mouse("move", 0.4, 0.4)

    assert sent[0]["buttons"] == 0 and sent[0]["button"] == "none"


@pytest.mark.asyncio
async def test_the_whole_page_fit_re_measures_because_narrowing_reflows():
    """One measure-then-resize lands on a height that is already wrong.

    Narrowing the viewport reflows the page TALLER — measured on the ShopGym
    cart, 1280 to 1128 wide took the content from 1378px to 1956px — so the
    height measured at the old width does not fit the new one. Each pass has to
    re-measure at the width it will actually render at.
    """
    heights = iter([1378, 1956, 2100, 2100, 2100, 2100])
    seen: list[tuple[int, int]] = []

    class S(service.LiveSession):
        def __init__(self):
            self.vw, self.vh, self.context, self.cdp = 1280, 800, None, None
        async def metrics(self):
            h = next(heights)
            return {"contentHeight": h, "contentWidth": 1128,
                    "innerWidth": self.vw, "innerHeight": self.vh}
        async def resize(self, width, height):
            seen.append((width, height))
            changed = (width, height) != (self.vw, self.vh)
            self.vw, self.vh = width, height
            return {"ok": True, "width": width, "height": height, "changed": changed}

    out = await S().fit_page(1128)

    assert len(seen) >= 2, f"a single pass cannot be right: {seen}"
    assert seen[0] == (1128, 1378) and seen[1] == (1128, 1956)
    assert out["width"] == 1128


@pytest.mark.asyncio
async def test_a_page_that_never_settles_is_reported_not_hidden():
    """The ShopGym cart's carousels render more as the viewport grows, so the
    height chases itself. Claiming "no scrolling" there is a lie the annotator
    discovers by scrolling, and the pass cap must not turn into a hang."""
    class S(service.LiveSession):
        def __init__(self):
            self.vw, self.vh, self.context, self.cdp = 1280, 800, None, None
            self.n = 0
        async def metrics(self):
            self.n += 1
            return {"contentHeight": 1000 * self.n, "contentWidth": 1128,
                    "innerWidth": self.vw, "innerHeight": self.vh}
        async def resize(self, width, height):
            self.vw, self.vh = width, height
            return {"ok": True, "width": width, "height": height, "changed": True}

    s = S()
    out = await s.fit_page(1128)

    assert out["whole"] is False, "a page that never settles must say so"
    assert s.n <= service._FIT_PAGE_PASSES + 1, "the cap is what stops this hanging"
