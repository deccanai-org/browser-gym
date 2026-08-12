# mp_031 / housewarming_breville_free_ship_gift — redesigned email-party Sol seed 0

**Date:** 2026-08-07  
**Mechanism:** brief false-anchors deliver-by **the 14th**; agent must open party-invite email (real party **June 11**). Gold = best-rated Breville ∩ New ∩ free ship ∩ arrives before June 11; confirm email includes gift note **and** earlier-date correction.  
**Model:** `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=80` · headless  
**Stack:** `STACK_SLOT=20` · gym `:10078` · bridge `:10091` · market `:25301` · mail `:25401` · calendar `:25402`  
**Env SHA (gym HEAD at pack time):** `b8e3a80ee6b562590ed551850751c6a1af1f6038`  
**Runner:** `browser-gym-seed-to-cua-gym` (+ local `mp_031` sync)

---

## Verdict

**PASS** (score **1.00**, success **True**, **42** steps).

Sol opened the birthday invite email first (June 11), ordered gold `mp031_breville_new_free_ontime` / `VM-2201` (BrewGear_Official 99.6%, New, free ship, on-time for June 11), messaged the seller a gift note (no wrap UI), and emailed alice a confirmation that also disclosed the party is sooner than the 14th.

---

## Gates before Sol

| Gate | Result |
|---|---|
| Fail-on-initial | score **0.0**, success False, no forbidden |
| Bridged UI oracle seed 0 | score **1.00**, success True, **11** steps (`mp_031_oracle_email_party_20260807`) |

---

## Sol seed 0 disposition

| Field | Value |
|---|---|
| Disposition | **PASS** |
| Score | **1.00** |
| Success | True |
| Steps | **42** |
| `specific_failure` | — |
| Forbidden fired? | **No** |

### Milestones

| Milestone | Fired @ | Notes |
|---|---:|---|
| `ordered_breville_best_rated_before_party` | 25 | `VM-2201` = gold SKU |
| `confirm_email_gift_and_earlier_date` | 41 | Confirm to alice + gift note + earlier-date language |
| `forbidden_wrong_brand` | — | |
| `forbidden_refurbished` | — | |
| `forbidden_paid_shipping` | — | |
| `forbidden_low_rated_seller` | — | |
| `forbidden_late_for_email_party` | — | |
| `forbidden_confirm_omits_earlier_date` | — | |

### Behavior notes

- Step 0–1: switched to Mail and opened Cousin Maya’s birthday invite (email authority, not calendar).
- Skipped late-for-party decoy after inspecting listings; selected BrewGear_Official best-rated free-ship New unit.
- Gift message went via ValueMart seller Messages (no cart gift-wrap affordance); confirm still carried gift-message tokens for the verifier.
- Finish reason cited June 11 delivery and order `VM-2201`.

---

## Traj path

`browser-gym-seed-to-cua-gym/trajectories/mp_031_sol_email_party_20260807/mp_031_housewarming_breville_free_ship_gift__0__18c8f186.jsonl`

Log: `browser-gym-seed-to-cua-gym/logs/mp_031_sol_email_party.out`

Oracle traj: `trajectories/mp_031_oracle_email_party_20260807/mp_031_housewarming_breville_free_ship_gift__0__514f15e5.jsonl`
