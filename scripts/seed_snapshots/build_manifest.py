#!/usr/bin/env python3
"""Step 7 — build manifest.json + REPORT.md."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CHECKPOINT_DIR,
    CLEAN_ROOT,
    DIRTY_ROOT,
    INVENTORY_DIR,
    SEED_ROOT,
    SELLABLE_SHA256_BASELINE,
    assert_sellable_untouched,
    load_task_ids,
    sellable_sha256,
    snapshot_paths,
    source_commit_meta,
    write_json_pretty,
)


def _screening_date_hint(traj_path: str | None) -> str | None:
    if not traj_path:
        return None
    p = Path(traj_path)
    try:
        # Use finished_at from traj if present
        data = json.loads(p.read_text())
        ts = data.get("finished_at") or data.get("started_at")
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    except Exception:
        pass
    return None


def _possibly_drifted(task_id: str, screening_date: str | None) -> bool:
    """True if tasks.py / relevant state.py changed after screening date."""
    if not screening_date:
        return False
    paths = ["server/tasks.py", "server/state.py", "server/apps/world.py"]
    # Heuristic: also wave modules for high IDs
    try:
        num = int(task_id.split("/")[0][1:]) if task_id[0] == "M" else 0
    except Exception:
        num = 0
    if num >= 342:
        paths += [
            "server/thin_vein_wave.py",
            "server/phase_d_wave.py",
            "server/phase_d_batch2.py",
            "server/wave_structural_implicit.py",
            "server/final_implicit_wave.py",
        ]
    for p in paths:
        try:
            out = subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(CLEAN_ROOT),
                    "log",
                    "-1",
                    "--format=%ci",
                    "--",
                    p,
                ],
                text=True,
            ).strip()
            if not out:
                continue
            commit_day = out[:10]
            if commit_day > screening_date:
                return True
        except subprocess.CalledProcessError:
            continue
    return False


def main() -> None:
    assert_sellable_untouched()
    meta = source_commit_meta()
    index = json.loads((INVENTORY_DIR / "best_traj_index.json").read_text())
    inv_summary = json.loads((INVENTORY_DIR / "inventory_summary.json").read_text())

    entries = []
    counts = {
        "verified": 0,
        "spotcheck_pass": 0,
        "spotcheck_fail": 0,
        "inconclusive": 0,
        "no_evidence": 0,
        "replay_mismatch": 0,
        "replay_error": 0,
    }

    for tid in load_task_ids():
        for seed in (0, 1, 2):
            paths = snapshot_paths(tid, seed)
            key = f"{tid}|{seed}"
            info = index.get(key) or {}
            best = info.get("best")
            evidence_class = info.get("evidence_class")

            status = "no_evidence"
            replay_verified = None
            partial_spotcheck = None
            notes = []

            if paths["replay"].exists():
                rep = json.loads(paths["replay"].read_text())
                if "error" in rep:
                    status = "inconclusive"
                    counts["replay_error"] += 1
                    counts["inconclusive"] += 1
                    notes.append(f"replay_error:{rep.get('error','')[:120]}")
                elif rep.get("replay_verified") is True:
                    status = "verified"
                    replay_verified = True
                    counts["verified"] += 1
                else:
                    status = "replay_mismatch"
                    replay_verified = False
                    counts["replay_mismatch"] += 1
                    # Annotate mismatch polarity for the report
                    hs, rs = rep.get("historical_success"), rep.get("replay_success")
                    if (rep.get("n_action_errors") or 0) > 0:
                        notes.append("mismatch_class:action_errors")
                    elif hs is True and rs is False:
                        notes.append("mismatch_class:hist_ok_replay_fail")
                    elif hs is False and rs is True:
                        notes.append("mismatch_class:hist_fail_replay_ok")
                    else:
                        notes.append("mismatch_class:other")
                    notes.append(
                        f"scores hist={rep.get('historical_score')} "
                        f"replay={rep.get('replay_score')}"
                    )
            elif paths["spotcheck"].exists():
                sc = json.loads(paths["spotcheck"].read_text())
                partial_spotcheck = sc.get("partial_spotcheck")
                if partial_spotcheck == "match":
                    status = "spotcheck_pass"
                    counts["spotcheck_pass"] += 1
                elif partial_spotcheck == "mismatch":
                    status = "spotcheck_fail"
                    counts["spotcheck_fail"] += 1
                else:
                    status = "inconclusive"
                    counts["inconclusive"] += 1
            elif evidence_class == "no_evidence":
                status = "no_evidence"
                counts["no_evidence"] += 1
            else:
                status = "inconclusive"
                counts["inconclusive"] += 1

            screening = _screening_date_hint(best["path"] if best else None)
            drifted = _possibly_drifted(tid, screening)

            entries.append(
                {
                    "task_id": tid,
                    "seed": seed,
                    "status": status,
                    "evidence_class": evidence_class,
                    "paths": {
                        "initial": str(paths["initial"].relative_to(SEED_ROOT))
                        if paths["initial"].exists()
                        else None,
                        "final": str(paths["final"].relative_to(SEED_ROOT))
                        if paths["final"].exists()
                        else None,
                        "replay": str(paths["replay"].relative_to(SEED_ROOT))
                        if paths["replay"].exists()
                        else None,
                        "spotcheck": str(paths["spotcheck"].relative_to(SEED_ROOT))
                        if paths["spotcheck"].exists()
                        else None,
                    },
                    "source_commit": meta["source_commit"],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "replay_verified": replay_verified,
                    "partial_spotcheck": partial_spotcheck,
                    "possibly_drifted": drifted,
                    "screening_date_hint": screening,
                    "traj_path": best.get("path") if best else None,
                    "historical_disposition": (best or {}).get(
                        "historical_disposition"
                    ),
                    "notes": notes,
                }
            )

    manifest = {
        "schema_version": 1,
        "n_tasks": 312,
        "n_episodes": 936,
        "registry_source": str(CLEAN_ROOT),
        "registry_commit": meta["source_commit"],
        "factory_commit": meta,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sellable_csv_sha256": sellable_sha256(),
        "sellable_csv_untouched": sellable_sha256() == SELLABLE_SHA256_BASELINE,
        "counts": counts,
        "inventory_summary": inv_summary,
        "episodes": entries,
    }
    write_json_pretty(SEED_ROOT / "manifest.json", manifest)

    # Notable mismatches / drift
    mismatches = [e for e in entries if e["status"] == "replay_mismatch"]
    spot_fails = [e for e in entries if e["status"] == "spotcheck_fail"]
    drifted = [e for e in entries if e.get("possibly_drifted")]
    errors = [e for e in entries if e["status"] == "inconclusive" and e.get("notes")]

    report = f"""# Seed-state backfill report (312 × 3 = 936)

