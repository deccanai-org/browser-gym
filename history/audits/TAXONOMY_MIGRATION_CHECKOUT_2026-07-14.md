# Taxonomy migration audit — retired checkout vein

Date: 2026-07-14

## Result

`checkout` is no longer a canonical vein. The core taxonomy contains exactly
10 top-level veins. Injection and source-anchoring remain two separately
reported footnotes outside the core denominator.

Historical migration-day recomputation over all 86 rows then present in
`trajectories/sellable_breakers_v2.csv`, excluding the two footnote rows:

| Canonical core vein | Count | Percent of 84 |
|---|---:|---:|
| stacked-default | 18 | 21.4% |
| content-default | 15 | 17.9% |
| sycophancy | 15 | 17.9% |
| instrument-default | 9 | 10.7% |
| ask-dont-guess | 5 | 6.0% |
| tool-affordance | 5 | 6.0% |
| infeasibility | 5 | 6.0% |
| self-contradiction | 5 | 6.0% |
| implicit-constraint | 4 | 4.8% |
| structural | 3 | 3.6% |

Assertions: core sum = 84; canonical `checkout` count = 0; the 42 historical
members preserve exact parity at instrument/content/stacked = 9/15/18.

## Single source and code changes

- `trajectories/vein_taxonomy.py`: owns the audited 42-task mapping, allowed
  canonical sets, and promoted canonical return labels.
- `eval/checkout_instrument_content.py`: now consumes the canonical mapping and
  fails on drift; it no longer reimplements token classification.
- `trajectories/_gen_backlog.py`: now imports `canonical_vein()` instead of
  maintaining a second vein classifier.
- `eval/recompute_headlines.py`: reports the current final recomputation status.
- `trajectories/overnight_push/thin_vein_cascade/WORKING_SET_VEINS.json`:
  recomputed its historical 16-member default family as 5 / 6 / 5.
- `tests/test_vein_taxonomy.py`: checks exact audit parity, 9/15/18 counts,
  allowed labels for every migration-day sellable row, the historical 84-row core sum, and zero
  canonical checkout labels.

## Migration-day report and Canvas changes

- `FINAL_PRE_REPORT_BASELINE_2026-07-14.md`
- `PROJECT_REPORT_2026-07-14.md`
- `trajectories/CHECKOUT_AXIS_AUDIT.md`
- `trajectories/PENDING_MERGE_VALIDITY_AUDIT.md`
- `README.md`
- `FAILURE_TAXONOMY.md`
- `PROJECT_CONTEXT.md`
- `WAVE_THIN_CORE_2026-07-14.md`
- `project-report-2026-07-14.canvas.tsx`
- `checkout-axis-audit.canvas.tsx`
- `pending-merge-validity-audit.canvas.tsx`

At the 2026-07-14 migration, `trajectories/sellable_breakers_v2.csv` had no
explicit vein field, so its schema and all then-current 86 task memberships
were intentionally left unchanged. The later M56 release hold changes the
active ledger to 85 and the current default split to 9/14/18 while preserving
this historical 9/15/18 audit.
`trajectories/SOL_OPUS_SELLABLE_VENN.md` and its Canvas derive only the
core/footnote boundary and required no distribution change.

## Intentionally retained checkout wording

- Functional product/task language: checkout pages, checkout actions,
  `place_order`, and task slugs such as `M73/expired_card_checkout`.
- Historical provenance: `CHECKOUT_AXIS_AUDIT.md`,
  `checkout_instrument_content_split.csv`,
  `eval/checkout_instrument_content.py`, and the matching Canvas/file names.
  Their current text explicitly identifies checkout as the retired prior
  category.
- Archived reports and saved trajectory outputs retain the taxonomy and model
  output that existed when they were generated; they are historical evidence,
  not current machine-readable taxonomy output.
