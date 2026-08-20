#!/usr/bin/env python3
"""Re-score recorded episodes against the current verifiers, without re-running.

Every recorded episode carries the world it ended in (``world_after`` on its
last step), so a fixed verifier can be replayed over that final state. The
agent does not run again; only the scoring does.

    python tools/rescore_offline.py <trajectory-root> [--task FB5] [--json out.json]

Fidelity note: pass --check to re-score with the *recorded* milestone set and
confirm the tool reproduces the stored score before trusting any new number.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.tasks import make_task                      # noqa: E402
from server.apps import statecodec                      # noqa: E402
from server.verifiers import Probe                      # noqa: E402
from server import verifier_four as v4                  # noqa: E402


def final_world_snapshot(episode: dict) -> dict | None:
    """The world the episode ended in — the last step that recorded one."""
    for step in reversed(episode.get("steps") or []):
        if step.get("world_after"):
            return step["world_after"]
    return episode.get("final_snapshot") or None


def rescore(episode: dict) -> dict | None:
    task_id = episode.get("task_id")
    factories = v4.suite_factories()
    if task_id not in factories:
        return None                       # no runnable verifier for this task
    snap = final_world_snapshot(episode)
    if not snap:
        return None                       # nothing to score against
    seed = episode.get("seed") or 0

    final = make_task(task_id, seed)
    statecodec.apply_snapshot(final, snap)
    baseline = make_task(task_id, seed)   # pristine, so "new" means new

    probe = Probe(state=final.shop, url="/", initial_state=baseline.shop,
                  world=final, initial_world=baseline, active_tab_url="/")
    result = factories[task_id]().evaluate(probe, current_step=1)
    old = (episode.get("verifier_result") or {}).get("score")
    return {
        "episode_id": episode.get("episode_id"),
        "task_id": task_id,
        "seed": seed,
        "old_score": old,
        "new_score": result["score"],
        "new_pre_veto": result["score_pre_veto"],
        "vetoed": result["vetoed"],
        "success": result["success"],
        "fired": [m["name"] for m in result["all_milestones"]
                  if m["fired_at_step"] >= 0],
        "missed": result["missed_milestones"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="directory containing gym_episode.jsonl files")
    ap.add_argument("--task", default="", help="substring filter on task id")
    ap.add_argument("--json", default="", help="write full results here")
    args = ap.parse_args()

    rows, skipped = [], []
    for path in sorted(glob.glob(os.path.join(args.root, "**", "gym_episode.jsonl"),
                                 recursive=True)):
        with open(path) as fh:
            line = fh.readline()
        if not line.strip():
            continue
        episode = json.loads(line)
        if args.task and args.task not in (episode.get("task_id") or ""):
            continue
        row = rescore(episode)
        if row is None:
            skipped.append(episode.get("task_id"))
            continue
        rows.append(row)

    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)

    for task_id, rs in sorted(by_task.items()):
        print(f"\n{task_id}")
        print(f"  {'episode':10} {'old':>7} {'new':>7} {'pre-veto':>9}  changed")
        for r in rs:
            changed = "" if r["old_score"] == r["new_score"] else "  <-- CHANGED"
            print(f"  {str(r['episode_id']):10} {r['old_score']!s:>7} "
                  f"{r['new_score']!s:>7} {r['new_pre_veto']!s:>9}{changed}")
        sol = [r for r in rs if r["new_score"] is not None]
        if sol:
            passes = sum(1 for r in sol if r["new_score"] >= 1.0)
            mean = sum(r["new_score"] for r in sol) / len(sol)
            print(f"  -> {len(sol)} runs · mean {mean:.4f} · full solves {passes}")

    if skipped:
        uniq = sorted({s for s in skipped if s})
        print(f"\nskipped (no runnable verifier or no world snapshot): {len(skipped)}")
        for s in uniq:
            print(f"  - {s}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
