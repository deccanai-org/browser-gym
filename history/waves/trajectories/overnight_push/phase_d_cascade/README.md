# Phase D cascade (15 built)

**cost-root:** `trajectories/overnight_push/phase_d_cascade/`  
**Protocol:** `eval.cascade_v2` / `eval.cascade_parallel` — Qwen→5.1→5.5→Sonnet.

| | |
|---|---|
| Tasks | 15 built (`tasks15.txt`) — batch1 + batch2 survivors |
| Seeds | 3 per task per tier; escalate if ≥2/3 BREAK |
| Oracle | PASS 45/45 @ 1.00 in `trajectories/phase_d_oracle/` |
| Cap | **$400** |
| Base port | **8170** (+2/shard) — avoids thin_vein 8160/8162/8164 |
| Shards | 3 |
| Active stamp | see `logs/ACTIVE_STAMP` |

Cascade and forensic are complete. **Confirmed genuine:** M354
(infeasibility) and M366 (self-contradiction). See `FORENSIC.md`. Do not merge
sellable CSV without later user instruction.
