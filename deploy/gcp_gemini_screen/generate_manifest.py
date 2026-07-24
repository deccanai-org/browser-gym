#!/usr/bin/env python3
"""Generate the Gemini K=3 census manifest from live ``server.tasks.TASKS``.

Full registry: 315 tasks × seeds {0,1,2} = 945 entries (task_index 0..944).
Smoke: first 5 entries of that same ordering (--tasks=5 / smoke_manifest.json).
Pilot-20: diverse 20-task × K=3 = 60 entries across mechanism veins (--pilot-20).

Deterministic ordering: sorted(TASKS.keys()) then seed ascending (full/smoke).
Pilot-20 uses a fixed RNG seed for within-vein picks (see --pilot-seed).

Usage:
    .venv/bin/python deploy/gcp_gemini_screen/generate_manifest.py
    .venv/bin/python deploy/gcp_gemini_screen/generate_manifest.py --out-dir deploy/gcp_gemini_screen/manifests
    .venv/bin/python deploy/gcp_gemini_screen/generate_manifest.py --pilot-20
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEEDS = (0, 1, 2)
SMOKE_N = 5
PILOT_N = 20
# Prefer one task per vein first, then fill; order is sampling priority for coverage.
PILOT_VEIN_PRIORITY = (
    "sycophancy",
    "stacked-default",
    "content-default",
    "instrument-default",
    "infeasibility",
    "self-contradiction",
    "ask-dont-guess",
    "tool-affordance",
    "implicit-constraint",
    "structural",
    "injection",
    "source-anchoring",
)


def build_entries() -> list[dict]:
    from server.tasks import TASKS

    task_ids = sorted(TASKS.keys())
    entries: list[dict] = []
    idx = 0
    for task_id in task_ids:
        for seed in SEEDS:
            entries.append({
                "task_index": idx,
                "task_id": task_id,
                "seed": seed,
            })
            idx += 1
    return entries


def _load_sellable_ids() -> set[str]:
    """Read-only: sellable ledger for breaker/defended mix. Never written."""
    path = ROOT / "trajectories/sellable_breakers_v2.csv"
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8") as f:
        return {r["task_id"] for r in csv.DictReader(f) if r.get("task_id")}


def select_pilot_tasks(n: int = PILOT_N, rng_seed: int = 42) -> list[dict]:
    """Diverse n-task sample across canonical veins (deterministic).

    Strategy:
      1. Tag every TASKS id with ``canonical_vein``.
      2. Round-robin across PILOT_VEIN_PRIORITY: first pass prefers sellable
         (breaker-candidate) when available; second pass prefers non-sellable
         (defended / unscored) to mix difficulty.
      3. Within a vein bucket, pick with a fixed RNG (not alphabetical first-N).
    """
    from server.tasks import TASKS
    from trajectories.vein_taxonomy import canonical_vein

    sellable = _load_sellable_ids()
    by_vein: dict[str, list[str]] = defaultdict(list)
    for tid in TASKS:
        by_vein[canonical_vein(tid)].append(tid)
    for v in by_vein:
        by_vein[v].sort()

    rng = random.Random(rng_seed)
    chosen: list[str] = []
    chosen_set: set[str] = set()
    rationale: list[dict] = []

    def _pick(vein: str, prefer_sellable: bool | None) -> str | None:
        pool = [t for t in by_vein.get(vein, []) if t not in chosen_set]
        if not pool:
            return None
        if prefer_sellable is True:
            sub = [t for t in pool if t in sellable] or pool
        elif prefer_sellable is False:
            sub = [t for t in pool if t not in sellable] or pool
        else:
            sub = pool
        return rng.choice(sub)

    # Pass A: one per priority vein (prefer sellable breaker when present).
    for vein in PILOT_VEIN_PRIORITY:
        if len(chosen) >= n:
            break
        tid = _pick(vein, prefer_sellable=True)
        if tid is None:
            continue
        chosen.append(tid)
        chosen_set.add(tid)
        rationale.append({
            "task_id": tid,
            "vein": vein,
            "sellable_ledger": tid in sellable,
            "pick": "pass_a_one_per_vein_prefer_sellable",
        })

    # Pass B: second from each vein preferring non-sellable (defended mix).
    for vein in PILOT_VEIN_PRIORITY:
        if len(chosen) >= n:
            break
        tid = _pick(vein, prefer_sellable=False)
        if tid is None:
            continue
        chosen.append(tid)
        chosen_set.add(tid)
        rationale.append({
            "task_id": tid,
            "vein": vein,
            "sellable_ledger": tid in sellable,
            "pick": "pass_b_second_prefer_non_sellable",
        })

    # Pass C: fill remaining from largest remaining veins (still RNG, not alpha).
    while len(chosen) < n:
        remaining_veins = [v for v in PILOT_VEIN_PRIORITY if any(
            t not in chosen_set for t in by_vein.get(v, [])
        )]
        if not remaining_veins:
            # Fall back to any unused task.
            leftover = [t for t in sorted(TASKS) if t not in chosen_set]
            if not leftover:
                break
            tid = rng.choice(leftover)
            vein = canonical_vein(tid)
        else:
            vein = remaining_veins[len(chosen) % len(remaining_veins)]
            tid = _pick(vein, prefer_sellable=None)
            if tid is None:
                break
        chosen.append(tid)
        chosen_set.add(tid)
        rationale.append({
            "task_id": tid,
            "vein": vein,
            "sellable_ledger": tid in sellable,
            "pick": "pass_c_fill",
        })

    if len(chosen) != n:
        raise SystemExit(f"pilot selection got {len(chosen)} tasks, want {n}")
    return rationale


def build_pilot_entries(rationale: list[dict]) -> list[dict]:
    entries: list[dict] = []
    idx = 0
    for row in rationale:
        for seed in SEEDS:
            entries.append({
                "task_index": idx,
                "task_id": row["task_id"],
                "seed": seed,
                "vein": row["vein"],
                "sellable_ledger": row["sellable_ledger"],
            })
            idx += 1
    return entries


def write_pilot_note(path: Path, rationale: list[dict], rng_seed: int) -> None:
    from collections import Counter

    vein_counts = Counter(r["vein"] for r in rationale)
    n_sell = sum(1 for r in rationale if r["sellable_ledger"])
    lines = [
        "# Local Gemini pilot-20 selection",
        "",
        f"Deterministic sample (`--pilot-seed={rng_seed}`): "
        f"**{len(rationale)} tasks × seeds {{0,1,2}} = {len(rationale) * len(SEEDS)} episodes**.",
        "",
        "Not the first 20 alphabetically. Spread across `canonical_vein()` families "
        "with a sellable-ledger mix (breaker candidates vs non-ledger / defended).",
        "",
        f"- Sellable-ledger members: **{n_sell}/{len(rationale)}**",
        f"- Non-ledger: **{len(rationale) - n_sell}/{len(rationale)}**",
        "",
        "## Vein counts",
        "",
    ]
    for vein, c in sorted(vein_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{vein}`: {c}")
    lines += ["", "## Chosen tasks", ""]
    lines.append("| task_id | vein | sellable ledger | pick pass |")
    lines.append("|---|---|---|---|")
    for r in rationale:
        lines.append(
            f"| `{r['task_id']}` | {r['vein']} | "
            f"{'yes' if r['sellable_ledger'] else 'no'} | {r['pick']} |"
        )
    lines += [
        "",
        "Read-only use of `trajectories/sellable_breakers_v2.csv` for mix labels — "
        "**not modified** by this pilot.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "manifests",
    )
    ap.add_argument(
        "--pilot-20",
        action="store_true",
        help="Write local_pilot_20.json (60 entries) + PILOT_20_NOTE.md only",
    )
    ap.add_argument("--pilot-n", type=int, default=PILOT_N)
    ap.add_argument("--pilot-seed", type=int, default=42,
                    help="RNG seed for within-vein pilot sampling")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.pilot_20:
        rationale = select_pilot_tasks(n=args.pilot_n, rng_seed=args.pilot_seed)
        entries = build_pilot_entries(rationale)
        pilot_path = args.out_dir / "local_pilot_20.json"
        note_path = args.out_dir / "PILOT_20_NOTE.md"
        meta_path = args.out_dir / "local_pilot_20_meta.json"
        pilot_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
        write_pilot_note(note_path, rationale, args.pilot_seed)
        meta = {
            "n_tasks": args.pilot_n,
            "seeds": list(SEEDS),
            "n_episodes": len(entries),
            "pilot_seed": args.pilot_seed,
            "ordering": (
                "diverse canonical_vein round-robin "
                f"(rng_seed={args.pilot_seed}); not alphabetical"
            ),
            "pilot_path": str(pilot_path.relative_to(ROOT)),
            "note_path": str(note_path.relative_to(ROOT)),
            "tasks": rationale,
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {pilot_path} ({len(entries)} entries, {args.pilot_n} tasks)")
        print(f"wrote {note_path}")
        print(f"wrote {meta_path}")
        return

    entries = build_entries()
    n_tasks = len(entries) // len(SEEDS)
    if len(entries) != n_tasks * len(SEEDS):
        raise SystemExit(f"manifest length {len(entries)} not divisible by {len(SEEDS)}")

    full_path = args.out_dir / "full_manifest_945.json"
    smoke_path = args.out_dir / "smoke_manifest_5.json"
    meta_path = args.out_dir / "manifest_meta.json"

    full_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    smoke_path.write_text(
        json.dumps(entries[:SMOKE_N], indent=2) + "\n", encoding="utf-8"
    )
    meta = {
        "n_tasks": n_tasks,
        "seeds": list(SEEDS),
        "n_episodes": len(entries),
        "smoke_n": SMOKE_N,
        "ordering": "sorted(TASKS.keys()) x seeds (0,1,2)",
        "full_path": str(full_path.relative_to(ROOT)),
        "smoke_path": str(smoke_path.relative_to(ROOT)),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {full_path} ({len(entries)} entries, {n_tasks} tasks)")
    print(f"wrote {smoke_path} ({SMOKE_N} entries)")
    print(f"wrote {meta_path}")


if __name__ == "__main__":
    main()
