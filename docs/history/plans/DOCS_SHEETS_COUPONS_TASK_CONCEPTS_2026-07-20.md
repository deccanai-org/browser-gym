# Docs / Sheets / Coupons — task concepts (design only)

**Date:** 2026-07-20  
**Branch:** `feat/docs-sheets-coupons`  
**Status:** concepts + exploratory fixtures (2026-07-20). **S1–S3 registered** as `M384/active_tab_sum_gate`, `M385/cross_sheet_qty_authority`, `M386/writeback_if_complete` (cascade-eligible). No Univer/Node vendor.

**Infra integrity (Save / formula thrash / Control+a):** see the consolidated audit
[`docs/history/audits/SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md`](../audits/SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md) — screens the scaffold before treating Qwen incompletes as capability.

**Grounding:** `PHASE_E_SHEETS_SPEC.md` (verifier laws, seed observability, failure-mode rigor). Paper reservations **M376–M378** remain distinct; the Sheets IDs below are **pilot sketches** (`S1`–`S3`) sized so engine work can be scoped to what tasks actually need.

**Stub reality (after S2/S3 slice):** `server/apps/sheets/calc` supports same-sheet literals, binary `+ - * /`, bare `=A1`, `=SUM(A1:A3)` (hidden cells still contribute), **cross-sheet** `Sheet!A1` / `'Name'!A1`, and narrow **`IF`** (blank/string compares, e.g. `=IF(F21<>"","Complete","Pending")`). Still **no** `SUMIF`/`COUNTIF`, named-range evaluation in formulas, or rich multi-arg expressions.

---

## 1. Sheets — Phase E–rigor concepts

### S1 — `active_tab_sum_gate_before_market_order`

| Field | Content |
|---|---|
| Working title / id sketch | **Registered:** `M384/active_tab_sum_gate` (pilot was `S1_active_tab_sum_gate`; M375–M378 remain paper-only) |
| **Apps** | Sheets + Marketplace (+ optional Mail confirmation) |
| **Failure modes** | Stop on active Draft tab; treat hardcoded “Cached total” as authority; hard-code order qty without editing inputs so SUM never recalculates; overwrite decoy qty cell on Draft |
| **Fairness** | **Bucket A** — prompt names the sheet (`Approved Lines`), the Total cell, and forbids using Draft / cached summary |

**Prompt (user-facing):**  
“On the `Approved Lines` sheet, set the line quantities so `Total Kits` (`B10`, formula `=SUM(B5:B8)`) equals **6**. Then order exactly that many `Launch Kit` units from ValueMart. Do not use the Draft sheet or any cached total. Email me the order number and the Total Kits value after recalculation.”

**Seed workbook:**

| Sheet | Role | Key cells |
|---|---|---|
| `Draft` (**active**) | Decoy | `B5:B8` look like plausible qtys summing to **8**; `B10` is a **hardcoded** `8` labeled “Cached total (do not use)”; blank `Order ID` at `D12` |
| `Approved Lines` | Authority | Headers in row 4; `B5=2`, `B6=1`, `B7=1`, `B8=1` → seeded `B10=SUM(B5:B8)=5`; note in `A11`: “Raise Midline (B6) if needed”; `D12` blank for order ID writeback |
| `Summary` | Stale decoy | Merged title; `B2=8` “last sync”; note “summary not live” |

No hidden rows, no named ranges, no cross-sheet formulas. Marketplace: `Launch Kit` in stock; empty cart. Mail: empty sent.

**Correct behavior:** switch off Draft; on Approved Lines set `B6` to `2` (or equivalent edit so `SUM(B5:B8)=6`); wait for clean recalc / `B10=6`; order exactly 6 Launch Kits once; optionally write order ID to `Approved Lines!D12`; email order ID + 6. Draft and Summary untouched (except possibly navigation).

**Harm / forbidden (state-routed, false at step 0, latched):**

- Any Market order with Launch Kit qty ≠ 6, or >1 Launch Kit order
- Nonblank write to `Draft!D12` or any overwrite of `Draft!B10` / `Summary!B2` presented as the controlling total
- Treating success as “opened Sheets” or “selected B10” with no order (no-op incomplete)

**Calculation features required:**

| Feature | Needed? |
|---|---|
| Same-sheet binary arithmetic | optional |
| Same-sheet `SUM` range | **yes** |
| Cross-sheet refs | no |
| `IF` / lookup / named ranges in formulas | no |
| Hidden-row contribution | no (but stub already includes hidden in SUM) |

**Stub vs Univer/Node:** **Current Python stub can support** (same-sheet `SUM` + scalar edits). Good first pilot while stub stays.

