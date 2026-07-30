"""Session management for the realistic-UI pilot (the LLD base->clone->discard model).

Two kinds of SID, over the CUA-Gym-Hub state API:
  * seed_sid    — the task's FROZEN canonical state per app (stable, idempotent).
  * attempt_sid — a per-attempt CLONE of the seed, mutated by the annotator, TTL-wiped.

Operations:
  seed_task(task, seed, mock_map)                     -> write base state under seed_sids
  start_session(task, seed, annotator, mock_map)      -> clone seeds -> attempt_sids, record it
  end_session(session_id)                             -> wipe attempt SIDs, mark ended
  expire_sessions()                                   -> wipe SIDs of sessions past TTL
  promote_golden(session_id)                          -> keep it; mark trajectory golden
  diffs(session_id)                                   -> per-app /go state_diff (the verifier signal)
  list_sessions()                                     -> registry rows

Sessions are tracked in a SQLite registry next to this file. mock_map is
"shop=http://localhost:5201,mail=http://localhost:5203,...".

CLI:
  python -m tools.session_manager start  --task M301/... --seed 0 --annotator alice --mock-map "shop=...,mail=..."
  python -m tools.session_manager diffs  --session <id>
  python -m tools.session_manager golden --session <id>
  python -m tools.session_manager end    --session <id>
  python -m tools.session_manager expire
  python -m tools.session_manager list
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sqlite3
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from tools.seed_to_cuagym import APP_TO_MOCK, transformed_states

DB = pathlib.Path(__file__).resolve().parent / ".pilot_sessions.sqlite"
DEFAULT_TTL_MIN = int(os.environ.get("PILOT_TTL_MIN", "90"))


# --------------------------------------------------------------- helpers -------
def _sanitize(s: str) -> str:
    # the mock sanitizes sids to [a-zA-Z0-9_-]; match that so seed_sids are stable.
    return re.sub(r"[^a-zA-Z0-9_-]", "_", s)


def _seed_sid(task_id: str, seed: int, app: str) -> str:
    return _sanitize(f"seed-{task_id}-{seed}-{app}")


def _http(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode() or "{}")


def _post_state(url: str, sid: str, state: dict, action: str = "set") -> dict:
    return _http("POST", f"{url.rstrip('/')}/post?sid={sid}", {"action": action, "state": state})


def _get_state(url: str, sid: str) -> dict:
    return _http("GET", f"{url.rstrip('/')}/state?sid={sid}").get("stored_state") or {}


def _reset(url: str, sid: str) -> dict:
    return _http("POST", f"{url.rstrip('/')}/post?sid={sid}", {"action": "reset"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_mock_map(s: str) -> dict[str, str]:
    return dict(p.split("=", 1) for p in s.split(",") if "=" in p)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS session(
        id TEXT PRIMARY KEY, task_id TEXT, seed INTEGER, annotator TEXT,
        status TEXT, started_at TEXT, expires_at TEXT, is_golden INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS session_app(
        session_id TEXT, app TEXT, mock TEXT, attempt_sid TEXT, url TEXT,
        FOREIGN KEY(session_id) REFERENCES session(id))""")
    return conn


# --------------------------------------------------------------- ops -----------
def seed_task(task_id: str, seed: int, mock_map: dict[str, str]) -> dict[str, str]:
    """Write the task's canonical state under a stable seed_sid per app. Idempotent."""
    out: dict[str, str] = {}
    for app, (_mock, state) in transformed_states(task_id, seed, list(mock_map)).items():
        url = mock_map.get(app)
        if not url:
            continue
        sid = _seed_sid(task_id, seed, app)
        _post_state(url, sid, state, "set")
        out[app] = sid
    return out


