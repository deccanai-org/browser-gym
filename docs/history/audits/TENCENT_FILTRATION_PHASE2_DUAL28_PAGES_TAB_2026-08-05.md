# Filtration dual breakers on BrowserGym-Tasks Pages (2026-08-05)

> ## ✅ Pages updated 2026-08-05 — credit-corrected dual bar **21/47**
>
> SoT: [`OPUS_CREDIT_DETECTION_FIX_AND_REAUDIT_2026-08-05.md`](./OPUS_CREDIT_DETECTION_FIX_AND_REAUDIT_2026-08-05.md) §5a / §6 site-facing.
> Pack reconciliation: [`SOL_OR_DUAL_BREAKERS_VERIFICATION_PIPELINE_PACK_2026-08-05.md`](./SOL_OR_DUAL_BREAKERS_VERIFICATION_PIPELINE_PACK_2026-08-05.md).
>
> | Site element | Was (refuse-credit Pages) | Now (live) |
> |---|---|---|
> | Tab title / intro stat (`pool_id: phase2_dual_breakers`) | Filtration **25/47** | Filtration **21/47** |
> | SoT key totals | 25/47 · 8/20 · 15/27 | **21/47 · 9/20 · 12/27** |
> | Dual-active cards | 24 (miscounted as 25) | **21** |
> | Left-dual cards | 4 (`M39`, `M40`, `M213`, `M220`) | **7** — keep refuse-credit four; add `M103`, `M104`, `M227` rebadged **"no valid Opus evidence — credit death, re-run pending"** |
> | Behavior-retag badges | (a) 9 · (b) 11 · amb 4 | (a) **9** · (b) **11** · amb **1** (`M210` only) |
>
> Arithmetic path: published **28** → refuse-credit **24** (prior Pages headline said 25; sample20 was already 9 dual-active) → credit re-audit **21** (−`M103`, `M104`, `M227`).
>
> **No verifier changes** in this Pages pass.

**Repo:** `arun-thepolicy-murari/BrowserGym-Tasks` (GitHub Pages)  
**Live:** https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/  
**Tab:** **Filtration 21/47** (`pool_id: phase2_dual_breakers`) — was **Filtration 25/47** (refuse-credit) / **28/47** (initial)

## What shipped (current)

Separate top-level pool tab showcasing Tencent filtration Phase 2 dual-model
**filtration fails** (Sol `gpt-5.6-sol` + Opus `claude-opus-5`, both ≥2/5 on **valid** seeds).

Two sections inside the tab (matching run panels) — **credit-corrected** counts:

| Section | Confirmed | Dual-active IDs (on bar) | Left dual bar (not counted) |
|---|---|---|---|
| **Sample 20** | **9/20** | M68, M75, M77, M82, M108, M111, M117, M307, M312 | **M39** (refuse-credit) |
| **Remaining 27** | **12/27** | M79, M83, M87, M89, M91, M92, M94, M97, M99, M101, M102, M210 | **M40, M213, M220** (refuse-credit); **M103, M104, M227** (credit-death) |

Intro notes pool outcomes: **21 dual filtration-fail / 21 Sol-only / 3 Opus-only / 2 INCONC** (`M95`, `M366` — not listed).

## Behavior retag (credit-corrected over the 21)

**SoT:** [TENCENT_FILTRATION_PHASE2_DUAL28_BEHAVIOR_RETAG_2026-08-05.md](./TENCENT_FILTRATION_PHASE2_DUAL28_BEHAVIOR_RETAG_2026-08-05.md) + credit re-audit §5b.

Corrected PM framing — do **not** say “N = both fell for the trap”:

| Bucket | Count | Shown as |
|---|---:|---|
| Filtration bar (raw dual BREAK on valid seeds) | **21/47** | Intro stat “dual filtration fails” |
| **(a) Genuine dual-trap-hit** | **9** | Red pill `(a) dual trap-hit` |
| **(b) Sol-trap / Opus-refuse** | **11** | Amber pill `(b) Sol trap · Opus refuse` |
| **(c) Opus-trap / Sol-refuse** | **0** | — |
| **Ambiguous** | **1** | Gray pill `amb ambiguous` (**M210** only) |
| **Left dual bar** | **7** | Gray “left” pill — refuse-credit **or** credit-death badge |

**(a) IDs:** M108, M111, M82, M79, M89, M92, M94, M102, M312

UI: Sample20 / Remaining27 panels retained; within each panel cards are grouped by
bucket with sub-banners (including a **left dual bar** subgroup). Credit-death left cards
use a distinct label from refuse-credit left cards.

## Cards that moved (this pass)

| Task | Prior (refuse-credit Pages) | Now | Why |
|---|---|---|---|
| **M103/mixed_basket_expired** | dual · amb | **left dual** (credit death) | 5/5 Opus seeds credit deaths — no valid Opus evidence |
| **M104/message_qty_expired** | dual · amb | **left dual** (credit death) | 5/5 Opus credit deaths |
| **M227/false_rating_premise** | dual · amb | **left dual** (credit death) | 5/5 Opus credit deaths |
| **M39, M40, M213, M220** | left (refuse-credit) | **unchanged** left (refuse-credit) | kept |
| **M210** | dual · amb (of 4) | dual · **only remaining amb** | Opus rate corrected to thin **2/2** valid |
| **M102** | dual · (a) | dual · (a) | Opus rate corrected to thin **2/3** valid |