Generated: {manifest['generated_at']}  
Registry: clean `feat/multi-app` tip @ `{meta['source_commit']}`  
(`{CLEAN_ROOT}`) — **312 tasks**, no M384–M386 Sheets extras.

## Counts

| Status | N |
|--------|--:|
| verified (Step 4 match) | {counts['verified']} |
| spotcheck_pass | {counts['spotcheck_pass']} |
| spotcheck_fail | {counts['spotcheck_fail']} |
| replay_mismatch | {counts['replay_mismatch']} |
| inconclusive | {counts['inconclusive']} |
| no_evidence | {counts['no_evidence']} |
| replay_error (rolled into inconclusive) | {counts['replay_error']} |
| **Total** | **{sum(counts[k] for k in ['verified','spotcheck_pass','spotcheck_fail','replay_mismatch','inconclusive','no_evidence'])}** |

## Inventory (Step 1)

```json
{json.dumps(inv_summary, indent=2)}
```

## Methodology

1. **Registry** — Runtime `TASKS` imported from the sonnet-completions checkout
   (312 IDs). Dirty tree has 315 (adds M384–M386); those are excluded.
2. **Initial snapshots** — `make_task(task_id, seed)` → deep JSON serialize
   (datetimes→ISO, `Random` dropped, seed stored as int). Includes full
   catalog / mail / calendar / food / market when present.
