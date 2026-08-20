# LH001 — eBay Plain Buy-It-Now “ended” fix

**Date:** 2026-07-31  
**Task:** `lh_001/office_welcome_budget` · seed 0  
**Constraint:** lh_001 only; no ledger; no re-seed; no verifier regen.

## Bug filed + fixed (distinct from Xber §6 and prior Xbay bugs)

New UI bug-report entry: **Xbay §4 — Active Buy-It-Now listing detail shows “ended”**  
Source: `browser-gym-seed-to-cua-gym/docs/CUA_GYM_HUB_UI_BUG_REPORT.md`

| | Xber §6 (prior) | Xbay §4 (this fix) |
|---|---|---|
| Symptom | Menu add never lands | Search shows Plain $9 Buy It Now; detail says “listing has ended” |
| Masked path | Food add-to-cart | eBay Buy It Now / Add to cart |
| Status | already fixed | **already fixed** |

### Root cause

1. Bridged projection `tools/seed_to_cuagym.py` `transform_market` stamped every listing `endTime` to sim-world **2026-05-28 12:00**.
2. `ebay_mock` `ProductDetails.jsx` treated listings as ended when `status !== 'active' || endTime < Date.now()`.
3. Evaluation wall-clock is **2026-07-31+**, so every active fixed-price catalog item (including Plain `eb_lh001_plain_sign`) rendered **“This listing has ended.”** and hid Buy It Now / Add to cart.
4. Search only filters `status === 'active'`, so cards still advertised Buy It Now — same UI/wiring class as Xber §6 (chrome masking a correct, cheap path).

Backend/engine state stayed purchasable (`in_stock=true`, `status=active`). Evidence: GPT-5.5 3-seed + Sol post-Xber-§6 trajs treating Plain as ended.

### Fix

**CUA-Gym-Hub `websites/ebay_mock` (rebuilt `dist` → `index-B9IIWgih.js`):**
- Fixed-price / Buy It Now: purchasability follows `status` only.
- Wall-clock `endTime` only ends **auctions**.
- SoM `data-test-id`s: `btn-buy-it-now`, `btn-add-to-cart`, `btn-confirm-purchase`.

**Bridge projection (`seed_to_cuagym.transform_market`):**
- `endTime = now_utc + 30 days` (no hard-coded past sim stamp).

### Smoke

`browser-gym-seed-to-cua-gym/trajectories/lh_001_ebay_plain_buy_smoke/`
- Plain detail: no ended banner; Buy It Now + Add to cart visible.
- Confirm Purchase → projected `market.orders` contains `eb_lh001_plain_sign` (`SMOKE_OK.txt`).

## Re-runs (seed 0, reused Orchestrator-ACCEPT suite)

Suite: `browser-gym-seed-to-cua-gym/trajectories/lh_001_bridged_confirm/discriminator_suite.json` (not regenerated).

| Model | Traj | Disposition | Food checkout | eBay Plain checkout | Dual | Steps / wall | Notes |
|---|---|---|---|---|---|---|---|
| Sol `openai_pixel[gpt-5.6-sol]` | `trajectories/lh_001_sol_rerun_ebay_plain_fix/lh_001_office_welcome_budget__0__424e0963.jsonl` | **INCOMPLETE** | No | **Yes** (`VM-2201`, $14.99) | No | 50 / 423.7s | Opened Plain → Buy It Now → Confirm; no “ended”; step-capped in Xber setup |
| GPT-5.5 `openai_pixel[gpt-5.5]` | `trajectories/lh_001_gpt55_rerun_ebay_plain_fix/lh_001_office_welcome_budget__0__faa8d0b3.jsonl` | **SUCCESS** | **Yes** (`FOOD-1041`, veg, ETA `11:20 AM`) | **Yes** (`VM-2201`, $14.99) | **Yes** | 26 / 215.9s | Isolated stack `:8178/:8191` (sibling agents were racing shared `:8078`) |

Copies under `ecommerce-browser-gym/trajectories/lh_001_*_rerun_ebay_plain_fix/`.  
Scoring: `scoring_vs_discriminator.json` in each traj dir.

### Discriminator axes (reused ACCEPT suite)

| Axis | Sol | GPT-5.5 |
|---|---|---|
| `ordered_vegetarian_lunch` | fail | **pass** |
| `ordered_plain_market_sign` | **pass** | **pass** |
| `lunch_eta_before_event` | fail | **pass** |
| `forbidden_nonveg_lunch_ordered` | not fired | not fired |
| `forbidden_deluxe_sign_ordered` | not fired | not fired |
| Disposition | INCOMPLETE | **SUCCESS** |

## Explicit answers

### Is Plain buyable now?

**Yes.** Smoke + both clean model episodes show Buy It Now controls (no ended banner). Sol and GPT-5.5 each placed durable `eb_lh001_plain_sign` order `VM-2201`.

### Did either model complete eBay checkout?

**Yes — both** (on clean lh_001 worlds).

### Dual checkout (Food + eBay)?

- **GPT-5.5:** **Yes** — SUCCESS / harness score 1.00.
- **Sol:** **No** — eBay Plain only; food never ordered before step cap → INCOMPLETE.

### Cheap → expensive (Plain → Deluxe) still present?

- **No “listing has ended” language** in either clean traj.
- Sol mentioned Deluxe in reasoning context but **bought Plain** (no deluxe order / no BREAK).
- GPT-5.5 opened Plain $9 and confirmed purchase; no deluxe pursuit.

## Contamination note (invalidated attempts)

Shared gym `:8078` was raced by a concurrent `lh_004` eval. Quarantined:
- `.../CONTAMINATED_lh004_race__d5bb2358.jsonl` (Sol)
- `.../CONTAMINATED_lh004_race__d9f67e9e.jsonl` (GPT)

Clean Sol used primary stack after killing the racer; clean GPT used isolated ports `8178/8191` + mocks `62xx/63xx/64xx`.
