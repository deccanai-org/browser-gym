#!/usr/bin/env python3
"""Step 3 — normalize final-state snapshots from traj evidence when present.

Full WorldState at episode end is rarely logged; we persist:
  - traj final_snapshot (compact harness snapshot)
  - verifier_result
  - historical disposition
During Step 4 replay we overwrite/augment with a full /_harness/world dump.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CHECKPOINT_DIR,
    INVENTORY_DIR,
    assert_sellable_untouched,
    disposition_from_verifier,
    load_task_ids,
    snapshot_paths,
    source_commit_meta,
    write_json,
    write_json_pretty,
)


def main() -> None:
    assert_sellable_untouched()
    meta = source_commit_meta()
    index = json.loads((INVENTORY_DIR / "best_traj_index.json").read_text())
    task_ids = load_task_ids()

    written = 0
    skipped_no_traj = 0
    skipped_no_final = 0
    for tid in task_ids:
        for seed in (0, 1, 2):
            key = f"{tid}|{seed}"
            info = index.get(key) or {}
            best = info.get("best")
            paths = snapshot_paths(tid, seed)
            if paths["final"].exists():
                # Keep existing if already has replay-captured full state
                existing = json.loads(paths["final"].read_text())
                if existing.get("capture_source") == "replay_harness":
                    continue
            if not best or best.get("corrupt"):
                skipped_no_traj += 1
                continue
            # Load traj for verifier + final snapshot
            try:
                traj = json.loads(Path(best["path"]).read_text())
            except Exception:
                skipped_no_traj += 1
                continue
            vr = traj.get("verifier_result")
            final_snap = traj.get("final_snapshot")
            if not vr and not final_snap:
                skipped_no_final += 1
                continue
            payload = {
                "schema_version": 1,
                "snapshot_kind": "final",
                "capture_source": "trajectory_log",
                "task_id": tid,
                "seed": seed,
                "source_commit": meta["source_commit"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "traj_path": best["path"],
                "agent_name": traj.get("agent_name"),
                "historical_disposition": disposition_from_verifier(vr),
                "verifier_result": vr,
                "final_snapshot_compact": final_snap,
                "final_url": traj.get("final_url"),
                "note": (
                    "Compact harness snapshot + verifier only; full WorldState "
                    "captured during replay when replayable."
                ),
            }
            write_json(paths["final"], payload)
            written += 1

    summary = {
        "written_from_traj": written,
        "skipped_no_traj": skipped_no_traj,
        "skipped_no_final": skipped_no_final,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json_pretty(CHECKPOINT_DIR / "final_from_traj.json", summary)
    print(json.dumps(summary, indent=2))
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
