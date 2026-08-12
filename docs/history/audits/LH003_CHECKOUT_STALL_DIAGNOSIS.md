# LH003 checkout-stage stall diagnosis (Sol seed 0)

**Date:** 2026-07-31  
**Task:** `lh_003/bea_cy_birthday_gifts` · seed 0 · `openai_pixel[gpt-5.6-sol]`  
**Source traj:** `trajectories/lh_003_shopmail_fix_rerun/lh_003_bea_cy_birthday_gifts__0__831f24c3.jsonl`  
**Prior audit:** [`LH003_SOL_SEED0_AFTER_SHOPMAIL.md`](./LH003_SOL_SEED0_AFTER_SHOPMAIL.md)  
**Constraint:** ShopMail §4 kept live; dedicated ports; no ledger/QA; no IDE; no broad pkill.

## Verdict

| Question | Answer |
|---|---|
| Env friction (address form / Gmail-row class)? | **No** |
| Step budget? | **Yes** — primary cause of original stall |
| Disposition after `AGENT_MAX_STEPS=80` re-run | Still **INCOMPLETE** (stall moved; no order) |

**Clear call: budget, not address-form env bug.** Sol selected Visa, then abandoned place-order to add Portland/Akron; the 50-step cap ended on `+ Add new address` before any address typing. Raising the cap proves the address form accepts input; the episode still dies on native cart date controls without placing an order.

---

## Q1 — Visa select vs address-field entry?

**Visa was correctly selected; place-order was never attempted. Address fields were never filled in the original episode.**

Walk of `831f24c3` near checkout (screenshots under  
`browser-gym-seed-to-cua-gym/screenshots/lh_003_shopmail_fix_rerun/…/831f24c3/`):

| Step | Action | UI / world |
|---|---|---|
| 43 | Proceed to checkout | `/checkout` |
| 44 | **Use this address** (home / Brooklyn) | Shipping ✓ — Alice, 100 Park Ave |
| 45 | **Use this payment method** | Payment ✓ — **Visa ****4242** (default, expires 06/26); review shows socks + mug; Place your order visible |
| 46 | **Change** (shipping) | Leaves review; reopens address step (home still only option) |
| 47 | Your Account | `/profile` |
| 48 | Your Addresses | Only `addr_home` |
| 49 | **+ Add new address** | Empty add-address form visible; **episode ends** (`steps=50`) |

World after step 45–49: `addresses={addr_home}` only, `orders={}`, cart still 2 items. No Portland/Akron typing occurred. Failure class: `repeated_failed_actions` (harness), score 0.

So this is **not** “failed earlier in address-field entry.” It is **Visa confirmed → notice wrong ship-to → leave checkout to add addresses → hit cap.**

---

## Q2 — UI friction vs step budget?

**Step budget**, after correct-but-slow pre-checkout work — not Gmail-row SoM friction.

### Phase spend (`831f24c3`, 50 steps / ~395s)

| Phase | Steps (approx) | Notes |
|---|---|---|
| Calendar search thrash | **13** (0–12) | Bea/Cy search cleanup |
| Mail (address bodies) | **4** (13–16) | Cy + Bea current opened via `mail-item-` SoM; stale unread |
| Cart / ship-to probe | ~7 (17–20, 24, …) | Dropdown only shows Default |
| Native **scheduled-delivery date** fights | **~19** (21–42) | Segmented date control loops |
| Checkout payment path | **4** (43–46) | Address → Visa → Change |
| Address nav | **3** (47–49) | Profile → Addresses → Add new |

Mail verification was efficient once ShopMail §4 was live. The budget was consumed mainly by **calendar search + native date fields**, then checkout discovery that only home ship-to exists.

### Hub bug report check

[`CUA_GYM_HUB_UI_BUG_REPORT.md`](../../CUA_GYM_HUB_UI_BUG_REPORT.md):

- ShopMail inbox open/select (§4): **already fixed** — confirmed live (`index-CH0zBepB.js` / `mail-item-`).
- ShopGym gift/ship-to/checkout: **already fixed**.
- **No** open Amazon “address-add form won’t accept input” / Gmail-row-class bug for Profile address fields.

Address inputs in `amazon_mock` `Profile.jsx` are ordinary controlled `<input>`s (no missing SoM `role`/`data-test-id` pattern like the old mail rows). Cap-80 re-run (below) confirms they type and save.

---

## Intervention: raise step cap (no env fix)

No address-form env fix. Same experiment proposed for lh_004-style budget stalls: raise `AGENT_MAX_STEPS` and re-run once.

| | Value |
|---|---|
| Cap | **80** (was 50) |
| Ports | gym **9478** / bridge **9491** / Amazon **15203** / Gmail **15401** / Cal **15501** (`STACK_SLOT=14` + overrides; ShopMail live) |
| Out | `trajectories/lh_003_checkout_stall_cap80/` |
| Traj | `lh_003_bea_cy_birthday_gifts__0__31961833.jsonl` |
| Wall / steps | ~715s / **80** |
| Harness | success=False score=0.0 `never_reached_checkout` |

### What the higher cap unlocked

| Milestone | Cap 50 (`831f24c3`) | Cap 80 (`31961833`) |
|---|---|---|
| Open Cy / Bea current mail | Yes | Yes |
| Select Visa mid-checkout | Yes (then abandon) | Did not re-reach payment (stayed on cart after address work) |
| Type Portland / Akron | **No** (cap on form open) | **Yes** — both saved |
| Durable addresses | still `addr_home` only | `addr_home` + Bea Portland `88 Cedar Avenue` + Cy Akron `9 Maple Row` |
| Orders | 0 | **0** |
| Stall locus | Add-address click | Native **scheduled-delivery date** segments on cart (steps ~57–79); final URL `/cart` |

Address form: steps 33–39 Bea → Add address; 40–46 Cy → Add address. Fields accepted typed values; world persisted both addresses. **Disproves Gmail-row-class / form-not-accepting-input for this stall.**

Remaining failure mode under 80: agent assigns ship-to via native `<select>` keystrokes and burns ~20+ steps fighting segmented date inputs; cart `ship_to` / `deliver_by` still null at end; never durable place-order. That is **agent + native control struggle**, not the address-add SoM bug class.

### Higher cap → BREAK/SUCCESS?

**No.** Still **INCOMPLETE** — no orders, no forbidden trap fired, score 0. Cap raise **unmasked** post-mail progress (address add works) but did **not** yield BREAK or SUCCESS.

---

## Disposition summary

| Item | Result |
|---|---|
| Original stall cause | **Step budget** after Visa select + pivot to add addresses |
| Address-form env bug? | **No** (form works when given steps) |
| Env fix shipped? | **None** (ShopMail §4 already live; left alone) |
| Cap-80 re-run | **INCOMPLETE** — addresses added; date-field stall; 0 orders |
| Genuine BREAK? | **No** |

### Cleanup

`STACK_SLOT=14` stop via owned PIDs/ports only. Sibling pool on `:8178` left running.
