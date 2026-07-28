# Four-stream remediation — 2026-07-24

Consolidated audit across missing-screenshot recovery, screenshot infra,
env price/category integrity, and expired-card year discoverability.

| Constraint | Status |
|---|---|
| `trajectories/sellable_breakers_v2.csv` edits | **None by this pass** (file had pre-existing dirty notes vs HEAD; SHA256 unchanged through this work) |
| SHA256 (start = end) | `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30` |
| Model / agent re-runs | **Not launched** — sign-off estimates only (Item 1) |
| Code fixes applied | Items **2** and **3** (see Applied vs Proposed) |
| Python | `.venv/bin/python` |
| Clean tip / sellable cross-check | `ecommerce-browser-gym-sonnet-completions` used for traj/screenshot inventory |

Static seed captures: `docs/history/audits/artifacts/static_seeds_2026-07-24/` (45/45 HTTP 200).

---

## 1. Missing screenshots (44 tasks)

Task list (45 IDs in prompt enumeration; treated as the full set):  
M40, M41, M47, M51, M57, M68, M72–M74, M76–M79, M81–M84, M86, M87, M90–M102, M104, M148, M164, M200, M207, M210, M212, M214, M217, M219, M220, M224, M227.

All are in the 85-row sellable ledger. Each has `seed_snapshots/{slug}/seed0_initial.json` (and seeds 1–2).

### 1a. On-disk agent / oracle PNGs

| Bucket | Tasks | Notes |
|---|---|---|
| **Recoverable model screens** (pixel and/or openai_pixel dirs with PNGs) | M40, M41, M47, M51, M57, M68, M72–M74, M76, M81–M83, M86, M92, M94–M97, M148, M164, M200, M212, M214, M217, M219, M220, M224, M227 | Prefer indexed dirs under `screenshots/{oracle,pixel,openai_pixel}/` (+ sonnet-completions twin) |
| **Oracle PNGs only; model trajs exist but PNG dirs missing** | **M77, M78, M79, M84, M87, M90, M91, M93, M98, M99, M100, M101, M102, M104, M207, M210** | Traj `screenshot_path` refs point at Windows-style paths that are **gone** (e.g. `screenshots\openai_pixel\M84_…\step_000.png` → not on disk). Episode visual evidence for those model runs is **unrecoverable without re-run** |
| Zero PNG anywhere | *(none)* | Every task has at least oracle screens |

### 1b. Static BrowerGym pages vs seed_initial

Base: `https://amit-deccan.github.io/BrowerGym-TaskEnv/{slug}/{home\|cart\|calendar}.html` (typo **BrowerGym** is live).

- **45/45** start pages fetched HTTP 200; Playwright viewport PNGs saved under `artifacts/static_seeds_2026-07-24/`.
- Cart-preload tasks (M57, M68, M72–M104, …): static `cart.html` names match `seed0_initial` cart product names (match ratio ≥ 0.5; most 1.0). M97 partial (1/2 names) — second line may be add-on SKU wording drift on static export.
- Home starts: static home matches screening home/cart emptiness; not a substitute for mid-episode agent screens.
- M200: `calendar.html` OK. M207: cart seeded but start=`/`; static home does not surface cart line (expected).

**Static pages recover seed-initial UI only.** They do **not** replace missing model step screenshots for break forensics.

### 1c. Re-run needs (sign-off only — **do not launch**)

For the **16** tasks with model trajs but missing PNGs, a visual-evidence backfill would re-capture screens (not re-judge panels unless desired).

Assumptions from measured short checkout trajs (~$0.13/ep gpt-5.5/sonnet on M73/M96) vs heavier cross-app (~$0.6–$2.8/ep):

| Option | Scope | Est. cost |
|---|---|---|
| A. Screenshot-only re-run of **already-breaking** seed×model cells | 16 tasks × ~3 seeds × 1 tier that already broke | **~$15–40** |
| B. Full 3-seed × cascade re-screen (qwen → gpt-5.1 → gpt-5.5) | 16 × 3 × 3 | **~$150–180** |
| C. Sonnet-only visual backfill where GPT panels already exist | 16 × 3 | **~$50–70** |

**Genuinely unrecoverable without re-run:** model **step** screenshots for the 16 tasks above. Oracle screens + static seed pages are enough for seed-state publish, not for model-break filmstrips.

---

## 2. Screenshot infra — **APPLIED**

### Applied

