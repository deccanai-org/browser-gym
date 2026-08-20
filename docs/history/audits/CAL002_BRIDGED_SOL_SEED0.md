# CAL002 Bridged Sol Seed0 — conditional_lunch_hold_cancel

**Date:** 2026-08-02  
**Task:** `cal_002/conditional_lunch_hold_cancel`  
**Constraint:** seed → oracle → Disc ACCEPT + minimal-diff → Sol seed 0 only; diagnose before scale; no ledger/QA.  
**Apps:** Calendar × Xber (Food).

## Hub map (exclusive ports)

| Role | Bridged hub | Port |
|---|---|---|
| Gym / harness | — | **11778** |
| Bridge | — | **11791** |
| Calendar | `google_calendar_mock` | **11801** |
| Food | `uber_eats_mock` (Xber) | **11811** |

`STACK_SLOT=37` + `STACK_PORT_OVERRIDES=1`; `STACK_APPS="calendar food"`.

## Brief

> My Xber lunch is taking forever. If I still have a Client lunch block on my calendar today, cancel the food order and delete that hold so my afternoon's free. If the hold's already gone, leave the order alone.

## Mechanism

Conditional cancel (mp_019-style gate on Calendar): hold present → cancel preparing Xber order **and** delete Client lunch; leave Team lunch decoy + delivered order intact.

## 1. Seed + UI (env gate)

- Snapshots: `browser-gym-seed-to-cua-gym/seed_snapshots/cal_002__conditional_lunch_hold_cancel/seed0_{initial,final}.json`
- Evidence: `trajectories/cal_002_bridged_confirm/seed_ui_evidence.json`

| Surface | Result |
|---|---|
| calendar week | Client lunch **True**; Team lunch **True** |
| Xber order | active id **True**; `btn-cancel-food-order` / Cancel order **True**; preparing **True** |

**Env gate: PASS** (Xber cancel affordance present).

## 2. Oracle / golden

- Mutations: `cancel_food_order(FOOD-CAL002-ACTIVE)` + `delete_event(ev_cal002_client_lunch)`
- Hand suite on golden: **PASS**
- Solver: `solve_cal_002_conditional_lunch_hold_cancel`

## 3. Discriminator + Orchestrator

- First structural suite REJECT: `state_empty` on deleted event id fails-closed when key is absent
- Repair: `state_len_eq` calendar.events==1 for hold deleted; forbidden over-delete via length==0
- Orchestrator: **ACCEPT** after repair
- Artifact: `trajectories/cal_002_bridged_confirm/discriminator_suite.json`

## 4. Sol seed 0

| Field | Value |
|---|---|
| Trajectory | `trajectories/cal_002_bridged_confirm/cal_002_conditional_lunch_hold_cancel__0__70b12ce5.jsonl` |
| Screenshots | `screenshots/cal_002_bridged_confirm/cal_002_conditional_lunch_hold_cancel__0__70b12ce5/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=50 · wall≈379s |
| Harness | success=False score=0.0 failure=`never_reached_checkout` |

Durable final: Client lunch still present; `FOOD-CAL002-ACTIVE` still `preparing`; Team lunch + delivered order intact.

## 5. Scoring / diagnosis

- **Disposition: INCOMPLETE**
- Disc on Sol final: correctness FAIL; forbidden_veto=False
- Env vs agent: **(b) Sol lost on working env** — found Client lunch via search/Day thrash but never opened edit→delete and never navigated to Xber cancel. Cancel button confirmed in seed UI.
- **STOP** — no scale.

Detail: `trajectories/cal_002_bridged_confirm/scoring_report.json`

## 6. Cap-80 Sol seed 0 re-run (2026-08-02)

| Field | Value |
|---|---|
| Cap | **80** (was 50) |
| Ports | same slot **37** · gym **11778** / bridge **11791** / cal **11801** / food **11811** |
| Suite | reused `trajectories/cal_002_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_002_cap80_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__b6f64e5d.jsonl` |
| Screenshots | `screenshots/cal_002_cap80_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__b6f64e5d/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**1** · wall≈15s |
| Harness | success=False score=0.0 failure=`never_reached_checkout` |

Durable final unchanged: Client lunch still present; `FOOD-CAL002-ACTIVE` still `preparing`; Team lunch + delivered intact.

### Diagnosis

- **Disposition: still INCOMPLETE** (no BREAK / no SUCCESS)
- Disc on Sol final: correctness FAIL; forbidden_veto=False
- Cap raise **not exercised** — agent clicked hub **Today**, landed on wall-clock **Aug 2026** week (blank), concluded the hold was already gone, and `finish`ed. Seed hold remains on gym frozen **Thu May 21**.
- Env vs agent: still **(b) agent miss on working env** (date/nav confusion → false abstain); not a step-budget stall.

Detail: `trajectories/cal_002_cap80_sol_seed0/scoring_report.json`
