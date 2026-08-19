"""FastAPI seam the realistic mock UIs call to drive the gym engine.

In *bridged* mode a mock UI, instead of mutating its local React store, sends the
semantic action here. The service forwards it to the gym's real action endpoint
(full logic: mutation + cross-app hook + scheduler), re-projects the advanced
world, and returns the fresh per-app state the tabs should render — so a shop
order's confirmation email shows up in the Gmail tab automatically. Each action
is also journalled to the hub as a `set_current`, which is what puts the whole
trajectory in cua-gym.

**A gym process holds ONE global world** (`server/main.py` SESSION), so an attempt
needs a gym to itself. This service is a router over a POOL of gym instances:
`GYM_URLS` lists them, a session leases one for its lifetime and releases it on
end/TTL. Concurrency ceiling = pool size; asking for more returns 503 rather than
silently letting two annotators share one world.

Run:
  GYM_URLS=http://127.0.0.1:8077,http://127.0.0.1:8078 HARNESS_TOKEN=... \
  uvicorn tools.bridge_service:app --port 8090

Routes (session-scoped; `{sid}` is the attempt id):
  POST /bridge/{sid}/open   {task_id, seed, sids?}  -> lease a gym, reset, baseline
  POST /bridge/{sid}/act    {action, payload}       -> {ok, status, apps}
  GET  /bridge/{sid}/state  [?app=shop]             -> {apps:{app:state}}
  GET  /bridge/{sid}/verify [?url=]                 -> the gym's real verdict
  POST /bridge/{sid}/close                          -> release the gym
  GET  /bridge/sessions                             -> pool + lease status

The unscoped /bridge/reset|act|state|verify routes still work and operate on a
single default session, so existing single-episode callers keep working.
"""
from __future__ import annotations

import atexit
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools.bridge import ACTIONS, Bridge

app = FastAPI(title="realistic-ui bridge")
# The mocks are separate origins; let them call this seam from the browser.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

DEFAULT_SESSION = "_default"
TTL_SEC = int(os.environ.get("BRIDGE_TTL_MIN", "90")) * 60

# How long a session must have been IDLE before a newcomer may take its gym when
# the pool is full.
#
# The plain TTL is generous on purpose — an annotator mid-task who steps away for
# twenty minutes must come back to their world. But an annotator who simply
# CLOSES THE TAB never calls /close, so their gym stays leased for the full TTL,
# and a pool of two is dead for an hour and a half after two abandoned tabs. That
# is not hypothetical: it is what the pool looked like when this was written, both
# gyms held by sessions idle for 75 minutes, every annotator getting "every gym in
# the bridge pool is busy".
#
# So idleness only costs you your gym when someone else actually needs one, and
# only after this much of it. An active session is never evicted, however full the
# pool is, because touching it resets the clock.
GRACE_SEC = int(os.environ.get("BRIDGE_GRACE_MIN", "12")) * 60


def _mock_map() -> dict[str, str]:
    """app -> state-API base. Explicit CUA_HUB_URL_* wins; otherwise the live hub."""
    explicit = {a: os.environ[f"CUA_HUB_URL_{a.upper()}"]
                for a in ("shop", "mail", "market", "calendar", "food")
                if os.environ.get(f"CUA_HUB_URL_{a.upper()}")}
    if explicit:
        return explicit
    if os.environ.get("BRIDGE_NO_HUB"):
        return {}
    from tools.cua_env import api_map
    return api_map()


#: Ceiling on gyms the bridge may START for itself. Each is a uvicorn process
#: holding ONE world, so this is the real answer to "how many annotators can work
#: at once" — a static GYM_URLS of two meant the third annotator was simply told
#: to come back later, and since a certify leases a second gym it was really the
#: SECOND annotator. Isolation is the point of one-gym-per-session; the fix is to
#: have enough gyms, not to share one.
MAX_GYMS = int(os.environ.get("BRIDGE_MAX_GYMS", "10"))
#: Where grown gyms are placed. Deliberately clear of the 80xx band the rest of
#: the stack publishes — the annotator frontend is on 8080, its backend on 8090,
#: this bridge on 8093 — because walking upward from 8077 put a "gym" on 8080 and
#: the pool then leased the FRONTEND to an annotator as their world.
GROW_PORT_BASE = int(os.environ.get("BRIDGE_GROW_PORT_BASE", "8300"))
#: Set BRIDGE_AUTOSCALE=0 to pin the pool to GYM_URLS (CI, or a hosted deploy
#: where the gyms are managed outside this process).
AUTOSCALE = os.environ.get("BRIDGE_AUTOSCALE", "1").strip().lower() not in ("0", "false", "off", "no")

