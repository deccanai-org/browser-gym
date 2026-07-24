# Gemini local pilot 20×3 — cost projection (2026-07-23)

## Status
- **Completed:** 60/60 episodes (`results/{0..59}.json`)
- **Workers:** finished; `STATUS.json` → `message: merged`, `failed_worker_exits: 0`
- **Merge:** launcher wrote outputs at 2026-07-23T21:04:13Z (fresh vs last result `59.json`)

## Cost (actual)
| Metric | Value |
|--------|-------|
| Total cost (est.) | **$439.1607** |
| $/episode | **$7.3193** |
| Tokens in / out | 219,028,303 / 92,007 |
| Tasks folded | 20 (11 breaker candidates ≥2/3, 9 defended) |

Artifacts: `cost_tracker_summary.json`, `coverage_matrix_gemini.csv`, `gemini_census_report.json`

## 945 projection at actual rate
- **945 × $7.3193 ≈ $6,916.78**
- Prior planning ballpark in `docs/history/plans/CURRENT_WORK_2026-07-21.md`: Gemini 3.1 Pro **~$1,200** for full screen

## Decision flags
| Question | Flag |
|----------|------|
| Revisit original ~$1,200 estimate? | **YES** — pilot implies ~**5.8×** higher (~$6.9k) |
| Revisit NO-GO on AI Studio Tier 1 (~$250/mo)? | **NO-GO confirmed / strengthened** — Tier 1 monthly budget covers ~34 episodes at this rate; cannot fund ~$6.9k census |

## Rate limits
- No `RESOURCE_EXHAUSTED` / rate-limit / 429 quota failures found in result JSONs or worker logs for this pilot.

## Explicit non-actions
- Did **not** launch Cloud Run / full 945.
- Did **not** touch sellable CSV.
