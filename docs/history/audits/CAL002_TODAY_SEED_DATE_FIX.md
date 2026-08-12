# CAL002 — Today navigation seed-date fix

**Date:** 2026-08-02  
**Task:** `cal_002/conditional_lunch_hold_cancel`  
**Constraint:** fix GymCal Today wall-clock bug; re-run Sol seed 0 on fixed env with reused ACCEPT suite; no ledger/QA.  
**Prior:** `docs/history/audits/CAL002_BRIDGED_SOL_SEED0.md` §6 (cap-80 → 1-step false abstain on blank Aug 2026).

## Verdict

**Env bug FIXED.** Header **Today** (and “is today” highlights) now use the frozen gym clock (`referenceToday` / `_gym_meta.today` = **2026-05-21**), not `Date.now()`.

Sol seed 0 on the fixed env **no longer** 1-step finishes on blank August — step 0 sees **Thu May 21** with **Client lunch** visible. Episode still **INCOMPLETE** (agent miss on GymEats Orders / delete persistence), disposition **(b) agent on working env**.

## Root cause

| Layer | Bug |
|---|---|
| `google_calendar_mock` `Header.jsx` `handleToday` | `dispatch(SET_DATE, new Date().toISOString())` → wall-clock (Aug 2026) |
| Week / Month / Sidebar / Agenda | `isSameDay(day, new Date())` highlighted wall-clock “today” |
| Bridge `transform_calendar` | Set `currentDate` to seeded today, but UI Today ignored it |

Same class as GymCal Day-view TZ / ValueMart wall-clock `endTime`: UI clock not bound to gym seeded today.

## Fix

**CUA-Gym-Hub** `websites/google_calendar_mock`:

1. `helpers.js` — `getReferenceTodayISO` / `getReferenceTodayDate`; `lockReferenceToday` prefers `_gym_meta.today` over createDefault wall-clock.
2. `StoreContext.jsx` — persist `referenceToday` across `LOAD_STATE`.
3. `Header.jsx` — Today → `getReferenceTodayISO(state)`; Quick Add anchors on reference today.
4. Week / Month / Sidebar / Agenda / Create — `isToday` / default create date use reference today.
5. Rebuild `dist` (`npm run build`).

**browser-gym-seed-to-cua-gym** `tools/seed_to_cuagym.py` `transform_calendar`:

- Stamp `"referenceToday": f"{TODAY}T00:00:00"` alongside `currentDate`.

Bug report: `docs/CUA_GYM_HUB_UI_BUG_REPORT.md` **GymCal §3** — **already fixed**.

## Smoke (Today → May 21 + Client lunch)

| Field | Value |
|---|---|
| Ports | gym **11778** / bridge **11791** / cal **11801** / food **11811** (`STACK_SLOT=37`, overrides) |
| Artifact | `trajectories/cal_002_today_seed_fix_smoke/` |
| Result | Navigate away to July → click **Today** → header **May 2026**; **Client lunch** visible; `referenceToday=2026-05-21T00:00:00` |

## Sol seed 0 re-run (cap 80, reused ACCEPT suite)

| Field | Value |
|---|---|
| Cap | **80** (`AGENT_MAX_STEPS=80`) |
| Suite | `trajectories/cal_002_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_002_today_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__31d08b6b.jsonl` |
| Screenshots | `screenshots/cal_002_today_fix_sol_seed0/cal_002_conditional_lunch_hold_cancel__0__31d08b6b/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**80** · wall≈730s |
| Harness | success=False score=0.0 failure=`repeated_failed_actions` |

### Today-fix evidence (step 0)

> GymCal is showing today, Thursday May 21, in week view. A **“Client lunch”** event is visibly scheduled from **12:30 PM–1:30 PM**

- `August 2026` **absent** from traj (vs prior cap-80 blank August finish).
- Agent attempted GymEats cancel + calendar delete; durable final unchanged: Client lunch still present; `FOOD-CAL002-ACTIVE` still `preparing`; Team lunch + delivered intact.

### Scoring / disposition

| Field | Value |
|---|---|
| Disposition | **INCOMPLETE** |
| Disc on Sol final | correctness FAIL; forbidden_veto=False |
| Env vs agent | **(b) agent miss on working env** after Today fix — not wall-clock nav |
| vs prior cap-80 | Env gate closed; remaining miss is GymEats Orders / delete path |

Detail: `trajectories/cal_002_today_fix_sol_seed0/scoring_report.json`

**Follow-up (same day):** Food `/orders` list + calendar Confirm-delete dist re-run → **SUCCESS** (9 steps). See `CAL002_FOOD_CANCEL_FORENSICS.md` §7 (`trajectories/cal_002_food_cancel_fix_sol_seed0/`).

## Hub map (this run)

| Role | Port |
|---|---|
| Gym | **11778** |
| Bridge | **11791** |
| Calendar | **11801** |
| Food | **11811** |

`STACK_SLOT=37` + `STACK_PORT_OVERRIDES=1` (`CALENDAR_PORT_OVERRIDE=11801`, `FOOD_PORT_OVERRIDE=11811`); `STACK_APPS="calendar food"`. Own PIDs only via `stop_bridged_stack.sh`.
