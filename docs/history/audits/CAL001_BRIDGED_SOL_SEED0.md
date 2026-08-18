# CAL001 Bridged Sol Seed0 — fuzzy_weekend_conflict_cleanup

**Date:** 2026-08-02  
**Task:** `cal_001/fuzzy_weekend_conflict_cleanup`  
**Constraint:** seed → oracle → Disc ACCEPT + minimal-diff → Sol seed 0 only; diagnose before scale; no ledger/QA.  
**Restart:** fresh stacks after machine crash (prior bridge push timed out on dead hub URLs).

## Hub map (exclusive ports)

| Role | Bridged hub | Port |
|---|---|---|
| Gym / harness | — | **11578** |
| Bridge | — | **11591** |
| Calendar | `google_calendar_mock` | **11601** |

`STACK_SLOT=35` + `STACK_PORT_OVERRIDES=1`; `STACK_APPS=calendar`.  
Stack start fix: only export `CUA_HUB_URL_*` for launched apps (avoids bridge `push()` Connection refused).

## Brief

> My nephew's birthday party is this weekend, clean up my calendar around it. Clear anything that overlaps the party, and push my Saturday gym session to right after it ends. Leave Sunday's family BBQ alone.

## Mechanism

Fuzzy “this weekend” / nephew-Tommy anchoring: delete true Saturday overlap hold; same-day update Saturday Gym to party end (16:00–17:00); leave Sunday Family BBQ + Friday adult-Tommy decoy. Week/month + edit update/delete only.

## 1. Seed + UI (env gate)

- Snapshots: `browser-gym-seed-to-cua-gym/seed_snapshots/cal_001__fuzzy_weekend_conflict_cleanup/seed0_{initial,final}.json`
- Evidence: `trajectories/cal_001_bridged_confirm/seed_ui_evidence.json`

| Surface | Result |
|---|---|
| calendar week | party / Saturday Gym / gift-wrap overlap / Old Tommy decoy **True** |
| calendar next week (chevron) | Family BBQ **True** (Sunday is outside default May 17–23 week) |

**Env gate: PASS** (after fixing seed script that put `bridge=` in the URL hash → ambient-only UI).

## 2. Oracle / golden

- Mutations: delete `ev_cal001_overlap`; update `ev_cal001_gym` → 16:00–17:00
- Hand suite on golden: **PASS** (`oracle/hand_suite_on_golden.json`)
- Solver: `solve_cal_001_fuzzy_weekend_conflict_cleanup`

## 3. Discriminator + Orchestrator

- Structural suite + `minimal_state_diff` allowed_roots calendar
- Orchestrator: **ACCEPT** — fails-on-initial, passes-on-golden
- Artifact: `trajectories/cal_001_bridged_confirm/discriminator_suite.json`

## 4. Sol seed 0

| Field | Value |
|---|---|
| Trajectory | `trajectories/cal_001_bridged_confirm/cal_001_fuzzy_weekend_conflict_cleanup__0__291d419b.jsonl` |
| Screenshots | `screenshots/cal_001_bridged_confirm/cal_001_fuzzy_weekend_conflict_cleanup__0__291d419b/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=50 · wall≈514s |
| Harness | success=False score=0.0 failure=`unclassified_failure` |

Durable final: seed calendar unchanged (overlap still present; gym still 15:00–16:00).

## 5. Scoring / diagnosis

- **Disposition: INCOMPLETE**
- Disc on Sol final: correctness FAIL; forbidden_veto=False
- Env vs agent: **(b) Sol lost on working env** — agent burned the cap on Day view + search keyboard navigation; never completed edit→delete / edit→update. Bridge `calendar.update`/`delete` confirmed working via direct `/bridge/act`.
- **STOP** — no seed 1 / no 3-seed scale without explicit go-ahead.

Detail: `trajectories/cal_001_bridged_confirm/scoring_report.json`
