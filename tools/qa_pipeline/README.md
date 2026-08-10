# Mock UI QA Pipeline

Automated discover → report → (optional) fix loop for the five mock UIs:

| App | Folder | Port |
|---|---|---|
| ShopGym | `websites/amazon_mock` | 5201 |
| ValueMart | `websites/ebay_mock` | 5202 |
| ShopMail | `websites/gmail_mock` | 5203 |
| GymCal | `websites/google_calendar_mock` | 5204 |
| GymEats | `websites/uber_eats_mock` | 5205 |

## Quick start

```bash
# From repo root — install once
pip install playwright pyyaml
playwright install chromium

# Serve all 5 UIs (preview builds) + run the full audit
python -m tools.qa_pipeline.run_qa

# Or against already-running servers:
python -m tools.qa_pipeline.run_qa --no-serve --base-url http://127.0.0.1

# Regression suite only (the 54 known defects from the Aug 2026 audit):
python -m tools.qa_pipeline.run_qa --suite regression

# Exhaustive crawl (every route, click, dropdown, scroll, viewport):
python -m tools.qa_pipeline.run_qa --suite full

# Apply safe auto-fixes for known pattern classes, then re-verify:
python -m tools.qa_pipeline.run_qa --auto-fix --suite regression
```

Reports land in `tools/qa_pipeline/reports/<timestamp>/`:

- `report.md` / `report.html` — findings with severity, app, repro steps
- `results.json` — machine-readable
- `screenshots/` — failure captures

## What it tests

1. **Regression checks** (`checks/regression.yaml`) — every finding from
   `docs/qa/QA_REPORT_2026-08-06.md` encoded as an executable assertion.
2. **Static / source checks** — seed/UI shape mismatches, money rounding helpers,
   frozen-clock consistency, HTML `min`/`max` without JS clamps.
3. **Full crawl** — every registered route × {1440×900, 768×1024, 375×812}:
   console errors, failed network, horizontal overflow, unclickable overlays,
   empty broken states, form validation smoke.

## Auto-fix (safe patterns only)

`--auto-fix` only applies *mechanical* patches that have a known, reviewed
template (e.g. clamp tip ≥ 0, `stockCount &&` → `stockCount != null &&`,
`value="Home"` → `value="Home & Garden"`). It never invents product logic.
After patching it rebuilds the affected app and re-runs the failing checks.

Baseline audit (human): `docs/qa/QA_REPORT_2026-08-06.md`
