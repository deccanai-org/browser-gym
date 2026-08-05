"""Export the task catalog the annotation platform seeds from.

The annotator needs a prompt, a title and a landing route for every task before
an annotator can pick one — and it needs them WITHOUT a running gym. Seeding the
catalog from a live `GET /_harness/tasks` (what it used to do) means a gym outage
silently produces an empty queue, and it still leaves `prompt` blank because that
endpoint only returns ids.

Everything here is derived offline:

  prompt / category / difficulty   server.seeddb.runtime.seed_source(tid, 0)
  start_path, per-app seed SIDs    tools/cua_task_sid_map.json
  primary_app, per-app routes      harness.runner (the gym's OWN mappers)

Deriving the routes here rather than in the annotator is deliberate: `_mock_start_path`
knows which gym deep-links have a safe equivalent in the realistic mocks and which
must fall back to the app root, and a second implementation of that over there
would drift.

The seed SIDs are recomputed with `tools.cua_env.seed_sid` and ASSERTED equal to
the map, so a SEED_REV bump can never ship a catalog that points at a sid family
nobody seeded.

    python -m tools.export_cua_catalog [-o tools/cua_task_catalog.json]

Bridged sessions do not consult the SIDs (the bridge baselines its own worlds from
a real gym reset), but they are carried so a plain-clone deployment works too.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from harness.runner import _mock_start_path, _seg_to_app
from server.apps.world import WorldState
from server.seeddb.runtime import seed_source
from server.tasks import TASKS
from tools.cua_env import SEED_REV, seed_sid
from tools.seed_to_cuagym import APP_TO_MOCK

HERE = pathlib.Path(__file__).resolve().parent
SID_MAP = HERE / "cua_task_sid_map.json"
DEFAULT_OUT = HERE / "cua_task_catalog.json"


def _brief(task_id: str) -> tuple[str, str, str]:
    """(prompt, category, difficulty) for a task, from its seed world.

    Goes through `seed_source` rather than `TASKS[tid](0)`: 298 of the 312 are
    category-M factories that return a WorldState (the whole 5-app world), not a
    bare shop GymState, and calling the factory directly fails for those.
    """
    base = seed_source(task_id, 0)
    shop = base.shop if isinstance(base, WorldState) else base
    return (
        (getattr(shop, "task_brief", "") or "").strip(),
        getattr(shop, "task_category", "") or "",
        getattr(shop, "task_difficulty", "") or "",
    )


def build() -> dict:
    if not SID_MAP.exists():
        sys.exit(f"!! {SID_MAP} missing — run tools/seed_all_tasks.py --plan first")
    sid_map = json.loads(SID_MAP.read_text())
    rows_by_id = {t["task_id"]: t for t in sid_map["tasks"]}

    tasks, drifted, missing = [], [], []
    for task_id in TASKS:
        row = rows_by_id.get(task_id)
        if row is None:
            missing.append(task_id)
            continue
        prompt, category, difficulty = _brief(task_id)
        gym_start = row.get("start_path") or ""
        primary = _seg_to_app(gym_start)

        apps = {}
        for app, mock in APP_TO_MOCK.items():
            got = seed_sid(task_id, 0, app)
            want = ((row.get("apps") or {}).get(app) or {}).get("sid")
            if want and got != want:
                drifted.append(f"{task_id}/{app}: computed {got} != map {want}")
            apps[app] = {
                "mock": mock,
                "sid": want or got,
                "sha256": ((row.get("apps") or {}).get(app) or {}).get("sha256", ""),
                # Where THIS app lands. Only the primary app honours the task's
                # deep-link; the others open at their own root.
                "start_path": (_mock_start_path(app, gym_start) or "/") if app == primary else "/",
            }

        tasks.append({
            "task_id": task_id,
            "prompt": prompt,
            "category": category,
            "difficulty": difficulty,
            "start_path": gym_start,
            "primary_app": primary,
            "in_85": bool(row.get("in_85")),
            "apps": apps,
        })

    if drifted:
        print(f"!! {len(drifted)} seed-SID mismatches — the map and cua_env disagree:", file=sys.stderr)
        for d in drifted[:10]:
            print(f"     {d}", file=sys.stderr)
        sys.exit("refusing to write a catalog that points at unseeded sids")
    if missing:
        print(f"note: {len(missing)} gym task(s) absent from the sid map "
              f"(e.g. {missing[:3]}) — they will not be annotatable", file=sys.stderr)

    return {
        "rev": sid_map.get("rev", 1),
        "seed_rev": SEED_REV,
        "seed": 0,
        "today": sid_map.get("today", ""),
        "app_to_mock": APP_TO_MOCK,
        "tasks": tasks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    cat = build()
    out = pathlib.Path(args.out)
    out.write_text(json.dumps(cat, indent=1, sort_keys=False))
    empty = [t["task_id"] for t in cat["tasks"] if not t["prompt"]]
    by_app: dict[str, int] = {}
    for t in cat["tasks"]:
        by_app[t["primary_app"]] = by_app.get(t["primary_app"], 0) + 1
    print(f"wrote {out}  ({len(cat['tasks'])} tasks, {out.stat().st_size // 1024}KB)")
    print(f"  primary app: {by_app}")
    print(f"  in_85: {sum(1 for t in cat['tasks'] if t['in_85'])}   empty prompts: {len(empty)}")
    if empty:
        print(f"  !! empty prompts: {empty[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