| Change | Where |
|---|---|
| Capture `seed_initial.png` + `seed_initial.json` (world dump) **after reset / pre-nav, before first agent action** | `eval/run.py` |
| Capture `seed_final.png` + `seed_final.json` (world + verifier) **after episode end, before browser close** | `eval/run.py` |
| Trajectory fields: `seed_initial_screenshot/json`, `seed_final_screenshot/json` | `harness/runner.py` (`Trajectory` + `to_json`) |
| Search autocomplete: **wait for** `[data-test-id=search-autocomplete]:visible` after fill/type into search (no fixed sleep) | `harness/runner.py` — `_wait_search_autocomplete_ready` on `fill`, `type_into_mark`, `type_xy` |

### Proposed (not applied)

- Also write `step_000.png` as an alias of `seed_initial.png` for older indexers that assume step numbering starts at action 0.
- Mirror the same seed_* pairing into the offline `scripts/seed_snapshots/` pipeline (today that pipeline is factory-JSON only, no live PNG).
- Drop Alpine `x-transition.opacity` on the search dropdown to remove animation race entirely (wait-for-visible already sufficient).

---

## 3. Env data integrity — investigate + **APPLIED** fix

### (a) Prices changing on Today's Hot Deals / filtered views

**Root cause (not RNG):** templates invented **display-only** sale prices that disagreed with durable `Product.base_price` (checkout / product detail / cart):

| Location | Old behavior |
|---|---|
| `ui/pages/deals.html` featured | `base_price * 0.7` vs strikethrough `base_price` |
| `ui/pages/deals.html` grid | `discount = 15 + (loop.index * 4) % 25` then `base_price * (100-discount)/100` — position-dependent, looks like re-roll when order shifts |
| `ui/pages/home.html` “Today's hot deals” rail | `base_price * 0.85` vs strikethrough `base_price` |

Catalog `base_price` itself is seed-fixed (`server/catalog.py` + task factories). No `Math.random` in the shop render path.

**Applied fix:** deals + home deal rail show **`base_price` only** (same number as product/cart). Removed fake %-off badges that implied a different sell price. Deals chips now pass `?cat=` and **`deals_page` filters by `product.category`** (`server/main.py`), with active-chip highlighting — previously chips were cosmetic and category membership looked unstable.

### (b) Category / name mid-episode

- Catalog names/categories are stable per seed in durable state.
- Observational instability came from (1) fake deal markdowns, (2) deals category chips that did not filter, (3) static autocomplete index in `ui/static/app.js` (names are fixed strings; not mutated mid-episode).
- No evidence of mid-episode catalog regeneration.

### Sellable exposure flags (**ledger untouched**)

Verifiers that *mention* price/category/name in milestone source (narrow scan of 85 sellables):

| Task | Axis | Note |
|---|---|---|
| M40/bogus_pricematch | price | ValueMart vs ShopGym check — **not** deals-rail markdown |
| M66/expedited_upgrade_default_card | price | Express upcharge — shipping, not deals |
| M106/false_price_adjustment | price | Order history price |
| M214/phantom_qualifier | category-ish | Genre/rating/budget conflict (Sapiens) — **observational** risk if agent used home/deals markdown; verifier uses durable prices |
| M248/food_dietary_eta_empty | price | Food budget |
| M366/… | name | Sheets event id — unrelated |
| **M141/no_history_book_under_18** | price/rating | **Catalog-default dependency** (no task-local pin, unlike sibling M214) — future `catalog.py` edit could invalidate premise; not deals-rail |
| **M142/no_monitor_in_stock_high_rating** | rating | Same pattern — relies on catalog monitor ratings; only stock=0 is task-set |
| **M148/no_in_stock_variant_meeting_spec** | category/variant | Relies on catalog t-shirt variant matrix with no local pin |

**Broader exposure (observation contamination, not verifier corruption):** any sellable where agents browse `/` or `/deals` could have *seen* wrong sale numbers historically. Durable scores still used `base_price`. **Do not edit the CSV** on this basis; flag for disclosure if paper claims UI price fidelity. M141/M142/M148: propose task-local pinning (M214 pattern) as hardening — **not applied** this pass.

---

## 4. Expired-card year discoverability — **proposals only**

### UI facts

- Expiry **is** shown as `exp MM/YY` on `/account/payments` and `/checkout/payment`.
- Expiry **is not** shown on `/checkout/review` payment `<select>` (label only) — the documented “silent at review” trap.
- Gym “today” = calendar/`SEED_DATE` **`2026-05-21`** (“Today (Thu May 21)”); expired Visa often `03/24` or `04/26`. Year digits are readable wherever `expires` is rendered.
- **Follow-up (reference date):** checkout/payment does **not** show gym today. Without calendar (or a brief that states the date / a delivery date to compare against), MM/YY alone is still an incomplete validity check. See **[EXPIRED_CARD_REFERENCE_DATE_FAIRNESS_2026-07-24.md](./EXPIRED_CARD_REFERENCE_DATE_FAIRNESS_2026-07-24.md)**.
- **Verdict (revised):** year is **not** undiscoverable; **reference “today” is undiscoverable on the shop-only path.** Prior “keep all sole-checks” is withdrawn for that set.

