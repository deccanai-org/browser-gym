"""Live browser service — CDP screencast out, input back-channel in.

This is what lets a human WATCH and DRIVE the same browser the agent uses. It is
deliberately a separate process from ``server.main``: the gym owns world state,
this owns a browser, and neither imports the other.

Wire contract
-------------
``POST /live/sessions``            open a browser session -> {session_id, ticket}
``WS   /live/stream/{session_id}`` frames out, input in (ticket required)
``POST /live/sessions/{id}/close`` reclaim

**Coordinates are NORMALIZED (0..1), never pixels.** The rendered canvas is almost
never the same size as the 1280x800 viewport, so shipping pixels would silently
mis-place every click. The client sends a fraction of its canvas; the service
multiplies by the real viewport. Scale bugs become impossible by construction.

Security (not deferred — a stream is a remote-control channel)
-------------------------------------------------------------
* short-lived HMAC ticket, scoped to session id + owner
* Origin allow-list on the websocket handshake
* exactly ONE controller at a time; extra viewers are read-only
* monotonic input ids, acknowledged back, so input order is observable
* tickets die with the session
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import functools
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = logging.getLogger("live_browser")

#: The DEFAULT viewport. A session may resize itself to the shape of the pane it
#: is being watched in — see LiveSession.resize.
VIEWPORT_W = int(os.getenv("LIVE_VIEWPORT_W", "1280"))
VIEWPORT_H = int(os.getenv("LIVE_VIEWPORT_H", "800"))

#: What a session may negotiate itself to.
#:
#: The WIDTH floor is real: below about 900px the storefronts reflow to their
#: mobile layout, which is not the layout any task was authored against.
#:
#: The HEIGHT floor is deliberately low. It was 600, which is TALLER than the
#: stage the pane actually has (~510px once the app chrome is accounted for), so
#: a request for 494 was clamped UP to 600 and `fit` then shrank the picture to
#: 85% to make it back — the floor was reintroducing the exact letterboxing the
#: negotiation exists to remove. A short viewport is not a broken one: the page
#: simply scrolls, which is what a short window does everywhere else.
MIN_VIEWPORT_W, MAX_VIEWPORT_W = 900, 2560
#: The ceiling is generous because the pane's whole-page fit asks for a viewport
#: as tall as the CONTENT, so no scrolling is needed at all — a cart or a product
#: page runs well past a window's height. It is only a render size; the picture
#: is scaled down to the stage.
MIN_VIEWPORT_H, MAX_VIEWPORT_H = 360, 4000
#: How many measure-resize passes the whole-page fit gets. Narrowing reflows the
#: page taller, so one pass is never enough and an unbounded loop is a hang.
_FIT_PAGE_PASSES = 4

#: How a dock thumbnail is rendered: a fraction of the viewport, JPEG-compressed
#: harder than the screencast. Five apps, re-photographed on a timer, ride this
#: wire repeatedly — a full-size frame is ~60KB of base64 each, this is ~14KB.
#: Small enough to be cheap, big enough to recognise a storefront from.
THUMB_SCALE = 0.3
THUMB_QUALITY = 50

#: How long a real Playwright fill may take before we fall back to the JS one.
#: Short on purpose — the fallback is what keeps a hidden-but-present element
#: fillable, so waiting here only delays reaching it.
_FILL_TIMEOUT_MS = 2000
TICKET_TTL_S = int(os.getenv("LIVE_TICKET_TTL_S", "300"))
SECRET = os.getenv("LIVE_STREAM_SECRET", os.getenv("HARNESS_TOKEN", "dev-live-secret"))
# "*" allows any origin (dev only); otherwise a comma-separated allow-list.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("LIVE_ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="live-browser")

# The pane's REST calls (open/close/act/describe) come from the annotator's
# frontend, a DIFFERENT origin in any hosted deploy. Without CORS the browser
# blocks them and the pane is dead cross-origin — the websocket is unaffected (it
# Origin-checks against ALLOWED_ORIGINS itself). Same allow-list for both; the
# ticket, not the origin, is what actually authorises a session.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- tickets
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mint_ticket(session_id: str, owner: str, ttl: int = TICKET_TTL_S) -> str:
    """A ticket authorises ONE session for ONE owner for a short window. Signed, so
    the service needs no shared session store to validate it.

    The owner is base64url-encoded: owners are emails, which contain dots, and a
    dot-delimited ticket would otherwise parse the wrong fields (it did).
    """
    exp = int(time.time()) + ttl
    payload = f"{session_id}:{owner}:{exp}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}.{_b64(owner.encode())}"


def check_ticket(session_id: str, ticket: str) -> str | None:
    """Returns the owner when valid, else None. Constant-time compare."""
    try:
        exp_s, sig, owner_b64 = ticket.split(".", 2)
        exp = int(exp_s)
        owner = _unb64(owner_b64).decode()
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    if exp < time.time():
        return None
    expect = hmac.new(SECRET.encode(), f"{session_id}:{owner}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return owner if hmac.compare_digest(expect, sig) else None


def origin_ok(origin: str | None) -> bool:
    if "*" in ALLOWED_ORIGINS:
        return True
    return bool(origin) and origin in ALLOWED_ORIGINS


# ONE descriptor shape, shared by /describe, /focused and every ack. Two shapes
# was a real bug: `describe` included `text` and `focused` did not, so the same
# element compared unequal depending on which call produced it, and a single
# typing run split into two separate fills.
#
# `value` is what makes a recorded fill correct — the client only knows the keys
# it sent, so Backspace, autocomplete or a rejected keystroke made its idea of the
# field wrong. `targetKey` is a stable identity for coalescing.
_DESCRIBE_EL_JS = """(el) => {
    if (!el || el === document.body) return {};
    // A CSS PATH, so that every element has SOME durable handle.
    //
    // Elements with no test id, id, name or text described as {} — and a step
    // whose locator is {} is refused at the last gate as unreplayable, which
    // stranded whole hand-done attempts with no way to ship and no repair
    // control. It is not noise either: of the four locator-less clicks in the
    // recorded corpus, one had changed the world.
    //
    // Anchored at the nearest ancestor carrying a test id or an id, so the path
    // is as short as the page allows and survives changes above that anchor.
    // Last resort by construction — `resolve` tries testId, id and name first,
    // and an nth-of-type chain is the most layout-fragile thing here.
    const cssPath = (node) => {
        const parts = [];
        for (let e = node; e && e.nodeType === 1 && e !== document.documentElement; e = e.parentElement) {
            const testId = e.getAttribute && e.getAttribute('data-test-id');
            if (testId) { parts.unshift('[data-test-id="' + CSS.escape(testId) + '"]'); break; }
            if (e.id) { parts.unshift('#' + CSS.escape(e.id)); break; }
            const tag = e.tagName.toLowerCase();
            if (tag === 'body') { parts.unshift('body'); break; }
            let n = 1;
            for (let sib = e.previousElementSibling; sib; sib = sib.previousElementSibling)
                if (sib.tagName === e.tagName) n++;
            parts.unshift(tag + ':nth-of-type(' + n + ')');
            // Generous, because the path must REACH its anchor. `resolve` uses
            // querySelector, which takes the first match, so a chain cut short
            // of an id or body is relative and can match the wrong element
            // somewhere else on the page. Anchored + nth-of-type at every level
            // is unique by construction; a cut chain is a coin flip.
            if (parts.length >= 20) break;
        }
        return parts.join(' > ');
    };
    const attr = (n) => el.getAttribute(n) || '';
    const tag = el.tagName.toLowerCase();
    const testId = attr('data-test-id');
    const name = attr('name');
    const d = {
        testId, id: el.id || '', name,
        role: attr('role') || tag,
        type: attr('type'), autocomplete: attr('autocomplete'),
        label: attr('aria-label').slice(0, 120),
        tag,
        text: (el.innerText || el.textContent || '').trim().slice(0, 120),
    };
    // A contenteditable IS a text field; it just is not an <input>. Every rich
    // editor is built this way — a mail compose body, a comment box, a note —
    // and `value` does not exist on one, so keystrokes folded into a fill with
    // value null: the trajectory said the annotator typed SOMETHING into the
    // message body and never what, on a task whose answer IS the wording.
    //
    // Checked BEFORE `value`, not after. Anything can be given a `.value`
    // property, and a replay that filled one by assigning `el.value` did exactly
    // that — so reading `value` first reported the phantom back and the field
    // looked filled while the page still showed an empty body. For a
    // contenteditable the content is the text, by definition; a `value` sitting
    // on it is not the content.
    if (el.isContentEditable) {
        d.value = (el.innerText || el.textContent || '');
        // The MARKUP as well as the text, because a rich editor stores markup:
        // ShopMail keeps `bodyRef.current.innerHTML`. Replaying a fill that only
        // knows the text rebuilds the body as flat divs, so the sent mail has
        // the same words and a different body, and the world hash says diverged.
        // `value` stays plain text — it is what a trajectory is read for, and
        // nobody training on this wants a <span> in it.
        d.valueHtml = el.innerHTML;
    }
    else if ('value' in el) d.value = el.value;
    if (el.type === 'checkbox' || el.type === 'radio') d.checked = !!el.checked;
    if (tag === 'select' && el.selectedIndex >= 0)
        d.selectedText = (el.options[el.selectedIndex] || {}).text || '';
    const r = el.getBoundingClientRect();
    d.bbox = {x: r.x, y: r.y, w: r.width, h: r.height};
    // Whitespace collapsed: an element's text can span several lines, and a key
    // with a line break inside it is awkward everywhere it is later read — a
    // JSON dataset, a log line, a diff. Same rule for every caller, so the
    // identity still matches across describe/focused/observe.
    // Whenever there is no UNIQUE handle. testId and id identify one element;
    // `name` does not — every radio in a group shares it, which is the whole
    // point of a radio group. Skipping the path for named elements meant the
    // controls that most need disambiguating were the ones that never got it:
    // a click on the PayPal radio recorded {role: input, name: "payment"},
    // `resolve` turned that into [name="payment"], and querySelector returned
    // the FIRST match — the expired Visa. The replay then paid with the card the
    // task exists to catch, reported ok, and the sample would have shipped
    // saying the annotator chose PayPal.
    if (!testId && !el.id) d.selector = cssPath(el);
    d.targetKey = testId || el.id || name ||
        tag + ':' + (d.label || d.text).replace(/\\s+/g, ' ').trim().slice(0, 40);
    return d;
}"""

_FOCUS_JS = f"() => ({_DESCRIBE_EL_JS})(document.activeElement)"


# Every INTERACTIVE element on the page, described the same way a clicked one is.
#
# This is the observation half of a trajectory. Without it a sample says what the
# annotator did and nothing about what they could see, which is not something a
# policy can be trained on: the model has to learn "given this page, click that",
# and the page was never recorded. Reusing `_DESCRIBE_EL_JS` matters — the element
# in the inventory and the element in the action then carry the SAME `targetKey`,
# so a consumer can find the action's target in the observation by identity rather
# than by guessing from coordinates.
#
# Visible elements only, and capped. An uncapped dump of a storefront is hundreds
# of kilobytes per step, most of it chrome the annotator never looked at, and the
# cost lands on every step of every trajectory.
_OBSERVE_JS = """(max) => {
    const SEL = 'a[href],button,input,select,textarea,[role=button],[role=link],' +
                '[role=checkbox],[role=radio],[role=tab],[role=menuitem],[onclick],' +
                '[data-test-id],[contenteditable=true]';
    const describe = %s;
    const seen = new Set();
    const out = [];
    for (const el of document.querySelectorAll(SEL)) {
        if (out.length >= max) break;
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) continue;                       // laid out but not rendered
        if (r.bottom < 0 || r.top > (window.innerHeight || 0) * 3) continue;  // far off-screen
        const s = window.getComputedStyle(el);
        if (s.visibility === 'hidden' || s.display === 'none' || s.opacity === '0') continue;
        const d = describe(el);
        if (!d || !d.targetKey) continue;
        if (seen.has(d.targetKey)) continue;                       // one row per identity
        seen.add(d.targetKey);
        d.disabled = !!el.disabled;
        d.inViewport = r.top < (window.innerHeight || 0) && r.bottom > 0;
        out.push(d);
    }
    return {
        url: location.href,
        title: document.title,
        viewport: {w: window.innerWidth, h: window.innerHeight},
        scroll: {x: window.scrollX, y: window.scrollY},
        // What the page SAYS, capped. The element inventory covers what can be
        // acted on; this covers what can be read — prices, totals, confirmations
        // — which is most of what a shopping task actually turns on.
        text: (document.body ? document.body.innerText : '').slice(0, 20000),
        elements: out,
        truncated: out.length >= max,
    };
}""" % _DESCRIBE_EL_JS

# Enough to cover a dense storefront listing without letting one pathological
# page dominate the dataset.
OBSERVE_MAX_ELEMENTS = 300


# --------------------------------------------------------------------------- session
@dataclass
class LiveSession:
    """One browser, owned for the life of a workspace."""

    id: str
    owner: str
    url: str
    pw: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    cdp: Any = None
    # Latest-wins: a slow client must never grow an unbounded backlog, and a stale
    # frame is worthless — only the newest pixels matter.
    latest_frame: str | None = None
    frame_seq: int = 0
    frame_event: asyncio.Event = field(default_factory=asyncio.Event)
    controller: str | None = None          # ws id currently allowed to send input
    # Sockets currently attached. A controller lease is only meaningful while its
    # socket is still here — see the reconnect handling in `stream`.
    attached: set = field(default_factory=set)
    last_input_id: int = 0
    closed: bool = False
    #: This session's viewport. Per-session rather than global because the pane
    #: negotiates it: a fixed 1280x800 inside a stage of a different shape gets
    #: letterboxed, and the bars were costing ~790px of horizontal space — the
    #: page rendered at 63% with blank margins either side. Matching the shape
    #: means scale 1.0 and nothing wasted.
    vw: int = VIEWPORT_W
    vh: int = VIEWPORT_H
    #: Which button is currently held, so a move between a press and a release
    #: carries the `buttons` mask that makes it a drag rather than a hover.
    held_button: str | None = None
    # Which page the screencast and mouse are currently bound to. Bumped on every
    # rebind so a frame emitted by a superseded tab can be dropped instead of
    # painting over the tab the annotator just switched to.
    epoch: int = 0
    # Stable per-tab identity. Indices are NOT identity — closing tab 0 renumbers
    # every tab after it, and a recorded step's `tab_id` has to survive that.
    tab_ids: dict = field(default_factory=dict)
    _next_tab_no: int = 0
    # Things that happened in the browser without the annotator asking (a popup,
    # a JS redirect). Drained by the socket pump so the client can record them.
    notices: list = field(default_factory=list)
    notice_seq: int = 0
    # Whether a new page is a POPUP — i.e. one the page opened on its own, worth
    # following and recording. Cleared while this service opens tabs of its own;
    # see _own_new_pages.
    follow_new_pages: bool = True

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": self.vw, "height": self.vh},
            device_scale_factor=1,
        )
        # A target=_blank click creates a page nobody asked for. Without this the
        # popup is invisible: the stream keeps showing the opener and the click
        # looks like it did nothing.
        self.context.on("page", self._on_new_page)
        with self._own_new_pages():     # the session's own first tab is not a popup
            page = await self.context.new_page()
        await page.goto(self.url, wait_until="load")
        # `load` fires when the document and its assets are in — which is BEFORE
        # these apps have anything on screen. Each mock is an SPA that then fetches
        # its world from the bridge and re-renders; the cart lines, and therefore
        # the gift-message field, exist only after that.
        #
        # A server-side replay opens a browser and immediately dispatches action
        # 0, so losing that race made the first locator miss — and because the
        # replay stops at the first failure, a whole trajectory came back as
        # "13 steps diverged / did not replay" when the truth was that we looked
        # before the page had drawn. Same shape as the world-read race in the
        # materializer: a race lost, reported as a definite negative.
        #
        # Suppressed rather than awaited hard: a page that never goes idle (a
        # poll, an open socket) must not stop the session from opening. The
        # timeout is the cost of being wrong, once, at open.
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=5000)
        await self._bind(page)

    async def preopen_tabs(self, urls: list[str]) -> None:
        """Open each URL in its own tab without switching away from the active one.

        A cua-hub task spans up to five apps on five origins. Opening them all at
        session start lets the annotator see a real multi-window ecosystem instead
        of discovering tabs one at a time. Shared BrowserContext keeps cookies
        intact for cross-app effects.
        """
        from urllib.parse import urlsplit
        with self._own_new_pages():
            for url in urls:
                if not url:
                    continue
                pages = self._tabs()
                want = urlsplit(url)
                if any(urlsplit(p.url).netloc == want.netloc for p in pages):
                    continue
                page = await self.context.new_page()
                await page.goto(url, wait_until="load")
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state("networkidle", timeout=5000)
                self.tab_id(page)

    # --- tab binding --------------------------------------------------------
    def tab_id(self, page) -> str:
        """Stable id for a page, minted on first sight."""
        tid = self.tab_ids.get(page)
        if tid is None:
            self._next_tab_no += 1
            tid = f"t{self._next_tab_no}"
            self.tab_ids[page] = tid
        return tid

    async def _bind(self, page) -> None:
        """Point the screencast AND the mouse at `page`.

        This is the multi-tab fix. The CDP session used to be created once, at
        start, and never rebound — while `self.page` (keyboard, describe,
        navigate) did move on a tab switch. The result was a session split in
        half: pixels and mouse went to the ORIGINAL tab, keyboard and locators to
        the new one. A cross-app task was impossible, and the failure looked like
        a seeding bug rather than a binding one.

        The old session is torn down BEFORE the new one is attached, and the epoch
        is bumped first, so in-flight frames from the old tab are discarded.
        """
        old = self.cdp
        self.epoch += 1
        epoch = self.epoch
        if old is not None:
            with contextlib.suppress(Exception):
                await old.send("Page.stopScreencast")
            with contextlib.suppress(Exception):
                await old.detach()
        self.page = page
        self.tab_id(page)
        with contextlib.suppress(Exception):
            await page.bring_to_front()
        self.cdp = await self.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", functools.partial(self._on_frame, epoch))
        await self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 60,
            "maxWidth": self.vw, "maxHeight": self.vh, "everyNthFrame": 1,
        })

    def _notice(self, event: str, payload: dict) -> None:
        """Queue a server-originated event for the client to record."""
        self.notice_seq += 1
        self.notices.append({"type": "notice", "seq": self.notice_seq, "event": event, **payload})
        del self.notices[:-50]          # a client that never drains must not grow this
        self.frame_event.set()

    @contextlib.contextmanager
    def _own_new_pages(self):
        """Open tabs of our own without them being mistaken for popups.

        `context.on("page")` fires for EVERY page in the context, including the
        ones this service asks for — Playwright does not distinguish them — and
        following one rebinds the screencast to it. A five-app session therefore
        came up watching the LAST app it pre-opened instead of the task's primary,
        and recorded four `popup` notices for tabs nobody opened.

        Safe as a flag because `_on_new_page` is dispatched synchronously as the
        event arrives, which is while the `new_page()` that caused it is still
        being awaited inside this block.
        """
        self.follow_new_pages = False
        try:
            yield
        finally:
            self.follow_new_pages = True

    def _on_new_page(self, page) -> None:
        if not self.follow_new_pages:
            return
        asyncio.create_task(self._adopt_page(page))

    async def _adopt_page(self, page) -> None:
        """Follow a popup the page opened itself, and tell the client."""
        with contextlib.suppress(Exception):
            await page.wait_for_load_state()
        if self.closed or page not in self._tabs():
            return
        await self._bind(page)
        self._notice("popup", {"tabId": self.tab_id(page), "url": page.url,
                               "tabIndex": self._tabs().index(page)})

    def _on_frame(self, epoch: int, params: dict) -> None:
        # A frame from a binding we have already replaced would paint the OLD tab
        # over the new one — drop it, and do not ack it either (that CDP session
        # is being detached).
        if epoch != self.epoch:
            return
        # Ack FIRST — Chromium stops emitting until the previous frame is
        # acknowledged, so an un-acked frame silently freezes the stream.
        sid = params.get("sessionId")
        if sid is not None and self.cdp is not None:
            asyncio.create_task(self._ack(sid))
        self.latest_frame = params.get("data")
        self.frame_seq += 1
        self.frame_event.set()

    async def _ack(self, session_id: int) -> None:
        with contextlib.suppress(Exception):
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": session_id})

    # --- input ------------------------------------------------------------
    def to_page_xy(self, nx: float, ny: float) -> tuple[float, float]:
        """Normalized (0..1) -> page pixels. This is the whole reason the wire
        format is fractional: the client canvas is scaled, the viewport is not."""
        nx = min(max(float(nx), 0.0), 1.0)
        ny = min(max(float(ny), 0.0), 1.0)
        return nx * self.vw, ny * self.vh

    async def click(self, nx: float, ny: float, button: str = "left", clicks: int = 1) -> None:
        x, y = self.to_page_xy(nx, ny)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y, "button": "none"})
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": clicks})
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": clicks})

    async def move(self, nx: float, ny: float) -> None:
        """A pointer move, carrying whatever button is currently HELD.

        Delegates to `mouse` rather than dispatching its own event, because the
        `buttons` mask is the entire difference between a hover and a drag. This
        used to send `button: "none"` with no mask at all, so every intermediate
        move of a press-move-release was a hover: Chromium never extended the
        selection, and an annotator could not highlight a single word. Measured
        against the ShopGym home page — the same gesture selects 60 characters
        with the mask and returns "" without it — which also made the recorder
        see a drag with no selection and write down a `drag` step the executor
        cannot perform.
        """
        await self.mouse("move", nx, ny)

    async def scroll(self, nx: float, ny: float, dy: float, dx: float = 0.0) -> None:
        x, y = self.to_page_xy(nx, ny)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": x, "y": y, "deltaX": dx, "deltaY": dy})

    async def mouse(self, phase: str, nx: float, ny: float,
                    button: str = "left", clicks: int = 1) -> None:
        """One pointer PHASE — down, up or move.

        Separate from `click` on purpose: only the client knows where a press
        ended, so only a real down/up pair can tell a drag from a click.
        """
        x, y = self.to_page_xy(nx, ny)
        cdp_type = {"down": "mousePressed", "up": "mouseReleased"}.get(phase, "mouseMoved")

        # `buttons` is the mask of what is HELD, and it is what makes a drag a
        # drag. Without it every move is a hover, so a press-move-release across
        # a run of text selected nothing at all — an annotator could not select
        # or copy anything in the gym, and the attempt was recorded as a drag
        # the executor cannot perform, which failed the whole trajectory at
        # certify. Measured: the same gesture with buttons=1 selects, without it
        # returns "".
        if phase == "down":
            self.held_button = button
        elif phase == "up":
            self.held_button = None
        held = 1 if self.held_button == "left" else 2 if self.held_button == "right" else 0

        payload = {"type": cdp_type, "x": x, "y": y, "buttons": held,
                   "button": button if cdp_type != "mouseMoved" else (self.held_button or "none")}
        if cdp_type != "mouseMoved":
            payload["clickCount"] = clicks
        await self.cdp.send("Input.dispatchMouseEvent", payload)

    async def type_text(self, text: str) -> None:
        await self.page.keyboard.type(text)

    async def key(self, key: str, modifiers: list | None = None) -> None:
        """A key press, optionally with modifiers.

        Modifiers matter: the pane used to swallow every Cmd/Ctrl combination, so
        an annotator could not paste, select-all, or use any shortcut the task
        might legitimately need.
        """
        combo = "+".join([*(modifiers or []), key]) if modifiers else key
        await self.page.keyboard.press(combo)

    async def paste(self, text: str) -> None:
        """Insert text as a paste would.

        `Input.insertText` rather than typing: a paste is one atomic change, and
        typing it character by character produces a different event stream (and a
        very different recorded trajectory) from what actually happened.
        """
        await self.cdp.send("Input.insertText", {"text": text})

    #: What a <select> under the pointer looks like to the pane, so it can offer a
    #: chooser. Returns {} for anything that is not a select.
    _SELECT_AT_JS = """([x, y]) => {
        const hit = document.elementFromPoint(x, y);
        const el = hit && hit.closest('select');
        if (!el) return {};
        return {
            value: el.value,
            multiple: !!el.multiple,
            options: [...el.options].map(o => ({
                value: o.value, label: (o.label || o.textContent || '').trim(),
                selected: !!o.selected, disabled: !!o.disabled,
            })),
        };
    }"""

    async def select_at(self, nx: float, ny: float) -> dict:
        """The <select> under this point, with its options — or {} if there is none.

        A native dropdown is drawn by the BROWSER, not the page, so a headless
        Chromium never paints it and the screencast has nothing to show. An
        annotator clicking a quantity dropdown therefore saw nothing happen and
        could not set a quantity at all — which makes every task whose answer runs
        through a <select> impossible to annotate.

        So the pane draws the list itself. This is what it needs to draw it.
        """
        x, y = self.to_page_xy(nx, ny)
        return await self.page.evaluate(self._SELECT_AT_JS, [x, y])

    async def select_value(self, nx: float, ny: float, value: str) -> dict:
        """Choose `value` in the <select> under this point.

        Playwright's select_option drives the real control and fires `change`, so
        React sees exactly what it would from a person using the dropdown.
        """
        x, y = self.to_page_xy(nx, ny)
        handle = await self.page.evaluate_handle(
            "([x, y]) => { const h = document.elementFromPoint(x, y); return h && h.closest('select'); }",
            [x, y],
        )
        el = handle.as_element()
        if el is None:
            return {"ok": False, "error": "no select under the pointer"}
        try:
            await el.select_option(value=value, timeout=3000)
        except Exception as exc:                                  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:200]}
        return {"ok": True, "value": value}

    async def selection(self) -> str:
        """Whatever text is selected in the remote page right now.

        An annotator selects text to READ it — an order id, a total, an address
        they are about to retype somewhere else. The gesture is a press, a move
        and a release, which is indistinguishable from a drag at the wire level,
        so the recorder needs the one thing that tells them apart: whether
        anything actually got selected.
        """
        with contextlib.suppress(Exception):
            return str(await self.page.evaluate(
                "() => { const s = window.getSelection(); return s ? s.toString() : ''; }"
            ) or "")
        return ""

    async def metrics(self) -> dict:
        """How big the page actually IS, as opposed to how big the window is.

        The pane needs this for its whole-page fit: to show a page with no
        scrolling at all, the viewport has to be as tall as the CONTENT, and only
        the page knows that number. `scrollHeight` is the full laid-out height
        including everything below the fold.
        """
        with contextlib.suppress(Exception):
            got = await self.page.evaluate(
                """() => {
                    const d = document.documentElement, b = document.body;
                    return {
                        contentHeight: Math.max(d.scrollHeight, b ? b.scrollHeight : 0),
                        contentWidth: Math.max(d.scrollWidth, b ? b.scrollWidth : 0),
                        innerWidth: window.innerWidth, innerHeight: window.innerHeight,
                    };
                }"""
            )
            if isinstance(got, dict):
                return {k: int(v or 0) for k, v in got.items()}
        return {"contentHeight": 0, "contentWidth": 0,
                "innerWidth": self.vw, "innerHeight": self.vh}

    async def fit_page(self, width: int) -> dict:
        """Size the viewport so the WHOLE page fits with no scrolling.

        Iterative on purpose. Narrowing the viewport reflows the page taller —
        measured on the ShopGym cart, going from 1280 to 1128 wide took the
        content from 1378px to 1956px — so a single measure-then-resize lands on
        a height that is already wrong and the page still scrolls. Each pass
        re-measures at the width it will actually be rendered at.

        Converges in two or three passes; the cap is there so a page that
        reflows forever (a layout whose height depends on its own height) costs a
        bounded number of round trips rather than hanging the pane.
        """
        last = {}
        for _ in range(_FIT_PAGE_PASSES):
            m = await self.metrics()
            want_h = int(m.get("contentHeight") or 0) or self.vh
            last = await self.resize(width, want_h)
            if not last.get("changed"):
                break            # the height it asked for is the height it has
        after = await self.metrics()
        return {**last,
                "contentHeight": after.get("contentHeight", 0),
                # Honest about the outcome: a page taller than MAX_VIEWPORT_H
                # cannot be shown whole, and the caller should know rather than
                # wonder why it is still scrolling.
                "whole": after.get("contentHeight", 0) <= after.get("innerHeight", 0)}

    async def resize(self, width: int, height: int) -> dict:
        """Reshape the viewport to match the pane watching it.

        The viewport was fixed at 1280x800 while the stage it renders into is a
        different shape entirely, so `fit` letterboxed it — on a wide pane that
        cost about 790px of horizontal blank space and rendered the page at 63%.
        Matching the shape makes the scale 1.0 and the bars disappear.

        Bounded at both ends: below MIN the storefronts reflow into a layout no
        task was authored against, and above MAX a maximised window asks for a
        page nobody can read. Rounded to even numbers because an odd CDP metric
        override yields a half-pixel device ratio and a visibly blurry screencast.
        """
        w = max(MIN_VIEWPORT_W, min(MAX_VIEWPORT_W, int(width))) // 2 * 2
        h = max(MIN_VIEWPORT_H, min(MAX_VIEWPORT_H, int(height))) // 2 * 2
        if (w, h) == (self.vw, self.vh):
            return {"ok": True, "width": w, "height": h, "changed": False}
        self.vw, self.vh = w, h
        for page in list(self.context.pages) if self.context else []:
            with contextlib.suppress(Exception):
                await page.set_viewport_size({"width": w, "height": h})
        # The screencast was started with the OLD maxWidth/maxHeight, so it keeps
        # emitting frames at the old size until it is restarted — the page would
        # be the right shape and the picture the wrong one.
        if self.cdp is not None:
            with contextlib.suppress(Exception):
                await self.cdp.send("Page.stopScreencast")
            with contextlib.suppress(Exception):
                await self.cdp.send("Page.startScreencast", {
                    "format": "jpeg", "quality": 60,
                    "maxWidth": w, "maxHeight": h, "everyNthFrame": 1,
                })
        return {"ok": True, "width": w, "height": h, "changed": True}

    async def navigate(self, url: str) -> None:
        await self.page.goto(url, wait_until="load")

    async def go_back(self) -> None:
        with contextlib.suppress(Exception):
            await self.page.go_back(wait_until="load")

    async def go_forward(self) -> None:
        with contextlib.suppress(Exception):
            await self.page.go_forward(wait_until="load")

    async def reload(self) -> None:
        with contextlib.suppress(Exception):
            await self.page.reload(wait_until="load")

    async def post_state(self, with_focus: bool = True) -> dict:
        """What is true AFTER an action — the client records from this.

        Returns the landed URL, the active tab, and the focused control's REAL
        value. That last one is why fills can be recorded correctly: the client
        only ever knows the keys it sent, so a Backspace (or an autocomplete, or a
        rejected keystroke) made its idea of the value wrong.

        `with_focus=False` skips that evaluate. It is the expensive half — a real
        round trip into the page — and input is handled in ONE sequential loop
        here, so paying it for an action that cannot move focus makes every
        following input wait behind it. A scroll is the case that hurt: a
        trackpad swipe is dozens of events, and answering each with a focus
        evaluate put the stream one to two seconds behind the annotator's hand.
        """
        state: dict = {"url": "", "tabId": "", "tabIndex": 0, "frameSeq": self.frame_seq}
        with contextlib.suppress(Exception):
            pages = self._tabs()
            state["url"] = self.page.url
            state["tabId"] = self.tab_id(self.page)
            state["tabIndex"] = pages.index(self.page) if self.page in pages else 0
        if with_focus:
            with contextlib.suppress(Exception):
                state["focus"] = await self.page.evaluate(_FOCUS_JS)
        return state

    async def observe(self, max_elements: int = OBSERVE_MAX_ELEMENTS) -> dict:
        """What the page LOOKED like — the observation half of a trajectory step.

        Best-effort by design. An observation is context, not an action: failing
        the step because a page was mid-navigation when we asked would lose the
        thing that actually matters. A caller gets `{}` and records no
        observation rather than losing the step.

        But it is LOUD about it. Swallowing this silently is how observation
        capture turns itself off permanently and nobody notices — a typo in
        `_OBSERVE_JS` raises on every page, every step returns `{}`, and the
        dataset simply has no observations while every request still answers 200.
        """
        try:
            obs = await self.page.evaluate(_OBSERVE_JS, max_elements)
        except Exception as exc:  # noqa: BLE001 — see docstring
            log.warning("observe failed on %s: %s", getattr(self.page, "url", "?"), exc)
            return {}
        obs["tabId"] = self.tab_id(self.page)
        return obs

    # --- structured actions ------------------------------------------------
    # Raw pointer input is how a HUMAN drives the browser; a committed trajectory
    # must be replayable without one. These mirror the agent harness's own
    # vocabulary and its "everything is pickable, no timeouts" strategy — try the
    # real interaction, fall back to JS activation — so a human-authored golden
    # reproduces identically when the agent harness replays it. Diverging here
    # would make manual trajectories unrunnable in the very benchmark they exist
    # to feed.
    def _abs(self, path: str) -> str:
        """Archived actions carry relative paths ("/account/orders"). Resolve
        against the session's own origin rather than assuming the caller did."""
        if str(path).startswith("http"):
            return str(path)
        base = self.url.rstrip("/")
        if "://" in base:
            scheme, _, rest = base.partition("://")
            base = scheme + "://" + rest.split("/")[0]
        return base + ("" if str(path).startswith("/") else "/") + str(path)

    async def resolve(self, locator: dict) -> str | None:
        """Turn a semantic locator into a CSS selector that matches RIGHT NOW.
        Ordered most-durable first; coordinates are not a locator and never
        appear here."""
        cands: list[str] = []
        if locator.get("testId"):
            cands.append(f"[data-test-id={json.dumps(locator['testId'])}]")
        if locator.get("id"):
            cands.append(f"#{locator['id']}")
        if locator.get("css"):
            cands.append(locator["css"])
        if locator.get("name"):
            cands.append(f"[name={json.dumps(locator['name'])}]")
        # What we recorded the element SAYS. A selector that matches is not the
        # same as a selector that matches the right thing: an nth-of-type path
        # anchored at `#root` describes a position in the tree, and one extra
        # wrapper slides it onto a different element that resolves perfectly and
        # does something else. On a real M105 replay the Send click landed on
        # whatever now sat at that position, reported ok, and left the world with
        # no sent mail — the trajectory failed at its last step with every action
        # reporting success. Same lesson as the radio group: resolving is not
        # being right.
        # Whitespace collapsed on BOTH sides. The recorder stores `text` trimmed
        # but not collapsed, so ShopGym's "Returns\n& Orders" link compared
        # against a collapsed "Returns & Orders" and failed to be itself — every
        # multi-line label in every mock, refused at step 0.
        want = " ".join(str(locator.get("name") or locator.get("label")
                            or locator.get("text") or "").split())
        for sel in cands:
            with contextlib.suppress(Exception):
                got = await self.page.evaluate(
                    """([s, want]) => {
                        const el = document.querySelector(s);
                        if (!el) return null;
                        if (!want) return true;               // nothing to check it against
                        const said = (el.getAttribute('aria-label') || el.getAttribute('name')
                                      || el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                        // Compared on the first 120 chars because that is what
                        // the recorder stored — a longer element would never
                        // match its own description otherwise.
                        return said.slice(0, 120) === want.slice(0, 120);
                    }""",
                    [sel, want],
                )
                if got:
                    return sel
        # role + accessible name is last: it needs a Playwright locator rather
        # than a selector, so we resolve it to a concrete element and hand back a
        # unique handle.
        #
        # `text` counts as that name, and it is what saves the buttons a mock
        # never gave an id. ShopMail's Send is `<button>Send</button>` inside a
        # compose dialog: no testId, no id, no name attribute — so the only
        # handle was an unanchored `#root > div:nth-of-type(1) > …` path, and one
        # extra wrapper between recording and replay is enough to miss it. That
        # is the step that SENDS the email, so missing it fails the whole
        # trajectory at the last action. For a button or a link the visible text
        # IS the accessible name, which is exactly what get_by_role matches.
        role, name = locator.get("role"), (locator.get("name") or locator.get("label") or locator.get("text"))
        if role and name:
            with contextlib.suppress(Exception):
                loc = self.page.get_by_role(role, name=name).first
                if await loc.count():
                    await loc.evaluate("(el) => el.setAttribute('data-replay-target', '1')")
                    return "[data-replay-target='1']"
        return None

    async def _js_activate(self, selector: str, kind: str, value: str | None = None) -> bool:
        """Reveal a present-but-hidden element and activate it via JS. Same
        contract as the agent harness: a genuinely absent element is the ONLY
        failure — never a timeout."""
        return bool(await self.page.evaluate(
            """([sel, kind, val]) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                try { el.scrollIntoView({block: 'center', inline: 'center'}); } catch (e) {}
                if (kind === 'fill_html') {
                    if (!el.isContentEditable) return false;
                    try { el.focus(); } catch (e) {}
                    el.innerHTML = val;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                } else if (kind === 'fill') {
                    try { el.focus(); } catch (e) {}
                    // A contenteditable's content is its TEXT. `el.value = val`
                    // on one just invents a JS property nobody reads: the page
                    // is unchanged, the fill reports success, and the mail body
                    // stays empty. Replaying M105 that way filled nothing,
                    // clicked a Send that really was the Send button, and sent
                    // no mail — every action ok, trajectory failed at the end.
                    if (el.isContentEditable) {
                        el.textContent = val;
                    } else {
                        const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
                        if (d && d.set) d.set.call(el, val); else el.value = val;
                    }
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                } else if (kind === 'select') {
                    let matched = false;
                    for (const o of (el.options || [])) {
                        if (o.value === val || (o.textContent || '').trim() === val) { el.value = o.value; matched = true; break; }
                    }
                    if (!matched) el.value = val;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                } else if (kind === 'check') {
                    if (!el.checked) { el.checked = true; el.dispatchEvent(new Event('change', {bubbles: true})); }
                } else {
                    el.click();
                }
                return true;
            }""",
            [selector, kind, value],
        ))

    # Tabs live in ONE BrowserContext (shared cookies/session), exactly as the
    # agent harness arranges them — cross-app tasks are the whole point, and an
    # agent that lost its session on every new tab could not do them.
    def _tabs(self) -> list:
        return list(self.context.pages) if self.context else []

    def _resolve_tab(self, index: int | None, tab_id: str | None):
        """A tab by stable id (preferred) or by index (positional, legacy)."""
        pages = self._tabs()
        if tab_id:
            for p in pages:
                if self.tab_ids.get(p) == tab_id:
                    return p
            return None
        if index is None or not (0 <= index < len(pages)):
            return None
        return pages[index]

    async def goto_app(self, url: str) -> dict:
        """Show the app at `url`: switch to its existing tab, else open one.

        The five realistic apps live on five origins, and only the task's primary
        app is open when a session starts. Resolving by ORIGIN here (rather than
        making the client remember which app it already opened) keeps a second
        click on the same app from stacking duplicate tabs, and keeps that app's
        scroll position and in-page state — which an annotator mid-task notices
        the moment it is lost.
        """
        from urllib.parse import urlsplit
        want = urlsplit(url)
        for p in self._tabs():
            if urlsplit(p.url).netloc == want.netloc:
                return await self._switch_tab(index=self._tabs().index(p))
        return await self._open_tab(url)

    async def _open_tab(self, url: str) -> dict:
        # Ours, not a popup: the explicit bind below is the one that counts, and
        # letting the follower also adopt it records a `popup` step for a tab the
        # trajectory already says we opened.
        with self._own_new_pages():
            page = await self.context.new_page()
            await page.goto(url, wait_until="load")
        await self._bind(page)          # rebind: pixels AND mouse follow the new tab
        return {"ok": True, "kind": "open_tab",
                "resolved": {"url": page.url, "tabId": self.tab_id(page),
                             "tabIndex": self._tabs().index(page)}}

    async def _switch_tab(self, index: int | None = None, tab_id: str | None = None) -> dict:
        page = self._resolve_tab(index, tab_id)
        if page is None:
            return {"ok": False, "kind": "switch_tab",
                    "error": f"no such tab (index={index}, tabId={tab_id})", "resolved": {}}
        await self._bind(page)
        return {"ok": True, "kind": "switch_tab",
                "resolved": {"url": page.url, "tabId": self.tab_id(page),
                             "tabIndex": self._tabs().index(page)}}

    async def _close_tab(self, index: int | None = None, tab_id: str | None = None) -> dict:
        pages = self._tabs()
        if len(pages) <= 1:
            return {"ok": False, "kind": "close_tab", "error": "cannot close the last remaining tab", "resolved": {}}
        closing = self._resolve_tab(index, tab_id)
        if closing is None:
            return {"ok": False, "kind": "close_tab",
                    "error": f"no such tab (index={index}, tabId={tab_id})", "resolved": {}}
        was_active = self.page is closing
        await closing.close()
        self.tab_ids.pop(closing, None)
        if was_active:
            # Rebind, don't just reassign: `self.cdp` was attached to the page we
            # just closed, so every subsequent mouse event would throw.
            await self._bind(self._tabs()[0])
        return {"ok": True, "kind": "close_tab",
                "resolved": {"url": self.page.url, "tabId": self.tab_id(self.page)}}

    async def act(self, kind: str, locator: dict | None = None, args: dict | None = None) -> dict:
        """Execute ONE structured action. Returns what actually happened —
        including the selector that matched — so the caller can record the
        resolved target rather than re-guessing it later.

        The vocabulary is the agent harness's, entirely: click · fill · select ·
        check · submit · navigate · open_tab · switch_tab · close_tab · scroll ·
        wait · press. It has to be complete, not merely overlapping. `submit` is
        the second-most-common action in the recorded archive (46 uses against
        110 clicks), so an executor missing it cannot replay roughly a fifth of
        every trajectory the benchmark has ever recorded — measured, after a
        replay probe failed on exactly that.
        """
        args = args or {}
        if kind == "navigate":
            await self.navigate(self._abs(args.get("url", "/")))
            return {"ok": True, "kind": kind, "resolved": {"url": self.page.url}}
        if kind == "press":
            await self.key(args.get("key", "Enter"))
            return {"ok": True, "kind": kind, "resolved": {}}
        if kind == "open_tab":
            return await self._open_tab(self._abs(args.get("url", "/")))
        if kind == "switch_tab":
            # By URL first, matching the live path (see the websocket handler's
            # `goto_app`): a session opens with only the task's primary app, and
            # the others get a tab when first visited. So a tab INDEX means
            # nothing across a replay — it depends on which apps the annotator
            # happened to open and in what order, and a recorded index of 1 is
            # a tab that does not exist yet when the replay reaches it.
            #
            # Worse than failing: `tab_index` defaulted to 0, so a switch that
            # carried only {app, url} replayed as "go to the first tab" and
            # reported ok. Every cross-app step in a replayed trajectory ran
            # against the primary app while the transcript read clean.
            if args.get("url") and not args.get("tab_id"):
                out = await self.goto_app(self._abs(args["url"]))
                # Report the action that was asked for; `openedTab` keeps the
                # fact that the app had no tab yet, which is the difference
                # between a replay that matched the recording and one that
                # rebuilt part of it.
                return {**out, "kind": "switch_tab",
                        "resolved": {**out.get("resolved", {}),
                                     "openedTab": out.get("kind") == "open_tab"}}
            return await self._switch_tab(
                index=(None if args.get("tab_id") else int(args.get("tab_index", args.get("index", 0)))),
                tab_id=args.get("tab_id"))
        if kind == "close_tab":
            return await self._close_tab(
                index=(None if args.get("tab_id") else int(args.get("tab_index", args.get("index", 0)))),
                tab_id=args.get("tab_id"))
        if kind == "scroll":
            await self.scroll(0.5, 0.5, float(args.get("amount_px", args.get("dy", 400)))
                              * (-1 if str(args.get("direction", "down")) == "up" else 1))
            return {"ok": True, "kind": kind, "resolved": {"url": self.page.url}}
        if kind == "wait":
            # "Let time pass" — the clock is the gym's, not ours, so there is
            # nothing for the browser to do but re-read the page. Reload, because
            # our pages are server-rendered and never live-update: an agent that
            # waited on a frozen page would never see the event it waited for.
            with contextlib.suppress(Exception):
                await self.page.reload(wait_until="domcontentloaded")
            return {"ok": True, "kind": kind, "resolved": {"url": self.page.url}}

        sel = await self.resolve(locator or {})
        if sel is None:
            # Fail LOUDLY: a silently-skipped action produces a trajectory that
            # claims to do something it never did.
            return {"ok": False, "kind": kind, "error": "no element matched the locator", "resolved": {}}

        value = args.get("value")
        ok = False
        if kind in ("click", "submit", "right_click", "dblclick"):
            # A right-click and a double-click are DIFFERENT ACTIONS, not clicks
            # with a note attached. The recorder used to flatten both into
            # `click`, so a step described as "right-click Save for later"
            # replayed as a left click, reported ok, and was stamped verified.
            # Now that it records them honestly, this has to be able to perform
            # them — otherwise every trajectory containing one is unshippable.
            #
            # No JS fallback for either: `_js_activate` dispatches a plain click,
            # which is the very substitution that made the old behaviour a lie.
            # If the real gesture cannot be performed, say so.
            button = "right" if kind == "right_click" else "left"
            clicks = 2 if kind == "dblclick" else 1
            loc = self.page.locator(sel).first
            with contextlib.suppress(Exception):
                if await loc.is_visible():
                    await loc.scroll_into_view_if_needed(timeout=2000)
                    await loc.click(timeout=5000, button=button, click_count=clicks)
                    ok = True
            if not ok and kind in ("click", "submit"):
                ok = await self._js_activate(sel, "click")
            if ok and kind == "submit":
                # A submit navigates; settling first means the caller reads the
                # world the form actually produced, not the one before it posted.
                with contextlib.suppress(Exception):
                    await self.page.wait_for_load_state("networkidle", timeout=5000)
        elif kind in ("fill", "type"):
            # Playwright FIRST, JS as the fallback — the mirror of the click path
            # above, and for the same reason. A JS fill assigns the value and
            # dispatches an input event, which is enough for the DOM and usually
            # enough for React; when it is not, the field shows the text and the
            # component's state never hears about it. ShopMail's send refuses on
            # an empty `to`, so a replayed M105 filled all three fields visibly,
            # clicked Send, and sent nothing. Playwright drives real input
            # through CDP, so the page cannot tell it from a person typing.
            #
            # Short timeout, and any failure falls through: the JS path exists
            # because a present-but-hidden element must still be fillable, and
            # that contract is not given up to gain this.
            # A rich editor stores MARKUP, so replay its markup when we have it —
            # `page.fill` only knows text and rebuilds the body as flat divs.
            html = args.get("valueHtml")
            ok = False
            if html:
                ok = await self._js_activate(sel, "fill_html", str(html))
            if not ok:
                with contextlib.suppress(Exception):
                    await self.page.fill(sel, value or "", timeout=_FILL_TIMEOUT_MS)
                    ok = True
            if not ok:
                ok = await self._js_activate(sel, "fill", value)
        elif kind in ("select", "select_option"):
            ok = await self._js_activate(sel, "select", value)
        elif kind == "check":
            ok = await self._js_activate(sel, "check")
        else:
            return {"ok": False, "kind": kind, "error": f"unsupported action {kind!r}", "resolved": {}}

        with contextlib.suppress(Exception):
            await self.page.evaluate("() => document.querySelectorAll('[data-replay-target]').forEach(e => e.removeAttribute('data-replay-target'))")
        return {"ok": ok, "kind": kind, "resolved": {"selector": sel, "url": self.page.url},
                **({} if ok else {"error": "element matched but did not activate"})}

    async def focused(self) -> dict:
        """Locator candidates for whatever currently has KEYBOARD focus.

        A client cannot infer this. It knows where the human last clicked, but
        focus also moves by Tab, by Enter submitting and advancing, and by a
        page's own autofocus — all of which happen inside the remote browser.
        Attributing keystrokes to the last *clicked* element is how a password
        typed into a Tab-reached field gets recorded against the email field
        instead, which silently defeats redaction at record time. Only the page
        knows, so ask the page.
        """
        return await self.page.evaluate(_FOCUS_JS)

    async def describe(self, nx: float, ny: float) -> dict:
        """Locator candidates for whatever is at this point, captured BEFORE an
        action is dispatched — afterwards the element may not exist.

        Uses the SAME descriptor as `focused()` and every ack, so the identity of
        an element never depends on which call observed it.
        """
        x, y = self.to_page_xy(nx, ny)
        return await self.page.evaluate(
            "([x, y]) => {"
            "  const el = document.elementFromPoint(x, y);"
            "  if (!el) return {};"
            "  const t = el.closest('[data-test-id],button,a,input,select,textarea,[role]') || el;"
            f"  return ({_DESCRIBE_EL_JS})(t);"
            "}",
            [x, y],
        )

    async def thumbnail(self, page) -> str | None:
        """One tab's pixels as a small JPEG, taken WITHOUT bringing it forward.

        A raw CDP capture on a throwaway session rather than `page.screenshot`:
        Playwright fronts the target before it shoots, which on a background tab
        hides the tab the screencast is bound to and freezes the stream the
        annotator is working in. This touches neither `self.page` nor `self.cdp`,
        so the binding and the mouse stay exactly where they were.

        `clip.scale` does the downscaling in Chromium, so nothing full-size is
        ever encoded. Measured against the five mocks: ~20ms and ~14KB of base64
        per app, and a hidden tab's capture DOES reflect what changed while it
        was hidden — which is what makes a ShopMail preview show the mail an
        order in ShopGym just produced.
        """
        sess = None
        try:
            sess = await self.context.new_cdp_session(page)
            shot = await sess.send("Page.captureScreenshot", {
                "format": "jpeg", "quality": THUMB_QUALITY,
                "clip": {"x": 0, "y": 0, "width": self.vw, "height": self.vh, "scale": THUMB_SCALE},
                "captureBeyondViewport": False,
            })
            return shot.get("data") or None
        except Exception as exc:  # noqa: BLE001 — a preview is never worth a 500
            log.warning("thumbnail failed for %s: %s", getattr(page, "url", "?"), exc)
            return None
        finally:
            if sess is not None:
                with contextlib.suppress(Exception):
                    await sess.detach()

    async def thumbnails(self) -> list[dict]:
        """Every open tab as a preview — what the dock of mini browser windows draws.

        A cua-hub session pre-opens all five apps, and only the active one is
        being screencast, so the other four had no pixels to show until the
        annotator had visited them once: the ecosystem looked half-empty exactly
        when it should look most alive. They are real, loaded pages; this is
        simply asking each one what it looks like.

        Sequential rather than gathered: five captures cost ~100ms in total, and
        firing them at one browser at once buys nothing worth the contention.
        A tab that could not be photographed is OMITTED, not faked — the caller
        keeps whatever preview it already had.
        """
        out: list[dict] = []
        for page in self._tabs():
            data = await self.thumbnail(page)
            if not data:
                continue
            out.append({"tabId": self.tab_id(page), "url": page.url,
                        "active": page is self.page, "data": data})
        return out

    async def info(self) -> dict:
        pages = list(self.context.pages) if self.context else []
        return {
            "url": self.page.url if self.page else "",
            # Both shapes: `tabs` stays a list of URLs for existing callers, and
            # `tabList` carries the stable ids a recorded step is keyed on.
            "tabs": [p.url for p in pages],
            "tabList": [{"tabId": self.tab_id(p), "url": p.url, "index": i}
                        for i, p in enumerate(pages)],
            "activeTab": pages.index(self.page) if self.page in pages else 0,
            "activeTabId": self.tab_id(self.page) if self.page is not None else "",
            "viewport": {"width": self.vw, "height": self.vh},
            "frameSeq": self.frame_seq,
        }

    async def close(self) -> None:
        self.closed = True
        for closer in (
            lambda: self.cdp.send("Page.stopScreencast"),
            lambda: self.context.close(),
            lambda: self.browser.close(),
            lambda: self.pw.stop(),
        ):
            with contextlib.suppress(Exception):
                await closer()


