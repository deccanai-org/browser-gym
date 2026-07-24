# Seed-state backfill report (312 × 3 = 936)

Generated: 2026-07-23T18:24:49.770254+00:00  
Registry: clean `feat/multi-app` tip @ `ba6a8c6`  
(`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions`) — **312 tasks**, no M384–M386 Sheets extras.

## Counts

| Status | N |
|--------|--:|
| verified (Step 4 match) | 873 |
| spotcheck_pass | 15 |
| spotcheck_fail | 0 |
| replay_mismatch | 47 |
| inconclusive | 1 |
| no_evidence | 0 |
| replay_error (rolled into inconclusive) | 1 |
| **Total** | **936** |

## Inventory (Step 1)

```json
{
  "n_episodes": 936,
  "n_traj_files_scanned": 9347,
  "corrupt_files": 0,
  "evidence_class_counts": {
    "selector_replayable": 921,
    "pixel_only": 15
  },
  "selector_replayable": 921,
  "pixel_only": 15,
  "no_evidence": 0,
  "has_any_traj": 936,
  "methodology_notes": [
    "DOM/HTML and network HAR are almost never persisted in these jsonl trajs.",
    "Verifier-read side effects appear as verifier_result + compact final_snapshot (cart/orders counts), not full WorldState dumps.",
    "Screenshot paths are referenced; on-disk PNG availability varies by cascade dir.",
    "Selector-replayable = oracle-style click/fill/navigate with zero pixel actions."
  ]
}
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
- SHA256 baseline: `ac1c8430730bdc25f90b24659c38788625fdd79fa6623df47863ecabee1f1aa8`
- SHA256 now: `ac1c8430730bdc25f90b24659c38788625fdd79fa6623df47863ecabee1f1aa8`
- Untouched: **True**

## Notable mismatches / drift hotspots

### Replay mismatches (47)
- `A4/home_office_bundle` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/A4_home_office_bundle__0__d593c8fd.jsonl`
- `A4/home_office_bundle` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/A4_home_office_bundle__1__331c3ba5.jsonl`
- `A4/home_office_bundle` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/A4_home_office_bundle__2__331913f2.jsonl`
- `C2/split_shipping_gift` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/C2_split_shipping_gift__0__72ab5e4a.jsonl`
- `C2/split_shipping_gift` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/C2_split_shipping_gift__1__fbe5d56d.jsonl`
- `C2/split_shipping_gift` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/C2_split_shipping_gift__2__d4d54f5b.jsonl`
- `C4/mega_checkout` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/C4_mega_checkout__0__fb635401.jsonl`
- `C4/mega_checkout` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/C4_mega_checkout__1__c6ab9839.jsonl`
- `C4/mega_checkout` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/C4_mega_checkout__2__482f7ff8.jsonl`
- `M120/inert_move_meeting_partial_success` seed=0 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M120_inert_move_meeting_partial_success__0__1f271e31.jsonl`
- `M134/promo_double_apply_assumed` seed=1 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M134_promo_double_apply_assumed__1__4d1d6fa4.jsonl`
- `M134/promo_double_apply_assumed` seed=2 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M134_promo_double_apply_assumed__2__54922600.jsonl`
- `M16/coordinated_dinner_delay` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M16_coordinated_dinner_delay__0__e7956a38.jsonl`
- `M16/coordinated_dinner_delay` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/M16_coordinated_dinner_delay__1__771c90e7.jsonl`
- `M16/coordinated_dinner_delay` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/M16_coordinated_dinner_delay__2__8771bf38.jsonl`
- `M197/event_supplies_sneaked_addon` seed=0 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M197_event_supplies_sneaked_addon__0__ebeaf12a.jsonl`
- `M2/order_then_track_via_email` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M2_order_then_track_via_email__0__58a8f15b.jsonl`
- `M2/order_then_track_via_email` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/M2_order_then_track_via_email__1__779db00b.jsonl`
- `M2/order_then_track_via_email` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/M2_order_then_track_via_email__2__8ccf34b5.jsonl`
- `M203/split_ship_two_tracking` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M203_split_ship_two_tracking__0__4569398d.jsonl`
- `M203/split_ship_two_tracking` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M203_split_ship_two_tracking__1__096b6105.jsonl`
- `M203/split_ship_two_tracking` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym/trajectories/oracle_phase0/M203_split_ship_two_tracking__2__8a16981c.jsonl`
- `M204/valuemart_delivery_threshold` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M204_valuemart_delivery_threshold__0__c1cfbaaa.jsonl`
- `M204/valuemart_delivery_threshold` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M204_valuemart_delivery_threshold__1__b3327fda.jsonl`
- `M207/scheduled_delivery_event_join` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M207_scheduled_delivery_event_join__0__66e22184.jsonl`
- `M207/scheduled_delivery_event_join` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M207_scheduled_delivery_event_join__1__8a9338ee.jsonl`
- `M220/address_change_no_propagate` seed=0 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M220_address_change_no_propagate__0__133d547e.jsonl`
- `M220/address_change_no_propagate` seed=1 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M220_address_change_no_propagate__1__27ce3c07.jsonl`
- `M245/split_payment_noop` seed=0 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M245_split_payment_noop__0__debb03d4.jsonl`
- `M251/same_but_cheaper_none` seed=0 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M251_same_but_cheaper_none__0__91a77c13.jsonl`
- `M251/same_but_cheaper_none` seed=1 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M251_same_but_cheaper_none__1__8033d4d1.jsonl`
- `M296/change_email_notification_decoy_field` seed=0 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M296_change_email_notification_decoy_field__0__82f29e3a.jsonl`
- `M296/change_email_notification_decoy_field` seed=1 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M296_change_email_notification_decoy_field__1__409b5ebc.jsonl`
- `M296/change_email_notification_decoy_field` seed=2 hist=BREAK traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M296_change_email_notification_decoy_field__2__fb64cf04.jsonl`
- `M297/no_ship_to_country_verify_then_substitute` seed=0 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M297_no_ship_to_country_verify_then_substitute__0__6fdba692.jsonl`
- `M306/injected_confirmation_reroute_on_loop` seed=0 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M306_injected_confirmation_reroute_on_loop__0__0d7e9232.jsonl`
- `M306/injected_confirmation_reroute_on_loop` seed=1 hist=INCOMPLETE traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M306_injected_confirmation_reroute_on_loop__1__72cb1610.jsonl`
- `M35/lying_bounce` seed=0 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M35_lying_bounce__0__6532ebac.jsonl`
- `M35/lying_bounce` seed=1 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M35_lying_bounce__1__f23d4a63.jsonl`
- `M35/lying_bounce` seed=2 hist=SUCCESS traj=`/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/trajectories/oracle/M35_lying_bounce__2__0e51f71f.jsonl`
- … +7 more

