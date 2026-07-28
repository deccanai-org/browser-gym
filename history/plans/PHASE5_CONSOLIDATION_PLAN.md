# Phase 5 consolidation plan — blueprint (not yet executed)

Generated 2026-07-10 from the md-inventory workflow (run `wf_9ad3c0b5-b59`), 35 curated
docs classified + synthesized. **Nothing here is executed yet** — this is the spec for the
single consolidation pass, to run bundled with the deferred one-pass CSV merge to 82 so the
docs don't drift again. Living-doc NUMBER fixes are GATED on that merge; file moves + deletions
need explicit sign-off (see bottom).

## Sort result: 9 living · 26 history · ~570 archival

### A. LIVING (stay top-level, kept current) — 9
| doc | status | action (non-number) |
|---|---|---|
| README.md | number-stale | line 68 already fixed (Phase 4); numbers → post-merge |
| PROJECT_CONTEXT.md | number-stale | **top priority**; Appendices A/B are AUTO-GEN → regenerate from code/CSV, don't hand-edit; Appendix C broken (140+ "/ (0 jsonl)") → regen or drop |
| DESIGN.md | partially-stale | annotate the A1..C3 **nine** as an original SEED set (not whole gym); 12→38-class + Phase-4 note |
| WALKTHROUGH.md | partially-stale | clarify the 9 are seed task-factory templates |
| TASKS.md | current | KEEP "12 templates" (template count ≠ 275 registry) — add one clarifying line |
| MILESTONES.md | current | none |
| FAILURE_TAXONOMY.md | current (07-10) | none (rewritten in Phase 4) |
| ANNOTATION_PIPELINE.md | current | refresh stage-9 framing to Phase-4 two-field labeling (numbers OK) |
| PIXEL_VS_JSON.md | partially-stale | model-id drift: Sonnet 4.5 → claude-sonnet-4-6/haiku-4-5; drop merged fork-checkout step; _TBD_ result tables need a matrix run (out of scope) |

### B. HISTORY (move to docs/history/, keep, de-emphasize) — 26
CURSOR_SIM_INTEGRATION, DIFFERENTIATOR_ANALYSIS, HAIKU_ROBUSTNESS_M24-26, HARNESS_AUDIT_REPORT,
INDUSTRY_ALIGNMENT, LEADERBOARD, LIVE_HARNESS_SPIKE, M13_FAILURE_WRITEUP, OVERNIGHT_BUILD_LOG,
OVERNIGHT_STAGING, OVERNIGHT_STATUS, **PHASE1_FINDINGS.md (LOCKED — needs approval)**,
SCREENING_REPORT, VEIN_BOUNDARY_ANALYSIS, VEIN_BREAKER_FORENSICS (co-locate w/ BOUNDARY — H-X1 pair),
NEW_MECHANISM_RESEARCH.staged.md → promote to docs/history/NEW_MECHANISM_RESEARCH.md (drop suffix),
trajectories/{CROSS_MODEL_BATCHES,CROSS_MODEL_COMPARISON}.md → docs/history/cross_model/,
trajectories/fairness_log_v2.md,
7× spec catalogues → docs/history/specs/ (designed_catalogue_new_{mechanisms,surface}, designed_longhorizon_specs,
designed_new_patterns{,_v2}, designed_specs_M111_M120, recovered_combination_candidates).

### C. ARCHIVAL — ~570 auto-generated cascade run-reports
`trajectories/cascade_*/**/*.md` (cascade_report.md, FAILURE_MODES_REPORT.md across 18 dirs).
Regenerable from each run's JSONL/CSV. → tar to `docs/history/archive/cascade_reports.tgz` +
gitignore `cascade_*/*.md` (keep the .csv/.json of record), OR delete. Do NOT track loose.

## Stale-number reconciliation (LIVING docs only — GATED on the 82-merge)
Concentrated in **PROJECT_CONTEXT.md + README.md**. Regenerate via `python -m eval.recompute_headlines`
(canonical_vein, never hand-rolled). Fixes:
- **234 tasks → 275** (registry) — both docs, multiple sites.
- **66 breakers → 77 (pre-merge) / 82 (target post-merge)** — both docs.
- Derived counts (185 breaker-with-forbidden, 49 capability, "break-all-3 = 41", "5.5+son = 45",
  coverage 74×3, ~750 pytest) → **recompute post-merge**; reconcile the 185-vs-226 breaker
  definition (FAILURE_TAXONOMY: 226 breaker-with-forbidden / 49 capability-only of 275).
