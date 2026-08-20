# mp_031 / housewarming_breville_free_ship_gift — Sol seed 0

**Date:** 2026-08-07  
**Constraint:** new task (Xbay Brand∩Free∩New∩seller + Xoogle deliver-by + Xmail confirm/gift note) → fail-on-initial + bridged oracle → Sol seed 0 only.  
**Model:** `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=80` · headless · `PYTHONUNBUFFERED=1`  
**Stack:** `STACK_SLOT=53` · gym `:13378` · bridge `:13391` · market `:58301` · mail `:58401` · calendar `:58402`  
**Env SHA:** `browser-gym-seed-to-cua-gym` `a9b8e2f` (+ local task/projection patches: `MarketProduct.brand`, address/payment-aware `MarketState`, `mp_031` seed/verifier/oracle)

---

## Verdict

**BREAK** (score **0.60**, success **False**, **47** steps).

Sol checked Xoogle (found Cousin's Housewarming on **June 14**), searched Xbay for Breville, and eventually checked out the **low-rated** free-ship New listing ($679, `DiscountBrew_Outlet` 81.4%) as `VM-2202` — firing `forbidden_low_rated_seller`. Gold SKU was also present as `VM-2201` (appeared mid-search thrash before the agent opened a listing). Gift note went to **Xbay seller Messages** (no cart gift-wrap UI on ebay_mock); confirmation was **forwarded** to alice without gift-message tokens → `confirm_email_with_gift_message` missed.

---

## Task id path

`mp_031/housewarming_breville_free_ship_gift`

SoT: `ecommerce-browser-gym/server/mp_031.py`  
Runner sync: `browser-gym-seed-to-cua-gym/server/mp_031.py` (+ tasks/verifiers/oracle; `MarketProduct.brand` in `transform_market`; merged `MarketState` addresses/payments + seller/condition/shipping/brand)

**Brief (exact):**  
> Put together a housewarming bundle for my cousin, a coffee maker from a brand she actually likes (she only drinks Breville, nothing else), has to ship free, and has to be new, not refurbished, ideally from a seller with decent ratings since it's a gift. Add a gift message but don't bother with gift wrap, she doesn't care about that. I need it to land by the 14th so check my calendar, I think there's a party that weekend. Email me the confirmation once it's placed.

**Gold:** calendar party June 14 → order `mp031_breville_new_free_ontime` (Breville ∩ New ∩ free ship ∩ BrewGear_Official 99.6% ∩ arrives by June 14) → email alice with confirm + gift note (Xbay has no gift-wrap affordance).

**Forbidden:** wrong brand (Cuisinart), Refurbished, paid shipping, low-rated seller, late ETA (arrives after the 14th).

---

## Seed layout

| Surface | Contents |
|---|---|
| **Xoogle** | `Cousin's Housewarming` **2026-06-14** 15:00–18:00; decoys: Monday standup (Jun 15), Dentist (Jun 10) |
| **Xbay gold** | Breville Barista Express · New · `$0` ship · BrewGear_Official **99.6%** · ETA by June 14 · `$699.95` |
| **Decoy brand** | Cuisinart Barista Bar · New · free ship · high rating · on-time ETA |
| **Decoy condition** | Breville · **Refurbished** · free ship · on-time |
| **Decoy shipping** | Breville · New · **`$24.99` ship** · on-time |
| **Decoy seller** | Breville · New · free ship · DiscountBrew_Outlet **81.4%** · on-time · `$679` |
| **Decoy ETA** | Breville · New · free ship · high rating · arrives **June 20–25** |
| **Gift rules** | Gift message required in agent-sent confirm email to alice (tokens: gift message/note, housewarming, cousin, congrats, …). No gift-wrap cart UI on Xbay — wrap cannot be selected. |
| **Mail** | Agent must email confirmation to `alice@shopgym.com` after place (auto inbox confirm alone is insufficient). |

---

## Sol seed 0 disposition

| Field | Value |
|---|---|
| Disposition | **BREAK** |
| Score | **0.60** |
| Success | False |
| Steps | **47** |
| `specific_failure` | `forbidden_low_rated_seller` |
| `agent_failure_class` | `unclassified_failure` |
| Forbidden fired? | **Yes** (`forbidden_low_rated_seller` @33) |

### Milestones

| Milestone | Fired @ | Notes |
|---|---:|---|
| `ordered_breville_new_free_ontime` | 18 | `VM-2201` gold present (appeared @16 during search thrash) |
| `confirm_email_with_gift_message` | — | Forwards of VM-2201/VM-2202 confirms lack gift-note tokens; seller Message ≠ `mail.sent` gift |
| `forbidden_wrong_brand` | — | |
| `forbidden_refurbished` | — | |
| `forbidden_paid_shipping` | — | |
| `forbidden_low_rated_seller` | 33 | `VM-2202` = `$679` DiscountBrew_Outlet |
| `forbidden_late_eta_misses_party` | — | Agent inspected late listing and skipped it |

### Trap?

**Yes — low-rated seller.** Sol correctly used the calendar (June 14), filtered to Breville / New / free shipping, skipped the late-ETA listing, then chose the cheaper on-time free-ship New unit despite **81.4%** seller feedback. Also spent steps hunting cart gift-wrap/message (Xbay has none), messaged the seller instead, and forwarded order confirms without an explicit gift note in the body.

**Note on early gold order:** `VM-2201` (gold) appears in `world_after` at step 16 during search-box Backspace, before any listing open — possible accidental Buy It Now / async checkout during search thrash. Agent later knowingly checked out the low-rated listing as `VM-2202`.

---

## Oracle / fail-on-initial

| Gate | Result |
|---|---|
| Fail-on-initial (verify @ step 0) | score **0.0**, success False, no forbidden |
| Bridged UI oracle seed 0 | score **1.00**, success True, **11** steps |

Oracle traj: `browser-gym-seed-to-cua-gym/trajectories/mp_031_oracle_bridged_seed0_20260807/mp_031_housewarming_breville_free_ship_gift__0__31e82267.jsonl`  
(First oracle attempt scored 0.40 before `MarketState` address/payment merge restored checkout; re-run after fix → 1.00.)

---

## Env / stack health during Sol

- Gym + market/mail/calendar hubs stayed up (HTTP 200) throughout.
- Brand facet: explicit `listing.brand` projected (`Breville` / `Cuisinart`) so coffee titles do not collapse to HomeChef.
- Xbay checkout requires addresses/payments on `MarketState` (merged into runner from address-selection work + seller/condition/shipping/brand fields).
- Stack released: `STACK_SLOT=53 tools/stop_bridged_stack.sh`.

---

## Monitoring notes

- Steps advanced 0→47 (~7.5 min); no stall, no ConnectError / bridge-loss.
- Search thrash early (malformed query / Control+a / Backspace) then recovered with brand-only `Breville` search.
- Agent opened calendar via search for "housewarming" and read Cousin's Housewarming (June 14) before shopping.
- `run_bridged_pilot_wave1.sh` `/bridge/health` hub_source gate 404s on current bridge (E-S002-1); Sol run used `start_bridged_stack.sh` + direct `eval.run`.

---

## Traj path

`browser-gym-seed-to-cua-gym/trajectories/mp_031_sol_bridged_seed0_20260807/mp_031_housewarming_breville_free_ship_gift__0__e666e88e.jsonl`

Log: `browser-gym-seed-to-cua-gym/logs/mp_031_sol_seed0.out`
