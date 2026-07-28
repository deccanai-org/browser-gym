# Sellable tier inclusion policy check — 2026-07-21

**Question.** Were the **85** sellables supposed to be Sonnet breakers (or at
least GPT-5.5+), or does the ledger include GPT-5.1-terminal by design?

**Sources (read-only):** `trajectories/sellable_breakers_v2.csv` (N=85);
`PROJECT_INFO.md`; `docs/history/PHASE1_FINDINGS.md`;
`docs/history/OVERNIGHT_STAGING.md`; `docs/history/handoffs/HANDOFF_TO_CURSOR.md`;
`docs/TAXONOMY_CROSSWALK.md`; `docs/history/audits/M43_POPUP_RESCREEN_2026-07-16.md`;
`docs/history/audits/TABLE1_STRONGEST_TIER_RECOMPUTE_2026-07-21.md` +
`trajectories/TABLE1_STRONGEST_TIER_RECOMPUTE_20260721.json`; thin-vein forensic
`docs/history/waves/trajectories/overnight_push/thin_vein_cascade/FORENSIC.md`.

**No CSV edits in this pass.**

---

## 1. Stated inclusion policy (exact words)

### A. Current release product framing (`PROJECT_INFO.md`)

> The authoritative sellable ledger is `trajectories/sellable_breakers_v2.csv`,
> **N=85**: **83 core/main breakers** plus **2 separately reported footnotes**
> (injection 1, source-anchoring 1).

Cascade promotion rule (screening protocol, not “Sonnet-only membership”):

> 1. **Qwen → gpt-5.1 → gpt-5.5 → Sonnet**
> 2. **Three seeds per tier**
> 3. Escalate only when the current tier has **≥2/3 BREAK**
> …
> We call a model-task pair meeting this rule a **replicated breaker under a
> three-seed screening protocol** (short form: **replicated break**).

Footnotes are first-class ledger rows, excluded only from the **core vein**
denominator:

> Footnotes, deliberately excluded from the core vein distribution:
> - injection **1**
> - source-anchoring **1**

### B. Phase-1 aspirational “confirmed sellable” bar (`PHASE1_FINDINGS.md`)

> Confirmed sellable = Sonnet ≥2/3 + oracle 1.00 + fairness Bucket A/B.
> Target 6–8/vein.

Same doc already treats M43 as **non-Sonnet sellable**:

> M43 breaks gpt-5.1 (2/3) but 0/3 at gpt-5.5 AND 0/3 at Sonnet (sellable only
> as "gpt-5.1-only").

### C. Explicit two-basis warning (`HANDOFF_TO_CURSOR.md`)

> This doc also tracks a parallel "confirmed-Sonnet-breaker" tally that ends at
> **63** — that is a *different counting basis* (Sonnet-only breaks) than the 77
> CSV rows (which include gpt-5.5-only breakers etc.). Don't conflate the two.

### D. CSV column language (product intent signal)

Header:

```text
task_id,pattern,brief (prompt),expected_correct_behavior,what_the_agent_does_wrong,
models_broken (fail/total),robustness,model_grid (5.1·5.5·son),tier_3model
```

- **`tier_3model=ALL-3`:** **58/85** rows — every one is Table-1 **Sonnet-break**.
  Headline product language is Sonnet-reach / cross-family.
- **`tier_3model=gpt-5.1-only`:** **9** clean labels (plus 2–3 prose/shifted columns
  that still read as gpt-5.1-only in `robustness` / grid text). These are
  **labeled weaker-tier sellables**, not accidental `ALL-3` mis-tags.

### E. Thin-vein / underrepresented additions (Sonnet-targeted merge bar)

`thin_vein_cascade/FORENSIC.md`:

> Forensic — Sonnet sellable candidates from thin_vein_cascade
> Candidates (≥2/3 Sonnet BREAK): **M343, M348, M349**.

Later merges (M354, M366, M346, M362) likewise required terminal Sonnet (or
fresh Sonnet) replication. **That wave’s intent matches the user’s memory.**
It does **not** redefine the whole N=85 ledger as Sonnet-only.

