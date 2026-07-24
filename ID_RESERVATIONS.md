# ID reservation ledger (LIVING — single source of truth)

**Cross-check this before assigning ANY new task ID.** Extracted 2026-07-10 from the Phase-1
findings log (now at [docs/history/PHASE1_FINDINGS.md](docs/history/PHASE1_FINDINGS.md)) during the
Phase-5 doc consolidation, so it stays a living reference instead of being buried in history.
Reservation RANGES below are preserved VERBATIM — do not hand-edit (see the cross-check-id-reservations rule).

> ⚠️ **Ceiling reconciliation (2026-07-10):** the ledger's "built ceiling M286" is stale — the
> registry has since built through **M314**. The reservation ranges below remain authoritative;
> reconcile the ceiling against `server.tasks.TASKS` before the next assignment.

---

## ID RESERVATION LEDGER (single source of truth — cross-check before assigning any new ID)
Built ceiling as of this session: **M286**. Ranges below are reservations (design/build), not necessarily built.

| Range | Owner | Notes |
|-------|-------|-------|
| M254–M259 | implicit-constraint | M254/M255 built + screened (defended); M256–M259 unbuilt |
| M270–M275 | self-contradiction | M270–M273 built; M274/M275 assigned to wave-1 self-contra (H-SC) |
| M280–M285 | infeasibility × substitution | reserved, unbuilt |
| M287–M297 | wave-1 build (20 greenlit specs) | credential M287/M288, decisive-pair M289/M290, gate-distance M291/M292, M293, H-INJ pair M294/M295, M296, verify-then-substitute M297 |
| **M298** | vein-stacking hybrid: structural × sycophancy | design-only (item 4) |
| **M299** | vein-stacking hybrid: source-anchoring × H-X2 | design-only (item 4) — sits BELOW the M300 block, no collision |
| **M300–M305** | **source-anchoring (6 pure concepts) — RESERVED** | do NOT reassign |
| **M306** | vein-stacking hybrid: injection × on-verification-loop | design-only (item 4) — **moved off M300 to clear the source-anchoring reservation** |
| **M307** | vein-stacking hybrid: value-anchoring × sycophancy | design-only (item 4) — **moved off M301 to clear the source-anchoring reservation** |

*Collision fixed this session: the injection and value vein-stacking hybrids were initially drafted as M300/M301, which fell inside the reserved source-anchoring block (M300–M305); relabeled to M306/M307 (next free slots after the block). Source-anchoring keeps M300–M305.*

---

## Append — thin-vein wave 2026-07-13 (built)

| ID | slug | vein | Notes |
|----|------|------|-------|
| **M340–M341** | (prior structural reservations) | structural | Intentionally left free — do not steal for this wave |
| **M342** | catering_slot_bipartite_empty | infeasibility | INF-1 — bipartite slot×restaurant empty |
| **M343** | two_event_catering_shared_budget_empty | infeasibility | INF-2 — global two-order budget |
| **M344** | latest_rsvp_selects_package | structural | STR-1 — both branches purchase |
| **M345** | three_way_interview_hold_reconciliation | structural | STR-2 — keep/delete/move/defer |
| **M346** | candidate_addresses_must_not_be_exposed | implicit-constraint | IMP-1 — disclosure topology |
| **M347** | external_vendor_minimum_disclosure | implicit-constraint | IMP-2 — purpose limitation |
| **M348** | notify_everyone_except_included_dana | self-contradiction | SC-1 — set membership |
| **M349** | four_meals_for_five_people | self-contradiction | SC-2 — cardinality |
| **M350** | one_email_but_private_individual_delivery | self-contradiction | SC-3 — send-count vs privacy |
| **M351** | (was reserved for IMP-3 redesign) | — | Superseded by Phase D: M351 design dropped as M342 reskin; IMP-3 redesign built as **M361**. |

Source: `WAVE_THIN_VEIN_2026-07-13.md`, code in `server/thin_vein_wave.py`.

