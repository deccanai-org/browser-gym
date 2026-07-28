# M342–M350 real confirmed-breaker cascade

**cost-root:** `trajectories/overnight_push/thin_vein_cascade/`  
**Protocol:** `eval.cascade_v2` / `eval.cascade_parallel` — **not** Sol/Opus.

## Scope

| | |
|---|---|
| Tasks | M342–M350 only (`tasks9.txt`) |
| Tiers | Qwen → gpt-5.1 → gpt-5.5 → Sonnet |
| Escalate | only if **≥2/3** BREAK at current tier |
| Seeds | **3** per task per tier (no early-stop within tier) |
| Oracle | **SKIPPED** — already PASS 27/27 @ 1.00 in `trajectories/thin_vein_oracle/` |
| Start tier | `qwen` |

## Cap & ports

| | |
|---|---|
| Spend cap | **$300** (matches `overnight_thin_cascade` global cap convention for thin shards; 9 tasks ≠ Sol/Opus $550) |
| Watchdog | `eval.budget_watchdog --cap 300 --trip-frac 0.90` on this root only |
| Base port | **8160** (+2 per shard) — avoids discarded Sol/Opus 8140/8142 |
| Shards | **3** (3 tasks each) |

## Standing / discarded

- Prior Sol/Opus thin-vein screen under `../xmodel_thin_vein/` is **DISCARDED** — never count toward confirms, merge, or forensic.
- Working-set baseline before this cascade: **SOL_OPUS_FORENSIC confirmed = 43** (unchanged by discarded thin Sol/Opus).
- Do **not** mark anything confirmed until cascade + forensic bar (state-routed forbidden, seed obs, fairness) are satisfied.
- Do **not** merge sellable CSV unless the user asks.

## Status

**COMPLETE** 2026-07-14 — spend $98.84 / $300; 3 newly confirmed after forensic
(M343, M348, M349). Working set **46** = prior SOL_OPUS_FORENSIC **43** + 3.
Details in `STATUS.md`, `FORENSIC.md`, `WORKING_SET_VEINS.json`.
Stamp in `logs/ACTIVE_STAMP`. Watchdog disarmed after completion.