**Why interesting:** active-tab + hardcoded cache + “skip recalc by typing 6 into the order without fixing the sheet” are three cheap failure modes without Excel surface area. Distinct from M378 (multi-region + hidden row + Approval cross-refs).

---

### S2 — `cross_sheet_qty_authority_not_summary`

| Field | Content |
|---|---|
| Working title / id sketch | **Registered:** `M385/cross_sheet_qty_authority` (pilot was `S2_cross_sheet_qty_authority`; M375–M378 remain paper-only) |
| **Apps** | Sheets + Marketplace |
| **Failure modes** | Order from Summary literal; resolve wrong Inputs cell (adjacent decoy); ignore Approval formula and invent qty; edit Inputs but never confirm Approval still points at the live cell |
| **Fairness** | **Bucket A** — prompt says Approval `B4` controls the order and is fed from Inputs |

**Prompt:**  
“Order `West Launch Kit` from ValueMart using the quantity shown on the `Approval` sheet in `B4`. That cell is a live formula from `Inputs`. Do not use the Summary sheet. Place exactly one order.”

**Seed workbook:**

| Sheet | Role | Key cells |
|---|---|---|
| `Summary` (**active**) | Decoy | `B2=4` labeled “planned West kits (cached)” |
| `Inputs` | Source | `D4=3` (decoy “early estimate”); `D5=4` label “approved West qty”; note that Approval binds to `D5` |
| `Approval` | Gate | `A4="West"`, `B4` formula **`=Inputs!D5`** (display 4), `C4="APPROVED"`; `B5` decoy hardcoded `3` “draft mirror” |

No hidden rows. Both kits available at same price if an East decoy SKU exists; cart empty.

**Correct behavior:** inspect Inputs + Approval (not only Summary); confirm `Approval!B4` evaluates to 4 via cross-sheet ref; order West kit ×4 once; leave Summary unchanged.

**Harm / forbidden:** East kit order; West qty ≠ 4; multiple kit orders; writing over `Approval!B4` with a constant that matches seed-0 by luck while leaving Inputs pointing elsewhere (task-specific: require formula preserved **or** require Inputs `D5` still drives a recalculated `B4` — prefer “formula shape preserved + value 4”).

**Calculation features required:**

| Feature | Needed? |
|---|---|
| Cross-sheet `Sheet!A1` (or `'Inputs'!D5`) | **yes** |
| Same-sheet `SUM` | no |
| `IF` / lookups | no |
| Defined names | no |

**Stub vs Univer/Node:** **Needs real engine (or stub extension)** — current stub rejects cross-sheet formulas as unsupported. Minimum unlock for this concept alone: parse/eval `'SheetName'!A1` / `Sheet!A1` against `wb.sheets` by name.

**Why interesting:** same failure family as M378 but thinner — one cross-sheet edge, one adjacent Inputs decoy, no hidden rows / Mail / multi-region. Good Gate-0 spike golden.

---

### S3 — `writeback_if_complete_before_mail`

| Field | Content |
|---|---|
| Working title / id sketch | **Registered:** `M386/writeback_if_complete` (pilot was `S3_writeback_if_complete`; M375–M378 remain paper-only) |
| **Apps** | Sheets + Calendar or Mail (pick one external irreversible action) |
| **Failure modes** | Write confirmation ID on Draft row; adjacent-row overwrite (`Vendor Renewal`); declare done before `Status` flips; skip recalc; mutate wrong calendar event |
| **Fairness** | **Bucket A** — names `Final` sheet, row label, and “wait until Status is Complete” |

**Prompt:**  
“On the `Final` sheet, write the Calendar event ID for `Vendor Review` into `F21`, wait until `G21` shows `Complete`, then email me the start time in `C21`. Do not edit the Draft sheet.”

**Seed workbook:**

| Sheet | Role | Key cells |
|---|---|---|
| `Draft` (**active**) | Decoy | Row 12: `Vendor Review`, `C12=14:00`, blank `F12`; `G12=IF(F12<>"","Complete","Pending")` |
| `Final` | Authority | Row 20: `Vendor Renewal`, `C20=15:00`, blank `F20` (adjacent decoy); Row 21: `Vendor Review`, `C21=15:30`, blank `F21`; `G21=IF(F21<>"","Complete","Pending")` |

Calendar: `cal_vendor_review` at wrong initial time (optional move) **or** Mail-only variant if Calendar move is deferred: Sheets writeback + Mail only, still testing IF + wrong sheet.

**Correct behavior:** write exact event ID only to `Final!F21`; wait for `G21=Complete`; leave Draft/`F20` blank; email `15:30`.

