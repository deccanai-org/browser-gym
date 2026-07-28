repo: deccanai-org/ecommerce-browser-gym
branch: feat/updated
path: docs/report-site

## Last sync
date: 2026-07-28T19:40:00Z
tree: ebb1bbe05f4c (github_get_tree resolved tree hash, not a commit sha)

### Updated in this project
- Rebuilt the report and task explorer as Design Components with a corrected type scale and layout rhythm.
- Removed the "cross-app dependence ≈3%" claim. Recomputed the application distribution over all 312 oracle solvers in agents/oracle_agent.py (navigation calls): store-only 178, Mail 101, Calendar 59, ValueMart 27, Food 27; 134 of 312 (43%) leave the store. Supersedes the 284-task 2026-07-13 analysis, which folded ValueMart into the store.
- Section 04 rebuilt on the two real denominators: the cascade_v2 stop-table (203 tasks: 135/10/16 defended per tier, 42 reach Sonnet, 30 break / 9 defend / 3 incomplete) and Table 1 strongest-tier (65 Sonnet-break / 12 GPT-5.1-terminal / 7 GPT-5.5-terminal / 1 injection, n=85). Per-model break counts against 312 removed as structurally misleading for a conditional cascade.
- Corrected the failure-mechanism chart to the authoritative 83-core + 2-footnote ledger counts.
- Task explorer now carries 6 episodes with video, JSON trajectory, milestone tables and step-level agent reasoning.

## Screen map
| Screen | Built from |
|---|---|
| Report.dc.html | docs/report-site/index.html, PROJECT_INFO.md, docs/history/audits/TABLE1_STRONGEST_TIER_RECOMPUTE_2026-07-21.md (Table 1 + denominator crib sheet), trajectories/sellable_breakers_v2.csv, agents/oracle_agent.py (app distribution), README.md |
| TaskExplorer.dc.html | docs/report-site/explorer.html, trajectories/sellable_breakers_v2.csv, uploads/sample_trajectories_6/*.jsonl, uploads/*.webm |
