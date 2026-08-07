# BrowserGym-Tasks: forbidden milestone chips (2026-08-07)

## Problem
On the annotation review UI (Sol Breakers / Wave-1 / Filtration), step-level verifier chips under model reasoning were always green (`✓ name`) whenever a milestone fired. Forbidden trap milestones (e.g. `shipped_stale_gift_message`, `paid_expired_visa`) therefore read as “pass” even when they were the BREAK trigger.

## Fix (UI semantics only — no data rewrite)
Canonical sources: `BrowserGym-Tasks/app/app.js` + `app/shell.html` (rebuild inlines into `index.html`).

Same change synced to `BrowserGym-Annotation-phase2` (shared UI fork).

Behavior:
- **Required met** → green chip `✓ name`
- **Forbidden fired** → red chip `✗ forbidden: name` (+ `· BREAK trigger` on first `fired_at_step`)
- **Required missed** → red chip `✗ missed: name` on last / break-trigger step
- **Progress** → muted chip (not green “success”)
- Fact lines (`shop.<milestone>: true`) use red for forbidden, green for required
- Gallery marks the earliest forbidden `fired_at_step` as the BREAK trigger step

## Validate
Open M83 (Wave-1) BREAK run: step 5 should show green `ordered_perfume_to_jordan`, red `forbidden: shipped_stale_gift_message · BREAK trigger`, muted `placed_perfume`, and step badge `BREAK`.

## Live
- URL: https://arun-thepolicy-murari.github.io/BrowserGym-Tasks/
- Deploy SHA: `fe8051914ed08a8df179b2c1e4ca840243981765` (Pages run [31203986977](https://github.com/arun-thepolicy-murari/BrowserGym-Tasks/actions/runs/31203986977), `workflow_dispatch` after push)
- Canonical: `BrowserGym-Tasks` (`arun-thepolicy-murari`). Annotation-phase2 got the same `app/` + `index.html` patch locally (`4010bb2`) but could not push to `amit-deccan/BrowserGym-Annotation-phase2` (403).
