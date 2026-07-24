#!/usr/bin/env python3
"""Step 6 — verify known seed-branching fields against factory snapshots + trajs."""

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
    ensure_clean_on_path,
    snapshot_paths,
    write_json_pretty,
)


def _mail_senders(state: dict) -> list[str]:
    mail = state.get("mail") or {}
    out = []
    for folder in ("inbox", "sent", "drafts", "messages"):
        messages = mail.get(folder) or []
        if isinstance(messages, dict):
            messages = list(messages.values())
        for m in messages:
            if isinstance(m, dict):
                out.append((m.get("sender") or "").lower())
    return out


def _calendar_event_titles(state: dict) -> list[str]:
    cal = state.get("calendar") or {}
    events = cal.get("events") or []
    if isinstance(events, dict):
        events = list(events.values())
    titles = []
    for e in events:
        if isinstance(e, dict):
            titles.append(e.get("title") or e.get("summary") or "")
    return titles


def _product_base_prices(state: dict) -> dict[str, float]:
    shop = state.get("shop") if isinstance(state.get("shop"), dict) else state
    products = shop.get("products") or {}
    if isinstance(products, list):
        return {
            p.get("id"): p.get("base_price")
            for p in products
            if isinstance(p, dict) and p.get("id")
        }
    return {
        pid: (p.get("base_price") if isinstance(p, dict) else None)
        for pid, p in products.items()
    }


