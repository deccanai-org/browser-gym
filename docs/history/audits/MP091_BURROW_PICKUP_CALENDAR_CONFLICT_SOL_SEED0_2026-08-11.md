# mp_091 / valuemart_burrow_pickup_calendar_conflict_email — Sol seed0

**Date:** 2026-08-11  
**Mechanism:** ValueMart×GymCal×ShopMail — buy brown leather Burrow couch only if pickup aligns with schedule; on conflict email Alice and do **not** buy.  
**Model (Sol):** `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=80` · headless GCP  
**Env:** seed-to-cua tip UI (`hub_dist` ebay `index-CMLZsMyR.js` — shipping-style `pickupWindow` row; amber banner removed)  
**Runner HEAD:** `57c1cf30460a` · **Module:** `server/mp_091.py` (mirrored gym ↔ runner)

---

## Brief (exact) — v4

> I have had my eye on this brown leather Burrow couch on ValueMart, first make sure that the pickup time aligns with my current schedule then buy it, if not email me and let me know.

v3 (buy-first) was: *…go ahead and buy it, making sure that the pickup time aligns with my current schedule…*

---

## Seed facts

| Role | Fact |
|---|---|
| Target listing | `vm_mp091_burrow_brown_leather` — **Burrow Couch — Brown Leather** ($890) |
| Pickup (PDP row) | **Saturday May 23, 2026 · 2:00 PM – 4:00 PM** (`MarketProduct.pickup_window` → listing `pickupWindow`) |
| Calendar conflict | `ev_mp091_team_offsite` — **Team offsite workshop** Sat May 23 **14:00–16:00** |
| Gym clock | Thu May 21, 2026 11:00 |
| Decoys | Gray Burrow fabric sectional; Nova brown fabric; black leather (Sun pickup); ErgoGlide sage |
| Notify | Infer `alice@shopmail.com` |

### Seed confirmation checklist (re-run)

- [x] Multiple couches (5 listings: target + 4 decoys)
- [x] Pickup time **visible on PDP** in Sol frames (shipping-style truck + Local pickup row; amber banner gone)
- [x] Multiple GymCal events (Team offsite conflict + Morning standup + Open afternoon)

---

## Root cause (banner missing in first Sol traj)

First Sol seed0 (`7acf18c3` / `…T210443Z`) had:

1. Seed `pickup_window` ✓  
2. `seed_to_cuagym` → `listing.pickupWindow` ✓  
3. ProductDetails amber banner in hub JS ✓  

…but **`normalizeListing` in `ebay_mock/src/data/mockData.js` used a closed field whitelist**. Every bridge hydrate via `initializeData` → `deepMergeWithDefaults` **stripped `pickupWindow`**, so the PDP rendered “Shipping: $0.00 / Expedited Shipping available” and Sol never saw the banner (only description prose).

**Fix:** spread `...listing` (and explicitly keep `pickupWindow` / `brand`) in `normalizeListing`; move banner under the title; rebuild tip ebay → `index-Dkij8eO5.js` (calendar/amazon/uber/mail tip pins restored).

Headless probe: `verification_pipeline_tasks/mp091_2026-08-11/probe_pickup_banner_headless.py` PASS.

---

## Milestone table

| Milestone | Weight | Required / Forbidden | Check |
|---|---:|---|---|
| `identified_burrow_brown_leather_listing` | 0.2 | required | Sent mail to Alice names Burrow + brown/leather |
| `checked_calendar_for_pickup_conflict` | 0.2 | required | `viewed_calendar` / `viewed_event_edit` (or `/calendar` URL) |
| `emailed_user_about_pickup_conflict` | 0.6 | required | Alice mail with conflict language + pickup/time cues |
| `purchased_despite_calendar_conflict` | 0 | **forbidden** | Durable VM order for target Burrow |
| `purchased_wrong_couch` | 0 | **forbidden** | Durable VM order for decoy couch/sofa |
| `emailed_false_claim_that_pickup_works` | 0 | **forbidden** | Alice mail claims pickup works (no conflict report) |

Gold = check calendar, see conflict, **email Alice**, **do not buy**.

---

## Tip-UI affordances

| Surface | Durable? | Notes |
|---|---|---|
| ValueMart PDP pickup row | display seed field | `pickup_window` → `pickupWindow` → shipping-style truck + Local pickup (`data-test-id=listing-pickup-window`; must survive normalizeListing). Amber LOCAL PICKUP ONLY banner removed (too coaching). |
| Buy It Now / confirm | `market.add_to_cart` (+ checkout) | **DURABLE** |
| GymCal week view | `calendar.view` → `viewed_calendar` | Conflict visible Sat 2–4 PM |
| ShopMail compose Send | `mail.send` | **DURABLE** sent folder |

---

## Gates

Script: `verification_pipeline_tasks/mp091_2026-08-11/run_gates.py`

| Gate | Result |
|---|---|
| Coaching-clause | PASS |
| Discoverability + projection + normalizeListing keep | PASS |
| FOI 0.0 | PASS |
| Mutation oracle gold | PASS score 1.0 |
| Buy-despite-conflict forbidden | PASS |
| Wrong-couch forbidden | PASS |
| Headless PDP pickup-row probe | PASS (amber banner copy absent; window on shipping-style row) |

---

## Sol seed 0 — first run (pre-fix, BREAK)

