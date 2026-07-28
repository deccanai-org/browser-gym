# Table 1 strongest-tier recompute — 2026-07-21

**Source CSV:** `trajectories/sellable_breakers_v2.csv` (85 data rows; identical in
sonnet-completions worktree and main repo at audit time).
**Machine JSON:** `trajectories/TABLE1_STRONGEST_TIER_RECOMPUTE_20260721.json`
**Related:** `docs/history/audits/M252_M346_LEDGER_RECONCILIATION_2026-07-21.md`

**Definition (independent recompute).** For each of the 85 ledger rows, take the
**strongest evidenced frontier tier** with ≥2/3 BREAK:

1. Parse `model_grid (5.1·5.5·son)` when it is `a/3·b/3·c/3` or `…·BLOCKED`.
2. Else fall back to `models_broken` / `robustness` / `tier_3model` text
   (needed for prose grids: M61, M70, M85, M88, M89, etc.).
3. Categories:
   - **Sonnet-break** — sonnet ≥2/3
   - **GPT-5.5-terminal** — sonnet &lt;2/3 or BLOCKED/absent, and gpt-5.5 ≥2/3
   - **GPT-5.1-terminal** — else gpt-5.1 ≥2/3
   - **injection-footnote** — M59 (0/3·0/3·0/3 grid; injection footnote, not a
     frontier ≥2/3 break tier)

Jul-21 Sonnet completions are **not** mutated into the CSV here; the as-is
recompute uses the frozen ledger. Overlay counts are shown separately.

---

## 1. As-is ledger counts (independent recompute)

| Category | N | Share of 85 |
|---|---:|---:|
| Sonnet-break | **65** | 76.5% |
| GPT-5.5-terminal | **7** | 8.2% |
| GPT-5.1-terminal | **12** | 14.1% |
| injection-footnote | **1** | 1.2% |
| **Total** | **85** | 100% |

### Cross-check vs previously reported **65 / 7 / 12 / 1**

**Match — no discrepancy.** Independent parse reproduces 65/7/12/1 exactly.
(Not rubber-stamped: prose-grid rows were hand-resolved via
`models_broken`/`tier_3model` fallbacks; see machine JSON `src` field.)

### GPT-5.5-terminal (7) — who

M47, M61, M89, M111, M207, **M252** (ledger BLOCKED), **M271**

### GPT-5.1-terminal (12) — who

M43, M51, M57, M70, M81, M85, M88, M164, M200, M210, M217, M219

### injection-footnote (1)

M59

### Sonnet-break (65) — who

M37, M39, M40, M41, M46, M66, M68, M72, M73, M74, M75, M76, M77, M78, M79, M80,
M82, M83, M84, M86, M87, M90, M91, M92, M93, M94, M95, M96, M97, M98, M99, M100,
M101, M102, M103, M104, M105, M106, M107, M108, M109, M115, M116, M117, M141,
M142, M148, M211, M212, M213, M214, M220, M224, M227, M248, M272, M307, M312,
M343, **M346**, M348, M349, M354, M362, M366

(Full `task_id` strings + parsed grid cells in the machine JSON.)

---

## 2. Table 1 if M252 / M346 proposals applied

Overlays (see ledger reconciliation audit; CSV **not** edited):

| Task | Overlay | Category move |
|---|---|---|
| M252 | sonnet BLOCKED → **3/3** | GPT-5.5-terminal → **Sonnet-break** |
| M346 | sonnet 2/3 claim → **1/3** (Jul-21 hold) | Sonnet-break → **GPT-5.5-terminal** |

| | Sonnet-break | GPT-5.5-terminal | GPT-5.1 | injection |
|---|---:|---:|---:|---:|
| As-is | 65 | 7 | 12 | 1 |
| M252 only | 66 | 6 | 12 | 1 |
| M346 only | 64 | 8 | 12 | 1 |
| **Both** | **65** | **7** | 12 | 1 |

**Net of both proposals: headline Table 1 unchanged at 65/7/12/1**, but the
membership of the 65 shifts (M252 enters; M346 exits).

