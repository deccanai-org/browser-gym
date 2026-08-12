# mp_066–070 non-ShopGym primary — Sol seed0 pack

**Date:** 2026-08-11  
**Model (Sol):** `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=80` · headless GCP ∥5 (launch prepared)  
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
| Hub pins (pre-build) | amazon `index-BhWb8Yg1.js`, calendar `index-8e84e2c6.js`, uber `index-DXWw629n.js`, mail `index-D_t66Cxn.js`, ebay `index-K79JnqJB.js` |
| Status | **BLOCKED** — `gcloud builds submit` failed: auth token refresh requires interactive `gcloud auth login` (ADC also stale; Docker daemon not running for local image push) |

### Re-launch after reauth

```bash
gcloud auth login
bash /Users/maroonferrari/Deccan/browser-gym-seed-to-cua-gym/deploy/filtration/scripts/build_and_execute_mp066_070_s0_sol.sh
```

Fill Sol table + GCS paths here after the job completes. Do **not** auto-Eligible.

---

## Eligible

**Not** auto-added. Coordinate with sibling Eligible pack (`2e56019c`) — they own site push.