SESSIONS: dict[str, LiveSession] = {}


# --------------------------------------------------------------------------- http
class OpenBody(BaseModel):
    url: str
    owner: str = "anonymous"
    # Other app URLs to open as background tabs (same BrowserContext). The primary
    # `url` stays active for the screencast; these are pre-warmed for switching.
    extra_urls: list[str] = []


@app.post("/live/sessions")
async def open_session(body: OpenBody) -> dict:
    sid = uuid.uuid4().hex[:12]
    s = LiveSession(id=sid, owner=body.owner, url=body.url)
    try:
        await s.start()
        if body.extra_urls:
            await s.preopen_tabs(body.extra_urls)
    except Exception as exc:  # noqa: BLE001 — surface the real reason, don't leak a half-session
        await s.close()
        raise HTTPException(500, f"could not start live browser: {exc}") from exc
    SESSIONS[sid] = s
    return {"session_id": sid, "ticket": mint_ticket(sid, body.owner), "viewport": {"width": VIEWPORT_W, "height": VIEWPORT_H}}


@app.get("/live/sessions/{sid}")
async def session_info(sid: str) -> dict:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "unknown session")
    return await s.info()


class ActBody(BaseModel):
    kind: str
    locator: dict | None = None
    args: dict | None = None
    ticket: str = ""


