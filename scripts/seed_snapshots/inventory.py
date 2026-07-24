#!/usr/bin/env python3
"""Step 1 — inventory evidence per (task_id, seed) episode."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    INVENTORY_DIR,
    PIXEL_KINDS,
    SELECTOR_KINDS,
    TRAJ_ROOTS,
    assert_sellable_untouched,
    disposition_from_verifier,
    load_task_ids,
    parse_traj_filename,
    write_json_pretty,
)


def _scan_one(path_str: str) -> dict | None:
    path = Path(path_str)
    parsed = parse_traj_filename(path)
    if not parsed:
        return None
    task_id, seed, epid = parsed
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return {
            "task_id": task_id,
            "seed": seed,
            "episode_id": epid,
            "path": str(path),
            "corrupt": True,
            "error": str(e),
        }

    steps = data.get("steps") or []
    kinds = Counter(s.get("action_kind") for s in steps)
    n_sel = sum(kinds[k] for k in SELECTOR_KINDS)
    n_pix = sum(kinds[k] for k in PIXEL_KINDS)
    screens = [
        s.get("screenshot_path")
        for s in steps
        if s.get("screenshot_path")
    ]
    # Resolve screenshot existence relative to traj parent / screens/
    existing_screens = 0
    for rel in screens[:3]:  # cheap sample
        if not rel:
            continue
        # Windows-style paths in some trajs
        rel_norm = rel.replace("\\", "/")
        candidates = [
            path.parent / rel_norm,
            path.parent / "screens" / Path(rel_norm).name,
            path.parent.parent / rel_norm,
        ]
        # Also common: screens/<episode_dir>/step_XXX.png beside jsonl
        ep_dir = path.stem  # includes task__seed__epid
        candidates.append(path.parent / "screens" / ep_dir / Path(rel_norm).name)
        if any(c.exists() for c in candidates):
            existing_screens += 1

    vr = data.get("verifier_result") or {}
    agent = data.get("agent_name") or ""
    return {
        "task_id": task_id,
        "seed": seed,
        "episode_id": epid,
        "path": str(path),
        "corrupt": False,
        "agent_name": agent,
        "is_oracle": agent == "oracle" or agent.startswith("oracle"),
        "n_steps": len(steps),
        "action_kinds": dict(kinds),
        "n_selector_actions": n_sel,
        "n_pixel_actions": n_pix,
        "replayable_selector": n_sel > 0 and n_pix == 0,
        "has_verifier_result": bool(vr),
        "historical_disposition": disposition_from_verifier(vr),
        "verifier_success": vr.get("success"),
        "verifier_score": vr.get("score"),
        "has_initial_snapshot": bool(data.get("initial_snapshot")),
        "has_final_snapshot": bool(data.get("final_snapshot")),
        "final_snapshot": data.get("final_snapshot"),
        "has_screenshot_refs": len(screens) > 0,
        "n_screenshot_refs": len(screens),
        "screenshots_exist_sample": existing_screens,
        "has_dom_html": any(
            s.get("dom_html") or s.get("html") or s.get("accessibility_tree")
            for s in steps
        ),
        "has_network_log": bool(data.get("network_log") or data.get("har")),
        "has_action_log": len(steps) > 0,
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
    }


def main() -> None:
    assert_sellable_untouched()
    task_ids = load_task_ids()
    task_set = set(task_ids)

    paths: list[str] = []
    for root in TRAJ_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.jsonl"):
            if "screens" in p.parts:
                continue
            parsed = parse_traj_filename(p)
            if not parsed:
                continue
            tid, seed, _ = parsed
            if tid in task_set and seed in (0, 1, 2):
                paths.append(str(p))

    print(f"[inventory] scanning {len(paths)} traj files…", flush=True)
    by_ep: dict[tuple[str, int], list[dict]] = defaultdict(list)
    corrupt = 0
    with ProcessPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_scan_one, p) for p in paths]
        done = 0
        for fut in as_completed(futs):
            rec = fut.result()
            done += 1
            if done % 500 == 0:
                print(f"  …{done}/{len(paths)}", flush=True)
            if rec is None:
                continue
            if rec.get("corrupt"):
                corrupt += 1
            by_ep[(rec["task_id"], rec["seed"])].append(rec)

    episodes = []
    for tid in task_ids:
        for seed in (0, 1, 2):
            recs = by_ep.get((tid, seed), [])
            # Prefer oracle selector replayable, then any selector, then richest
            def rank(r: dict) -> tuple:
                return (
                    1 if r.get("corrupt") else 0,
                    3 if r.get("is_oracle") and r.get("replayable_selector") else
                    2 if r.get("replayable_selector") else
                    1 if r.get("n_selector_actions", 0) > 0 else 0,
                    r.get("n_steps") or 0,
                    1 if r.get("has_verifier_result") else 0,
                )

            recs_sorted = sorted(recs, key=rank, reverse=True)
            best = recs_sorted[0] if recs_sorted else None
            evidence = {
                "task_id": tid,
                "seed": seed,
                "n_traj_files": len(recs),
                "best": best,
                "all_paths": [r["path"] for r in recs_sorted],
            }
            if best is None:
                evidence["evidence_class"] = "no_evidence"
            elif best.get("corrupt") and len(recs_sorted) == 1:
                evidence["evidence_class"] = "corrupt_only"
            elif best.get("replayable_selector"):
                evidence["evidence_class"] = "selector_replayable"
            elif best.get("n_pixel_actions", 0) > 0:
                evidence["evidence_class"] = "pixel_only"
            elif best.get("has_verifier_result") or best.get("has_final_snapshot"):
                evidence["evidence_class"] = "verifier_or_snapshot_only"
            elif best.get("has_screenshot_refs"):
                evidence["evidence_class"] = "screenshots_only"
            else:
                evidence["evidence_class"] = "thin"
            episodes.append(evidence)

    class_counts = Counter(e["evidence_class"] for e in episodes)
    summary = {
        "n_episodes": len(episodes),
        "n_traj_files_scanned": len(paths),
        "corrupt_files": corrupt,
        "evidence_class_counts": dict(class_counts),
        "selector_replayable": class_counts.get("selector_replayable", 0),
        "pixel_only": class_counts.get("pixel_only", 0),
        "no_evidence": class_counts.get("no_evidence", 0),
        "has_any_traj": sum(1 for e in episodes if e["n_traj_files"] > 0),
        "methodology_notes": [
            "DOM/HTML and network HAR are almost never persisted in these jsonl trajs.",
            "Verifier-read side effects appear as verifier_result + compact final_snapshot "
            "(cart/orders counts), not full WorldState dumps.",
            "Screenshot paths are referenced; on-disk PNG availability varies by cascade dir.",
            "Selector-replayable = oracle-style click/fill/navigate with zero pixel actions.",
        ],
    }

    write_json_pretty(INVENTORY_DIR / "inventory_summary.json", summary)
    write_json_pretty(INVENTORY_DIR / "episodes.json", {"episodes": episodes})
    # Slim index for later stages
    best_index = {}
    for e in episodes:
        key = f"{e['task_id']}|{e['seed']}"
        best_index[key] = {
            "evidence_class": e["evidence_class"],
            "best": e["best"],
            "n_traj_files": e["n_traj_files"],
        }
    write_json_pretty(INVENTORY_DIR / "best_traj_index.json", best_index)
    print(json.dumps(summary, indent=2))
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
