# mp_060 Friday rewrite — Eligible e9

**Date:** 2026-08-11  
**Task:** `mp_060/cousin_dinner_email_calendar_schedule` (Eligible **e9**)  
**Change:** Rewrite uniqueness from Thursday-gold / Fri Team-sync to **Friday-only** dinner with vegetarian + for-two + under-$30 constraints.

## Uniqueness proof (dates)

| Day | Date | Constraint |
|---|---|---|
| Thu | `2026-05-21` | Gym clock noon; **Dentist cleaning 15:00–16:00** (distract — calendar open required) |
| Fri | `2026-05-22` | Jamie arrives midday; evening open; **no Alice calendar conflict** (Team sync removed) → **sole valid dinner night** |
| Sat | `2026-05-23` | Pottery **1–8pm**; dinner-hours overlap arithmetic (13:00–20:00 ∩ 18:00–21:00 = 120 min) → unavailable |
| Sun | `2026-05-24` | Morning departure → no evening dinner |

## Veg / for-two scoring decision

1. **Vegetarian:** GymEats `Dish.tags` is a real scorable field. Gold + veggie bowl carry `vegetarian`; steak trap carries `meat`. Milestone `ordered_vegetarian_dinner_for_two` resolves tags via restaurant menu lookup on durable order line `dish_id`. **No dish-name-only fallback needed** (name fallback retained only if dish missing from menu).
2. **For two:** Durable on `FoodCartItem.quantity` / order lines — **qty ≥ 2**, or named portion (`for two` / `for 2` / `serves 2`), or total veg qty across lines ≥ 2. Gold path uses named **Vegetarian Dinner for Two** at $26.50 + $2.49 fee = **$28.99 < $30**. Alternate: 2× Harvest Veggie Bowl = $26.49.

## Milestones

**Required:** `read_full_cousin_email` (0.2), `identified_saturday_unavailable_from_time_range` (0.2), `checked_own_calendar_confirmed_friday_clear` (0.15), `selected_friday_as_correct_night` (0.15), `ordered_vegetarian_dinner_for_two` (0.15), `order_total_under_30` (0.15).

**Forbidden:** `ordered_on_saturday_conflict_night`, `ordered_non_vegetarian_item`, `order_total_over_30`, `order_defaulted_to_asap_despite_future_pick`.

## Pre-launch gates

Script: `verification_pipeline_tasks/mp060_friday_rewrite_2026-08-11/run_gates.py` (gym + runner) — **ALL PASS**.

- Coaching-clause: clean (veg/budget/for-two in brief; no night coaching).
- Discoverability: email Fri midday / Sat 1–8pm pottery / Sun morning; Thu dentist + Fri clear; schedule-ahead Fri slot; veg+budget+qty path.
- FOI 0.0; mutation-oracle gold 1.0; Sat / non-veg / over-budget / ASAP forbiddens fire.

## Seed email

From **Jamie Anderson**, subject `omg can't wait!!` — arrival Friday midday, pottery Saturday 1–8pm, Sunday morning departure (no explicit “dinner Saturday will NOT work” coaching).

## Prompt (verbatim)

> My cousin Jamie is visiting for a long weekend and I want to plan something nice. Check the email she sent, see what days work around my calendar, and get a vegetarian dinner for two under 30 dollars for whichever night makes sense.

## Sol seed0 (GCP tip-UI)

- Tip-UI only; `enable_schedule_ahead=True`; no headed local.
- Deploy: `browser-gym-seed-to-cua-gym/deploy/filtration/scripts/build_and_execute_mp060_sol_seed0.sh`
- **Execution:** `filtration-mp060-sol-seed0-jgsrp`
- **RUN_ID:** `mp060-sol-seed0-20260811T204033Z`
- **GCS:** `gs://gemini-503300-filtration-runs/filtration/mp060_friday_rewrite_20260811/mp060-sol-seed0-20260811T204033Z/`
- **Episode:** `mp_060_cousin_dinner_email_calendar_schedule__0__2a4f61fe`
- **Disposition:** **HOLD** · score **1.0** · success True · **59** steps
- **Path:** read Jamie email + calendar → two× Harvest Veggie Bowl (`d_mp060_veggie_bowl` qty 2) scheduled `2026-05-22`, durable total **$24.00**

## Notes vs prior narrative

Prior e9 / DB_DIFF framed **Thursday** gold and **Saturday** as the primary Sol trap with Fri Team sync. Those narratives are superseded by this rewrite — prefer this audit over `DB_DIFF_REPORT_MP060_2026-08-11.md` / old Saturday-as-wrong Thursday-gold copy for e9.