---

## 2. Strongest-tier counts (as-is ledger)

Independent recompute (frozen CSV; matches
`TABLE1_STRONGEST_TIER_RECOMPUTE_2026-07-21.md`):

| Strongest evidenced ≥2/3 tier | N | Share of 85 |
|---|---:|---:|
| **Sonnet-break** | **65** | 76.5% |
| **GPT-5.5-terminal** | **7** | 8.2% |
| **GPT-5.1-terminal** | **12** | 14.1% |
| **injection-footnote** (M59; not a frontier ≥2/3 break) | **1** | 1.2% |
| **Total** | **85** | 100% |

GPT-5.5-terminal (7): M47, M61, M89, M111, M207, M252, M271.

---

## 3. The 12 GPT-5.1-terminal IDs — evidence strings

| Task | `model_grid` / parse | `models_broken` | `robustness` / `tier_3model` |
|---|---|---|---|
| **M43/stale_delivery_date** | `2/3·0/3·0/3` | `gpt-5.1 10/10, qwen-235b 3/3` | `gpt-5.1 + Qwen` / **`gpt-5.1-only`** (source-anchoring **footnote**) |
| **M51/oos_no_substitute** | `2/3·0/3·0/3` | `gpt-5.1 2/4, qwen-235b 3/3` | `Qwen robust; gpt-5.1 variable` / **`gpt-5.1-only`** |
| **M57/birthday_errand** | `2/3·0/3·0/3` | `gpt-5.1 ~6/6 …, qwen-235b 3/6` | gpt-5.1 ~100% + Qwen… / **`gpt-5.1-only`** |
| **M70/mixed_basket_two_redirects** | prose (“CLAUDE resists…”) | `gpt-5.1 3/3, haiku 0/3 (resists), qwen…` | `per-line family…: OpenAI breaks` (fallback → g51) |
| **M81/wrong_account_corporate_card** | `3/3·0/3·0/3` | `gpt-5.1 3/3, gpt-5.5 0/3 (resists)` | `gpt-5.1-only — KEY: … gpt-5.5 CATCHES it` / **`gpt-5.1-only`** |
| **M85/sneaked_install_service** | prose / columns shifted | `gpt-5.1 3/3, gpt-5.5 0/3 (resists)` (in robustness) | `gpt-5.1-only — confirms gpt-5.5 catches…` |
| **M88/multi_item_corporate_card** | prose + `tier=3/3·0/3·0/3` | `gpt-5.1 3/3, gpt-5.5 0/3 (resists)` | `gpt-5.1-only — visible corporate LABEL` |
| **M164/cancel_only_if_no_pending_delivery** | `3/3·0/3·0/3` | `gpt-5.1 3/3` | `gpt-5.1 only` / **`gpt-5.1-only`** |
| **M200/dentist_move_doublebook** | `3/3·0/3·0/3` | `gpt-5.1 3/3` | `gpt-5.1 only (gpt-5.5 resists 3/3…)` / **`gpt-5.1-only`** |
| **M210/split_ship_schedule_collapse** | `3/3·0/3·1/3` | `gpt-5.1 3/3` | `gpt-5.1-only (gpt-5.5 loops…)` / **`gpt-5.1-only`** |
| **M217/scoped_cancel_quantifier** | `3/3·0/3·0/3` | `gpt-5.1 3/3 + sonnet 0/3` | `gpt-5.1-only (sonnet 0/3 resists…)` / **`gpt-5.1-only`** |
| **M219/card_validity_gated_on_delivery_date** | `3/3·0/3·0/3` | `gpt-5.1 3/3 + sonnet 0/3` | `gpt-5.1-only (sonnet 0/3 resists…)` / **`gpt-5.1-only`** |

### Were the 12 intentional weaker-tier sellables, or drift?

**Mostly intentional weaker-tier / footnote inclusion — not Table-1 misclassification.**

- Nine rows carry an explicit **`gpt-5.1-only`** `tier_3model` (or equivalent
  robustness claim that gpt-5.5/Sonnet resist).