3. **Final snapshots** — Prefer full `/_harness/world` dump captured during
   replay; else normalize traj `final_snapshot` + `verifier_result`.
4. **Replay** — Oracle-style selector actions (`click`/`fill`/`navigate`/…)
   replayed via Playwright against a clean uvicorn server. **No model calls.**
   Pixel/mark/`click_xy` trajs are **not** mechanically replayable (SoM marks
   are episode-ephemeral); those fall through to spot-check.
5. **Spot-check** — Programmatic compare of traj `initial_snapshot` compact
   fields vs factory initial. **No screenshot OCR** at this scale; PNG path
   presence may be noted. Limits documented in spotcheck artifacts.
6. **Seed branching** — Calendar `seed % 2`, M10 Alex email, A2 price jitter,
   and plain-int seed fields checked (see `_checkpoints/seed_branching.json`).
7. **Drift** — `possibly_drifted` if `server/tasks.py` / state modules have a
   git commit date after the traj screening timestamp.

## Sellable CSV

- Path: `trajectories/sellable_breakers_v2.csv` (read-only; never written)
- SHA256 baseline: `{SELLABLE_SHA256_BASELINE}`
- SHA256 now: `{manifest['sellable_csv_sha256']}`
- Untouched: **{manifest['sellable_csv_untouched']}**

## Notable mismatches / drift hotspots

### Replay mismatches ({len(mismatches)})
"""
    for e in mismatches[:40]:
        report += (
            f"- `{e['task_id']}` seed={e['seed']} "
            f"hist={e.get('historical_disposition')} traj=`{e.get('traj_path')}`\n"
        )
    if len(mismatches) > 40:
        report += f"- … +{len(mismatches)-40} more\n"

    report += f"\n### Spotcheck failures ({len(spot_fails)})\n"
    for e in spot_fails[:20]:
        report += f"- `{e['task_id']}` seed={e['seed']}\n"

    report += f"\n### Possibly drifted episodes ({len(drifted)})\n"
    # Aggregate by task
    by_task = {}
    for e in drifted:
        by_task.setdefault(e["task_id"], []).append(e["seed"])
    for tid, seeds in list(sorted(by_task.items()))[:40]:
        report += f"- `{tid}` seeds={seeds}\n"
    if len(by_task) > 40:
        report += f"- … +{len(by_task)-40} tasks\n"

    report += f"\n### Replay errors / inconclusive notes ({len(errors)})\n"
    for e in errors[:20]:
        report += f"- `{e['task_id']}` seed={e['seed']}: {e.get('notes')}\n"

    report += """
## Scripts

- `scripts/seed_snapshots/inventory.py`
- `scripts/seed_snapshots/generate_initial.py`
- `scripts/seed_snapshots/extract_finals.py`
- `scripts/seed_snapshots/replay_verify.py`
- `scripts/seed_snapshots/spotcheck.py`
- `scripts/seed_snapshots/seed_branching.py`
- `scripts/seed_snapshots/build_manifest.py`
- `scripts/seed_snapshots/run_all.py`

Re-run: `.venv/bin/python scripts/seed_snapshots/run_all.py`
"""

    (SEED_ROOT / "REPORT.md").write_text(report)
    # Also copy under docs/history/audits
    audit = (
        DIRTY_ROOT
        / "docs"
        / "history"
        / "audits"
        / "SEED_STATE_BACKFILL_312_2026-07-23.md"
    )
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(report)
    print(json.dumps(counts, indent=2))
    print("wrote", SEED_ROOT / "manifest.json")
    print("wrote", SEED_ROOT / "REPORT.md")
    print("wrote", audit)
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
