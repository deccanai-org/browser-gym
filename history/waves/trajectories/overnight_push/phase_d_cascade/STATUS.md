# STATUS — phase_d_cascade (15 built)

| | |
|---|---|
| Stamp | **20260714_105851** |
| Cost-root | `trajectories/overnight_push/phase_d_cascade/` |
| Tasks | `tasks15.txt` — all 15 built Phase D IDs |
| Cap | **$400** (watchdog disarmed after clean completion; spent $38.77) |
| Base ports | **8170 / 8172 / 8174** (3 shards) |
| Oracle | **PASS 45/45 @ 1.00** — `trajectories/phase_d_oracle/` |
| Thin-vein | left alone on 8160/8162/8164 |

## Screen (complete — Qwen→5.1→5.5→Sonnet, escalate ≥2/3)

All built: M353, M354, M357, M358, M361, M362, M366, M367, M368, M369, M370, M371, M372, M373, M374.

Prior stamp `20260714_103146` screened first 5; this stamp re-runs full set (same cost-root).

Cascade completed cleanly with 15/15 task rows, no shard failures, and $38.77
spent. Terminal candidates were M354 and M366 (both Sonnet 3/3).

**Confirmed genuine after forensic:** **M354** (infeasibility) and **M366**
(self-contradiction). See `FORENSIC.md` and
`FORENSIC_SONNET_CANDIDATES.json`. CSV remains unmerged.