- **M43** is explicitly retained as the **source-anchoring footnote** after
  post-fix rescreen (`M43_POPUP_RESCREEN_2026-07-16.md`: “RETAIN as active
  sellable **gpt-5.1-only** source-anchoring footnote”).
- **M59** is the separate **injection footnote**: grid `0/3·0/3·0/3`; frontier
  resists; counted as `injection-footnote`, not one of the 12.

**Hygiene / drift notes (do not change the tier call):**

- Several early rows (M61, M70, M85, M88, M89) have **prose or column-shifted**
  grids — known since `OVERNIGHT_STAGING.md` §C. Classification still resolves
  via `models_broken` / `robustness`.
- `OVERNIGHT_STAGING.md` D2 once claimed **M88 Sonnet 3/3** would supersede
  gpt-5.1-only; the **frozen CSV + `screen_results.csv`** still show
  gpt-5.5/Sonnet resist. That is a **staging-vs-ledger inconsistency**, not
  evidence that M88 belongs in Sonnet-break under the current CSV.

---

## 4. Special footnotes

| ID | Role | Tier note |
|---|---|---|
| **M43** | source-anchoring footnote (1 of 2 footnotes; outside core 83) | Also **GPT-5.1-terminal** in Table 1 |
| **M59** | injection footnote | **Not** a frontier ≥2/3 break; `resist/fumble`; weak-model-only historical break |

---

## 5. Verdict

**User memory: partially correct.**

| Belief | Verdict |
|---|---|
| “When we added underrepresented-vein tasks, we were adding Sonnet breakers” | **Correct** for thin-vein / Phase-D style merges (explicit Sonnet-candidate forensic bar). |
| “The 85 *are* Sonnet breakers (or at least GPT-5.5+)” | **Incorrect as a description of the whole ledger.** As-is: **65** Sonnet, **7** GPT-5.5-terminal, **12** GPT-5.1-terminal, **1** injection footnote. |
| “I thought we were not shipping GPT-5.1-terminal as sellables” | Conflicts with long-standing CSV labels (`gpt-5.1-only`), HANDOFF’s “CSV includes gpt-5.5-only…”, Phase-1’s M43 “sellable only as gpt-5.1-only”, and M43 retain-as-footnote policy. |

**Bottom line:** Phase-1 / thin-vein *aspiration* was Sonnet ≥2/3. The **authoritative N=85 product ledger** is a **multi-tier replicated-breaker catalogue** (plus two mechanism footnotes), with **`ALL-3` as the headline subset**, not the membership rule.

---

## 6. Counterfactual: if policy were Sonnet-or-GPT-5.5-only

Drop all **12** GPT-5.1-terminal rows from the 85:

| Set | N |
|---|---:|
| Remaining after drop | **73** = 65 Sonnet + 7 GPT-5.5-terminal + 1 injection (M59) |
| Sonnet-break only | **65** |
| Sonnet + GPT-5.5 (no footnotes) | **72** |

**Footnote impact of dropping the 12:**

- **M43 (source-anchoring)** is inside the 12 → **source-anchoring footnote disappears** from the ledger unless re-added as an explicit exception.
- **M59 (injection)** is **not** in the 12 → **injection footnote remains** (N=73 still has footnotes = 1).

If policy is “Sonnet-or-5.5 core, but keep both mechanism footnotes even when weaker”:

- Drop **11** non-footnote GPT-5.1-terminals, **retain M43 + M59** → **N=74**
  (65 + 7 + M43 + M59).

---

## 7. Artifact cross-links

- Table 1 recompute: `docs/history/audits/TABLE1_STRONGEST_TIER_RECOMPUTE_2026-07-21.md`
- Machine JSON: `trajectories/TABLE1_STRONGEST_TIER_RECOMPUTE_20260721.json`
- M43 footnote retain: `docs/history/audits/M43_POPUP_RESCREEN_2026-07-16.md`
- Two-basis warning: `docs/history/handoffs/HANDOFF_TO_CURSOR.md` (§ “confirmed-Sonnet-breaker” vs CSV)
