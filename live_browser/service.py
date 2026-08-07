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

VIEWPORT_W = int(os.getenv("LIVE_VIEWPORT_W", "1280"))
VIEWPORT_H = int(os.getenv("LIVE_VIEWPORT_H", "800"))
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
    if ('value' in el) d.value = el.value;
    if (el.type === 'checkbox' || el.type === 'radio') d.checked = !!el.checked;
    if (tag === 'select' && el.selectedIndex >= 0)
        d.selectedText = (el.options[el.selectedIndex] || {}).text || '';
    const r = el.getBoundingClientRect();
    d.bbox = {x: r.x, y: r.y, w: r.width, h: r.height};
    // Whitespace collapsed: an element's text can span several lines, and a key
    // with a line break inside it is awkward everywhere it is later read — a
    // JSON dataset, a log line, a diff. Same rule for every caller, so the
    // identity still matches across describe/focused/observe.
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

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            device_scale_factor=1,
        )
        # A target=_blank click creates a page nobody asked for. Without this the
        # popup is invisible: the stream keeps showing the opener and the click
        # looks like it did nothing.
        self.context.on("page", self._on_new_page)
        page = await self.context.new_page()
        await page.goto(self.url, wait_until="load")
        await self._bind(page)

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
            "maxWidth": VIEWPORT_W, "maxHeight": VIEWPORT_H, "everyNthFrame": 1,
        })

    def _notice(self, event: str, payload: dict) -> None:
        """Queue a server-originated event for the client to record."""
        self.notice_seq += 1
        self.notices.append({"type": "notice", "seq": self.notice_seq, "event": event, **payload})
        del self.notices[:-50]          # a client that never drains must not grow this
        self.frame_event.set()

    def _on_new_page(self, page) -> None:
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
        return nx * VIEWPORT_W, ny * VIEWPORT_H

    async def click(self, nx: float, ny: float, button: str = "left", clicks: int = 1) -> None:
        x, y = self.to_page_xy(nx, ny)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y, "button": "none"})
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": button, "clickCount": clicks})
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": button, "clickCount": clicks})

    async def move(self, nx: float, ny: float) -> None:
        x, y = self.to_page_xy(nx, ny)
        await self.cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})

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
        payload = {"type": cdp_type, "x": x, "y": y,
                   "button": button if cdp_type != "mouseMoved" else "none"}
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

    async def post_state(self) -> dict:
        """What is true AFTER an action — the client records from this.

        Returns the landed URL, the active tab, and the focused control's REAL
        value. That last one is why fills can be recorded correctly: the client
        only ever knows the keys it sent, so a Backspace (or an autocomplete, or a
        rejected keystroke) made its idea of the value wrong.
        """
        state: dict = {"url": "", "tabId": "", "tabIndex": 0, "frameSeq": self.frame_seq}
        with contextlib.suppress(Exception):
            pages = self._tabs()
            state["url"] = self.page.url
            state["tabId"] = self.tab_id(self.page)
            state["tabIndex"] = pages.index(self.page) if self.page in pages else 0
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
        for sel in cands:
            with contextlib.suppress(Exception):
                if await self.page.evaluate("(s) => !!document.querySelector(s)", sel):
                    return sel
        # role+name is last: it needs a Playwright locator rather than a selector,
        # so we resolve it to a concrete element and hand back a unique handle.
        if locator.get("role") and locator.get("name"):
            with contextlib.suppress(Exception):
                loc = self.page.get_by_role(locator["role"], name=locator["name"]).first
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
                if (kind === 'fill') {
                    try { el.focus(); } catch (e) {}
                    const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
                    if (d && d.set) d.set.call(el, val); else el.value = val;
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
            "viewport": {"width": VIEWPORT_W, "height": VIEWPORT_H},
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


@app.post("/live/sessions")
async def open_session(body: OpenBody) -> dict:
    sid = uuid.uuid4().hex[:12]
    s = LiveSession(id=sid, owner=body.owner, url=body.url)
    try:
        await s.start()
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


class FocusBody(BaseModel):
    ticket: str = ""


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
    return {"seq": s.frame_seq, "data": s.latest_frame or "",
            "viewport": {"width": VIEWPORT_W, "height": VIEWPORT_H}}


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
                "state": None if kind == "move" else await s.post_state(),
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