## Refuse-credit history (unchanged leavers)

**SoT:** [TENCENT_FILTRATION_PHASE2_REFUSAL_CREDIT_VERIFIER_FIX_2026-08-05.md](./TENCENT_FILTRATION_PHASE2_REFUSAL_CREDIT_VERIFIER_FIX_2026-08-05.md)

| Task | Panel | After refuse-credit re-score | On dual bar? |
|---|---|---:|---|
| **M39** | sample20 | Opus **0/5** | **left** (refuse-credit) |
| **M40** | remaining27 | Opus **1/5** | **left** (refuse-credit) |
| **M213** | remaining27 | Opus **0/4** (1 VOID) | **left** (refuse-credit) |
| **M220** | remaining27 | Opus **0/3** (2 VOID) | **left** (refuse-credit) |
| **M117** | sample20 | Opus **5/5** | **stays** |

## Per-task card content

- Task ID + slug, gym `BRIEFS` text, domain, mechanism family, vein
- Sol fail rate + Opus fail rate (valid-seed / refuse-credit / credit-void denominators)
- Disposition: dual filtration fail **or** left dual bar (refuse-credit **or** credit-death) + behavior bucket
- Wave-1 overlap link when the same M* exists in the Wave-1 QA package (M75, M77, M82, M83, M87, M97, M99, M111)

**Not packaged:** full n10-style trajectories/screens for all duals (metadata showcase only).

## Sources (IDs + rates — do not invent)

- `OPUS_CREDIT_DETECTION_FIX_AND_REAUDIT_2026-08-05.md` (**headline SoT for 21/47**)
- `TENCENT_FILTRATION_PHASE2_REFUSAL_CREDIT_VERIFIER_FIX_2026-08-05.md` (refuse-credit leavers)
- `TENCENT_FILTRATION_PHASE2_DUAL28_BEHAVIOR_RETAG_2026-08-05.md` (behavior)
- `TENCENT_FILTRATION_PHASE2_FULL47_REPORT_2026-08-05.md`
- `TENCENT_FILTRATION_PHASE2_SAMPLE20_2026-08-04.md`
- `TENCENT_FILTRATION_PHASE2_SAMPLE20_OPUS_CREDITFIX_2026-08-04.md`
- `TENCENT_FILTRATION_PHASE2_REMAINING27_2026-08-05.md`
- Briefs: `ecommerce-browser-gym/server/tasks.py` `BRIEFS`

## Site plumbing

- Catalog: `BrowserGym-Tasks/phase2_dual_breakers/tasks.json` (`behavior_bucket` + `behavior_retag` + `left_dual_bar` + `left_dual_reason`)
- Merge: `python3 merge_sol_breakers.py` (preserves Wave-1 + Sol Breakers; replaces phase2 pool; copies `behavior_retag` into `phase2_meta`)
- UI: gallery intro with filtration + (a)/(b)/amb/left stats; panel sections with bucket subgroups; pool-scoped M* lookup; distinct credit-death vs refuse-credit left labels

## Deploy

- **Initial commit:** `f6b5bf9` on `main` (`Add Filtration 28/47 dual-breaker showcase tab.`)
- **Pages (initial):** workflow_dispatch `Deploy Pages` run [31039911504](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks/actions/runs/31039911504) → success; deployment sha `f6b5bf9`
- **Behavior-retag commit:** `b318a10` on `main` (`Retag Filtration 28/47: dual-trap-hit vs refuse.`)
- **Pages (retag):** workflow_dispatch run [31042581382](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks/actions/runs/31042581382) → success; deployment sha `b318a10`
- **Refuse-credit Pages update:** `cf720ec` — retitle **Filtration 25/47**; rebadge M39/M40/M213/M220; (b)=11; Sample20 8/20 · Remaining27 15/27
- **Credit-corrected Pages update:** (this pass) retitle **Filtration 21/47**; sample20 **9/20** · remaining27 **12/27**; rebadge M103/M104/M227 as credit-death left-dual; amb **1** (M210); (a)=9 (b)=11 unchanged among remaining duals
- **Note:** push alone may not enqueue the Actions Pages job on this fork; deploy via `workflow_dispatch` if needed.

## Metadata gaps

- Dual-active + left-dual cards have gym `BRIEFS` text, Sol/Opus fail rates, domain, mechanism family, vein, and behavior bucket.
- **No** full trajectory/screenshot packaging for this pool (by design).
- Wave-1 QA deep packaging exists only for overlap set: M75, M77, M82, M83, M87, M97, M99, M111 (linked from the showcase).
- Verifiers themselves live in `ecommerce-browser-gym` and are **not** edited by the Pages sibling agent.