#: Gyms this process started, url -> Popen. Kept so status can report them and so
#: they die with the bridge rather than outliving it as orphans.
_GROWN: "dict[str, subprocess.Popen]" = {}
#: REENTRANT: `_grow_pool` holds this while it checks the cap, and the cap check
#: calls `_gym_pool()`, which takes it again to read the grown set. With a plain
#: Lock that is a deadlock — the bridge froze on the first annotator who needed a
#: third gym, which is precisely the case this code exists to serve.
_GROWN_LOCK = threading.RLock()


def _gym_pool() -> list[str]:
    urls = os.environ.get("GYM_URLS") or os.environ.get("GYM_URL") or "http://127.0.0.1:8077"
    static = [u.strip().rstrip("/") for u in urls.split(",") if u.strip()]
    with _GROWN_LOCK:
        grown = [u for u in _GROWN if u not in static]
    return static + grown


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
        sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sk.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _is_a_gym(url: str) -> bool:
    """Is a GYM listening here — not merely something that speaks HTTP.

    "Any HTTP answer means it booted" is what let a port collision become a
    correctness bug: the probe accepted the annotator frontend's index.html as a
    ready gym, and the pool then leased that URL to an annotator as their world.
    A gym is identified by its own routes, so ask for the schema and look for
    them.
    """
    try:
        with urllib.request.urlopen(f"{url}/openapi.json", timeout=2) as f:
            spec = json.loads(f.read() or b"{}")
    except Exception:                # noqa: BLE001 — not listening, or not FastAPI
        return False
    return any(str(p).startswith("/_harness") for p in (spec.get("paths") or {}))


def _grow_pool() -> str | None:
    """Start one more gym and return its URL, or None if we may not.

    A gym is a uvicorn process holding a single world — exactly what
    run_bridged_stack.sh starts — so the bridge can start another itself when a
    real annotator would otherwise be refused. Bounded by MAX_GYMS: this is a
    per-annotator world, not an unbounded resource, and an unbounded loop here
    would fill the host instead of merely violating a policy.
    """
    if not AUTOSCALE:
        return None
    with _GROWN_LOCK:
        if len(_gym_pool()) >= MAX_GYMS:
            return None
        port = next((p for p in range(GROW_PORT_BASE, GROW_PORT_BASE + MAX_GYMS * 4)
                     if _port_is_free(p)), None)
        if port is None:
            return None
        url = f"http://127.0.0.1:{port}"
        log = open(os.path.join(tempfile.gettempdir(), f"gym_{port}.log"), "ab", buffering=0)
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=log, stderr=log, start_new_session=True,
        )
        _GROWN[url] = proc

    # Wait for it to actually answer. Handing back a URL that 502s would turn a
    # capacity problem into a much more confusing one.
    for _ in range(GROW_WAIT_TRIES):
        if proc.poll() is not None:
            with _GROWN_LOCK:
                _GROWN.pop(url, None)
            return None
        if _is_a_gym(url):
            return url
        time.sleep(GROW_WAIT_MS / 1000)
    with _GROWN_LOCK:
        _GROWN.pop(url, None)
    proc.terminate()
    return None


GROW_WAIT_TRIES = int(os.environ.get("BRIDGE_GROW_WAIT_TRIES", "60"))
GROW_WAIT_MS = int(os.environ.get("BRIDGE_GROW_WAIT_MS", "500"))


# BRIDGE_TICK=0 disables the per-action scheduler tick — set this when an external
# harness (eval.run) owns the clock, so scheduled events aren't advanced ahead of
# the agent's observation.
_TICK = os.environ.get("BRIDGE_TICK", "1").strip().lower() not in ("0", "false", "off", "no")


class _Session:
    def __init__(self, sid: str, gym_url: str):
        self.sid, self.gym_url = sid, gym_url
        self.touched = time.monotonic()
        self.bridge = Bridge(gym_url=gym_url, mock_map=_mock_map(),
                             harness_token=os.environ.get("HARNESS_TOKEN", ""),
                             tick_enabled=_TICK)