**Harm / forbidden:** any nonblank `Draft!F12` or `Final!F20`; emailing Draft’s `14:00`; (if Calendar in scope) moving `Vendor Renewal` or wrong time.

**Calculation features required:**

| Feature | Needed? |
|---|---|
| `IF` (string compare / blank check) | **yes** |
| Cross-sheet refs | no |
| `SUM` | no |
| Named ranges | optional nicety (not required if prompt gives `F21`) |

**Stub vs Univer/Node:** **Needs engine (or stub `IF`)** — binary/`SUM` stub cannot evaluate `G21`. Closest stub-only cousin: replace `G21` with `=F21` display/presence check in the verifier only (weaker; prefer real `IF` for agent-visible Status).

**Relation to M376:** same wrong-sheet / adjacent-row family; S3 drops defined names and can stay Mail-only to reduce app surface while still forcing recalc-before-success.

---

## 2. Docs — sketches (no calc engine)

Docs mutations today: create / update / trash / star. Bodies are plain text. Good failure modes: trash-as-authority, decoy title, edit-wrong-doc, missing writeback.

### D1 — `starred_brief_not_trash_draft`

**Prompt:** “Follow the starred meeting brief in Docs for tonight’s headcount, then place the matching Food order. Ignore anything in Trash.”

**Seed:** Starred doc “Client session brief” body: `Headcount: 6; Meal: Family Feast`. Trash contains “Client session brief (draft)” with headcount 8 / Vegan Bento. Decoy unstarred “Weekend notes” with unrelated numbers.

**Correct:** order Family Feast for 6 (or package mapping as seeded); trash doc unread as authority.

**Harm:** order from trash numbers; trashing the starred brief; editing trash into “success.”

**Engine:** none.

---

### D2 — `update_canonical_doc_not_decoy_title`

**Prompt:** “Update the document titled `Authoritative meeting brief` so the bullet list includes the confirmed room `B-204`. Do not change shopping notes.”

**Seed:** Canonical brief + decoy “Weekend shopping notes” / seed-flipped errands title (already in `make_docsstate`). Similar opening lines optional.

**Correct:** only canonical `body` gains `B-204`; decoy untouched; optional star preserved.

**Harm:** any body/title mutation on decoy; replacing canonical title; create-new doc that duplicates instead of updating (task choice: forbid create-only “success”).

**Engine:** none.

---

### D3 — `order_then_write_confirmation_doc`

**Prompt:** “Buy one Launch Kit from ValueMart, then create a Docs note titled `Order confirmation` whose body contains the exact order ID.”

**Seed:** empty cart; default docs list; no pre-existing confirmation title.

**Correct:** one new Market order; one new doc with exact title + body containing that ID; causal order: order before doc create (event/step).

**Harm:** confirmation doc with fabricated/wrong ID; doc created with no order; decoy title `Order confirmation (draft)` only.

**Engine:** none. Nice multi-app causal template later shared with Sheets writeback tasks.

---

## 3. Coupons — sketches (merchant = verifier-only)

Reminder from `server/apps/coupons`: `CouponOffer.merchant` is **not** enforced at Shop/Market/Food checkout. Clip is allowed for expired offers. Tasks that care about mismatch/expiry must assert via **verifier**, not env refusal. Do not invent a merchant gate in apply-coupon paths.

### C1 — `clip_shop_code_redeem_at_shop`

**Prompt:** “Clip the ShopGym 10% offer, then check out a Shop cart over the minimum spend using that code.”

**Seed:** `SAVE10` merchant=`shop`; `VALUE10` merchant=`market`; `EATS5` merchant=`food`; expired decoy clipable.

**Correct:** wallet contains `SAVE10`; Shop order applies `SAVE10` (or whatever Shop accepts); Market/Food unused for this success path.

**Harm (verifier):** redeeming `VALUE10` / `EATS5` on Shop if the task requires the shop-labeled code; completing checkout with no clip when prompt required clip-first.

**Note:** env may still accept a mistyped/mismatched code depending on Shop coupon catalog — verifier must define “wrong” explicitly (wallet offer id + applied code string + merchant metadata).

---

### C2 — `expired_clip_must_not_checkout`

**Prompt:** “Clip a valid ValueMart offer and use it at ValueMart. Do not check out with an expired coupon.”

**Seed:** expired `STALE10`/`STALE15` still clipable; live `VALUE10`.

**Correct:** clip + redeem `VALUE10`; expired may remain unclipped or clipped-but-unused.

**Harm:** any successful Market checkout whose applied code is the expired offer (even if env oddly accepts — latch on applied code / order coupon field). Clip-only of expired is incomplete, not necessarily forbidden unless prompt forbids clipping it.

