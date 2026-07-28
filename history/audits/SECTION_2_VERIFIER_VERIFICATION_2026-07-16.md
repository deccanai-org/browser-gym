# Section 2 — Verifier verification — 2026-07-16

Protocol: `docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` §2A–§2C.
Living sellable set: exact **85** from `trajectories/sellable_breakers_v2.csv`.

Membership notes:

- **M56/gift_errand** is a **release hold** and is **not** in the active 85
  ([hold note](M56_RELEASE_HOLD_2026-07-15.md)).
- Footnote classes remaining inside the 85 (e.g. injection M59, source-anchoring
  M43) stay sellable; no mass removals in this pass.

## B1) Four-part test coverage

### Method

Inventory reused:

- `trajectories/task_verifier_inventory.json` `seed_audit` (forbidden false @0,
  noop incomplete) — **85/85**
- `tests/test_section3_reward_hacking.py::test_preexisting_state_cannot_succeed_or_fire_forbidden`
  — parametric seed/untouched for all 85
- Focused pytest attribution via
  `eval/prepublication_section2_coverage.py` (AST + name/body classification)
- Prior latch probes for M271/M272/M307/M312 in Section 3

### Result

| Metric | Value |
|---|---|
| N complete (all four parts present) | **85/85** |
| Incomplete | **none** |

Machine-readable matrix:
[`trajectories/prepublication_section2_20260716/four_part_coverage.json`](../../../trajectories/prepublication_section2_20260716/four_part_coverage.json)

Regenerate:

```bash
.venv/bin/python -m eval.prepublication_section2_coverage
```

### Additive tests (genuine missing cells only)

Prior focused gaps (positive and/or named-forbidden) for
M271, M272, M307, M312, M354 → closed additively in:

[`tests/test_section2_four_part_gaps.py`](../../../tests/test_section2_four_part_gaps.py)

```bash
.venv/bin/python -m pytest -q tests/test_section2_four_part_gaps.py
```

No verifier semantics changed. No sellable removals.

**Five-task confirmation (M271/M272/M307/M312/M354):** purely missing focused
pytest cells — writing the tests pinned existing suite behavior and did **not**
reveal unexpected verifier semantics. Evidence: additive-only
`tests/test_section2_four_part_gaps.py`; no edits to those five suites/factories
in `server/verifiers.py` / task builders for this coverage work (unrelated
working-tree edits touch M291 docs/BRIEFS only).

### Per-part evidence sources (all 85)

| Part | Primary evidence |
|---|---|
| seed-state | Inventory `seed_audit` + Section 3 preexisting probe (+ focused `env_truth` / gap tests where present) |
| positive-path | Focused pytest asserting `success is True` / `score == 1.0` (incl. gap file) |
| forbidden-path | Focused pytest asserting named forbidden fires and/or Section 3 latch for M271/272/307/312 |
| do-nothing | Inventory noop incomplete + Section 3 untouched `success is False` (+ focused do-nothing names) |

## B2) Independent Reviewer B process

### Process materials (human-usable)

| Path | Role |
|---|---|
| [`trajectories/prepublication_section2_20260716/reviewer_b/INSTRUCTIONS.md`](../../../trajectories/prepublication_section2_20260716/reviewer_b/INSTRUCTIONS.md) | Blindness rules, sheet fields, reconciliation |
| [`.../PROMPTS_ONLY.md`](../../../trajectories/prepublication_section2_20260716/reviewer_b/PROMPTS_ONLY.md) / [`prompts_only.json`](../../../trajectories/prepublication_section2_20260716/reviewer_b/prompts_only.json) | Prompts only — no verifier source |
| [`.../scoring_sheet_template.csv`](../../../trajectories/prepublication_section2_20260716/reviewer_b/scoring_sheet_template.csv) | Blank human sheet (`human_reviewer_b`) |
| [`.../RECONCILIATION_LOG.md`](../../../trajectories/prepublication_section2_20260716/reviewer_b/RECONCILIATION_LOG.md) | Disagreement log template |

Also mirrored as:
[`docs/history/audits/SECTION_2_INDEPENDENT_REVIEWER_2026-07-16.md`](SECTION_2_INDEPENDENT_REVIEWER_2026-07-16.md)

### AI-B first fill (not human)

| Field | Value |
|---|---|
| Run? | **Yes** |
| Label | `independent_ai_reviewer_b` |
| Human complete? | **No** |
| Scores | `reviewer_b/independent_ai_reviewer_b_scores.{json,csv}` |
| Comparison | `reviewer_b/comparison_ai_b_vs_verifier.json` |

Contamination note (honest): the same coding agent has previously seen verifier
code in-repo. The fill is prompt-heuristic and **must not** be cited as human
independent review.

### Divergence highlights (do not mass-change verifiers)

Curated for human B priority rewrite:

1. **M59** — phishing/PII exfil (not generic “verify claims”)
2. **M43** — reminder must track **live** delivery day
3. **M211** — false “stopped” email after cancel no-op on shipped order
4. **M346** — three separate candidate ETA emails (no co-exposure)
5. **M362** — dinner order OK; therapy details in delivery note forbidden

Broader theme-miss flags in the comparison JSON are coarse lexical heuristics;
treat as a review queue, not a verifier rewrite list.

### Remaining for human Reviewer B

1. Fill `scoring_sheet_template.csv` blind from `PROMPTS_ONLY.md`
2. Reconcile vs ledger + inventory; append `RECONCILIATION_LOG.md`
3. Only then mark protocol §2C human checkboxes closed

## Protocol checkbox recommendations (§2)

See updates in `docs/PRE_PUBLICATION_VALIDATION_PROTOCOL.md` §2A / §2C.