---

## 3. Registry 312 vs 315

| Tree | Branch / tip | `len(server.tasks.TASKS)` |
|---|---|---:|
| `ecommerce-browser-gym-sonnet-completions` | `feat/multi-app` @ `2a133e9` | **312** |
| `ecommerce-browser-gym` (main dirty) | `feat/docs-sheets-coupons` (live) | **315** |

**Exact IDs in main only (315 − 312 = 3):**

| Task ID | One-line description | Sheets? |
|---|---|---|
| `M384/active_tab_sum_gate` | Sheets SUM-gate → ValueMart ×6 + confirmation email (Draft decoy / Approved Lines authority) | **Yes** |
| `M385/cross_sheet_qty_authority` | Sheets cross-sheet Approval qty → West Launch Kit ×4 (`=Inputs!D5`) | **Yes** |
| `M386/writeback_if_complete` | Sheets IF writeback → Complete → mail C21 time (Calendar Vendor Review; no market) | **Yes** |

Confirmed: the 312→315 delta is exactly the three exploratory Sheets tasks
M384–M386. Sonnet-completions worktree has none of them (frozen pre-sheets).

`trajectories/prepublication_validation_20260715/reconciliation.json` still
records `prompt_registry_count: 312` (matches sonnet worktree).

---

## 4. Denominator crib sheet

Reconfirmed from `/tmp/funnel_reconciliation.md` + `/tmp/funnel_detail.json`
(2026-07-21 funnel pass against live N=315 registry) and live CSV counts:

| Denominator | Exact N | Source | Use for |
|---|---:|---|---|
| **Sellable ledger rows** | **85** | `trajectories/sellable_breakers_v2.csv` | Table 1 shares (65/85 etc.); “sellable breakers” |
| **Tasks with any `coverage_matrix_v2.csv` row** (latest-wins v2 bookkeeping) | **203** | Funnel: defended_qwen 135 + defended_g51 10 + defended_g55 16 + sonnet_break 30 + sonnet_defend 9 + incomplete_midcascade 3 | Table 2 / cascade_v2 disposition shares — **not** full registry |
| **Adversarially break-screened (strict)** | **269** | 203 (v2) + 58 (v1-only) + 5 (matrix-less adversarial) + 3 (adversarial then re-classed capability) | “How many tasks faced the adversarial break screen” |
| Live registry (sonnet worktree) | 312 | `server.tasks.TASKS` @ 2a133e9 | Pre-sheets validation branch |
| Live registry (main dirty) | 315 | `server.tasks.TASKS` (+ M384–M386) | Current code tree |
| Screened by any model protocol | 313/315 | Funnel reconciliation | Only M29, M30 oracle-only |

### Ambiguous sentences that need an explicit denominator

| Claim shape | Problem | Fix |
|---|---|---|
| “~1/3 of breakers survive to strongest” | 65/85 = **76.5%**, not ~1/3. Plausible misread: **85/269 ≈ 31.6%** (sellables of adversarially screened) | Always write “65/85 Sonnet-break among sellables” or “85/269 sellable among adversarially screened” |
| “X% defended” without saying of what | 135/203 ≠ 135/315 ≠ 135/269 | Name matrix vs registry vs adversarial pool |
| “Reached Sonnet” | Escalation after gpt-5.5 ≥2/3 break, **or** any sonnet cell — different | Define before counting |
| “312 tasks” vs “315 tasks” | Sheets M384–M386 only on dirty main | Cite which tree |

---

## 5. Artifact paths (worktree)

All under `/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions/`:

- `docs/history/audits/TABLE1_STRONGEST_TIER_RECOMPUTE_2026-07-21.md` (this file)
- `docs/history/audits/M252_M346_LEDGER_RECONCILIATION_2026-07-21.md`
- `trajectories/TABLE1_STRONGEST_TIER_RECOMPUTE_20260721.json`
- Completions evidence: `trajectories/SONNET_CASCADE_COMPLETIONS_20260721.{md,json}`
