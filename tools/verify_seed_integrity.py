"""Is the seed data actually correct — not just present?

`seed_all_tasks --verify` proves the bytes on the hub match the manifest. That
says nothing about whether the bytes are *right*. This checks the content:

  ids       every literal id a task's verifier names (p_…, pay_…, ORD-…, cal_…)
            exists somewhere in that task's seeded projection. A verifier that
            keys on an id the seed never had can never fire.
  structure catalogs non-empty, a user with at least one address and one payment
            method, every order carrying the card it was charged to, the calendar
            clock frozen to the gym's TODAY, and the engagement signals
            (recentlyViewed / wishlist) still empty so nothing looks pre-visited.
  meta      every app state carries _gym_meta naming its own task.

Writes tools/cua_task_sid_map.json: task -> per-app (mock, seed_sid, sha256),
which is both the deploy manifest and what `--db` checks the live rows against.

Usage:
  python -m tools.verify_seed_integrity            # local projections only
  python -m tools.verify_seed_integrity --db       # also diff against cua-gym
  python -m tools.verify_seed_integrity --tasks-file tools/twenty_tasks.txt
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import pathlib
import re
import subprocess
import sys

import server.verifiers as V
from server.apps.calendar.state import TODAY
from server.main import START_PATHS, TASKS
from tools.cua_env import APP_TO_MOCK, SEED_REV, hub_key, seed_sid
from tools.seed_to_cuagym import transformed_states

MAP = pathlib.Path(__file__).resolve().parent / "cua_task_sid_map.json"
BREAKERS = pathlib.Path(__file__).resolve().parent.parent / "trajectories" / "sellable_breakers_v2.csv"

# The id prefixes task authors actually use. Anything matching one of these
# inside a suite's source is a literal the seed has to provide.
ID_RE = re.compile(r"[\"']((?:p_|pay_|addr_|ORD-|ORD_|cal_|ev_|sub_|SUB-|d_|r_|em_|ret_)[A-Za-z0-9_\-]+)[\"']")

# Literals a verifier names on purpose without the seed providing them, because
# the lookup is guarded and falls back to a property that IS seeded. Listed
# one-by-one with the fallback, so a genuinely dangling id still gets reported.
GUARDED_IDS = {
    ("M122/flight_delay_dinner_reschedule", "em_delay"):
        "id is auto-generated; falls back to matching sender alerts@gymair.com",
}


def canonical(state: dict) -> str:
    return json.dumps(state, sort_keys=True, separators=(",", ":"))


def check_task(task_id: str) -> tuple[dict, list[tuple[str, str, str]]]:
    problems: list[tuple[str, str, str]] = []
    states = transformed_states(task_id, 0)
    rec = {"task_id": task_id, "start_path": START_PATHS.get(task_id, "/"), "apps": {}}

    for app, (mock, st) in states.items():
        blob = canonical(st)
        rec["apps"][app] = {"mock": mock, "sid": seed_sid(task_id, 0, app),
                            "sha256": hashlib.sha256(blob.encode()).hexdigest()}
        if (st.get("_gym_meta") or {}).get("task_id") != task_id:
            problems.append((task_id, app, "missing/incorrect _gym_meta"))
        # A gym seed's images must be self-contained: local /assets or inline
        # data: URIs, never a placeholder-image CDN (picsum is non-deterministic
        # and breaks offline). Everything renders from a real, stable asset.
        # Match the CDN *hosts* (with a dot), not bare words — "placeholder"
        # and "unsplash" appear legitimately in email body prose.
        for cdn in ("picsum.photos", "placekitten.com", "placehold.co", "placehold.it",
                    "placeholder.com", "loremflickr.com", "source.unsplash.com",
                    "via.placeholder.com", "dummyimage.com"):
            if cdn in blob:
                problems.append((task_id, app, f"{blob.count(cdn)} {cdn} image URL(s) — no placeholder CDNs allowed"))
        if app == "shop":
            if not st.get("products"):
                problems.append((task_id, app, "empty catalog"))
            user = st.get("user") or {}
            if not user.get("addresses"):
                problems.append((task_id, app, "user has no addresses"))
            if not user.get("paymentMethods"):
                problems.append((task_id, app, "user has no payment methods"))
            for o in st.get("orders") or []:
                if not (o.get("paymentMethod") or {}).get("id"):
                    problems.append((task_id, app, f"order {o.get('id')} lost its payment id"))
            if st.get("recentlyViewed") or st.get("wishlist"):
                problems.append((task_id, app, "engagement signal pre-filled"))
        elif app == "mail" and not st.get("emails"):
            problems.append((task_id, app, "no emails"))
        elif app == "calendar" and not str(st.get("currentDate", "")).startswith(TODAY):
            problems.append((task_id, app, f"clock not frozen ({st.get('currentDate')})"))
        elif app == "food" and not st.get("restaurants"):
            problems.append((task_id, app, "no restaurants"))

    factory = V.SUITE_FACTORIES.get(task_id)
    if factory is not None:
        try:
            ids = set(ID_RE.findall(inspect.getsource(factory)))
        except OSError:
            ids = set()
        blob = json.dumps({a: s for a, (_m, s) in states.items()})
        for i in sorted(ids):
            if i not in blob and (task_id, i) not in GUARDED_IDS:
                problems.append((task_id, "verifier", f"references {i}, absent from the seed"))
    return rec, problems


def db_check(rows: list[dict]) -> int:
    """Diff the live cua-gym rows against the map. Needs ~/.pgpass."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
        for r in rows:
            for a in r["apps"].values():
                fh.write(f"{a['mock']},{a['sid']},{r['task_id']}\n")
        path = fh.name
    sql = f"""
CREATE TEMP TABLE exp(mock text, sid uuid, task text);
\\copy exp FROM '{path}' WITH (FORMAT csv)
\\pset tuples_only on
\\pset format unaligned
\\pset fieldsep ' | '
SELECT 'expected', count(*) FROM exp
UNION ALL SELECT 'present', count(*) FROM exp e JOIN mock_states s USING (mock,sid)
UNION ALL SELECT 'MISSING', count(*) FROM exp e LEFT JOIN mock_states s USING (mock,sid) WHERE s.sid IS NULL
UNION ALL SELECT 'task mismatch', count(*) FROM exp e JOIN mock_states s USING (mock,sid)
     WHERE s.state->'_gym_meta'->>'task_id' IS DISTINCT FROM e.task
UNION ALL SELECT 'baseline drifted', count(*) FROM exp e JOIN mock_states s USING (mock,sid)
     WHERE s.initial_state IS DISTINCT FROM s.state;
"""
    p = subprocess.run(["psql", "-h", "10.0.141.72", "-U", "postgres", "-d", "cua-gym", "-q"],
                       input=sql, capture_output=True, text=True)
    print(p.stdout.strip() or p.stderr.strip())
    bad = [l for l in p.stdout.splitlines()
           if l.startswith(("MISSING", "task mismatch", "baseline drifted")) and not l.rstrip().endswith("| 0")]
    return 1 if (bad or p.returncode) else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tasks-file")
    ap.add_argument("--db", action="store_true", help="also diff against the live cua-gym rows")
    args = ap.parse_args(argv)

    if args.tasks_file:
        wanted = [w for w in (l.split("#", 1)[0].strip()
                              for l in pathlib.Path(args.tasks_file).read_text().splitlines()) if w]
        tasks = [t for w in wanted
                 for t in [w if w in TASKS else next((x for x in TASKS if x.split("/")[0] == w), None)] if t]
    else:
        tasks = list(TASKS)

    breakers = ({r["task_id"] for r in csv.DictReader(BREAKERS.open())}
                if BREAKERS.exists() else set())

    rows, problems = [], []
    for t in tasks:
        try:
            rec, probs = check_task(t)
        except Exception as e:
            problems.append((t, "build", repr(e)[:80]))
            continue
        rec["in_85"] = t in breakers
        rows.append(rec)
        problems.extend(probs)

    cells = sum(len(r["apps"]) for r in rows)
    print(f"tasks {len(rows)}  cells {cells}  in-85 {sum(1 for r in rows if r['in_85'])}")
    print(f"content problems: {len(problems)}")
    for t, app, msg in problems[:25]:
        print(f"   {t:52s} {app:9s} {msg}")

    MAP.write_text(json.dumps(
        {"rev": SEED_REV, "today": TODAY, "app_to_mock": {a: hub_key(m) for a, m in APP_TO_MOCK.items()}, "tasks": rows}, indent=1))
    print(f"wrote {MAP.name}")

    rc = 1 if problems else 0
    if args.db:
        rc |= db_check(rows)
    return rc


if __name__ == "__main__":
    sys.exit(main())
