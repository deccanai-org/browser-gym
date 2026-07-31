"""Seed cua-gym directly over psql, bypassing the hub's HTTP API.

Same result as `seed_all_tasks --apply`, minus the dependency on the hub being
reachable — which matters, because the hub is a name in a sub-zone that has
disappeared from public DNS at least once while the database itself stayed up.

It writes exactly what the API's PostgresStateStore writes (see
backend/app/storage.py): an upsert into mock_states plus an append to
mock_state_events. Two deliberate differences, both in our favour for a re-seed:

  * initial_state is set together with state. The API's `set` only freezes
    initial_state when it is NULL, so a changed projection needs a delete first;
    here the row is written atomically and there is no window where a browser
    could load the sid and freeze the mock's own defaults as the baseline.
  * one transaction for the whole run, so a failure leaves nothing half-applied.

Usage:
  python -m tools.seed_via_psql                       # all 312 tasks, seed 0
  python -m tools.seed_via_psql --tasks-file tools/twenty_tasks.txt
  python -m tools.seed_via_psql --dry-run             # write the SQL, don't run it
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import subprocess
import sys
import tempfile

from server.tasks import TASKS
from tools.cua_env import seed_sid
from tools.seed_to_cuagym import transformed_states

PGHOST = "10.0.141.72"
PGUSER = "postgres"
PGDB = "cua-gym"


def rows(tasks: list[str], seed: int = 0):
    """(mock, sid, task_id, state_json) per app, for every task."""
    for tid in tasks:
        for app, (mock, state) in transformed_states(tid, seed).items():
            yield mock, seed_sid(tid, seed, app), tid, json.dumps(
                state, sort_keys=True, separators=(",", ":"))


SQL = """
\\set ON_ERROR_STOP on
BEGIN;
CREATE TEMP TABLE _seed(mock text, sid uuid, task text, state jsonb) ON COMMIT DROP;
\\copy _seed FROM '{csv}' WITH (FORMAT csv)

-- current AND baseline together: a re-seed must move the frozen initial_state
-- too, or every diff-based check keeps comparing against the old projection.
INSERT INTO mock_states (mock, sid, state, initial_state)
SELECT mock, sid, state, state FROM _seed
ON CONFLICT (mock, sid) DO UPDATE
   SET state = EXCLUDED.state,
       initial_state = EXCLUDED.initial_state,
       updated_at = now();

-- the hub appends an event for every write; keep the trail honest.
INSERT INTO mock_state_events (mock, sid, action, state)
SELECT mock, sid, 'set', state FROM _seed;

SELECT count(*) AS seeded FROM _seed;
COMMIT;
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks-file")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.tasks_file:
        wanted = [w for w in (l.split("#", 1)[0].strip()
                              for l in pathlib.Path(args.tasks_file).read_text().splitlines()) if w]
        tasks = [t for w in wanted
                 for t in [w if w in TASKS else next((x for x in TASKS if x.split("/")[0] == w), None)] if t]
    else:
        tasks = list(TASKS)

    tmp = pathlib.Path(tempfile.mkdtemp()) / "seed.csv"
    n = 0
    with tmp.open("w", newline="") as fh:
        w = csv.writer(fh)
        for r in rows(tasks, args.seed):
            w.writerow(r)
            n += 1
    print(f"built {n} cells over {len(tasks)} tasks -> {tmp} ({tmp.stat().st_size / 1e6:.1f} MB)")

    sql = SQL.format(csv=tmp)
    if args.dry_run:
        out = tmp.with_suffix(".sql")
        out.write_text(sql)
        print(f"dry run — SQL at {out}")
        return 0

    p = subprocess.run(["psql", "-h", PGHOST, "-U", PGUSER, "-d", PGDB, "-q", "-v", "ON_ERROR_STOP=1"],
                       input=sql, capture_output=True, text=True)
    print((p.stdout or "").strip() or (p.stderr or "").strip())
    if p.returncode:
        print(f"!! psql exited {p.returncode}", file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())
