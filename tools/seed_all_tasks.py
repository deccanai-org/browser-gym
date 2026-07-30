"""Seed gym tasks' canonical state into the CUA-Gym-Hub (the frozen base).

For each (task, seed, app) it writes the transformed state under a stable UUIDv5
seed_sid. Annotators never open a seed_sid — session_manager clones it into a
per-attempt sid first (opening one would mutate it: the mocks post their state on
mount, before any click).

Four modes, meant to be run in this order:

  --plan     build every cell locally and write a manifest. No network.
  --diff     compare the hub against the manifest. Classifies each cell:
               MISSING  never seeded            -> safe to apply
               OK       matches the manifest    -> leave alone
               STALE    seeded, different bytes -> needs --repair
               DRIFTED  someone opened the sid  -> needs --repair
  --apply    write the MISSING cells; with --repair also reset+set STALE/DRIFTED.
  --verify   re-diff and fail unless everything is OK.

`set` does NOT re-freeze an existing initial_state, so a changed projection needs
either --repair (reset deletes the row, then set re-freezes) or a SEED_REV bump.

Usage:
  python -m tools.seed_all_tasks --plan  --tasks-file twenty.txt
  python -m tools.seed_all_tasks --diff  --tasks-file twenty.txt
  python -m tools.seed_all_tasks --apply --tasks-file twenty.txt
  python -m tools.seed_all_tasks --verify --tasks-file twenty.txt
  python -m tools.seed_all_tasks --plan --all            # all 312
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import sys
import urllib.request

from server.tasks import TASKS
from tools import session_manager as sm
from tools.cua_env import env_name
from tools.seed_to_cuagym import transformed_states

MANIFEST = pathlib.Path(__file__).resolve().parent / "cua_seed_manifest.json"


def canonical(state: dict) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def digest(state: dict) -> str:
    return hashlib.sha256(canonical(state).encode()).hexdigest()


# ------------------------------------------------------------------ plan -------
def plan(tasks: list[str], seeds: list[int]) -> dict:
    cells, errors = [], []
    for tid in tasks:
        for seed in seeds:
            try:
                states = transformed_states(tid, seed)
            except Exception as e:
                errors.append({"task_id": tid, "seed": seed, "error": repr(e)})
                continue
            for app, (mock, state) in states.items():
                cells.append({
                    "task_id": tid, "seed": seed, "app": app, "mock": mock,
                    "seed_sid": sm._seed_sid(tid, seed, app), "rev": sm.SEED_REV,
                    "sha256": digest(state), "bytes": len(canonical(state)),
                })
    return {"env": env_name(), "rev": sm.SEED_REV, "tasks": len(tasks),
            "cells": cells, "errors": errors}


# ------------------------------------------------------------------ diff -------
def _go(api: str, sid: str) -> dict:
    with urllib.request.urlopen(f"{api.rstrip('/')}/go?sid={sid}", timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def classify(cell: dict, api: str) -> dict:
    out = dict(cell)
    try:
        d = _go(api, cell["seed_sid"])
    except Exception as e:
        out["status"], out["note"] = "ERROR", repr(e)
        return out
    initial, current = d.get("initial_state"), d.get("current_state")
    if initial is None:
        out["status"] = "MISSING"
    elif digest(initial) != cell["sha256"]:
        out["status"] = "STALE"
    elif current is not None and digest(current) != cell["sha256"]:
        # baseline is right, but something has since written to the sid
        out["status"] = "DRIFTED"
    else:
        out["status"] = "OK"
    return out


def diff(cells: list[dict], apis: dict[str, str], workers: int = 8) -> list[dict]:
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda c: classify(c, apis[c["app"]]), cells))


# ----------------------------------------------------------------- apply -------
def _post(api: str, sid: str, body: dict) -> None:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/post?sid={sid}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()


def apply_cell(cell: dict, api: str, repair: bool) -> dict:
    out = dict(cell)
    status = cell.get("status")
    if status == "OK":
        out["action"] = "skip"
        return out
    if status in ("STALE", "DRIFTED") and not repair:
        out["action"] = "needs-repair"
        return out
    try:
        _, state = transformed_states(cell["task_id"], cell["seed"], [cell["app"]])[cell["app"]]
        if status in ("STALE", "DRIFTED"):
            # reset DELETES the row, which is what lets the following set
            # re-freeze initial_state; a plain set would keep the old baseline.
            _post(api, cell["seed_sid"], {"action": "reset"})
        _post(api, cell["seed_sid"], {"action": "set", "state": state})
        out["action"] = "repaired" if status in ("STALE", "DRIFTED") else "seeded"
    except Exception as e:
        out["action"], out["note"] = "ERROR", repr(e)
    return out


def apply(cells: list[dict], apis: dict[str, str], repair: bool, workers: int = 8) -> list[dict]:
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda c: apply_cell(c, apis[c["app"]], repair), cells))


# ------------------------------------------------------------------ cli --------
def _tasks_from(args) -> list[str]:
    if args.tasks_file:
        wanted = [w for w in (l.split("#", 1)[0].strip()
                              for l in pathlib.Path(args.tasks_file).read_text().splitlines()) if w]
        out, missing = [], []
        for w in wanted:
            hit = w if w in TASKS else next((t for t in TASKS if t.split("/")[0] == w), None)
            (out.append(hit) if hit else missing.append(w))
        if missing:
            print(f"!! unknown tasks: {missing}", file=sys.stderr)
        return out
    tasks = list(TASKS)
    return tasks[:args.limit] if args.limit else tasks


def _summarize(rows: list[dict], key: str) -> dict:
    c: dict = {}
    for r in rows:
        c[r.get(key)] = c.get(r.get(key), 0) + 1
    return c


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    m = ap.add_mutually_exclusive_group(required=True)
    for f in ("plan", "diff", "apply", "verify"):
        m.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--tasks-file")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--repair", action="store_true", help="with --apply: reset+set STALE/DRIFTED")
    ap.add_argument("--mock-map", default=None, help="default: the live hub (CUA_ENV)")
    args = ap.parse_args(argv)

    apis = sm.parse_mock_map(args.mock_map)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    if args.plan:
        man = plan(_tasks_from(args), seeds)
        MANIFEST.write_text(json.dumps(man, indent=1))
        print(f"planned {len(man['cells'])} cells over {man['tasks']} tasks -> {MANIFEST}")
        if man["errors"]:
            print(f"!! {len(man['errors'])} build errors", file=sys.stderr)
            return 1
        return 0

    if not MANIFEST.exists():
        print("no manifest — run --plan first", file=sys.stderr)
        return 2
    cells = json.loads(MANIFEST.read_text())["cells"]

    if args.diff or args.verify:
        rows = diff(cells, apis)
        counts = _summarize(rows, "status")
        for r in rows:
            if r["status"] != "OK":
                print(f"  {r['status']:8s} {r['task_id']:46s} {r['app']:9s} {r.get('note','')}")
        print(f"{counts}  ({len(rows)} cells)")
        if args.verify:
            ok = counts.get("OK", 0) == len(rows)
            print("VERIFY: PASS" if ok else "VERIFY: FAIL")
            return 0 if ok else 1
        return 0

    rows = apply(diff(cells, apis), apis, args.repair)
    print(f"{_summarize(rows, 'action')}  ({len(rows)} cells)")
    for r in rows:
        if r.get("action") in ("ERROR", "needs-repair"):
            print(f"  {r['action']:12s} {r['task_id']:46s} {r['app']:9s} {r.get('note','')}")
    return 1 if any(r.get("action") == "ERROR" for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