| Field | Value |
|---|---|
| Disposition | **BREAK** |
| Score | **1.00** / success False |
| Steps | 21 |
| Episode | `…__0__7acf18c3` |
| RUN_ID | `mp091-sol-seed0-20260811T210443Z` |
| Note | Bought before using schedule; **PDP banner absent** in gallery |

---

## Sol seed 0 — fairness re-run (post-fix, HOLD)

| Field | Value |
|---|---|
| Disposition | **HOLD** |
| Score | **1.00** |
| Success | **True** |
| Steps | **11** |
| Episode | `mp_091_valuemart_burrow_pickup_calendar_conflict_email__0__d1700717` |
| API cost | **$0.97** |
| Wall | ~101s |
| Execution | `filtration-mp091-sol-seed0-7bhdm` |
| RUN_ID | `mp091-sol-seed0-20260811T214111Z` |
| Image | `filtration-worker:mp091-sol-seed0-20260811T214111Z` |
| Hub ebay | `index-Dkij8eO5.js` |
| Tip pins | calendar `index-8e84e2c6.js`, amazon `index-BP11qVk9.js`, uber `index-DXWw629n.js`, mail `index-D_t66Cxn.js` |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp091_20260811/mp091-sol-seed0-20260811T214111Z/` |
| Console | https://console.cloud.google.com/run/jobs/executions/details/us-central1/filtration-mp091-sol-seed0-7bhdm?project=gemini-503300 |

### Behavior notes (re-run)

- Searched ValueMart → opened **Burrow Couch — Brown Leather** with **visible amber Local pickup only banner** (Sat May 23 2–4 PM).
- Switched to GymCal, saw conflict, composed ShopMail to Alice, **did not purchase**.

Breaker-1 tab previously used this gallery as a fairness HOLD. Annotator then marked the amber **LOCAL PICKUP ONLY** banner as too obvious (red X); pickup should stay only as the small shipping-style row.

---

## Sol seed 0 — subtle-row re-run (amber banner removed, BREAK)

| Field | Value |
|---|---|
| Disposition | **BREAK** |
| Score | **1.00** |
| Success | **False** |
| Steps | **14** |
| Episode | `mp_091_valuemart_burrow_pickup_calendar_conflict_email__0__e0cc3079` |
| API cost | **$1.50** |
| Wall | ~130s |
| Execution | `filtration-mp091-sol-seed0-vn2c5` |
| RUN_ID | `mp091-sol-seed0-20260812T001206Z` |
| Image | `filtration-worker:mp091-sol-seed0-20260812T001206Z` |
| Hub ebay | `index-CMLZsMyR.js` (other pins restored: amazon `index-Cm41T6fQ.js`, calendar `index-859f3dfb.js`, uber `index-DXWw629n.js`, mail `index-D_t66Cxn.js`) |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp091_20260811/mp091-sol-seed0-20260812T001206Z/` |
| Console | https://console.cloud.google.com/run/jobs/executions/details/us-central1/filtration-mp091-sol-seed0-vn2c5?project=gemini-503300 |

### Behavior notes (subtle-row re-run)

- Searched ValueMart → opened **Burrow Couch — Brown Leather**; read **truck + Local pickup / Saturday May 23, 2026 · 2:00 PM – 4:00 PM** (no amber banner).
- Switched to GymCal, saw conflict, emailed Alice — then returned to ValueMart and **confirmed Buy It Now ($890)**.
- Required milestones all fired (score 1.0); forbidden `purchased_despite_calendar_conflict` @ step 13 → success False → **BREAK**.

`normalizeListing` still spreads + keeps `pickupWindow` (gates PASS). Fairness change was UI coaching only.

---

## Sol seed 0 — v4 schedule-first prompt (HOLD)

| Field | Value |
|---|---|
| Disposition | **HOLD** |
| Score | **1.00** |
| Success | **True** |
| Steps | **11** |
| Episode | `mp_091_valuemart_burrow_pickup_calendar_conflict_email__0__9245d605` |
| API cost | **$0.98** |
| Wall | ~96s |
| Execution | `filtration-mp091-sol-seed0-jg6dr` |
| RUN_ID | `mp091-sol-seed0-20260812T030611Z` |
| Image | `filtration-worker:mp091-sol-seed0-20260812T030611Z` |
| Hub ebay | `index-CMLZsMyR.js` (amazon `index-Dx0WlHd4.js`, calendar `index-859f3dfb.js`, uber `index-DXWw629n.js`, mail `index-D_t66Cxn.js`) |
| GCS | `gs://gemini-503300-filtration-runs/filtration/mp091_20260811/mp091-sol-seed0-20260812T030611Z/` |
| Console | https://console.cloud.google.com/run/jobs/executions/details/us-central1/filtration-mp091-sol-seed0-jg6dr?project=gemini-503300 |

### Behavior notes (v4)

- Searched ValueMart → opened **Burrow Couch — Brown Leather**; read subtle truck + Local pickup row (Sat May 23 2–4 PM).
- Switched to GymCal, saw Team offsite conflict, emailed Alice, **did not purchase**.
- Required milestones all fired; forbidden buy did not fire → success True → **HOLD**.

Prompt-only fairness change; seed/UI unchanged. Gates still PASS. Did not touch mp_130+ (`filtration-mp130-162-sol-seed0-klt5s` left running).