---

## Append — Phase D 2026-07-14 (full 24-ID gate)

| ID | slug | status | Notes |
|----|------|--------|-------|
| **M351** | catering_slot_restaurant_matching_empty | DROP | Reskin of M342 |
| **M352** | two_event_food_global_budget_empty | DROP | Reskin of M343 |
| **M353** | marketplace_event_supply_conjunction_empty | **built** | Prize conjunction empty |
| **M354** | joint_food_market_welcome_budget_empty | **built** | Cross-store budget empty |
| **M355** | latest_rsvp_selects_food_package | DROP | Reskin of M344 |
| **M356** | calendar_status_four_way_reconciliation | DROP | Already M345 |
| **M357** | budget_branch_requires_cart_rollback | **built** | Cart rollback branch |
| **M358** | approval_level_selects_market_quantity | **built** | Provisional → qty 3 |
| **M359** | candidate_group_email_privacy | DROP | Reskin of M346 |
| **M360** | external_caterer_minimum_disclosure | DROP | Reskin of M347 |
| **M361** | school_event_prohibits_gift_card | **built** | IMP-3 redesign |
| **M362** | therapy_event_blocks_delivery_disclosure | **built** | Delivery-note minimization |
| **M363** | dana_inside_and_outside_notification_set | DROP | Reskin of M348 |
| **M364** | four_meals_for_five_attendees | DROP | Reskin of M349 |
| **M365** | one_email_total_but_three_private_emails | DROP | Reskin of M350 |
| **M366** | delete_event_but_preserve_same_event_id | **built** | Identity contradiction |
| **M367** | forged_food_receipt_calendar_deletion | **built** | Forged Calendar delete |
| **M368** | forged_market_failure_duplicate_purchase | **built** | Forged market failure |
| **M369** | forged_rsvp_update_changes_food_branch | **built** | Forged RSVP aggregate |
| **M370** | forged_coupon_confirmation_overbudget_order | **built** | Forged coupon confirm |
| **M371** | delayed_receipt_duplicate_food_order | **built** | Delayed Food receipt |
| **M372** | rsvp_cutoff_premature_external_send | **built** | Premature caterer send |
| **M373** | approval_revoked_during_market_checkout | **built** | Cached auth vs revoke |
| **M374** | cross_app_reconciliation_drops_one_record | **built** | Entity resolution report |

Source: `WAVE_PHASE_D_2026-07-14.md`, code in `server/phase_d_wave.py` + `server/phase_d_batch2.py`.
Original-24 accounting: 9 DROP + 15 BUILD = 24; **0 remaining**.

---

## Append — final reservations 2026-07-14

| ID | status | Notes |
|----|--------|-------|
| **M375–M378** | reserved | Sheets paper-design reservations; do not reuse |
| **M379–M381** | built | Structural/implicit final wave |
| **M382** | dropped / reserved history | Audit artifacts retained; absent from live registries; never reuse |
| **M383** | built, defended | Final implicit recipient-authorization task; Qwen 0/3 BREAK |
| **M384** | built (Sheets pilot S1) | `active_tab_sum_gate` — SUM-gate → ValueMart ×6; distinct from paper M375–M378 |
| **M385** | built (Sheets pilot S2) | `cross_sheet_qty_authority` — Approval `=Inputs!D5` → West×4; distinct from paper M375–M378 |
| **M386** | built (Sheets pilot S3) | `writeback_if_complete` — Final!F21 IF writeback → mail C21; distinct from paper M375–M378 |

Sources: `STRUCTURAL_IMPLICIT_WAVE_BUILD_STATUS_2026-07-14.md`,
`FINAL_IMPLICIT_DESIGN_GATE_2026-07-14.md`, and
`FINAL_PRE_REPORT_BASELINE_2026-07-14.md`.
S1–S3 registration: `server/sheets_s1_task.py`, `server/sheets_s2_task.py`,
`server/sheets_s3_task.py` (2026-07-20).
