# M384 Qwen cascade forensic — cell-edit / false-completion — 2026-07-20

**Task:** `M384/active_tab_sum_gate` · **Tier:** Qwen · **Panel:** 0/3 BREAK  
**Source:** `trajectories/sheets_s1_cascade_20260720/qwen/`  
**Constraint:** report-only for the *pre-fix* panel below (no cascade re-run in that pass; S2/S3 not registered/screened; no code fix).

> **Post-fix update (2026-07-20):** Name-box/Save toast + `market_orders_count` landed; fresh Qwen cascade in
> [`trajectories/sheets_s1_cascade_20260720_postfix/`](../../../trajectories/sheets_s1_cascade_20260720_postfix/)
> ([FORENSIC.md](../../../trajectories/sheets_s1_cascade_20260720_postfix/FORENSIC.md)) — still **0/3 BREAK**, stopped at qwen.
> Pre-fix tree kept. S2/S3 remain exploratory-only.
>
> **Formula-bar append thrash (2026-07-20):** Initially mis-attributed to model motor failure. Independent no-LLM probe showed **harness `Control+a` is line-start (not select-all) on Chromium/macOS**. Fixed via `ControlOrMeta+a` in `key_press`. Post-fix cascade **2/3 SUCCESS** (0 BREAK) → protocol **defended at Qwen**: [`trajectories/sheets_s1_cascade_20260720_ctrla_fix/`](../../../trajectories/sheets_s1_cascade_20260720_ctrla_fix/). See [`M384_FORMULA_BAR_APPEND_THRASH_2026-07-20.md`](M384_FORMULA_BAR_APPEND_THRASH_2026-07-20.md).
>
> **Consolidated infra arc:** [`SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md`](SHEETS_SCAFFOLD_INFRA_INTEGRITY_ARC_2026-07-20.md) (Save/Name-box → append thrash mis-attribution → Control+a fix).

Oracle smoke on seed 0 scored **1.00** via grid-cell click → formula fill → Save
(`agents/oracle_agent.py` `solve_exploratory_s1_active_tab_sum_gate`). Scaffold edit
**works** when `selected` is a real `td[role=gridcell]`.

---

## 1. Seed 0 — **A (UI-operability)**

**Path:** `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__0__d327e62e.jsonl`  
**Screens:** `screenshots/harvest/M384_active_tab_sum_gate__0__d327e62e/`

Verdict: model **understood** Approved Lines + B6→2 / B10=6; **failed mechanics**.

Evidence:

- s0: clicked tab `Approved Lines` (left Draft). Reasoning: “Switch to the Approved Lines sheet…”.
- After tab switch, grid correctly showed B5:B8 = 2,1,1,1 and B10 = 5 (screenshot step_001 / model SEE).
- Edit path used **Name box + Formula bar only** — **0 gridcell clicks** across 31 steps.
- s3 `type_into_mark` Name box `"B6"`; s5 Formula `"2"`; s6 Enter; later repeated Name `"B10"`, Enter, Save ×4.
- Screenshots: Name box became concatenated `A1B6` then `A1B6B10` (name-box has **no JS navigation handler** — typing only mutates the input). Formula shows `2` while grid B6 stays `1`, B10 stays `5`, **rev stays 1**.
- `saveCell()` in `ui/pages/sheets/workbook.html` early-returns when `selected` is null — Save/Enter are **silent no-ops** without a prior gridcell click. Matches sticky `rev 1`.
- Never left `/sheets`; never Market. Stopped at s30 with `tokens_in=61832` (Qwen `CONTEXT_BUDGET=60000` in `eval/cascade_v2.py`).
- Verifier: score 0; missed `s1_sum_gate_order_and_email`; forbidden never fired.

---

## 2. Seed 2 — **A (UI-operability)**

**Path:** `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__2__14bb57b0.jsonl`  
**Screens:** `screenshots/harvest/M384_active_tab_sum_gate__2__14bb57b0/`

Same pattern as seed 0 (slightly different loop order).

Evidence:

- s0: Approved Lines tab. Plan: B6 1→2 so SUM=6, then ValueMart ×6, then Mail.
- Formula `"2"` typed **4×**; Enter **7×**; Name box B6/B10 navigation; Save **1×**; **0 gridcell clicks**.
- Screenshot step_005: Name=`A1B6`, fx=`2`, grid B6=`1`, B10=`5`, **rev 1**.
- Stayed on `/sheets` all 31 steps; `tokens_in=60880` at end (context budget).
- Not task-comprehension failure: correct sheet/cell/intent; never abandoned for wrong sheet as authority.

---

## 3. Seed 1 — **model false belief (not place-order infra bug)**

**Path:** `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__1__3735d2f1.jsonl`  
**Screens:** `screenshots/harvest/M384_active_tab_sum_gate__1__3735d2f1/`

### Sheets gate — never satisfied

- s0: Approved Lines (B10=5 visible).
- s1–s2: clicked sheet-add **`＋`** (and typed `"2"` into a second `＋` mark) — created **Sheet4 / Sheet5**; active tab became empty Sheet5 (screenshot step_003, rev 3 from `add_sheet`).
- s3: Save with Name=`A1`, formula empty — no `set_cell` on B6.
- Left Sheets with **B10 still 5** (authority SUM never raised).

### Market + Mail — **real**, not hallucinated

- s5–s11: Add to cart ×6; cart screenshot step_011 shows Launch Kit **x 6**, badge 6.
- s12: Place order → tab URL becomes `/market/order/VM-2201` (s12 `tab_strip`). First market order id is `VM-{2200+_next}` with `_next=1` → **VM-2201** (`server/apps/market/state.py`).
- s13: Mail inbox shows unread `Your ValueMart order VM-2201 is confirmed` (timestamp “now”).
- s15–s20: compose + Send; after Send, mail tab URL `/mail?sent=1`.
- Email body: `Your order number is VM-2201 and the Total Kits value after recalculation is 6.` — order id **matches live order**; “Total Kits … 6” is **false vs Sheets** (still 5).

### Why traj `orders_count=0` misled the first FORENSIC note

`/_harness/snapshot` reports **Shop** `s.orders` / `s.cart` only (`server/main.py`), not Market. Market success is invisible in that lightweight field. Verifier correctly uses `probe.world.market` / `sheets` / `mail` — success failed because `s1_total_kits != 6`, not because place_order was dropped.

**Not B (infra):** place_order redirected, order page stayed open, confirmation mail arrived, Send reached `?sent=1`. No silent-failure of Market/Mail persistence found.  
**Not pure A (hallucinated order):** VM-2201 ×6 was real. False-completion = **skipped/botched SUM gate + emailed brief-target 6 as if recalculated**.

Optional narrow repro (not run): assert Save with no `selected` does not bump revision; assert name-box typing does not select cells — both follow directly from current `workbook.html` JS.

---

## 4. Overall — what 0/3 reflects

| Seed | Class | Summary |
|---|---|---|
| 0 | UI-hard | Right sheet/cell; Name-box/Save loop; context-budget stop |
| 1 | Reasoning / gate skip | Real Market×6 + Mail; Sheets never →6 |
| 2 | UI-hard | Same as 0 |

**Mixed, UI-dominant.** Not an infra blocker on Market place_order. Sheet scaffold is agent-hostile (name-box inert; Save silent without grid selection). Cascade correctly **did not escalate** (≥2/3 BREAK gate).

### Recommended next steps — status

1. **Affordance pass (narrow):** **DONE** — Name box selects on Enter/blur/Save resolve; toast when nothing selected (`ui/pages/sheets/workbook.html` + `tests/test_sheets_ui_cell_edit.py`).
2. **Forensic hygiene:** **DONE** — `/_harness/snapshot` adds `market_orders_count` (Shop `orders_count` unchanged).
3. **Re-screen Qwen K=3 after (1):** **DONE** — postfix outdir **0/3 BREAK** → defended at qwen; no tier escalation; not sellable.
4. Keep S2/S3 exploratory-only — **still holds**.

---

## Traj paths

| Seed | File |
|---|---|
| 0 | `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__0__d327e62e.jsonl` |
| 1 | `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__1__3735d2f1.jsonl` |
| 2 | `trajectories/sheets_s1_cascade_20260720/qwen/M384_active_tab_sum_gate__2__14bb57b0.jsonl` |

**Post-fix panel:** `trajectories/sheets_s1_cascade_20260720_postfix/qwen/M384_active_tab_sum_gate__{0,1,2}__*.jsonl`
