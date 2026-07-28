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
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

    async def start(self) -> None:
        from playwright.async_api import async_playwright

        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            device_scale_factor=1,
        )
        self.page = await self.context.new_page()
        await self.page.goto(self.url, wait_until="load")
        self.cdp = await self.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        await self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": 60,
            "maxWidth": VIEWPORT_W, "maxHeight": VIEWPORT_H, "everyNthFrame": 1,
        })

    def _on_frame(self, params: dict) -> None:
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

    async def type_text(self, text: str) -> None:
        await self.page.keyboard.type(text)

    async def key(self, key: str) -> None:
        await self.page.keyboard.press(key)

    async def navigate(self, url: str) -> None:
        await self.page.goto(url, wait_until="load")

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

    async def _open_tab(self, url: str) -> dict:
        page = await self.context.new_page()
        await page.goto(url, wait_until="load")
        self.page = page
        await page.bring_to_front()
        return {"ok": True, "kind": "open_tab",
                "resolved": {"url": page.url, "tabIndex": self._tabs().index(page)}}

    async def _switch_tab(self, index: int) -> dict:
        pages = self._tabs()
        if not (0 <= index < len(pages)):
            return {"ok": False, "kind": "switch_tab",
                    "error": f"tab index {index} out of range (0..{len(pages) - 1})", "resolved": {}}
        self.page = pages[index]
        await self.page.bring_to_front()
        return {"ok": True, "kind": "switch_tab", "resolved": {"url": self.page.url, "tabIndex": index}}

    async def _close_tab(self, index: int) -> dict:
        pages = self._tabs()
        if len(pages) <= 1:
            return {"ok": False, "kind": "close_tab", "error": "cannot close the last remaining tab", "resolved": {}}
        if not (0 <= index < len(pages)):
            return {"ok": False, "kind": "close_tab",
                    "error": f"tab index {index} out of range (0..{len(pages) - 1})", "resolved": {}}
        closing = pages[index]
        await closing.close()
        if self.page is closing:
            self.page = self._tabs()[0]
            await self.page.bring_to_front()
        return {"ok": True, "kind": "close_tab", "resolved": {"url": self.page.url}}

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
            return await self._switch_tab(int(args.get("tab_index", args.get("index", 0))))
        if kind == "close_tab":
            return await self._close_tab(int(args.get("tab_index", args.get("index", 0))))
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
        if kind in ("click", "submit"):
            loc = self.page.locator(sel).first
            with contextlib.suppress(Exception):
                if await loc.is_visible():
                    await loc.scroll_into_view_if_needed(timeout=2000)
                    await loc.click(timeout=5000)
                    ok = True
            if not ok:
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
        return await self.page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body) return {};
                return {
                    testId: el.getAttribute('data-test-id') || '',
                    id: el.id || '',
                    name: el.getAttribute('name') || '',
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    autocomplete: el.getAttribute('autocomplete') || '',
                    label: (el.getAttribute('aria-label') || '').slice(0, 120),
                    tag: el.tagName.toLowerCase(),
                };
            }"""
        )

    async def describe(self, nx: float, ny: float) -> dict:
        """Locator candidates for whatever is at this point, captured BEFORE an
        action is dispatched — afterwards the element may not exist."""
        x, y = self.to_page_xy(nx, ny)
        return await self.page.evaluate(
            """([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return {};
                const t = el.closest('[data-test-id],button,a,input,select,textarea,[role]') || el;
                return {
                    testId: t.getAttribute('data-test-id') || '',
                    id: t.id || '',
                    name: t.getAttribute('name') || '',
                    role: t.getAttribute('role') || t.tagName.toLowerCase(),
                    type: t.getAttribute('type') || '',
                    autocomplete: t.getAttribute('autocomplete') || '',
                    label: (t.getAttribute('aria-label') || '').slice(0, 120),
                    text: (t.textContent || '').trim().slice(0, 120),
                    tag: t.tagName.toLowerCase(),
                };
            }""",
            [x, y],
        )

    async def info(self) -> dict:
        pages = self.context.pages if self.context else []
        return {
            "url": self.page.url if self.page else "",
            "tabs": [p.url for p in pages],
            "activeTab": pages.index(self.page) if self.page in pages else 0,
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
        while not s.closed:
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
                await s.key(msg.get("key", ""))
            elif kind == "navigate":
                await s.navigate(msg.get("url", ""))
            else:
                await ws.send_text(json.dumps({"type": "ack", "id": input_id, "applied": False, "reason": "unknown"}))
                continue
            await ws.send_text(json.dumps({"type": "ack", "id": input_id, "applied": True}))
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
