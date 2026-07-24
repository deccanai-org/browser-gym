# Failure-mode report

- **Task**: `M384/active_tab_sum_gate`
- **Model**: `qwen/qwen3-vl-235b-a22b-instruct`  ·  **UI variant**: `normal`
- **Runs**: 1  ·  **Successes**: 0  ·  **Failures**: 1  (failure rate **100%**)

Each failure carries TWO layers: a broad `failure_class` (reusable taxonomy label) and a crystallized `failure_mode_signature` (the recurring causal chain). Clusters are grouped by SIGNATURE.

## Recurring failure modes (by signature, most frequent first)

### `missed:s1_sum_gate_order_and_email`  —  1/1 (100%)

- **dominant failure_class**: `never_reached_checkout`  (breakdown: {'never_reached_checkout': 1})
- **missed required milestones**: ['s1_sum_gate_order_and_email']
- **app path**: shop
- **fact gap (required facts never observed)**: none
- **representative episode**: `14bb57b0` (seed 2, stalled at step 0, 31 steps)