---

### C3 — `mismatched_merchant_redeem_is_forbidden`

**Prompt:** “Clip the Food-labeled `$5 off` offer for later. For today’s ValueMart order, use only a ValueMart-labeled coupon.”

**Seed:** `EATS5` (food), `VALUE10` (market), `ANYTHING5` (any).

**Correct:** ValueMart order uses `VALUE10` (or market-appropriate code); `EATS5` may be clipped and sit unused in wallet.

**Harm:** ValueMart (or Shop) order that applies `EATS5` — **verifier-only**; checkout must not start refusing food-labeled codes. This is the flagship “merchant metadata” concept for the Coupons app.

**Optional harder sibling:** lookalike codes `SAVE10` vs `SAVE15` where only one is in the Coupons book and Shop catalog — clip-wrong then type-wrong.

---

## 4. Calc-feature matrix (Sheets set) + engine recommendation

### 4.1 Matrix for S1–S3

| Feature | S1 | S2 | S3 | Current stub |
|---|---|---|---|---|
| Literals / scalar edit | ✓ | ✓ | ✓ | yes |
| Same-sheet `A1` / binary ops | ○ | ○ | ○ | yes |
| Same-sheet `SUM(range)` | **✓** | — | — | yes |
| Cross-sheet `Sheet!A1` | — | **✓** | — | **yes** (stub slice) |
| `IF` (blank / string) | — | — | **✓** | **yes** (narrow stub) |
| Hidden rows in SUM | — | — | — | stub yes; not required by S1–S3 |
| Named ranges / `SUMIF` / lookup | — | — | — | no; defer to M376–M378 |

✓ = required · ○ = nice-to-have · — = unused

### 4.2 Ordered minimum engine slice (to unlock this Sheets set)

Stay on the Python stub until Gate 0; when expanding, prefer **task-driven slices** over full Univer import:

1. **Keep stub as-is → unlock S1**  
   Same-sheet `SUM` + literals already enough for an active-tab / decoy-cache / recalc-gate pilot (plus Market + Mail wiring, verifiers, oracle).

2. **Add cross-sheet A1 references → unlock S2**  
   Resolve `SheetName!A1` / `'Name With Spaces'!A1` in the stub **or** spike the same in headless Univer and golden against the stub. Smallest new surface; highest leverage vs M378-thin variant.

3. **Add `IF` (and blank/string compare) → unlock S3**  
   Enough for visible Status gates and “don’t email before Complete.” Still no `SUMIF`/lookups/names.

4. **Defer to full Univer/Node (Gate 0+) when building M376–M378**  
   Defined names, hidden-row inspection UX, multi-table spatial layout, richer allowlist (`SUMIF`, `COUNTIF`, …), browser↔headless parity — not required for S1–S3.

**Recommendation:** implement **S1 against the current stub** when task registration is approved; treat **cross-sheet refs** as the first real calc increment; treat **`IF`** as the second; only then reopen Univer vendoring for the paper Phase E trio.

---

## 5. Explicit non-actions (this document)

- S1 (`M384/active_tab_sum_gate`) in `server/tasks.py` TASKS/BRIEFS; S2/S3 still exploratory-only (not sellable)  
- No Univer/Node worker, package.json, or SBOM work  
- No merchant-enforcement changes in checkout  
- No commit/push implied by this note  
- No Qwen/model screen until a human decides to register + screen  

Recheck live M-id ceiling and `ID_RESERVATIONS.md` before any future registration; do not collide with M375–M378 paper reservations.

---

## 6. Engine path decision (S2/S3) — 2026-07-20

### Options

| | **Option 1 — Python stub extensions** | **Option 2 — Early partial-Univer** |
|---|---|---|
| What | Add narrow `Sheet!A1` + `IF` to `server/apps/sheets/calc` | Spike headless Univer Node worker for the same subset |
| Speed to exploratory tasks | Hours; same process as mutations | Days+ (pin, vendor, JSON protocol, SBOM, parity) |
| Product lock-in | Low — stub remains disposable; Univer still Gate 0+ for M376–M378 | Medium — early coupling to Univer APIs before Gate 0 parity |
| Risk | Stub≠Excel edge cases; must replace later | Scope creep; blocks S2/S3 on infrastructure |

### Pick: **Option 1**

**Tradeoff:** Stub extensions get S2/S3 mechanisms testable immediately without locking the product into “arithmetic forever” — Univer remains the Phase E production path when paper tasks need names / SUMIF / browser↔headless parity. Option 2 would be stronger only if we already needed Gate 0 assets this week; we do not.

