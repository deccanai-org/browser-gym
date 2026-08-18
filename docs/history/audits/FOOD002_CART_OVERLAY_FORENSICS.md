# FOOD002 Cart Overlay Forensics

**Date:** 2026-08-03  
**Task:** `food_002/reorder_most_frequent_last_month`  
**Prior audit:** `FOOD002_BRIDGED_SOL_SEED0.md` (INCOMPLETE — `never_reached_checkout`)  
**Constraint:** diagnose blank cart overlay; fix if genuine env bug; rebuild `uber_eats_mock` dist; Sol seed 0 once; no ledger/QA; `STACK_SLOT=42` / own PIDs only.

## Verdict

**Genuine GymEats env bug (bridged cart shape crash), not seed-specific cart state.**

After flattening bridged cart lines for `CartPanel` / checkout, Sol seed 0 placed the correct Burger Barn usual (`FOOD-1041`) in **11 steps**, harness **success=True score=1.00**.

## Diagnosis

| Question | Answer |
|---|---|
| Invisible-modal / Tailwind overlay class (like ItemModal §6)? | **No.** `CartPanel` already used plain CSS (`.cart-overlay` / `CartPanel.css`). Overlay positioned correctly. |
| Seed-specific empty / corrupt cart? | **No.** Engine cart held correct `r_burger` + `d_classic` + `d_fries` after Sol adds (prior traj durable + this re-run). |
| Root cause | **Bridged projection shape mismatch → React render crash.** |

### Mechanism

1. Sol correctly adds usual items via `bridgeAct('food.add_to_cart')`.
2. Bridge / `transform_food` re-projects cart lines as nested StoreContext shape:
   `{cartItemId, menuItem:{id,name,price,…}, quantity, modifiers, instructions}`  
   (confirmed on live slot 42 after add: no flat `name` / `selectedOptions` / `totalPrice`).
3. `AppContext.initializeData` deep-merged that projection onto defaults **without** normalizing cart lines.
4. `CartPanel.jsx` assumed flat AppContext lines and did `item.selectedOptions.length` → **TypeError**.
5. No error boundary → React tree white-screens → SoM sees a **blank page with zero marks** (prior Sol burned remaining budget on “blank cart overlay”).

Same class as OrderTracking’s nested `menuItem.name` fix, but for **live agent-built cart** after bridged add (not seeded orders). Distinct from GymEats bug-report §1–§2 (seeded id / qty wiring) and §6 (Tailwind ItemModal).

## Fix (CUA-Gym-Hub `websites/uber_eats_mock`)

Rebuilt `dist` → served `index-BUhAwd-h.js`.

| Change | Purpose |
|---|---|
| `normalizeAppCartItem` / `normalizeAppCart` in `dataManager.js` | Flatten nested bridged lines on every `initializeData` / bridge poll |
| `CartPanel.jsx` | Defense-in-depth normalize; safe options access; `data-test-id="btn-go-to-checkout"` / close aria-label |
| `CheckoutPage.jsx` | Same normalize so Place order shows names/totals |

## Smoke (slot 42)

Path: `trajectories/food_002_cart_overlay_fix/`

- Reset `food_002` seed 0 → bridge-add `d_classic` + `d_fries` → open Cart in Playwright.
- **Before fix class:** nested projection crash. **After:** overlay shows Burger Barn lines + **Go to Checkout** (`SMOKE_OK`).

## Sol re-run (seed 0 only)

| Field | Value |
|---|---|
| Stack | `STACK_SLOT=42` · `STACK_APPS="food"` · gym `:12278` / bridge `:12291` / food `:47403` |
| Model | `openai_pixel[gpt-5.6-sol]` · `AGENT_MAX_STEPS=60` |
| Trajectory | `trajectories/food_002_sol_rerun_cart_overlay_fix/food_002_reorder_most_frequent_last_month__0__12ad9ad5.jsonl` |
| Steps / wall | **11** / ≈68s |
| Harness | **success=True score=1.00** · failure=null |

Path: Account → Orders → April Burger Barn → View Store → add Classic + Fries → **Cart opens with lines** → Go to Checkout → Place order → finish.

| Durable | Result |
|---|---|
| New order | **`FOOD-1041`** Burger Barn · 1× Classic Cheeseburger + 1× Crispy Fries |
| Cart after | empty |
| Recency decoy | not ordered |

## Explicit answers

1. **Bug class:** GymEats bridged cart-line shape crash (env), not seed cart state, not Tailwind-invisible modal.
2. **Fixable?** Yes — fixed + dist rebuilt + smoke + Sol confirm.
3. **Does correct Burger Barn reasoning complete into a real order after fix?** **Yes** — `FOOD-1041` placed; episode success.

## Paths

- Hub: `CUA-Gym-Hub/websites/uber_eats_mock/src/{utils/dataManager.js,components/CartPanel.jsx,pages/CheckoutPage.jsx}`
- Primary trajs: `browser-gym-seed-to-cua-gym/trajectories/food_002_{cart_overlay_fix,sol_rerun_cart_overlay_fix}/`
- Copy: `ecommerce-browser-gym/trajectories/food_002_{cart_overlay_fix,sol_rerun_cart_overlay_fix}/`
- Prior incomplete: `FOOD002_BRIDGED_SOL_SEED0.md`

## Ports / PIDs

`STACK_SLOT=42` via `tools/start_bridged_stack.sh`; cleanup `STACK_SLOT=42 STACK_APPS="food" tools/stop_bridged_stack.sh` (owned ports/PIDs only; stopped after re-run).