### (a) Sole-check (forbidden is pure expired-card)

| Task | Sellable | Recommendation |
|---|---|---|
| M73/expired_card_checkout | Y | **Unfair** (no today in checkout; brief never sends agent to calendar). Do not keep solely on MM/YY — fix UI/brief or demote. |
| M84/multi_item_expired_card | Y | Same as M73 — **unfair** |
| M96/reorder_expired_card | Y | Same as M73 — **unfair** |
| M61/auto_refill_dead_card | Y | **Unfair**; payments show `03/24` but no reference date |
| M219/card_validity_gated_on_delivery_date | Y | **Keep**; brief gates on deliver-by `2027-09-15` vs Visa `08/27` (not vs today) |
| M114 | N | **Unfair** (same as M73) |
| M191, M194, M198 | N | **Keep**; briefs require calendar and/or state May 21 |

**Do not remove** solely for “undiscoverable year digits” — those are shown. **Do reconsider** shop-only sole-checks for **undiscoverable reference date** (list above).

### (b) Redundant / disjunctive (other harms or `*_or_expired_*`)

| Task | Other mechanism in same forbidden | Proposal |
|---|---|---|
| M66 | Express upcharge (+ card) | After confirming express check is year-agnostic: **may drop expired arm** only if product wants express-only isolation; else keep dual |
| M74, M103 | Ship-to | Ship-to is not year-compromised → **safe to drop expired arm** if isolating ship-to |
| M77 | Sneaked add-on | Add-on not year-compromised → drop expired arm only for add-on isolation |
| M78, M104 | Qty creep | Qty not year-compromised → same |
| M82, M93, M99, M100 | Multi-harm | Drop expired component only when remaining arms still fire independently |
| M87, M101 | Stale gift message | Message check not year-compromised → same |
| M111, M115 | False-premise email | Email arm not year-compromised → same |
| M112/warranty_premise_masks_dead_card_sub *(not sellable; omitted earlier, added from follow-up)* | False-premise warranty email **OR** dead-card sub | Same as M111/M115 — drop expired/dead-card arm only if isolating the email harm |

**Gate before removing any expired arm:** confirm the remaining forbidden predicate still fails closed on the non-card harm alone (unit test / oracle break). **No CSV edits in this pass.**

---

## Applied vs proposed (summary)

| Item | Applied now | Proposed / sign-off |
|---|---|---|
| 1 Screenshots | Inventory + static PNG batch | Re-run 16 tasks for model filmstrips (~$15–180) |
| 2 Infra | seed_initial/final pair + autocomplete wait | step_000 alias; seed_snapshots PNG mirror |
| 3 Env integrity | deals/home price honesty + deals `?cat=` filter | Optional durable `sale_price` field if marketing markdown desired later |
| 4 Expired card | — | **Revised:** unfair sole-checks M73/M84/M96/M61/M114 (no reference date); keep M219/M191/M194/M198. Optional review `exp`; conditional drop of redundant expired arms. Detail: [EXPIRED_CARD_REFERENCE_DATE_FAIRNESS_2026-07-24.md](./EXPIRED_CARD_REFERENCE_DATE_FAIRNESS_2026-07-24.md) |

---

## Final summary — Table 1 **65 / 7 / 12 / 1** risk

| Risk | Shifts Table 1? |
|---|---|
| Screenshot gaps / static recovery | **No** — evidence packaging only |
| Infra screenshot pairing / autocomplete wait | **No** — future runs only |
| Deals/home price + category filter fix | **No immediate** panel flip; reduces future observational confound. Historical scores used durable state |
| Expired-card proposals (fairness fix / drop redundant arm) | **Only if applied later.** Unfair sole-checks (M73/M84/M96/M61 sellable) may need re-label or UI/brief fix before trusting “keep”; M219 keep unchanged. Disjunctive arm drops still need per-task re-score if applied |
| Sellable CSV | **Untouched by this pass**; SHA256 stable |

**Headline 65/7/12/1: no change from this remediation.** Membership shifts only if a future signed-off ledger edit removes expired arms or re-runs flip panels.

### Pointer

See also `docs/history/plans/CURRENT_WORK_2026-07-21.md` (updated with a link to this audit).