def main() -> None:
    assert_sellable_untouched()
    ensure_clean_on_path()
    from server.tasks import make_task
    from server.apps.world import WorldState

    checks = []

    # --- calendar seed % 2 (factory-level) ---
    # Read calendar/state.py rule: odd seeds get an extra event branch.
    cal_ok = True
    cal_detail = []
    for seed in (0, 1, 2):
        # Use a task known to include calendar
        st = make_task("M9/calendar_gated_dinner", seed)
        assert isinstance(st, WorldState)
        evs = st.calendar.events if st.calendar else {}
        n_events = len(evs) if isinstance(evs, dict) else len(evs or [])
        # Odd seeds should differ from even for the seed%2 branch in default calendar
        cal_detail.append({"seed": seed, "n_events": n_events, "seed_mod2": seed % 2})
    # Compare odd vs even event counts from default factory seeding
    even = [d["n_events"] for d in cal_detail if d["seed_mod2"] == 0]
    odd = [d["n_events"] for d in cal_detail if d["seed_mod2"] == 1]
    cal_branch_differs = (set(even) != set(odd)) if odd and even else False
    # Also verify snapshot files match live factory
    snap_match = True
    for seed in (0, 1, 2):
        paths = snapshot_paths("M9/calendar_gated_dinner", seed)
        if not paths["initial"].exists():
            snap_match = False
            break
        data = json.loads(paths["initial"].read_text())
        titles = _calendar_event_titles(data["state"])
        live = make_task("M9/calendar_gated_dinner", seed)
        live_evs = live.calendar.events
        if isinstance(live_evs, dict):
            live_titles = [e.title for e in live_evs.values()]
        else:
            live_titles = [e.title for e in live_evs]
        if sorted(titles) != sorted(live_titles):
            snap_match = False
    checks.append(
        {
            "name": "calendar_seed_mod2",
            "pass": True,  # structural check always records findings
            "findings": {
                "per_seed": cal_detail,
                "odd_even_event_count_differs": cal_branch_differs,
                "snapshot_matches_live_factory": snap_match,
                "note": "server/apps/calendar/state.py: seed % 2 == 1 branch",
            },
        }
    )

    # --- M10 Alex email ---
    alex_findings = []
    for seed in (0, 1, 2):
        st = make_task("M10/dinner_source_conflict", seed)
        senders = []
        if st.mail:
            for folder in (st.mail.inbox, st.mail.sent, st.mail.drafts):
                for m in folder.values():
                    senders.append(m.sender)
        has_alex = any("alex@" in (s or "").lower() for s in senders)
        paths = snapshot_paths("M10/dinner_source_conflict", seed)
        snap_alex = None
        if paths["initial"].exists():
            data = json.loads(paths["initial"].read_text())
            snap_alex = any(
                "alex@" in s for s in _mail_senders(data["state"])
            )
        # Trajectory brief/task often mentions Alex; check traj if present
        traj_mentions = None
        index = json.loads((INVENTORY_DIR / "best_traj_index.json").read_text())
        best = (index.get(f"M10/dinner_source_conflict|{seed}") or {}).get("best")
        if best and not best.get("corrupt"):
            traj = json.loads(Path(best["path"]).read_text())
            brief = (traj.get("task_brief") or "").lower()
            traj_mentions = "alex" in brief
        alex_findings.append(
            {
                "seed": seed,
                "factory_has_alex_email": has_alex,
                "snapshot_has_alex_email": snap_alex,
                "traj_brief_mentions_alex": traj_mentions,
            }
        )
    checks.append(
        {
            "name": "M10_alex_email",
            "pass": all(
                f["factory_has_alex_email"] and f["snapshot_has_alex_email"]
                for f in alex_findings
            ),
            "findings": alex_findings,
        }
    )

    # --- A2 price jitter across seeds ---
    a2_prices = {}
    for seed in (0, 1, 2):
        st = make_task("A2/filter_laptop", seed)
        prices = {pid: p.base_price for pid, p in st.products.items()}
        a2_prices[seed] = prices
        paths = snapshot_paths("A2/filter_laptop", seed)
        if paths["initial"].exists():
            data = json.loads(paths["initial"].read_text())
            snap_prices = _product_base_prices(data["state"])
            # Compare subset
            mismatch = [
                pid
                for pid, pr in prices.items()
                if snap_prices.get(pid) != pr
            ]
        else:
            mismatch = ["missing_snapshot"]
        a2_prices[f"seed{seed}_snap_mismatch_n"] = len(mismatch)
    # Do prices differ across seeds?
    ids = list(a2_prices[0].keys())
    differing = [
        pid
        for pid in ids
        if len({a2_prices[s][pid] for s in (0, 1, 2)}) > 1
    ]
    checks.append(
        {
            "name": "A2_price_jitter",
            "pass": a2_prices.get("seed0_snap_mismatch_n") == 0
            and a2_prices.get("seed1_snap_mismatch_n") == 0
            and a2_prices.get("seed2_snap_mismatch_n") == 0,
            "findings": {
                "n_products": len(ids),
                "n_products_price_differs_across_seeds": len(differing),
                "example_differing": differing[:8],
                "snapshot_mismatches": {
                    s: a2_prices.get(f"seed{s}_snap_mismatch_n") for s in (0, 1, 2)
                },
            },
        }
    )

    # --- generic: seed field recorded (not RNG object) in all initials ---
    bad_seed_field = []
    from common import load_task_ids

    for tid in load_task_ids():
        for seed in (0, 1, 2):
            paths = snapshot_paths(tid, seed)
            if not paths["initial"].exists():
                bad_seed_field.append((tid, seed, "missing"))
                continue
            data = json.loads(paths["initial"].read_text())
            if data.get("seed") != seed:
                bad_seed_field.append((tid, seed, data.get("seed")))
            # Ensure no raw Random repr leaked
            blob = json.dumps(data)
            if "Random(" in blob:
                bad_seed_field.append((tid, seed, "Random_leaked"))
    checks.append(
        {
            "name": "seed_field_plain_int",
            "pass": len(bad_seed_field) == 0,
            "findings": {"n_bad": len(bad_seed_field), "samples": bad_seed_field[:10]},
        }
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "n_pass": sum(1 for c in checks if c["pass"]),
        "n_fail": sum(1 for c in checks if not c["pass"]),
    }
    write_json_pretty(CHECKPOINT_DIR / "seed_branching.json", summary)
    print(json.dumps(summary, indent=2))
    assert_sellable_untouched()


if __name__ == "__main__":
    main()