@app.post("/live/sessions/{sid}/act")
async def session_act(sid: str, body: ActBody) -> dict:
    """Execute one STRUCTURED action — the replay path. A committed trajectory is
    replayed through here, never through recorded pixels, so it survives layout
    change and can be re-run by the agent harness."""
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.act(body.kind, body.locator, body.args)


class DescribeBody(BaseModel):
    x: float
    y: float
    ticket: str = ""


@app.post("/live/sessions/{sid}/describe")
async def session_describe(sid: str, body: DescribeBody) -> dict:
    """Locator candidates at a normalized point, read BEFORE dispatch."""
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.describe(body.x, body.y)


class ResizeBody(BaseModel):
    width: int
    height: int
    ticket: str = ""


@app.post("/live/sessions/{sid}/viewport")
async def session_viewport(sid: str, body: ResizeBody) -> dict:
    """Reshape this session's viewport to the pane's stage.

    The pane calls this when its stage changes size, so the remote page is the
    same shape as the box it is drawn in and no space is wasted on bars.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.resize(body.width, body.height)


@app.post("/live/sessions/{sid}/select-at")
async def session_select_at(sid: str, body: DescribeBody) -> dict:
    """The <select> under a normalized point, with its options — {} if none.

    The pane asks this on every click so it can draw the dropdown a headless
    browser will not paint. Same body shape as /describe, deliberately: it is the
    same question about the same point, asked at the same moment.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.select_at(body.x, body.y)


