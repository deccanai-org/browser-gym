#!/usr/bin/env python3
"""Run the exploratory S1 UI-only oracle (not a sellable).

Requires a live gym server. Example:

  .venv/bin/uvicorn server.main:app --port 8765 &
  .venv/bin/python scripts/run_sheets_s1_oracle.py --server http://127.0.0.1:8765 --seeds 0,1,2

Writes trajectories under trajectories/exploratory_s1_oracle/ and prints a
scorecard. Expects score 1.00 on each seed when the scaffold + hook are healthy.

Does NOT register in server/tasks.py; uses the exploratory reset hook.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.run import _parse_seeds, _run_one  # noqa: E402
from harness.auth import ensure_harness_token  # noqa: E402

TASK_ID = "exploratory/S1_active_tab_sum_gate"
OUT = ROOT / "trajectories" / "exploratory_s1_oracle"


async def main() -> int:
    ensure_harness_token()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", default="http://127.0.0.1:8765")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    seeds = _parse_seeds(args.seeds)
    OUT.mkdir(parents=True, exist_ok=True)
    screens = OUT / "screenshots"
    screens.mkdir(parents=True, exist_ok=True)

    rows = []
    for seed in seeds:
        print(f"=== oracle {TASK_ID} seed={seed} ===", flush=True)
        traj = await _run_one(
            agent_kind="oracle",
            task_id=TASK_ID,
            seed=seed,
            server_url=args.server.rstrip("/"),
            headless=not args.headed,
            record_video=False,
            out_traj_dir=OUT,
            out_screens_dir=screens,
            llm_model=None,
        )
        score = float((traj.verifier_result or {}).get("score") or 0.0)
        success = bool((traj.verifier_result or {}).get("success"))
        print(
            f"seed={seed} success={success} score={score:.2f} "
            f"error={traj.error!r}",
            flush=True,
        )
        rows.append({
            "seed": seed,
            "success": success,
            "score": score,
            "error": traj.error,
            "episode_id": traj.episode_id,
        })

    card = {
        "task_id": TASK_ID,
        "agent": "oracle",
        "ui_only": True,
        "seeds": rows,
        "all_1_00": all(
            r["success"] and abs(r["score"] - 1.0) < 1e-9 for r in rows
        ),
    }
    card_path = OUT / "scorecard.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps(card, indent=2), flush=True)
    print(f"scorecard: {card_path}", flush=True)
    return 0 if card["all_1_00"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
