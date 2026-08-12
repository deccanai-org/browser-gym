# CAL007 Bridged Sol Seed0 — standup_single_occurrence_move

**Date:** 2026-08-03  
**Task:** `cal_007/standup_single_occurrence_move`  
**Constraint:** seed → oracle → Disc ACCEPT + minimal-diff → Sol seed 0 only; diagnose before scale; no ledger/QA.  
**Apps:** Calendar only.

## Hub map (exclusive ports)

| Role | Bridged hub | Port |
|---|---|---|
| Gym / harness | — | **12178** |
| Bridge | — | **12191** |
| Calendar | `google_calendar_mock` | **46402** |

`STACK_SLOT=41`; `STACK_APPS="calendar"`. Own PIDs only via `stop_bridged_stack.sh`.

## Brief

> My Tuesday standup moved to Wednesday just for this week, everything else stays the same.

## Mechanism

This week's Tuesday standup is a **one-off exception** (`ev_cal007_standup_this`, Tue May 19, `recurring=none`) beside a **weekly series** master (`ev_cal007_standup_series`, Tue May 26+, `recurring=weekly`). UI shows a continuous weekly Team Standup. Correct = **edit only this week's instance → Wed May 20**. Trap = edit the series master onto Wednesday (all future weeks move). Decoys: Wed 1:1 with Priya, weekly Product Sync, Dentist. Week/month + edit update only (no day-view / click-create).

## 1. Seed + UI (env gate)

- Snapshots: `seed_snapshots/cal_007__standup_single_occurrence_move/seed0_{initial,final}.json`
- Evidence: `trajectories/cal_007_bridged_confirm/seed_ui_evidence.json`

| Surface | Result |
|---|---|
| calendar week (Today) | Team Standup **True**; Product Sync **True** |
| calendar next week | Team Standup (series) **True** |
| calendar month | Standup / 1:1 / Dentist **True** |
| event open | this-week standup opened; times present |

**Env gate: PASS.**

## 2. Oracle / golden

- Mutation: `update_event(ev_cal007_standup_this, day=2026-05-20)`
- Hand suite on golden: **PASS** (`oracle/hand_suite_on_golden.json`)
- Solver: `solve_cal_007_standup_single_occurrence_move`

## 3. Discriminator + Orchestrator

- Structural suite: this-week @ Wed + series still Tue/weekly + count=5 + decoys intact + forbidden series→Wed + forbidden 1:1 deleted + minimal-diff
- Orchestrator: **ACCEPT** — fails-on-initial, passes-on-golden
- Artifact: `trajectories/cal_007_bridged_confirm/discriminator_suite.json`

## 4. Sol seed 0

| Field | Value |
|---|---|
| Trajectory | `trajectories/cal_007_bridged_confirm/cal_007_standup_single_occurrence_move__0__5d206516.jsonl` |
| Screenshots | `screenshots/cal_007_bridged_confirm/cal_007_standup_single_occurrence_move__0__5d206516/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**50** · wall≈407s |
| Harness | success=False score=0.0 failure=`repeated_failed_actions` |

Durable final unchanged from seed:

- `ev_cal007_standup_this` still **Tue May 19** (not moved)
- `ev_cal007_standup_series` still **Tue May 26 weekly**
- 1:1 / Product Sync / Dentist intact

## 5. Scoring / diagnosis

- **Disposition: INCOMPLETE**
- Disc on Sol final: correctness FAIL; forbidden_veto=False
- Hand suite: success milestone FALSE; series-move forbidden FALSE
- Env vs agent: **(b) Sol lost on working env** — opened the correct this-week one-off (`Does not repeat` in step_002), attempted May 19→20 day increments on datetime-local, then Tab/Enter thrash toward Save; **never clicked the visible Save button**; no durable mutation. Not a series-edit BREAK.
- **STOP** — no scale to seeds 1–2.

Detail: `trajectories/cal_007_bridged_confirm/scoring_report.json`

## 6. Unit test

`tests/test_cross_app_verifiers.py::test_cal_007_single_occurrence_succeeds_series_move_breaks` — **PASS**.