class _Pool:
    """Leases gym instances to sessions. One world per gym, one gym per session."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def _reap_locked(self) -> None:
        now = time.monotonic()
        stale = [s for s, x in self._sessions.items()
                 if s != DEFAULT_SESSION and now - x.touched > TTL_SEC]
        # The back-compat default session is created eagerly (module import binds
        # BRIDGE), so on a one-gym pool it would otherwise hold the only slot and
        # every real session would get a 503. An unopened default owns nothing.
        if (d := self._sessions.get(DEFAULT_SESSION)) is not None and d.bridge.task_id is None:
            stale.append(DEFAULT_SESSION)
        for sid in stale:
            self._sessions.pop(sid, None)

    def get(self, sid: str, create: bool = False) -> _Session | None:
        with self._lock:
            self._reap_locked()
            s = self._sessions.get(sid)
            if s is not None:
                s.touched = time.monotonic()
                return s
            if not create:
                return None
            free = [u for u in _gym_pool()
                    if u not in {x.gym_url for x in self._sessions.values()}]
            if not free:
                # Nothing free. GROW first — an annotator should get their own
                # world, not wait for someone else's or take it from them. Only
                # once we are at the cap does the old eviction/refusal path apply.
                #
                # Released outside the lock: starting a gym takes seconds, and
                # holding the pool lock for it would block every other session's
                # touch/status call for the duration.
                grown = None
                self._lock.release()
                try:
                    grown = _grow_pool()
                finally:
                    self._lock.acquire()
                # Re-check under the lock: another thread may have finished first,
                # or freed a gym while we were growing.
                if (s := self._sessions.get(sid)) is not None:
                    s.touched = time.monotonic()
                    return s
                taken = {x.gym_url for x in self._sessions.values()}
                free = [u for u in ([grown] if grown else []) + _gym_pool()
                        if u and u not in taken]
            if not free:
                # At the cap. Take the gym off the session that has gone longest
                # without being touched, provided it is past the grace period —
                # almost always a closed tab, which never calls /close and would
                # otherwise hold its gym for the whole TTL.
                victim = self._lru_evictable_locked()
                if victim is None:
                    return None
                free = [self._sessions.pop(victim).gym_url]
            s = _Session(sid, free[0])
            self._sessions[sid] = s
            return s

    def _lru_evictable_locked(self) -> str | None:
        """The idlest session past GRACE_SEC, or None if every session is in use.

        Returning None is what keeps this from being a footgun: with every gym
        genuinely busy the caller still gets its 503 and the annotator is told to
        try again, rather than someone mid-task losing their world to a newcomer.
        """
        now = time.monotonic()
        idle = [(now - x.touched, sid) for sid, x in self._sessions.items()
                if now - x.touched > GRACE_SEC]
        return max(idle)[1] if idle else None

    def close(self, sid: str) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None

    def status(self) -> dict:
        with self._lock:
            pool = _gym_pool()
            with _GROWN_LOCK:
                grown = sorted(_GROWN)
            return {"pool": pool, "capacity": len(pool),
                    # What the pool may still become, so "busy" can be told apart
                    # from "at the ceiling" without reading the source.
                    "maxGyms": MAX_GYMS if AUTOSCALE else len(pool),
                    "autoscale": AUTOSCALE, "grown": grown,
                    "sessions": {s: {"gym": x.gym_url, "task_id": x.bridge.task_id,
                                     "idle_sec": round(time.monotonic() - x.touched)}
                                 for s, x in self._sessions.items()}}


POOL = _Pool()


@atexit.register
def _stop_grown_gyms() -> None:
    """Gyms this process started die with it. Without this a bridge restart
    leaves them running, holding their ports, and the next bridge grows a second
    set beside them."""
    with _GROWN_LOCK:
        procs = list(_GROWN.values())
        _GROWN.clear()
    for pr in procs:
        with contextlib.suppress(Exception):
            pr.terminate()


class PoolExhausted(RuntimeError):
    """No gym is free. Never silently share one instead."""


# The unscoped `/bridge/*` routes drive a single shared world with no session id.
# That is fine for a one-off CLI/eval run and WRONG for a hosted multi-annotator
# deploy, so it is opt-in.
_ALLOW_DEFAULT = os.environ.get("BRIDGE_DEFAULT_SESSION", "0").strip().lower() in ("1", "true", "yes")


def _default() -> _Session:
    """The back-compat unscoped session.

    This used to fall back to `_Session(DEFAULT_SESSION, _gym_pool()[0])` when the
    pool was full — an UNREGISTERED session on gym #0, which is almost certainly
    leased to a real annotator. It would then `/reset` that gym and destroy their
    world, silently, and precisely under load. Refuse instead: a 503 is a bad
    afternoon, sharing a world is corrupted data.
    """
    if not _ALLOW_DEFAULT:
        raise PoolExhausted(
            "the unscoped /bridge routes are disabled — pass a session id "
            "(/bridge/{sid}/…), or set BRIDGE_DEFAULT_SESSION=1 for single-run CLI use"
        )
    s = POOL.get(DEFAULT_SESSION, create=True)
    if s is None:
        raise PoolExhausted("no free gym instance")
    return s


def __getattr__(name: str):
    """`BRIDGE` resolved lazily (PEP 562).

    Binding it at import leased a pool slot just by importing the module, which
    on a small pool is a slot a real annotator then cannot have — and the reaper
    only reclaims it on the *next* `get`, so the first real `/open` could still
    lose the race.
    """
    if name == "BRIDGE":
        return _default().bridge
    raise AttributeError(name)


def _all_state(bridge: Bridge) -> dict[str, dict]:
    return {app: state for app, (_mock, state) in bridge.project().items()}


class OpenReq(BaseModel):
    task_id: str
    seed: int = 0
    # {app: attempt_sid} — where this session's state is journalled in the hub.
    sids: dict[str, str] = {}
    # Re-open a session that is ALREADY on this task/seed by resetting it to the
    # seed world. Off by default: a plain re-open (a reconnect, a second replica,
    # a double-click) must not throw away work in progress.
    force: bool = False


class ResetReq(BaseModel):
    task_id: str
    seed: int = 0


class ActReq(BaseModel):
    action: str
    payload: dict = {}


def _open(bridge: Bridge, task_id: str, seed: int, sids: dict | None = None) -> dict:
    if sids:
        bridge.session.update(sids)
    meta = bridge.reset(task_id, seed)
    if bridge.mock_map:
        # baseline: freeze the hub's initial_state once. Every action after this
        # appends its own event row instead of overwriting the baseline.
        bridge.push(baseline=True)
    return {"ok": bool(meta), "task_id": meta.get("task_id"),
            "task_brief": meta.get("task_brief"), "apps": _all_state(bridge)}


def _act(bridge: Bridge, req: ActReq) -> dict:
    if req.action not in ACTIONS:
        return {"ok": False, "error": f"unknown action {req.action!r}",
                "known": sorted(ACTIONS)}
    r = bridge.act(req.action, **req.payload)
    out = {"ok": r["ok"], "status": r["status"], "apps": _all_state(bridge)}
    # Pass the engine's refusal reason through so a mock can tell the user WHY an
    # action did nothing, instead of silently applying an unchanged world.
    if r.get("error"):
        out["error"] = r["error"]
    return out


# ------------------------------------------------------------- session-scoped --
@app.post("/bridge/{sid}/open")
def open_session(sid: str, req: OpenReq) -> dict:
    s = POOL.get(sid, create=True)
    if s is None:
        return {"ok": False, "error": "no free gym instance", "status": 503,
                **POOL.status()}
    # Idempotent. Opening resets the gym to the seed world, so a SECOND open on a
    # live session destroys whatever the annotator has built — reachable today on
    # a reconnect or a double-click, and guaranteed with more than one backend
    # replica. Same task and seed means "attach to what is already here".
    if not req.force and s.bridge.task_id == req.task_id and s.bridge.seed == req.seed:
        if req.sids:
            s.bridge.session.update(req.sids)
        return {"ok": True, "reused": True, "task_id": s.bridge.task_id,
                "apps": _all_state(s.bridge), "gym_url": s.gym_url}
    out = _open(s.bridge, req.task_id, req.seed, req.sids)
    out["reused"] = False
    out["gym_url"] = s.gym_url
    return out


@app.post("/bridge/{sid}/act")
def act_session(sid: str, req: ActReq) -> dict:
    s = POOL.get(sid)
    if s is None:
        return {"ok": False, "error": f"unknown session {sid!r} — call /open first"}
    return _act(s.bridge, req)


@app.get("/bridge/{sid}/state")
def state_session(sid: str, app: str | None = None) -> dict:
    s = POOL.get(sid)
    if s is None:
        return {"apps": {}, "error": f"unknown session {sid!r}"}
    allst = _all_state(s.bridge)
    return {"apps": {app: allst.get(app)} if app else allst}


@app.get("/bridge/{sid}/verify")
def verify_session(sid: str, url: str = "") -> dict:
    s = POOL.get(sid)
    if s is None:
        return {"error": f"unknown session {sid!r}"}
    return s.bridge.verify(url=url)


class RepushReq(BaseModel):
    # The engine's step clock as of the restored world. Load-bearing: `reset`
    # zeroes `_step`, so without this the next action ticks from 1 and the
    # scheduler re-fires cross-app events that were already delivered.
    step: int | None = None


@app.post("/bridge/{sid}/repush")
def repush_session(sid: str, req: RepushReq) -> dict:
    """Re-project the engine's CURRENT world into the five mocks.

    Used after restoring a checkpoint into a freshly-leased gym: the engine holds
    the annotator's world again, but the hub rows still hold the seed projection,
    so without this their tabs render the seed until the first click.

    `push()` (not `push(baseline=True)`) — the frozen initial_state stays as it
    was, so the delta verifiers keep comparing against the seed.
    """
    s = POOL.get(sid)
    if s is None:
        return {"ok": False, "error": f"unknown session {sid!r} — call /open first"}
    if req.step is not None:
        s.bridge._step = int(req.step)
    return {"ok": True, "pushed": s.bridge.push(), "apps": _all_state(s.bridge)}


@app.post("/bridge/{sid}/close")
def close_session(sid: str) -> dict:
    return {"ok": POOL.close(sid)}


@app.get("/bridge/sessions")
def sessions() -> dict:
    return POOL.status()


@app.get("/bridge/health")
def health() -> dict:
    """Pilot wiring check: hub_source must be explicit-env for isolated stacks."""
    explicit = {
        a: os.environ[f"CUA_HUB_URL_{a.upper()}"]
        for a in ("shop", "mail", "market", "calendar", "food")
        if os.environ.get(f"CUA_HUB_URL_{a.upper()}")
    }
    if explicit:
        hub_source = "explicit-env"
    elif os.environ.get("BRIDGE_NO_HUB"):
        hub_source = "no-hub"
    else:
        hub_source = "cua-env-default"
    # `hub_map` is what eval.run preflight reads (must be non-empty when
    # --app-origins drives bridged hubs). Keep `explicit_apps` for older checks.
    hub_map = dict(explicit) if explicit else _mock_map()
    return {
        "ok": True,
        "hub_source": hub_source,
        "explicit_apps": sorted(explicit.keys()),
        "hub_map": hub_map,
        "mock_map": hub_map,
        "gym_pool": _gym_pool(),
        "bridge_tick": _TICK,
    }


# ------------------------------------------------ single-episode (back-compat) --
# These drive ONE shared world with no session id, so a multi-annotator deploy
# leaves them off (BRIDGE_DEFAULT_SESSION=0, the default). The refusal shape is
# the same `{"ok": false, ..., "status": 503}` body the annotator's
# `bridge_client` already maps to BridgePoolExhausted.
def _no_default(exc: PoolExhausted) -> dict:
    return {"ok": False, "error": str(exc), "status": 503, **POOL.status()}


@app.post("/bridge/reset")
def reset(req: ResetReq) -> dict:
    try:
        return _open(_default().bridge, req.task_id, req.seed)
    except PoolExhausted as exc:
        return _no_default(exc)


@app.post("/bridge/act")
def act(req: ActReq) -> dict:
    try:
        return _act(_default().bridge, req)
    except PoolExhausted as exc:
        return _no_default(exc)


@app.get("/bridge/state")
def state(app: str | None = None) -> dict:
    try:
        allst = _all_state(_default().bridge)
    except PoolExhausted as exc:
        return {"apps": {}, **_no_default(exc)}
    return {"apps": {app: allst.get(app)} if app else allst}


@app.get("/bridge/verify")
def verify(url: str = "") -> dict:
    try:
        return _default().bridge.verify(url=url)
    except PoolExhausted as exc:
        return _no_default(exc)


@app.get("/bridge/actions")
def actions() -> dict:
    """The semantic actions each app's UI can drive (for wiring the client)."""
    out: dict[str, list] = {}
    for name, (method, path, fields) in ACTIONS.items():
        out.setdefault(name.split(".")[0], []).append(
            {"action": name, "method": method, "path": path, "fields": list(fields)})
    return out
