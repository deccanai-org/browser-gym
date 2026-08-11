# mp_066–070 non-ShopGym primary — Sol seed0 pack

**Date:** 2026-08-11  
**Model (Sol):** `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=80` · headless GCP ∥5 (seed0 complete)  
**Env:** seed-to-cua tip UI wipe-bake. No CUA-Gym-Hub / no headed browser.  
**Modules:** `server/mp_066.py` … `mp_070.py`, mirrored gym ↔ runner  
**Pack:** `verification_pipeline_tasks/mp066_070_2026-08-11/`  
**Eligible:** **not** added (sibling packing Eligible Suite separately)

---

## Briefs (coaching-free)

| ID | Brief |
|---|---|
| mp_066 | The ValueMart seller says my desk is ready for pickup, but I think that's the wrong week, can you sort it out. |
| mp_067 | Can you sort dinner for game night, check who's coming and what they can eat. |
| mp_068 | I've had my eye on a couch on ValueMart, grab it whenever it's actually the best time to buy. |
| mp_069 | My neighbor's selling her bike stand on ValueMart, she said she'd throw in the helmet too, can you grab it and confirm with her. |
| mp_070 | Order lunch for Thursday's team meeting like usual. |

---

## Mechanisms

### mp_066 / valuemart_seller_dispute_and_calendar_pickup_reschedule
ValueMart Purchases banner **June 14–16** vs ShopMail seller thread **June 21–23**. GymCal conflict **June 22** only inside the true window. Gym clock `2026-06-11`. Gold: report conflict on true window.

### mp_067 / gymeats_group_order_dietary_conflict_reschedule
Mail RSVP thread: Dan cancels, Carol dairy correction, Sunday reschedule. GymCal stale on Saturday. Gold: dairy-free serves-3 pack with `scheduled_delivery=2026-05-24`. `enable_schedule_ahead=True`.

### mp_068 / valuemart_price_watch_vs_gymcal_deadline
Couch $380 (was $450, “may drop further end of month”) vs Move-in **May 26**. Gold: buy now at $380.

### mp_069 / mail_thread_promise_vs_valuemart_listing_reality
Neighbor mail promises helmet; listing is stand-only. Gold: buy stand + email neighbor about discrepancy.

### mp_070 / gymcal_recurring_event_single_instance_food_order
This-Thu one-off **CANCELLED** + weekly series master next Thu (cal_007 pattern). Gold: open instance, abstain, report cancel. **Probe:** both events persist in `CalendarState` and `transform_calendar` projection.

---

## Affordances / harness notes

- `tools/seed_to_cuagym.py`: `currentDate` now follows `calendar.gym_now` (needed for June windows on mp_066).
- ebay_mock: added `data-test-id="btn-buy-it-now"` + `btn-confirm-purchase` (oracle Buy It Now path).
- Bridged ebay Messages tab remains hidden — mp_066 banner uses order `status`; mp_069 follow-up uses ShopMail (durable).

---

## Gates (pre-Sol)

| Gate | Result |
|---|---|
| Fail-on-initial (all five) | **0.0** / success False / no forbidden |
| Discoverability | Banner/mail/cal (066); thread+stale cal+food (067); couch+deadline (068); promise vs listing (069); recurring override durable (070) — **OK** |
| Mutation / durable gold | **1.0** success True for all five |
| Coaching-clause | **Pass** |
| mp_070 override probe | **OK** — instance `recurring=none` + CANCELLED description; series `weekly` from May 28; both in projection |

Script: `verification_pipeline_tasks/mp066_070_2026-08-11/run_gates.py`

---

## Sol seed0 (GCP)

| Field | Value |
|---|---|
| Launch script | `deploy/filtration/scripts/build_and_execute_mp066_070_s0_sol.sh` |
| Manifest | `deploy/filtration/manifests/mp066_070_s0_sol.json` |
| Image | `filtration-worker:mp066-070-s0-20260811T164258Z` |
| Job / exec | `filtration-mp066-070-s0` / `filtration-mp066-070-s0-6fv92` |
| Run ID | `mp066-070-s0-20260811T164258Z` |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp066_070_s0_20260811/mp066-070-s0-20260811T164258Z/` |
| Hub pins | amazon `index-BhWb8Yg1.js`, calendar `index-8e84e2c6.js`, uber `index-DXWw629n.js`, mail `index-D_t66Cxn.js`, ebay `index-K79JnqJB.js` |
| Runner HEAD | `3d7362d06772b58a2fccded8abdfdc8b5ea9451a` |
| Status | **DONE** — Cloud Run 5/5 task pods succeeded (~18m); Sol **1 HOLD / 4 BREAK** |

| idx | task | seed | disposition | score | success | steps | failure | note |
|---|---|---:|---|---:|---|---:|---|---|
| 0 | mp_066/valuemart_seller_dispute_and_calendar_pickup_reschedule | 0 | **HOLD** | **1.0** | True | 43 | — | Clean Sol success |
| 1 | mp_067/gymeats_group_order_dietary_conflict_reschedule | 0 | **BREAK** | 0.2 | False | 80 | `unclassified_failure` | Cap-out; partial progress only |
| 2 | mp_068/valuemart_price_watch_vs_gymcal_deadline | 0 | **BREAK** | **1.0** | False | 32 | `repeated_failed_actions` | Reward 1.0 but filtration marks success=False / BREAK |
| 3 | mp_069/mail_thread_promise_vs_valuemart_listing_reality | 0 | **BREAK** | 0.0 | False | 80 | `never_reached_checkout` | Cap-out; no purchase |
| 4 | mp_070/gymcal_recurring_event_single_instance_food_order | 0 | **BREAK** | 0.4 | False | 80 | `never_reached_checkout` | Cap-out; partial only |

**Cost (sum):** ~$123 API / Luna · no credit deaths · all `valid=true`.

Do **not** auto-Eligible.

---

## Eligible

Added 2026-08-11 as **e14–e17 · seed0 BREAK** (mp_067–070 only). **mp_066 HOLD omitted.**  
See `ELIGIBLE_ADD_MP067_070_BREAKERS_2026-08-11.md`. Coordinated with sibling 3-seed fill (`63f10860`).
