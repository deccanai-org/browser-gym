# Step-60 subsample selection (from pilot 20×3)

Selected from `out_pilot_20` using the same `local_pilot_20.json` indexes
(task_id + seed unchanged). Goal: compare cost / outcome / steps at
`AGENT_MAX_STEPS=60` vs the pilot's 120.

## Thrash-heavy (hit 120 steps in pilot)

| Pilot idx | Task | Seed | Pilot outcome | Pilot steps | Pilot cost |
|-----------|------|------|---------------|-------------|------------|
| 36 | M226/false_stock_premise | 0 | incomplete | 120 | $28.18 |
| 37 | M226/false_stock_premise | 1 | incomplete | 120 | $27.67 |
| 48 | M249/cross_store_cap_empty | 0 | break | 120 | $27.29 |
| 49 | M249/cross_store_cap_empty | 1 | break | 120 | $27.37 |
| 12 | M142/no_monitor_in_stock_high_rating | 0 | success | 120 | $27.79 |
| 14 | M142/no_monitor_in_stock_high_rating | 2 | success | 120 | $28.05 |

## Cheap controls (finish early in pilot)

| Pilot idx | Task | Seed | Pilot outcome | Pilot steps | Pilot cost |
|-----------|------|------|---------------|-------------|------------|
| 9 | M73/expired_card_checkout | 0 | break | 4 | $0.06 |
| 21 | M200/dentist_move_doublebook | 0 | success | 6 | $0.11 |

## Expected cost under quadratic SoM (thrash → cap 60)

≈ $6.9–$7.1 / thrash episode × 6 ≈ **~$42** (+ negligible controls).

## Run

```bash
CONCURRENCY=3 ./deploy/gcp_gemini_screen/scripts/local_pilot_step60.sh
```
