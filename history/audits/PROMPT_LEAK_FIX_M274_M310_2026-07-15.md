# Prompt Leak Fix — M274–M310 — 2026-07-15

## Verdict

**CLOSED.** Live briefs for M274, M291, M294, M295, M300, M301, M308,
M309, and M310 are now natural user-facing requests only. Internal hypothesis,
verifier, registration, implementation, fairness-bucket, and expected-result
language was removed without changing each task's intended semantics.

Authenticated reset responses are covered by
`tests/test_prompt_leakage.py`; the same test rejects known internal markers.
Each of the nine exact task IDs is reset through the authenticated
`/_harness/reset` route and the returned `task_brief` is checked—not merely
the source dictionary.

## Registry/export evidence

- Current brief snapshot: `docs/history/snapshots/ALL_TASK_BRIEFS.md`
- Validation:
  `trajectories/prepublication_prompt_fix_20260715/brief_registry_validation.json`
- Result: 312 registry tasks, 312 non-empty briefs, 312 unique archive
  headings, exact ordered set equality.

## Historical evidence status

All historical trajectories for these nine IDs are invalid for prompt-clean
claims and are marked superseded in:

`trajectories/prepublication_prompt_fix_20260715/historical_runs_superseded.json`

None of the nine IDs appears in `trajectories/sellable_breakers_v2.csv`; the
active sellable count is unaffected.

Focused and full-suite outputs are archived under
`trajectories/prepublication_validation_20260715/`.