def start_session(task_id: str, seed: int, annotator: str, mock_map: dict[str, str],
                  ttl_min: int = DEFAULT_TTL_MIN) -> dict:
    """Clone each app's frozen seed into a fresh attempt_sid and record the session."""
    seed_sids = seed_task(task_id, seed, mock_map)  # ensure the base exists
    session_id = str(uuid.uuid4())
    started = _now()
    expires = started + timedelta(minutes=ttl_min)
    conn = _db()
    conn.execute("INSERT INTO session VALUES (?,?,?,?,?,?,?,0)",
                 (session_id, task_id, seed, annotator, "active",
                  started.isoformat(), expires.isoformat()))
    apps = []
    for app, seedsid in seed_sids.items():
        url = mock_map[app]
        state = _get_state(url, seedsid)              # read the frozen seed
        attempt = str(uuid.uuid4())
        _post_state(url, attempt, state, "set")       # clone -> attempt's own initial+current
        frag = "#/inbox" if APP_TO_MOCK.get(app) == "gmail_mock" else ""
        open_url = f"{url.rstrip('/')}/?sid={attempt}{frag}"
        conn.execute("INSERT INTO session_app VALUES (?,?,?,?,?)",
                     (session_id, app, APP_TO_MOCK[app], attempt, url))
        apps.append({"app": app, "attempt_sid": attempt, "url": open_url})
    conn.commit()
    conn.close()
    return {"session_id": session_id, "task_id": task_id, "seed": seed,
            "annotator": annotator, "expires_at": expires.isoformat(), "apps": apps}


def _session_apps(conn, session_id):
    return conn.execute(
        "SELECT app, mock, attempt_sid, url FROM session_app WHERE session_id=?",
        (session_id,)).fetchall()


def end_session(session_id: str) -> None:
    conn = _db()
    for _app, _mock, attempt, url in _session_apps(conn, session_id):
        try:
            _reset(url, attempt)
        except Exception:
            pass
    conn.execute("UPDATE session SET status='ended' WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


def expire_sessions() -> int:
    """Wipe attempt SIDs of active, non-golden sessions past their TTL."""
    now = _now().isoformat()
    conn = _db()
    rows = conn.execute(
        "SELECT id FROM session WHERE status='active' AND is_golden=0 AND expires_at<?",
        (now,)).fetchall()
    for (sid,) in rows:
        for _app, _mock, attempt, url in _session_apps(conn, sid):
            try:
                _reset(url, attempt)
            except Exception:
                pass
        conn.execute("UPDATE session SET status='expired' WHERE id=?", (sid,))
    conn.commit()
    n = len(rows)
    conn.close()
    return n


def promote_golden(session_id: str) -> None:
    conn = _db()
    conn.execute("UPDATE session SET is_golden=1 WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


def diffs(session_id: str) -> dict:
    """Per-app /go state_diff for the session — the verifier signal (initial vs current)."""
    conn = _db()
    apps = _session_apps(conn, session_id)
    conn.close()
    out = {}
    for app, _mock, attempt, url in apps:
        try:
            out[app] = _http("GET", f"{url.rstrip('/')}/go?sid={attempt}").get("state_diff")
        except Exception as e:
            out[app] = {"error": repr(e)}
    return out


def list_sessions() -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT id, task_id, seed, annotator, status, expires_at, is_golden FROM session "
        "ORDER BY started_at DESC").fetchall()
    conn.close()
    cols = ["id", "task_id", "seed", "annotator", "status", "expires_at", "is_golden"]
    return [dict(zip(cols, r)) for r in rows]


# --------------------------------------------------------------- cli -----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start")
    p.add_argument("--task", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--annotator", default="anon")
    p.add_argument("--mock-map", required=True)
    p.add_argument("--ttl-min", type=int, default=DEFAULT_TTL_MIN)

    for name in ("end", "golden", "diffs"):
        q = sub.add_parser(name)
        q.add_argument("--session", required=True)

    sub.add_parser("expire")
    sub.add_parser("list")

    args = ap.parse_args(argv)

    if args.cmd == "start":
        res = start_session(args.task, args.seed, args.annotator,
                            parse_mock_map(args.mock_map), args.ttl_min)
        print(f"session {res['session_id']}  (expires {res['expires_at']})")
        for a in res["apps"]:
            print(f"  open: {a['url']}")
    elif args.cmd == "end":
        end_session(args.session)
        print("ended")
    elif args.cmd == "golden":
        promote_golden(args.session)
        print("promoted to golden")
    elif args.cmd == "diffs":
        print(json.dumps(diffs(args.session), indent=2, ensure_ascii=False))
    elif args.cmd == "expire":
        print(f"expired {expire_sessions()} session(s)")
    elif args.cmd == "list":
        for s in list_sessions():
            print(f"  {s['id']}  {s['status']:8} golden={s['is_golden']}  {s['annotator']:10} {s['task_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
