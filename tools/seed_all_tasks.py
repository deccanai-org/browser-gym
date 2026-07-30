"""Seed EVERY gym task's canonical state into the running mocks (the frozen base).

Run once at deploy: for each task (and seed) it writes the transformed per-app state
under a stable seed_sid (`seed-{task}-{seed}-{app}`) via the mocks' state API. The
annotator then clones these seed_sids into per-attempt sessions (session_manager).

  HUB mocks must be running.  mock-map = "shop=URL,mail=URL,market=URL,calendar=URL,food=URL"

Usage:
  python -m tools.seed_all_tasks --mock-map "$MM"                 # all 312 tasks, seed 0
  python -m tools.seed_all_tasks --mock-map "$MM" --seeds 0,42    # multiple seeds
  python -m tools.seed_all_tasks --mock-map "$MM" --limit 5       # a sample (smoke test)
"""

from __future__ import annotations

import argparse
import sys

from server.tasks import TASKS
from tools import session_manager as sm


def seed_all(mock_map: dict[str, str], seeds: list[int], limit: int | None = None) -> tuple[int, int]:
    tasks = list(TASKS)
    if limit:
        tasks = tasks[:limit]
    cells = 0
    for i, tid in enumerate(tasks):
        for seed in seeds:
            try:
                sm.seed_task(tid, seed, mock_map)
                cells += 1
            except Exception as e:  # a bad mock/URL shouldn't abort the whole batch
                print(f"  !! {tid} seed {seed}: {e!r}", file=sys.stderr)
        if (i + 1) % 25 == 0:
            print(f"  ...{i + 1}/{len(tasks)} tasks")
    return cells, len(tasks)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mock-map", required=True, help="shop=URL,mail=URL,market=URL,calendar=URL,food=URL")
    ap.add_argument("--seeds", default="0", help="comma-separated seeds (default 0)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N tasks (smoke test)")
    args = ap.parse_args(argv)

    mm = sm.parse_mock_map(args.mock_map)
    seeds = [int(s) for s in args.seeds.split(",") if s.strip() != ""]
    cells, ntasks = seed_all(mm, seeds, args.limit)
    print(f"seeded {cells} cells ({ntasks} tasks x {len(seeds)} seed(s)) into {len(mm)} mocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