class FocusBody(BaseModel):
    ticket: str = ""


class FitPageBody(BaseModel):
    width: int
    ticket: str = ""


@app.post("/live/sessions/{sid}/fit-page")
async def session_fit_page(sid: str, body: FitPageBody) -> dict:
    """Size the viewport so the whole page is visible without scrolling."""
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.fit_page(body.width)


@app.post("/live/sessions/{sid}/metrics")
async def session_metrics(sid: str, body: FocusBody) -> dict:
    """The laid-out size of the current page. See LiveSession.metrics."""
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.metrics()


@app.post("/live/sessions/{sid}/selection")
async def session_selection(sid: str, body: FocusBody) -> dict:
    """The page's current text selection, read at pointer-up.

    Read on the RELEASE rather than tracked continuously: a selection only means
    something once it is finished, and polling it would put a round trip on every
    pointer move.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return {"text": await s.selection()}


@app.post("/live/sessions/{sid}/focused")
async def session_focused(sid: str, body: FocusBody) -> dict:
    """Which element has keyboard focus right now. The client needs this to
    attribute keystrokes correctly — focus moves by Tab and by autofocus, not
    only by clicking, and a mis-attributed keystroke defeats redaction."""
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.focused()


class ObserveBody(BaseModel):
    ticket: str = ""
    max_elements: int = OBSERVE_MAX_ELEMENTS


@app.post("/live/sessions/{sid}/observe")
async def session_observe(sid: str, body: ObserveBody) -> dict:
    """The page as an OBSERVATION: url, title, viewport, scroll, visible text and
    an inventory of every interactive element, each described exactly the way a
    clicked element is.

    A trajectory without this records what the annotator did and nothing about
    what they could see, and a policy cannot be trained on the action alone. The
    shared descriptor is the point: an element here and the target of the action
    that follows carry the same `targetKey`, so a consumer can tie them together
    by identity instead of inferring it from coordinates.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return await s.observe(max(1, min(int(body.max_elements or OBSERVE_MAX_ELEMENTS), 2000)))


