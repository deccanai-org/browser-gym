# CAL004 Bridged Sol Seed0 — dentist_mail_reschedule_clear

**Date:** 2026-08-02  
**Task:** `cal_004/dentist_mail_reschedule_clear`  
**Constraint:** seed → oracle → Disc ACCEPT + minimal-diff → Sol seed 0 only; diagnose before scale; no ledger/QA.  
**Apps:** Calendar × Gmail.  
**Brief style:** goal-only (lh_002/lh_003 natural-source; no trap spoilers).

## Hub map (exclusive ports)

| Role | Bridged hub | Port |
|---|---|---|
| Gym / harness | — | **10578** |
| Bridge | — | **10591** |
| Calendar | `google_calendar_mock` | **10601** |
| Mail | `gmail_mock` | **10611** |

`STACK_SLOT=25` + `STACK_PORT_OVERRIDES=1` (`CALENDAR_PORT_OVERRIDE=10601`, `MAIL_PORT_OVERRIDE=10611`); `STACK_APPS="calendar mail"`. Own PIDs only via `stop_bridged_stack.sh`.

## Brief

> My dentist appointment got moved — the confirmation is in my email. Get my calendar straight for it.

## Mechanism

Mail source-anchoring (latest River Dental 3:00 PM confirmation vs stale 10:00 AM reminder) + same-day **update** of Dentist Cleaning to 15:00–16:00 + **delete** of Budget review occupying that slot. Decoy: today's Teeth whitening consult (same clock, wrong day). Standup near old morning slot must stay. Week/month + edit update/delete only.

## 1. Seed + UI (env gate)

- Snapshots: `browser-gym-seed-to-cua-gym/seed_snapshots/cal_004__dentist_mail_reschedule_clear/seed0_{initial,final}.json`
- Evidence: `trajectories/cal_004_bridged_confirm/seed_ui_evidence.json`

| Surface | Result |
|---|---|
| calendar week | Dentist / Budget / Standup / whitening **True** |
| gmail inbox | reschedule 3:00 + stale 10:00 + River Dental **True** |

**Env gate: PASS.**

## 2. Oracle / golden

- Mutations: `update` dentist → 15:00–16:00; `delete` Budget review
- Hand suite on golden: **PASS** (`oracle/hand_suite_on_golden.json`)
- Solver: `solve_cal_004_dentist_mail_reschedule_clear`

## 3. Discriminator + Orchestrator

- Structural suite: dentist @15:00–16:00 + event-count 3 + standup/whitening intact + whitening-deleted forbidden + minimal-diff (calendar/mail)
- Note: hand-suite silent-doublebook forbidden is **not** mirrored as a Disc forbidden (would be TRUE on golden if keyed only on dentist@15:00, or TRUE on initial if keyed only on budget present). Disc covers wrong-decoy delete; QuietBreak BREAK for silent clash is hand-suite.
- Orchestrator: **ACCEPT** — fails-on-initial, passes-on-golden
- Artifact: `trajectories/cal_004_bridged_confirm/discriminator_suite.json`

## 4. Sol seed 0

| Field | Value |
|---|---|
| Trajectory | `trajectories/cal_004_bridged_confirm/cal_004_dentist_mail_reschedule_clear__0__f215e54d.jsonl` |
| Screenshots | `screenshots/cal_004_bridged_confirm/cal_004_dentist_mail_reschedule_clear__0__f215e54d/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**20** · wall≈138s |
| Harness | success=False score=0.0 failure=`unclassified_failure` |

Durable final:

- Dentist Cleaning **moved** to 15:00–16:00 (mail latest followed)
- Budget review **still present** at 15:00–16:00 → silent double-book
- Standup + whitening intact

## 5. Scoring / diagnosis

- **Disposition: BREAK** (hand QuietBreak — `silent_doublebook_new_slot` fired at step 18)
- Disc on Sol final: correctness FAIL (budget not deleted; dentist-moved CP PASS); forbidden_veto=False (whitening intact) → Disc alone would read INCOMPLETE; hand suite is authoritative for this trap
- Env vs agent: **(a) genuine BREAK on working env** — Sol read latest mail and updated dentist onto occupied 15:00 without clearing Budget review; bridge `calendar.update`/`delete` and oracle path proven
- **Scale to 3: YES** — clean seed-0 BREAK on the designed trap; confirm rate before pool claim

Detail: `trajectories/cal_004_bridged_confirm/scoring_report.json`

## 6. Seeds 1–2 (scale confirm)

| Seed | Disposition | Episode | Notes |
|---|---|---|---|
| 1 | **BREAK** | `61a03f2b` | Same silent double-book (dentist@15 + budget@15) |
| 2 | **BREAK** | `72750add` | Same |

**3/3 BREAK** — confirmed. Full write-up: `CAL004_SOL_BRIDGED_3SEED.md`. Scoring: `trajectories/cal_004_sol_3seed/scoring_vs_discriminator.json`.

## Brief proposal

`docs/history/audits/CAL_NEW_BRIEF_PROPOSAL.md`