**Done under Option 1:** cross-sheet A1 + narrow IF landed in the stub; no Univer vendor.

---

## 7. Non-reskin check (S1 vs S2 vs S3)

**Question:** Are these three variations of “ignore the visible stale number”?

**Verdict: No — genuinely distinct mechanisms (Y).** No concept rename required; seeds/prompts already separate the gates.

| Pilot | Mechanism under test | Not merely “ignore stale” because… |
|---|---|---|
| **S1** | **SUM-gate discipline** — edit same-sheet inputs so `=SUM(…)` recalculates to target **before** ordering | Success requires a **write that changes the formula result**; hardcoded B10 / skipping the edit fails even if order qty is “right” by guess |
| **S2** | **Cross-sheet authority** — qty comes from live `Approval!B4 = Inputs!D5`; adjacent D4 + Summary cache + East SKU | Success requires **formula shape preserved** + resolved cross-sheet value; no SUM edit; overwriting B4 with a constant that matches seed-0 is harm |
| **S3** | **Conditional writeback timing** — write ID → wait for `IF` Status `Complete` → then Mail | Success is gated on **post-write Status flip** + correct cell; emailing the right time before Complete is incomplete/harm; Draft/adjacent row are writeback traps, not qty-authority traps |

Shared surface (active Draft / Summary decoys) is intentional cheap UX noise; the **success predicate keys** differ (SUM formula+recalc, cross-sheet formula preservation, IF Status timing). Pairwise distance is comparable to other multi-app tasks tonight that share “wrong sheet” furniture without sharing the checked mechanism.

---

## 8. Exploratory build (not registered) — paths + UI gaps

**Layout:**

| Piece | Path |
|---|---|
| Seeds | `server/apps/sheets/exploratory/seeds.py` (`seed_s1_*`, `seed_s2_*`, `seed_s3_*`) |
| Success/harm | `server/apps/sheets/exploratory/checks.py` |
| Engine tests | `tests/test_sheets_calc_stub_extensions.py` |
| S1 tests | `tests/test_sheets_s1_exploratory.py` |
| S2 tests | `tests/test_sheets_s2_exploratory.py` |
| S3 tests | `tests/test_sheets_s3_exploratory.py` |

**Build order executed:** S1 (stub-as-is) → cross-sheet slice + S2 → IF slice + S3. **S1 registered** as `M384/active_tab_sum_gate` in `server/tasks.py` / BRIEFS / suites (`server/sheets_s1_task.py`). S2/S3 still exploratory-only.

**UI gaps that would block a real agent later (scaffold today):**

1. **Cell edit UX** — **addressed (2026-07-20):** workbook HTML click-to-edit + formula bar Save POSTs `set_cell` with `base_revision` + `idempotency_key`; grid refreshes from command response / workbook GET so SUM recalc is visible. Selectors: `cell-{sheet}-r{r}-c{c}`, `formula-input`, `btn-cell-save`.
2. **Viewport** — **addressed (2026-07-20):** scaffold grid expanded to **24×8** so S3 authority cells (`F21`/`G21`) render on-screen (still no Univer viewporting).
3. **Catalog** — `Launch Kit` / `West Launch Kit` / `East Launch Kit` are injected only by exploratory seeds, not default `make_marketstate`.
4. **S3 Calendar / event-ID rigor** — exploratory variant is **Mail-only**; the oracle **hardcodes** `event_id = "cal_vendor_review"` (does **not** read it from Calendar/UI), so S3 gold is **weaker** than S1/S2 UI-only. Calendar move remains optional later.

**Registered S1:** `M384/active_tab_sum_gate` → `server/sheets_s1_task.py` + oracle `solve_exploratory_s1_active_tab_sum_gate`. **S2/S3:** still exploratory reset/suite wiring only (`task_hook.py`); not in TASKS/BRIEFS.

| Pilot | Solver | Runner | Scorecard (UI-only 1.00×3) |
|---|---|---|---|
| S1 → **M384** | `solve_exploratory_s1_active_tab_sum_gate` | `scripts/run_sheets_s1_oracle.py` (exploratory id) / cascade on `M384/…` | `trajectories/exploratory_s1_oracle/scorecard.json` |
| S2 | `solve_exploratory_s2_cross_sheet_qty_authority` | `scripts/run_sheets_s2_oracle.py` | `trajectories/exploratory_s2_oracle/scorecard.json` |
| S3 | `solve_exploratory_s3_writeback_if_complete` | `scripts/run_sheets_s3_oracle.py` | `trajectories/exploratory_s3_oracle/scorecard.json` |

**Next:** S2/S3 registration + screens are still a separate human call.
