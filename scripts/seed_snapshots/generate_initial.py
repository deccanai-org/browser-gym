#!/usr/bin/env python3
"""Step 2 — backfill initial-state snapshots for all 312×3 episodes."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CHECKPOINT_DIR,
    CLEAN_ROOT,
    assert_sellable_untouched,
    deep_serialize,
    ensure_clean_on_path,
    load_task_ids,
    snapshot_paths,
    source_commit_meta,
    write_json,
    write_json_pretty,
)


def _one(args: tuple[str, int, dict]) -> dict:
    task_id, seed, meta = args
    ensure_clean_on_path()
    from server.tasks import make_task
    from server.apps.world import WorldState

    paths = snapshot_paths(task_id, seed)
    if paths["initial"].exists():
        return {"task_id": task_id, "seed": seed, "status": "skipped_exists"}

    state = make_task(task_id, seed)
    kind = "WorldState" if isinstance(state, WorldState) else "GymState"
    payload = {
        "schema_version": 1,
        "snapshot_kind": "initial",
        "task_id": task_id,
        "seed": seed,
        "state_type": kind,
        "source_commit": meta["source_commit"],
        "state_file_tips": meta.get("state_file_tips"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "factory_root": str(CLEAN_ROOT),
        "state": deep_serialize(state),
        # Compact verifier-facing view as well
        "to_json": deep_serialize(state.to_json()),
    }
    write_json(paths["initial"], payload)
    return {"task_id": task_id, "seed": seed, "status": "ok", "state_type": kind}


def main() -> None:
    assert_sellable_untouched()
    ensure_clean_on_path()
    meta = source_commit_meta()
    task_ids = load_task_ids()
    jobs = [(tid, s, meta) for tid in task_ids for s in (0, 1, 2)]
    print(f"[initial] generating {len(jobs)} snapshots…", flush=True)

    results = []
    # ProcessPool: each worker imports clean server
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_one, j): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                tid, seed, _ = futs[fut]
                results.append(
                    {"task_id": tid, "seed": seed, "status": "error", "error": str(e)}
                )
            if done % 100 == 0:
                print(f"  …{done}/{len(jobs)}", flush=True)

    ok = sum(1 for r in results if r["status"] in ("ok", "skipped_exists"))
    err = [r for r in results if r["status"] == "error"]
    summary = {
        "n_jobs": len(jobs),
        "ok_or_skipped": ok,
        "errors": len(err),
        "error_samples": err[:10],
        "source_commit": meta["source_commit"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_pretty(CHECKPOINT_DIR / "initial_generation.json", summary)
    print(json.dumps(summary, indent=2))
    if err:
        raise SystemExit(f"initial generation had {len(err)} errors")
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