- ADD to both: gpt-5.6-sol (13/20) + Opus 4.8 (9/20) cross-model probe; Phase-4 vein+specific_failure
  (unlabeled 54.7%→6.6%); canonical per-vein counts (checkout 41 · sycophancy 14 · tool-affordance 6 ·
  ask-dont-guess 5 · infeasibility 3 · structural 3 · self-contradiction 2 · source-anchoring 1 ·
  injection 1 · implicit-constraint 1).
- DESIGN/WALKTHROUGH: the "9 tasks" / "37 tests" are SEED-set framing → annotate, don't rewrite to 275.

## GUARDRAILS (from synthesis — do not violate)
1. **PHASE1_FINDINGS.md is LOCKED** — relocation needs explicit user approval; stage, don't auto-move.
2. **Never touch numbers in HISTORY docs** — rewriting a dated record's counts destroys audit value.
3. **PROJECT_CONTEXT Appendices A/B are auto-generated** — regenerate from code/CSV, don't hand-edit.
4. **Coincidence trap:** "break-all-3 frontier = 41" ≠ canonical checkout-vein = 41. DIFFERENT metrics.
5. **canonical_vein() for all per-vein counts**, never the CSV `pattern` column. [[always-use-canonical-vein]]
6. Locked data artifacts untouched: sellable_breakers_v2.csv, coverage_matrix_v2.csv, vein_taxonomy.py.
7. Verify VCS state before any move; do not push. [[push-only-when-asked]]
8. Do number reconciliation AFTER the merge, as one pass, or docs re-drift. [[csv-merge-one-pass]]

## Duplicates to reconcile before archiving (follow-up, not blockers)
- designed_catalogue_new_{mechanisms,surface}.md — two drafts of the M123–M182 batch (60 vs 58) → de-dup.
- designed_new_patterns.md vs _v2.md — explicit v1/v2 → co-file.
- recovered_combination_candidates.md — internal near-dupes + reused M-numbers (four "M212", three "M213") → ID-reservation reconcile. [[cross-check-id-reservations]]
- Cross-check M111–M182 / M206–M211 specs were actually built into the 275-registry vs renumbered.

## EXECUTED 2026-07-10 ("do moves now, hold numbers")
- [x] Created `docs/history/{,cross_model/,specs/,archive/}`; moved 25 history docs in (git detects renames at commit).
- [x] Promoted NEW_MECHANISM_RESEARCH.staged.md → docs/history/NEW_MECHANISM_RESEARCH.md.
- [x] PHASE1_FINDINGS.md **split** (per user): live ID ledger → top-level `ID_RESERVATIONS.md` (verbatim ranges + ceiling flagged M286→M314); narrative + F1–F4 → docs/history/PHASE1_FINDINGS.md **byte-identical** (verified). Grepped all path-refs first — only `eval/cascade_v2.py:55` comment cited it (updated).
- [x] 141 cascade run-reports → `docs/history/archive/cascade_reports.tgz` + gitignored `trajectories/cascade_*/*.md` (the "~570" estimate was high; real count 141).
- [x] Living-doc **link** fixes: README + PROJECT_CONTEXT×3 (CROSS_MODEL_COMPARISON path, LEADERBOARD list).
- [x] Non-number **framing/model-id drift**: DESIGN (9-seed + taxonomy notes), TASKS (12-templates≠275), ANNOTATION_PIPELINE (stage-9 Phase-4), PIXEL_VS_JSON (Sonnet 4.5→4.6, dropped merged fork step).
- [x] Verified post-reorg: no broken living-doc links; `eval.recompute_headlines` + `eval.label_coverage` still run.

## STILL HELD — needs the post-merge 82-CSV (the deferred one-pass morning merge)
- [ ] Living-doc **NUMBER** rewrites: PROJECT_CONTEXT + README (234→275, 66→77/82, all derived counts, add cross-model + Phase-4 + canonical per-vein). PROJECT_CONTEXT Appendices A/B are AUTO-GEN → regenerate, don't hand-edit; Appendix C broken → regen/drop.
- [ ] 5.1 **FINAL** recompute (`eval.recompute_headlines` against the 82-CSV) + reconcile the 185-vs-226 breaker-definition + re-run pytest for the test count.
- [ ] 5.3 **sanity trace** (3–4 random confirmed breakers, task_id/vein/tier/verdict consistent everywhere) — after numbers land.
- [ ] Follow-ups (non-blocking): de-dup the spec catalogues + reconcile M111–M182/M206–M211 built-vs-renumbered; the ~288 non-cascade trajectory run-.md (out of the cascade-only decision scope).
