"""FastAPI seam the realistic mock UIs call to drive the gym engine.

In *bridged* mode a mock UI, instead of mutating its local React store, sends the
semantic action here. The service forwards it to the gym's real action endpoint
(full logic: mutation + cross-app hook + scheduler), re-projects the advanced
world, and returns the fresh per-app state the tabs should render — so a shop
order's confirmation email shows up in the Gmail tab automatically.

One service instance = one live episode (the gym keeps a single global world).
For many concurrent annotators, run one (gym + bridge) per attempt, or keep the
mocks read-only-seeded via tools/session_manager and bridge only the active tab.

Run:  GYM_URL=http://127.0.0.1:8077 HARNESS_TOKEN=... \
      uvicorn tools.bridge_service:app --port 8090

Routes:
  POST /bridge/reset  {task_id, seed}      -> {ok, task_id, apps:{app:state}}
  POST /bridge/act    {action, payload}    -> {ok, status, apps:{app:state}}
  GET  /bridge/state  [?app=shop]          -> {apps:{app:state}}
  GET  /bridge/verify [?url=]              -> the gym's real milestone verdict
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from tools.bridge import ACTIONS, Bridge

app = FastAPI(title="realistic-ui bridge")
# The mocks are separate origins; let them call this seam from the browser.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _mock_map() -> dict[str, str]:
    return {a: os.environ[f"CUA_HUB_URL_{a.upper()}"]
            for a in ("shop", "mail", "market", "calendar", "food")
            if os.environ.get(f"CUA_HUB_URL_{a.upper()}")}


# One live episode per service instance.
# BRIDGE_TICK=0 disables the per-action scheduler tick — set this when an external
# harness (eval.run) owns the clock, so scheduled events aren't advanced ahead of
# the agent's observation.
_TICK = os.environ.get("BRIDGE_TICK", "1").strip().lower() not in ("0", "false", "off", "no")
BRIDGE = Bridge(
    gym_url=os.environ.get("GYM_URL", "http://127.0.0.1:8077"),
    mock_map=_mock_map(),
    harness_token=os.environ.get("HARNESS_TOKEN", ""),
    tick_enabled=_TICK,
)


def _all_state() -> dict[str, dict]:
    return {app: state for app, (_mock, state) in BRIDGE.project().items()}


class ResetReq(BaseModel):
    task_id: str
    seed: int = 0


class ActReq(BaseModel):
    action: str
    payload: dict = {}


@app.post("/bridge/reset")
def reset(req: ResetReq) -> dict:
    meta = BRIDGE.reset(req.task_id, req.seed)
    if BRIDGE.mock_map:
        BRIDGE.push()
    return {"ok": bool(meta), "task_id": meta.get("task_id"),
            "task_brief": meta.get("task_brief"), "apps": _all_state()}


@app.post("/bridge/act")
def act(req: ActReq) -> dict:
    if req.action not in ACTIONS:
        return {"ok": False, "error": f"unknown action {req.action!r}",
                "known": sorted(ACTIONS)}
    r = BRIDGE.act(req.action, **req.payload)
    return {"ok": r["ok"], "status": r["status"], "apps": _all_state()}


@app.get("/bridge/state")
def state(app: str | None = None) -> dict:
    allst = _all_state()
    return {"apps": {app: allst.get(app)} if app else allst}


@app.get("/bridge/verify")
def verify(url: str = "") -> dict:
    return BRIDGE.verify(url=url)


@app.get("/bridge/actions")
def actions() -> dict:
    """The semantic actions each app's UI can drive (for wiring the client)."""
    out: dict[str, list] = {}
    for name, (method, path, fields) in ACTIONS.items():
        out.setdefault(name.split(".")[0], []).append(
            {"action": name, "method": method, "path": path, "fields": list(fields)})
    return out