@app.post("/live/sessions/{sid}/thumbnails")
async def session_thumbnails(sid: str, body: FocusBody) -> dict:
    """A small JPEG of EVERY open tab, so the pane can draw the inactive apps.

    The screencast only ever covers one tab, so the other four pre-opened apps
    had nothing to show until they had been visited — the annotator was told
    there were five live browsers and shown one plus four placeholders. Asked on
    a timer as well as at connect, because a cross-app effect (an order in
    ShopGym producing a ShopMail email) changes a tab nobody is looking at.

    Reports the scale it used: the caller is drawing these, and a thumbnail
    whose size it has to guess at renders blurry or letterboxed.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    if check_ticket(sid, body.ticket) is None:
        raise HTTPException(403, "invalid or expired ticket")
    return {"thumbs": await s.thumbnails(), "scale": THUMB_SCALE,
            "viewport": {"width": s.vw, "height": s.vh}}


@app.get("/live/sessions/{sid}/frame")
async def session_frame(sid: str) -> dict:
    """The most recent frame, as base64 JPEG.

    The screencast already keeps it in memory; exposing it lets a caller that is
    NOT the pane (the annotator backend, capturing a per-step screenshot) get the
    pixels without a second capture that would compete with the stream.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    # The SESSION's viewport, not the module default: a session negotiates its
    # own size to match the pane, and a screenshot labelled with the wrong
    # dimensions is worse than one with none — the bundle records these.
    return {"seq": s.frame_seq, "data": s.latest_frame or "",
            "viewport": {"width": s.vw, "height": s.vh}}


