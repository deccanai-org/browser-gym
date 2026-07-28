# Phase C wave-2 (the 20-task doc) — triage BEFORE build (2026-07-10)

Two verifications run (agents, read-only): app-affordance scout vs branch code + canonical vein/novelty.
Nothing built. Renumber = **doc-id + 8** (M315–M334 → **M323–M342**), because M315/M316/M318 are BUILT and
M317/M319–M322 are reserved (PHASE_C_BUILD.md) → M323 is the first free slot.

## App-affordance corrections (doc claims vs actual code)
- ✅ Market coupon logic is as claimed: `expired` + `min_subtotal` + `percent_off`; free-delivery keyed on
  PRE-discount subtotal → the doc's $24.99→$28.48 math (M324/doc) is CORRECT.
- ❌ **ETA is FIXED PER-RESTAURANT** (`Restaurant.eta_label`), NOT per-order/per-dish, and there is NO async
  tracking that can differ from the receipt. → **M320/doc (live-tracking 8:05 ≠ receipt 7:20) is UNBUILDABLE
  as described.** M323/doc (two trays w/ different ETAs) only works if the two trays are TWO DIFFERENT
  restaurants (different eta_labels), not two dishes of one.
- ⚠️ `delivered` is on the WorldEvent wrapper (bus), not in the FoodOrderPlaced payload — verifiers CAN require
  `world.events[].delivered==True`, so M333/M334 gating is fine (clarification, not a blocker).
- ❌ **FLASH25 coupon is not seeded** (only VALUE10); M322/doc must seed its own (tasks do add coupons, ok).
- ✅ Single-restaurant cart guard, Calendar CRUD (update_event NOT overlap-guarded), Mail read/send, fixed date
  2026-05-21 — all confirmed.

## Vein + novelty (canonical mechanism, NOT the doc's labels) — renumbered ids
| new id | doc | true vein | novelty | verdict |
|---|---|---|---|---|
| M323 | M315 food_arrival_empty_window | self-contradiction | RESKIN of M271/M273–275 | DROP |
| M324 | M316 reschedule_preserve_only_time | self-contradiction | new-ish (vs M318) | MAYBE |
| M325 | M317 market_charge_floor_ceiling | self-contradiction *(doc mislabeled infeasibility)* | RESKIN of M270 | DROP |
| M326 | M318 delete_and_keep_calendar_hold | self-contradiction | new-ish | MAYBE |
| M327 | M319 single_order_two_restaurants | tool-affordance *(doc mislabeled infeasibility)* | RESKIN of M131 | DROP |
| M328 | M320 stale_food_eta_calendar_authority | source-anchoring | RESKIN of M299 **+ UNBUILDABLE (ETA)** | DROP |
| M329 | M321 stale_vegan_email_live_menu | source-anchoring | new-ish (menu-attribute surface) | MAYBE |
| M330 | M322 stale_coupon_authority_market | source-anchoring | RESKIN of M299 | DROP |
| M331 | M323 stale_invite_live_calendar_food | source-anchoring | new-ish (needs 2 restaurants) | MAYBE |
| M332 | M324 stale_delivered_price_market | source-anchoring | RESKIN of M228 | DROP |
| M333 | M325 celiac_named_tempura | implicit-constraint | **RESKIN of M255/M253/M311** | DROP |
| M334 | M326 flight_powerbank_limit | implicit-constraint | **RESKIN of M312** (≈dup of M329/doc) | DROP |
| M335 | M327 external_calendar_confidentiality | **data-boundary — NEW** *(doc mislabeled injection; vein-homeless)* | **NOVEL** | BUILD* |
| M336 | M328 fasting_cutoff_food | implicit-constraint (temporal) | **new-ish** (temporal cutoff vs static M252) | BUILD |
| M337 | M329 travel_voltage_mismatch | implicit-constraint | RESKIN of M312 (dup of M334) | DROP |
| M338 | M330 latest_rsvp_threshold | structural (latest-per-sender quantifier) | **NOVEL** | BUILD |
| M339 | M331 scoped_calendar_cleanup | structural | RESKIN of M217 | DROP |
| M340 | M332 allowance_gated_market_checkout | structural (conditional-gate) | new-ish | MAYBE |
| M341 | M333 receipt_eta_conditional_notify | structural (conditional-route) | new-ish | MAYBE |
| M342 | M334 second_order_budget_gate | structural | RESKIN of M340 (its own sibling) | DROP |

**The 3 you flagged:** M333/celiac = RESKIN of M255 (named product + implied health constraint + safe alt —
identical). M334/powerbank = RESKIN of M312 (named item violates a spec + false "already checked"). M336/fasting
= genuinely new-ish (TEMPORAL cutoff derived by comparing ETA to a stated time, vs M252's static label).

## Recommendation
- **DROP the 11 reskins** (above).
- **BUILD (genuinely novel):** M338 (latest-per-sender quantifier, structural), M336 (temporal fasting cutoff,
  implicit-constraint), M335 (data-boundary/redaction — but it needs a **vein decision first**: it's not injection
  and has no canonical vein token; either mint a new "confidentiality/data-boundary" vein or map it).
- **MAYBE (marginal, grows the thin veins):** M324 + M326 (self-contradiction), M340 + M341 (structural),
  M329 + M331 (source-anchoring on a fresh surface; M331 needs 2 restaurants).
- Net: the doc's "20 novel" is really **~3 clearly-new + ~6 marginal + 11 reskins**, with 1 unbuildable-as-described.