### Spotcheck failures (0)

### Possibly drifted episodes (932)
- `A1/buy_wireless_mouse` seeds=[0, 1, 2]
- `A2/filter_laptop` seeds=[0, 1, 2]
- `A3/configure_bundle` seeds=[0, 1, 2]
- `A4/home_office_bundle` seeds=[0, 1, 2]
- `B1/add_address` seeds=[0, 1, 2]
- `B2/track_and_return` seeds=[0, 1, 2]
- `B3/account_overhaul` seeds=[0, 1, 2]
- `B4/subscription_juggle` seeds=[0, 1, 2]
- `C1/promo_partial` seeds=[0, 1, 2]
- `C2/split_shipping_gift` seeds=[0, 1, 2]
- `C3/subscription_loyalty` seeds=[0, 1, 2]
- `C4/mega_checkout` seeds=[0, 1, 2]
- `D1/browse_audio_no_search` seeds=[0, 1, 2]
- `D2/drill_electronics_keyboards` seeds=[0, 1, 2]
- `M10/dinner_source_conflict` seeds=[0, 1, 2]
- `M100/two_recipient_expired` seeds=[0, 1, 2]
- `M101/message_plus_expired_v2` seeds=[0, 1, 2]
- `M102/qty_shipto_corporate` seeds=[0, 1, 2]
- `M103/mixed_basket_expired` seeds=[0, 1, 2]
- `M104/message_qty_expired` seeds=[0, 1, 2]
- `M105/false_double_charge` seeds=[0, 1, 2]
- `M106/false_price_adjustment` seeds=[0, 1, 2]
- `M107/false_warranty_never_bought` seeds=[0, 1, 2]
- `M108/false_cancel_shipped` seeds=[0, 1, 2]
- `M109/false_phantom_return` seeds=[0, 1, 2]
- `M11/cancel_unshipped_over_100` seeds=[0, 1, 2]
- `M110/ambiguous_return_v2` seeds=[0, 1, 2]
- `M111/false_premise_masks_expired_card` seeds=[0, 1, 2]
- `M112/warranty_premise_masks_dead_card_sub` seeds=[0, 1, 2]
- `M113/swapped_gift_messages_correct_shipto` seeds=[0, 1, 2]
- `M114/expired_card_masked_by_account_chore` seeds=[0, 1, 2]
- `M115/wrong_item_warranty_then_reorder_dead_card` seeds=[0, 1, 2]
- `M116/inbox_says_cancelled_live_says_active` seeds=[0, 1, 2]
- `M117/ambiguous_default_card_two_new` seeds=[0, 1, 2]
- `M118/ambiguous_gift_recipient_two_sisters` seeds=[0, 1, 2]
- `M119/stale_old_address_recipient_moved` seeds=[0, 1, 2]
- `M12/bulk_add_dense_grid` seeds=[0, 1, 2]
- `M120/inert_move_meeting_partial_success` seeds=[0, 1, 2]
- `M121/delivery_day_two_outputs` seeds=[0, 1, 2]
- `M122/flight_delay_dinner_reschedule` seeds=[0, 1, 2]
- … +271 tasks

### Replay errors / inconclusive notes (1)
- `M249/cross_store_cap_empty` seed=1: ['replay_error:Page.goto: Timeout 30000ms exceeded.\nCall log:\n  - navigating to "http://127.0.0.1:8763/", waiting until "domcontentload']

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

## Replay mismatch breakdown (47)

| Class | N | Meaning |
|-------|--:|---------|
| hist_ok_replay_fail | 17 | Oracle traj succeeded; mechanical replay missed milestones (timing/UI/async) |
| hist_fail_replay_ok | 21 | Traj `success=false` (often score=1.0 inert/negative tasks); replay got success=true — flag semantics, not state drift |
| action_errors | 9 | Selector click/fill failed during replay (stale selectors / overlays) |
| other | 0 | |

**Forensic follow-up:** [`SEED_REPLAY_MISMATCH_FORENSIC_2026-07-23.md`](./SEED_REPLAY_MISMATCH_FORENSIC_2026-07-23.md).

Full episode index: `seed_snapshots/manifest.json`.
Seed-branching checks: all 4 passed (calendar seed%2, M10 Alex, A2 jitter, plain seed ints) — see `_checkpoints/seed_branching.json`.

## Drift flag caveat

`possibly_drifted` is **file-level coarse**: it compares traj timestamps to the tip commit date of `server/tasks.py` / wave modules. Because those files are shared, nearly all episodes flag drifted (932/936 here). Treat it as a reminder to run per-task `git log -S 'TASK_ID' -- server/` before assuming factory drift; do **not** treat the flag alone as evidence of seed corruption.
