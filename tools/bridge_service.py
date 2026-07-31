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

import os
import threading
import time

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


def _gym_pool() -> list[str]:
    urls = os.environ.get("GYM_URLS") or os.environ.get("GYM_URL") or "http://127.0.0.1:8077"
    return [u.strip().rstrip("/") for u in urls.split(",") if u.strip()]


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
                return None
            s = _Session(sid, free[0])
            self._sessions[sid] = s
            return s

    def close(self, sid: str) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None

    def status(self) -> dict:
        with self._lock:
            pool = _gym_pool()
            return {"pool": pool, "capacity": len(pool),
                    "sessions": {s: {"gym": x.gym_url, "task_id": x.bridge.task_id,
                                     "idle_sec": round(time.monotonic() - x.touched)}
                                 for s, x in self._sessions.items()}}


POOL = _Pool()


def _default() -> _Session:
    s = POOL.get(DEFAULT_SESSION, create=True)
    if s is None:            # pool exhausted; fall back to the first gym
        s = _Session(DEFAULT_SESSION, _gym_pool()[0])
    return s


# Back-compat: existing single-episode callers (and tests) import BRIDGE.
BRIDGE = _default().bridge


def _all_state(bridge: Bridge) -> dict[str, dict]:
    return {app: state for app, (_mock, state) in bridge.project().items()}


class OpenReq(BaseModel):
    task_id: str
    seed: int = 0
    # {app: attempt_sid} — where this session's state is journalled in the hub.
    sids: dict[str, str] = {}


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
    return {"ok": r["ok"], "status": r["status"], "apps": _all_state(bridge)}


# ------------------------------------------------------------- session-scoped --
@app.post("/bridge/{sid}/open")
def open_session(sid: str, req: OpenReq) -> dict:
    s = POOL.get(sid, create=True)
    if s is None:
        return {"ok": False, "error": "no free gym instance", "status": 503,
                **POOL.status()}
    out = _open(s.bridge, req.task_id, req.seed, req.sids)
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


@app.post("/bridge/{sid}/close")
def close_session(sid: str) -> dict:
    return {"ok": POOL.close(sid)}


@app.get("/bridge/sessions")
def sessions() -> dict:
    return POOL.status()


# ------------------------------------------------ single-episode (back-compat) --
@app.post("/bridge/reset")
def reset(req: ResetReq) -> dict:
    return _open(_default().bridge, req.task_id, req.seed)


@app.post("/bridge/act")
def act(req: ActReq) -> dict:
    return _act(_default().bridge, req)


@app.get("/bridge/state")
def state(app: str | None = None) -> dict:
    allst = _all_state(_default().bridge)
    return {"apps": {app: allst.get(app)} if app else allst}


@app.get("/bridge/verify")
def verify(url: str = "") -> dict:
    return _default().bridge.verify(url=url)


@app.get("/bridge/actions")
def actions() -> dict:
    """The semantic actions each app's UI can drive (for wiring the client)."""
    out: dict[str, list] = {}
    for name, (method, path, fields) in ACTIONS.items():
        out.setdefault(name.split(".")[0], []).append(
            {"action": name, "method": method, "path": path, "fields": list(fields)})
    return out
