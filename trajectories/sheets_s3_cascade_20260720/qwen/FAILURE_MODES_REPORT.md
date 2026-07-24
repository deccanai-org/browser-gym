# Failure-mode report

- **Task**: `M386/writeback_if_complete`
- **Model**: `qwen/qwen3-vl-235b-a22b-instruct`  ·  **UI variant**: `normal`
- **Runs**: 1  ·  **Successes**: 0  ·  **Failures**: 1  (failure rate **100%**)

Each failure carries TWO layers: a broad `failure_class` (reusable taxonomy label) and a crystallized `failure_mode_signature` (the recurring causal chain). Clusters are grouped by SIGNATURE.

## Recurring failure modes (by signature, most frequent first)

### `missed:s3_writeback_if_then_mail`  —  1/1 (100%)

- **dominant failure_class**: `unclassified_failure`  (breakdown: {'unclassified_failure': 1})
- **missed required milestones**: ['s3_writeback_if_then_mail']
- **app path**: shop -> mail
- **fact gap (required facts never observed)**: none
- **representative episode**: `bbe5840d` (seed 2, stalled at step 0, 22 steps)
