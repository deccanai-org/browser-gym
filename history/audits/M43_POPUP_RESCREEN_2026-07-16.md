# M43 popup-tracking post-fix rescreen — 2026-07-16

Policy mirror: [M37 revalidation](M37_PREPUBLICATION_REVALIDATION_2026-07-15.md)
(fresh k=3 cascade under corrected harness before post-fix panels may be
cited; do not silently keep pre-fix panels as post-fix evidence).

## Sellable membership

**YES — M43 is in the active sellable set**
(`trajectories/sellable_breakers_v2.csv` row `M43/stale_delivery_date`,
source-anchoring footnote; historical class `gpt-5.1-only`).

## Why rescreen was owed

M43's gold path depends on live tracking ETA. Agents may open View tracking
via `window.open`. Prior model panels were screened **before** the
`BrowserCtx` popup-tracking fix (`harness/runner.py`). Harness-level fix was
already unit-verified; paid model rescreen was still owed for sellable
classification claims.

## Fresh cascade (corrected harness)

Command:

```bash
.venv/bin/python -m eval.cascade_v2 \
  --tasks "M43/stale_delivery_date" \
  --out trajectories/prepublication_m43_popup_rescreen_20260716/cascade \
  --base-port 8250 --cap 100 --confirm --max-steps 120
```

| Tier | Valid | Break | Success | Incomplete | Invalid |
|---|---:|---:|---:|---:|---:|
| Qwen | 3/3 | **2/3** | 0/3 | 1/3 | 0/3 |
| GPT-5.1 | 3/3 | **2/3** | 0/3 | 1/3 | 0/3 |
| GPT-5.5 | 3/3 | **1/3** | 2/3 | 0/3 | 0/3 |
| Sonnet | — | — | — | — | not reached |

- Escalate gate (≥2/3): passed at Qwen and GPT-5.1; **failed at GPT-5.5** → stop
- `stopped_at_tier`: `gpt-5.5`
- `reached_sonnet`: false
- Terminal status: **COMPLETE** (not credit-blocked)
- Spend: **$5.68**

Evidence:

- `trajectories/prepublication_m43_popup_rescreen_20260716/cascade/coverage_matrix_v2.csv`
- `trajectories/prepublication_m43_popup_rescreen_20260716/cascade/FORENSIC.json`
- `trajectories/prepublication_m43_popup_rescreen_20260716/cascade/FORENSIC.md`
- `trajectories/prepublication_m43_popup_rescreen_20260716/cascade/run.log`
- Per-tier trajectories under `cascade/{qwen,gpt-5.1,gpt-5.5}/`

## Membership decision

**RETAIN** as active sellable **gpt-5.1-only** source-anchoring footnote.

Clean reproduction of the historical classifying pattern succeeded under the
fixed harness (≥2/3 BREAK at Qwen and GPT-5.1; GPT-5.5 <2/3). Removal
condition (“fails clean reproduction”) was **not** met. No ledger hold.

**Publication rule:** cite only these post-fix panels for M43 model-break
claims. Pre-fix directories (`m43_gpt51`, `opus_crossmodel_b2/M43_*`,
`sonnet_distinct/M43_*`, etc.) remain historical and must not be described as
post-fix evidence.

## Relation to Section 1C harness check

Popup tab tracking itself remains CLOSED at harness/unit level
([popup post-fix note](SECTION_1C_POPUP_TRACKING_POSTFIX_2026-07-16.md)).
This audit closes the **paid M43 rescreen** owed for sellable classification.