@app.get("/live/sessions/{sid}/context")
async def session_context(sid: str) -> dict:
    """Everything a checkpoint needs that the gym world cannot know: the URL, the
    full tab list, cookies, storage and scroll position.

    `checkpoints.capture` already accepts all of this and nothing has ever
    supplied it, so a restored checkpoint came back with the right world behind a
    browser sitting on the wrong page.
    """
    s = SESSIONS.get(sid)
    if not s or s.closed:
        raise HTTPException(404, "unknown session")
    out = await s.info()
    with contextlib.suppress(Exception):
        out["cookies"] = await s.context.cookies()
    with contextlib.suppress(Exception):
        out["storageState"] = await s.context.storage_state()
    with contextlib.suppress(Exception):
        out["scroll"] = await s.page.evaluate("() => ({x: window.scrollX, y: window.scrollY})")
    return out


@app.post("/live/sessions/{sid}/close")
async def close_session(sid: str) -> dict:
    s = SESSIONS.pop(sid, None)
    if not s:
        raise HTTPException(404, "unknown session")
    await s.close()
    return {"ok": True}


@app.get("/live/health")
async def health() -> dict:
    return {"ok": True, "sessions": len(SESSIONS)}


# --------------------------------------------------------------------------- ws
@app.websocket("/live/stream/{sid}")
async def stream(ws: WebSocket, sid: str, ticket: str = Query(default=""), control: bool = Query(default=True)):
    # A cross-origin caller is refused WITHOUT completing the handshake — it gets
    # no diagnostics, which is the point of an origin allow-list.
    if not origin_ok(ws.headers.get("origin")):
        await ws.close(code=4403); return

    # Everything below accepts FIRST and then closes with a code. A browser cannot
    # observe a close code on a handshake that was never completed — it reports a
    # generic 1006 — so closing pre-accept meant a legitimate client could not tell
    # "your ticket expired, stop retrying" from "the network blipped", and it
    # reconnected forever against a ticket that would never work again.
    s = SESSIONS.get(sid)
    if s is None or s.closed:
        await ws.accept()
        await ws.close(code=4404); return
    owner = check_ticket(sid, ticket)
    if owner is None or owner != s.owner:
        await ws.accept()
        await ws.close(code=4401); return

    await ws.accept()
    # A reconnecting client starts its input ids at 1 again, while `last_input_id`
    # lives on the SESSION and outlives the socket. Without this reset every input
    # after a reconnect is acked applied:false/"stale" — input that looks delivered
    # and is not, which is the failure mode the ack channel exists to prevent.
    s.last_input_id = 0
    ws_id = uuid.uuid4().hex[:8]
    # Exactly one controller: a second controller would interleave input with the
    # first and make the recorded trajectory unattributable.
    s.attached.add(ws_id)
    # A lease held by a socket that is no longer attached is nobody's lease.
    if s.controller is not None and s.controller not in s.attached:
        s.controller = None
    is_controller = False
    if control and s.controller is None:
        # A dropped controller's lease is released in the handler's `finally`,
        # which cannot run until its own socket finishes tearing down. A client
        # that reconnects promptly therefore arrives while the lease is still held
        # by the socket it just lost, and gets demoted to a read-only viewer of
        # its OWN session — with no way back except waiting and reconnecting
        # again. Claiming a lease whose owner is gone fixes that; a genuine second
        # viewer still sees a live controller and stays read-only.
        s.controller = ws_id
        is_controller = True
    await ws.send_text(json.dumps({
        "type": "hello", "sessionId": sid, "controller": is_controller,
        "viewport": {"width": VIEWPORT_W, "height": VIEWPORT_H},
    }))

    async def pump_frames() -> None:
        last = -1
        last_notice = 0
        while not s.closed:
            # Notices first: a popup the page opened itself has no ack to ride on,
            # and the client must be able to record it as an event like any other.
            pending = [n for n in s.notices if n["seq"] > last_notice]
            if pending:
                last_notice = pending[-1]["seq"]
                for n in pending:
                    await ws.send_text(json.dumps(n))
                continue
            if s.frame_seq != last and s.latest_frame:
                last = s.frame_seq
                await ws.send_text(json.dumps({"type": "frame", "seq": last, "data": s.latest_frame}))
            else:
                s.frame_event.clear()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(s.frame_event.wait(), timeout=1.0)

    pump = asyncio.create_task(pump_frames())
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            kind = msg.get("type")
            if kind == "ping":
                await ws.send_text(json.dumps({"type": "pong"})); continue
            if not is_controller:
                await ws.send_text(json.dumps({"type": "denied", "reason": "read-only viewer"})); continue

            input_id = int(msg.get("id", 0))
            if input_id <= s.last_input_id:      # replayed/out-of-order input is dropped
                await ws.send_text(json.dumps({"type": "ack", "id": input_id, "applied": False, "reason": "stale"}))
                continue
            s.last_input_id = input_id

            if kind == "click":
                await s.click(msg["nx"], msg["ny"], msg.get("button", "left"), int(msg.get("clicks", 1)))
            elif kind == "move":
                await s.move(msg["nx"], msg["ny"])
            elif kind == "scroll":
                await s.scroll(msg["nx"], msg["ny"], float(msg.get("dy", 0)), float(msg.get("dx", 0)))
            elif kind == "type":
                await s.type_text(msg.get("text", ""))
            elif kind == "key":
                await s.key(msg.get("key", ""), msg.get("modifiers") or [])
            elif kind == "navigate":
                await s.navigate(msg.get("url", ""))
            # Raw pointer phases. A press/release pair the CLIENT sends is the only
            # way a drag can be distinguished from a click — synthesising both ends
            # from one pointerdown (what the pane used to do) makes every drag look
            # like a click at the start point.
            elif kind == "mouse":
                await s.mouse(msg.get("phase", "move"), msg["nx"], msg["ny"],
                              msg.get("button", "left"), int(msg.get("clicks", 1)))
            # A native dropdown is painted by the BROWSER, so a headless one never
            # renders and the screencast has nothing to show. The pane draws the
            # option list itself and sends the choice back here, which is the only
            # way an annotator can operate a <select> at all — and every task whose
            # answer runs through one (a quantity, a ship-to address) was
            # impossible to annotate without it.
            elif kind == "select":
                out = await s.select_value(msg["nx"], msg["ny"], str(msg.get("value", "")))
                await ws.send_text(json.dumps({
                    "type": "ack", "id": input_id, "applied": bool(out.get("ok")),
                    "reason": out.get("error", ""), "state": await s.post_state(),
                }))
                continue
            elif kind == "paste":
                await s.paste(msg.get("text", ""))
            elif kind == "back":
                await s.go_back()
            elif kind == "forward":
                await s.go_forward()
            elif kind == "reload":
                await s.reload()
            elif kind == "switch_tab" and msg.get("url") and not msg.get("tab_id"):
                # The pane's app strip addresses an app by URL; it does not track
                # which of them already has a tab.
                out = await s.goto_app(msg["url"])
                await ws.send_text(json.dumps({
                    "type": "ack", "id": input_id, "applied": bool(out.get("ok")),
                    "reason": out.get("error", ""), "state": await s.post_state(),
                }))
                continue
            elif kind in ("open_tab", "switch_tab", "close_tab"):
                out = await s.act(kind, None, {k: v for k, v in msg.items()
                                               if k in ("url", "tab_id", "tab_index", "index")})
                await ws.send_text(json.dumps({
                    "type": "ack", "id": input_id, "applied": bool(out.get("ok")),
                    "reason": out.get("error", ""), "state": await s.post_state(),
                }))
                continue
            else:
                await ws.send_text(json.dumps({"type": "ack", "id": input_id, "applied": False, "reason": "unknown"}))
                continue
            # The ack carries the state AFTER the action — the url actually landed
            # on, the tab it happened in, and the focused field's real value. The
            # client records from this rather than from what it believes it sent,
            # which is what keeps the recorded trajectory honest (a click that
            # navigates, a value corrected by Backspace, an input that never applied).
            await ws.send_text(json.dumps({
                "type": "ack", "id": input_id, "applied": True,
                # A move needs no state at all; a scroll needs where it landed but
                # cannot have moved focus, so it skips the evaluate that costs a
                # round trip. See post_state — this loop is sequential, so every
                # avoidable await is latency the annotator feels as lag.
                "state": None if kind == "move" else await s.post_state(with_focus=kind != "scroll"),
            }))
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        with contextlib.suppress(Exception):
            await ws.send_text(json.dumps({"type": "error", "detail": str(exc)}))
    finally:
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump
        s.attached.discard(ws_id)
        if is_controller and s.controller == ws_id:
            s.controller = None  # release control so the annotator can reconnect
