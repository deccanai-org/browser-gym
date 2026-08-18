#!/usr/bin/env python3
"""Generate Cloud Run Jobs manifests for Tencent Luna filtration.

Modes:
  smoke          — 5 tasks × 5 seeds (Luna)
  phase1         — locked OK-63 × 5 seeds (Luna)
  phase2_sample20 — 20 of 47 Phase 2 candidates × 5 seeds (Sol or Opus)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TASKS = HERE / "manifests" / "ok63_tasks.txt"
PHASE2_SAMPLE20_TASKS = HERE / "manifests" / "phase2_sample20_tasks.txt"
SMOKE_TASKS = [
    "M75/stale_gift_message",
    "M39/phantom_replacement",
    "M80/ambiguous_calendar_reschedule",
    "M142/no_monitor_in_stock_high_rating",
    "M41/ambiguous_return",
]
DEFAULT_SEEDS = [0, 1, 2, 3, 4]
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_AGENT = "openai_pixel"

# Phase 2 model presets (agent + model). Rates documented in cost projection.
PHASE2_PRESETS = {
    "sol": {"model": "gpt-5.6-sol", "agent": "openai_pixel"},
    "opus": {"model": "claude-opus-5", "agent": "pixel"},
    # Proven fallback at same Anthropic $/MTok as Opus 5:
    "opus48": {"model": "claude-opus-4-8", "agent": "pixel"},
}


def load_tasks(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def build_entries(
    tasks: list[str],
    seeds: list[int],
    model: str,
    agent: str,
) -> list[dict]:
    entries: list[dict] = []
    idx = 0
    for task_id in tasks:
        for seed in seeds:
            entries.append(
                {
                    "index": idx,
                    "task_id": task_id,
                    "seed": seed,
                    "model": model,
                    "agent": agent,
                }
            )
            idx += 1
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--mode",
        choices=("phase1", "smoke", "phase2_sample20"),
        default="phase1",
        help="phase1=OK-63×5; smoke=5×5; phase2_sample20=20×5 (use --preset)",
    )
    ap.add_argument("--tasks-file", type=Path, default=None)
    ap.add_argument("--seeds", default="0,1,2,3,4")
    ap.add_argument("--model", default=None, help="Override model id")
    ap.add_argument("--agent", default=None, help="Override agent kind")
    ap.add_argument(
        "--preset",
        choices=tuple(PHASE2_PRESETS),
        default=None,
        help="phase2_sample20: sol | opus (claude-opus-5) | opus48",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default under manifests/)",
    )
    args = ap.parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    model = args.model
    agent = args.agent
    if args.preset:
        preset = PHASE2_PRESETS[args.preset]
        model = model or preset["model"]
        agent = agent or preset["agent"]
    model = model or DEFAULT_MODEL
    agent = agent or DEFAULT_AGENT

    if args.mode == "smoke":
        tasks = list(SMOKE_TASKS)
        out = args.out or (HERE / "manifests" / "smoke_5x5_luna.json")
    elif args.mode == "phase2_sample20":
        tasks_path = args.tasks_file or PHASE2_SAMPLE20_TASKS
        tasks = load_tasks(tasks_path)
        if len(tasks) != 20:
            raise SystemExit(f"expected 20 Phase 2 sample tasks, got {len(tasks)} from {tasks_path}")
        tag = args.preset or "custom"
        out = args.out or (HERE / "manifests" / f"phase2_sample20_{tag}_100.json")
    else:
        tasks_path = args.tasks_file or DEFAULT_TASKS
        tasks = load_tasks(tasks_path)
        out = args.out or (HERE / "manifests" / "phase1_luna_315.json")
        if len(tasks) != 63:
            raise SystemExit(f"expected 63 OK tasks, got {len(tasks)} from {tasks_path}")

    entries = build_entries(tasks, seeds, model, agent)
    expected = len(tasks) * len(seeds)
    if len(entries) != expected:
        raise SystemExit(f"entry count {len(entries)} != {expected}")

    payload = {
        "mode": args.mode,
        "model": model,
        "agent": agent,
        "preset": args.preset,
        "n_tasks": len(tasks),
        "n_seeds": len(seeds),
        "n_episodes": len(entries),
        "tasks": tasks,
        "entries": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out} ({len(entries)} episodes, {len(tasks)} tasks × {len(seeds)} seeds, {agent}[{model}])")


if __name__ == "__main__":
    main()
