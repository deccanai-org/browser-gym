#!/usr/bin/env python3
"""Step 5 — partial spot-check for non-replayable episodes.

Honest limits: we do NOT run OCR across hundreds of screenshots. Instead:
  1. If earliest compact initial_snapshot from traj exists, compare key fields
     to Step-2 factory initial (cart/orders/user/promo).
  2. If screenshot PNGs exist on disk, record path presence only
     (not visual content match).
  3. Otherwise mark inconclusive.
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
    load_task_ids,
    snapshot_paths,
    write_json,
    write_json_pretty,
)


COMPARE_KEYS = (
    "current_user_id",
    "cart_item_count",
    "orders_count",
    "returns_count",
    "subscriptions_count",
    "applied_promo",
)


def _compact_from_initial(initial: dict) -> dict:
    """Derive compact harness-like fields from full initial snapshot."""
    st = initial.get("state") or {}
    toj = initial.get("to_json") or {}
    # WorldState nests shop
    shop = st.get("shop") if isinstance(st.get("shop"), dict) else st
    toj_shop = toj.get("shop") if isinstance(toj.get("shop"), dict) else toj
    cart = shop.get("cart") or {}
    items = cart.get("items") or []
    qty = 0
    for it in items:
        if isinstance(it, dict):
            qty += int(it.get("quantity") or 0)
    orders = shop.get("orders") or {}
    returns = shop.get("returns") or {}
    subs = shop.get("subscriptions") or {}
    return {
        "current_user_id": shop.get("current_user_id")
        or toj_shop.get("current_user_id"),
        "cart_item_count": qty
        if items
        else toj_shop.get("cart_item_count", 0) or 0,
        "orders_count": len(orders)
        if isinstance(orders, dict)
        else toj_shop.get("orders_count", 0) or 0,
        "returns_count": len(returns)
        if isinstance(returns, dict)
        else 0,
        "subscriptions_count": len(subs)
        if isinstance(subs, dict)
        else 0,
        "applied_promo": cart.get("applied_promo"),
    }


def main() -> None:
    assert_sellable_untouched()
    index = json.loads((INVENTORY_DIR / "best_traj_index.json").read_text())
    counts = {
        "match": 0,
        "mismatch": 0,
        "inconclusive": 0,
        "skipped_replayable": 0,
    }

    for tid in load_task_ids():
        for seed in (0, 1, 2):
            key = f"{tid}|{seed}"
            info = index.get(key) or {}
            cls = info.get("evidence_class")
            paths = snapshot_paths(tid, seed)
            # Skip episodes that got full replay verification
            if paths["replay"].exists():
                rep = json.loads(paths["replay"].read_text())
                if "error" not in rep and rep.get("n_steps_replayed", 0) > 0:
                    counts["skipped_replayable"] += 1
                    continue

            best = info.get("best")
            result = {
                "task_id": tid,
                "seed": seed,
                "evidence_class": cls,
                "methodology": (
                    "Programmatic compare of traj initial_snapshot compact "
                    "fields vs factory initial; no screenshot OCR."
                ),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            if not best or best.get("corrupt"):
                result["partial_spotcheck"] = "inconclusive"
                result["reason"] = "no_usable_traj"
                counts["inconclusive"] += 1
                write_json(paths["spotcheck"], result)
                continue

            # Load traj initial_snapshot
            try:
                traj = json.loads(Path(best["path"]).read_text())
            except Exception as e:
                result["partial_spotcheck"] = "inconclusive"
                result["reason"] = f"traj_unreadable:{e}"
                counts["inconclusive"] += 1
                write_json(paths["spotcheck"], result)
                continue

            traj_init = traj.get("initial_snapshot")
            if not traj_init or not paths["initial"].exists():
                # Screenshot presence only
                has_refs = bool(best.get("has_screenshot_refs"))
                result["partial_spotcheck"] = "inconclusive"
                result["reason"] = (
                    "no_initial_snapshot_pair"
                    + ("; screenshot_refs_present" if has_refs else "")
                )
                result["screenshot_refs"] = best.get("n_screenshot_refs", 0)
                counts["inconclusive"] += 1
                write_json(paths["spotcheck"], result)
                continue

            initial = json.loads(paths["initial"].read_text())
            factory_compact = _compact_from_initial(initial)
            diffs = {}
            for k in COMPARE_KEYS:
                a = traj_init.get(k)
                b = factory_compact.get(k)
                # Normalize None/0
                if a != b:
                    diffs[k] = {"traj": a, "factory": b}

            if not diffs:
                result["partial_spotcheck"] = "match"
                counts["match"] += 1
            else:
                result["partial_spotcheck"] = "mismatch"
                result["diffs"] = diffs
                counts["mismatch"] += 1
            result["traj_initial_snapshot"] = {
                k: traj_init.get(k) for k in COMPARE_KEYS
            }
            result["factory_compact"] = factory_compact
            write_json(paths["spotcheck"], result)

    summary = {
        **counts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limits": [
            "No OCR / visual screenshot inspection at scale.",
            "Compares only compact harness fields available in traj headers.",
            "Screenshot path references noted when present but content unread.",
        ],
    }
    write_json_pretty(CHECKPOINT_DIR / "spotcheck_summary.json", summary)
    print(json.dumps(summary, indent=2))
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
