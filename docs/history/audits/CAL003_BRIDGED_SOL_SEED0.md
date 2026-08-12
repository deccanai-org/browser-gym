# CAL003 Bridged Sol Seed0 — mail_reconcile_holds_move

**Date:** 2026-08-02  
**Task:** `cal_003/mail_reconcile_holds_move`  
**Constraint:** seed → oracle → Disc ACCEPT + minimal-diff → Sol seed 0 only; diagnose before scale; no ledger/QA.  
**Apps:** Calendar × Gmail.

## Hub map (exclusive ports)

| Role | Bridged hub | Port |
|---|---|---|
| Gym / harness | — | **11978** |
| Bridge | — | **11991** |
| Calendar | `google_calendar_mock` | **12001** |
| Mail | `gmail_mock` | **12011** |

`STACK_SLOT=39` + `STACK_PORT_OVERRIDES=1`; `STACK_APPS="calendar mail"`.

## Brief

> Go through tomorrow's interview holds using the latest emails. Delete any declined slots, and move whoever asked to reschedule to the time they proposed, but only if it's actually free. Leave the confirmed ones alone. Email recruiting@shopgym.com a one-line summary of what you changed.

## Mechanism

Mail×Calendar reconcile with free/busy gate: latest Ben decline → delete; Cy proposes 15:00 but Hiring sync occupies it → leave Cy; Ava confirmed → leave; one-line recruiting summary.

## 1. Seed + UI (env gate)

- Snapshots: `browser-gym-seed-to-cua-gym/seed_snapshots/cal_003__mail_reconcile_holds_move/seed0_{initial,final}.json`
- Evidence: `trajectories/cal_003_bridged_confirm/seed_ui_evidence.json`

| Surface | Result |
|---|---|
| calendar week | Ava / Ben / Cy / Hiring sync **True** |
| gmail inbox | decline / reschedule / confirm signals **True** |

**Env gate: PASS.**

## 2. Oracle / golden

- Mutations: delete Ben; send recruiting summary (Cy unmoved)
- Hand suite on golden: **PASS**
- Solver: `solve_cal_003_mail_reconcile_holds_move`

## 3. Discriminator + Orchestrator

- Structural suite: event-count + collection_any survivors + recruiting `mail.sent` + forbidden Cy@15:00 / Ava deleted
- Orchestrator: **ACCEPT** — fails-on-initial, passes-on-golden
- Artifact: `trajectories/cal_003_bridged_confirm/discriminator_suite.json`

## 4. Sol seed 0

| Field | Value |
|---|---|
| Trajectory | `trajectories/cal_003_bridged_confirm/cal_003_mail_reconcile_holds_move__0__37917301.jsonl` |
| Screenshots | `screenshots/cal_003_bridged_confirm/cal_003_mail_reconcile_holds_move__0__37917301/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=37 · wall≈270s |
| Harness | success=False score=0.0 failure=`unclassified_failure` |

Durable final:

- Ben hold **still present** (UI delete confirm mis-clicked; bridge `calendar.delete` works when called with `event_id`)
- Ava / Cy / Hiring sync intact (Cy correctly left at 13:00–14:00)
- Sent mail to `recruiting@shopgym.com` (body mangled with HTML signature prefix but contains delete summary text)

## 5. Scoring / diagnosis

- **Disposition: INCOMPLETE**
- Disc on Sol final: correctness FAIL (Ben not deleted); recruiting email CP PASS; forbidden_veto=False
- Env vs agent: **(b) Sol lost on working env** for the delete confirm — agent opened Ben editor and Delete dialog but SoM click hit the wrong Delete control; post-hoc `/bridge/act calendar.delete` removes Ben cleanly. Email compose path works with signature pollution.
- **STOP** — no scale.

Detail: `trajectories/cal_003_bridged_confirm/scoring_report.json`

## 6. Cap-80 Sol seed 0 re-run (2026-08-02)

| Field | Value |
|---|---|
| Cap | **80** (was 50) |
| Ports | same slot **39** · gym **11978** / bridge **11991** / cal **12001** / mail **12011** |
| Suite | reused `trajectories/cal_003_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_003_cap80_sol_seed0/cal_003_mail_reconcile_holds_move__0__aace9d05.jsonl` |
| Screenshots | `screenshots/cal_003_cap80_sol_seed0/cal_003_mail_reconcile_holds_move__0__aace9d05/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**34** · wall≈215s |
| Harness | success=False score=0.0 failure=`unclassified_failure` |

Durable final:

- Ben hold **still present** (delete UI path again failed to commit)
- Ava / Cy / Hiring sync intact (Cy correctly left at 13:00–14:00)
- Recruiting summary email CP **PASS**

### Diagnosis

- **Disposition: still INCOMPLETE** (no BREAK / no SUCCESS)
- Disc on Sol final: correctness FAIL (Ben not deleted); recruiting email PASS; forbidden_veto=False
- Cap raise **unused** — episode finished at 34/80 with the same Ben-delete miss as cap-50.
- Env vs agent: **(b) Sol lost on working env** (delete confirm / open path); not step-budget limited.

Detail: `trajectories/cal_003_cap80_sol_seed0/scoring_report.json`

## 7. Post Ben-delete fix — Sol seed 0 (2026-08-02)

| Field | Value |
|---|---|
| Cap | **80** |
| Ports | slot **39** · gym **11978** / bridge **11991** / cal **12001** / mail **12011** |
| Calendar dist | rebuilt Hub `index-b42ea636.js` via `vite preview` (Confirm delete labels + stable EventModal deps) |
| Suite | reused `trajectories/cal_003_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_003_ben_delete_fix_sol_seed0/cal_003_mail_reconcile_holds_move__0__c5410268.jsonl` |
| Screenshots | `screenshots/cal_003_ben_delete_fix_sol_seed0/cal_003_mail_reconcile_holds_move__0__c5410268/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**32** · wall≈233s |
| Harness | success=True score=1.0 |

Durable final:

- Ben hold **deleted** (step 24 `Delete event` → step 25 `Confirm delete` committed)
- Ava / Cy / Hiring sync intact (Cy left at 13:00–14:00)
- Recruiting summary email CP **PASS**

### Diagnosis

- **Disposition: SUCCESS**
- Disc on Sol final: correctness PASS · forbidden_veto=False · minimal_diff PASS
- Confirms forensics root cause in `CAL003_BEN_DELETE_FORENSICS.md` (§3–4); env fix sufficient for Sol seed 0.

Detail: `trajectories/cal_003_ben_delete_fix_sol_seed0/scoring_report.json`
