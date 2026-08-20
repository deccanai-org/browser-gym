# CAL001 View→Edit forensics (Day-fix Sol seed0)

**Date:** 2026-08-02  
**Question:** Did Sol correctly identify the Saturday gym/party overlap, and why did it never transition from viewing to editing? Is there a UI/SoM affordance bug like cal_003’s confirm-dialog miss?  
**Trajectory:** `trajectories/cal_001_dayfix_sol_seed0/cal_001_fuzzy_weekend_conflict_cleanup__0__fc2a54e8.jsonl`  
**Screenshots:** `screenshots/cal_001_dayfix_sol_seed0/cal_001_fuzzy_weekend_conflict_cleanup__0__fc2a54e8/`  
**Model:** `openai_pixel[gpt-5.6-sol]` · **steps 80 / cap 80**  
**Priors:** `CAL001_DAY_VIEW_ROUTING.md`, `CAL001_BRIDGED_SOL_SEED0.md`, `CAL003_BEN_DELETE_FORENSICS.md`

---

## Verdict

**Env SoM affordance bug on view→edit openers (primary), not a reasoning miss on which events to change.**

Sol identified the correct party / overlap / gym / BBQ plan by **step 23–26**, then spent most of the remaining budget unable to open an existing event because **search-result cards and Week/Schedule event chips are clickable `<div>`s with no ARIA `role` / accessible name** — SoM (`harness/som.py` interactable-role filter) never numbers them. Keyboard fallbacks (Tab / ArrowDown / Enter / Delete) on unmarked search results also fail to open the editor.

At **step 78–79** Sol finally reached Hold’s editor via a **Schedule ↔ search-panel spatial collision** (same accidental pattern as cal_003 steps 23–24), clicked trash **`Delete event`** `[446,142]`, and the **Delete event?** confirm appeared — then the **cap ended** with no confirm click. Seed gym/overlap unchanged; junk Quick-add `ev_4` created.

**Not** the same failure class as cal_003’s confirm-dialog race (trash clicked + confirm attempted + poll dismissed dialog). Confirm was never attempted here. Related class: **SoM click-target affordance** (unmarked event openers). Day-view mitigation confirmed (0 Day entries).

---

## 1. Evidence Sol identified correctly (reasoning quotes)

Parsed with `.venv/bin/python` from pretty-printed episode JSON (`steps[]`).

| Step | Quote (from `reasoning` / `raw_model_output`) |
|---|---|
| **23** | Plan: Tommy’s party Sat May 23 **2:00–4:00 PM**; remove **“Hold — gift wrap” 2:30–3:00 PM**; move **Saturday gym 3:00–4:00 → 4:00–5:00**; leave Sunday BBQ. Observation: *“The raw calendar state visibly confirms the exact records…”* |
| **26** | *“Schedule view clearly lists Tommy’s 8th Birthday Party at 2:00 PM, the overlapping ‘Hold — gift wrap run’ at 2:30 PM, and Saturday Gym at 3:00 PM. … Family BBQ separately on Sunday, which must remain untouched.”* |
| **26** | Also: *“The event rows themselves are not exposed as numbered marks…”* |
| **29** | *“Tommy’s 8th Birthday Party is Saturday 2:00–4:00 PM; ‘Hold — gift wrap run’ overlaps from 2:30–3:15 PM; Saturday Gym is 3:00–4:00 PM.”* |
| **35** | *“Confirm exact times: party 2:00–4:00 PM; overlapping hold 2:30–3:00 PM; Saturday Gym 3:00–4:00 PM.”* |
| **79** | *“Delete ‘Hold — gift wrap run’ because its 2:30–3:00 PM time overlaps Tommy’s 2:00–4:00 PM birthday party.”* + observation: Hold editor open at those times. |

Early noise (steps 0–14): hallucinated “morning gym 8–9 AM” / “kids’ soccer” from Week chrome before Debug State + search grounded the seed titles. **Correct plan locked by step 23**; Schedule UI confirmation at step 26.

BBQ left alone throughout (forbidden veto false; `sunday_bbq_intact` pass).

---

## 2. Attempts to open / edit / delete — what happened

| Steps | Intent | Action | Outcome |
|---|---|---|---|
| 0–3, 10, 15–21 | Find party | Search `nephew`/`party`; Enter / Tab on result | Result card visible; **no SoM mark**; keyboard does not open editor |
| 4–8, 11–13, 22 | Read times | Debug State `/go`, Debug API, Ctrl+F | Times confirmed in raw state; leaves interactive calendar |
| 16, 38–39 | Focus Saturday | Mini-cal **23**; Enter | `SET_DATE` only — no Day (mitigated); no event open |
| 24–25, 35–36, 40–41 | Prefer editable list | Week menu → **Schedule** | Schedule lists party/hold/gym/BBQ; **rows unmarked** |
| 26–32, 50–56, 75–76 | Open Hold via search | Type hold title; ArrowDown / Enter / **Delete** key | Result card unmarked; delete key no-ops; hold still in state |
| 28–29 | Alt path | Quick add → Cancel | Creation-only; not useful for edit/delete |
| 43–45 | Settings / nav | Settings, hamburger | No path to edit existing events |
| 46–49, 58–68 | “Edit” via Create | Open blank EventModal; type Saturday Gym; datetime thrash; Close | Never edits seed `ev_cal001_gym`; discarded draft |
| 69–71 | Reschedule via Quick add | NL “Saturday Gym May 23 2026 4pm to 5pm” → Add Event | Creates **`ev_4`** on wrong day/time; seed gym unchanged |
| **78** | Reason: open Hold search result | `click_mark` 13 **`Schedule`** `[1096,131]` | **Hold editor opens** (Week still selected in header — click hit search card under/at Schedule coords in right panel `z-20`) |
| **79** | Delete Hold | `click_mark` 12 **`Delete event`** `[446,142]` | Confirm **Delete event?** visible (`step_079.png`); **episode ends** — no `Confirm delete` |

Final durable state (facts / scoring): party + hold + seed gym intact; BBQ intact; extra `ev_4`. Correctness FAIL; disposition **INCOMPLETE**.

---

## 3. Affordance: broken/missing SoM vs agent never tried edit

### Missing SoM on event openers (env — primary)

`harness/som.py` only marks ARIA interactable roles (`button`, `link`, `textbox`, …). Xoogle openers are plain clickable divs:

| Surface | Code | SoM? |
|---|---|---|
| Search result card | `App.jsx` `<div onClick=…>` (no `role` / `aria-label` / `tabIndex`) | **No** — Sol: “result … has no numbered click mark” (steps 15, 27, 51, …) |
| Schedule rows | `AgendaView.jsx` `<div onClick=…>` | **No** — Sol: “event rows … not annotated” (steps 26, 37, 42) |
| Week chips | `WeekView.jsx` `<div data-event-chip onClick=…>` | **No** — Sol: “blocks … not individually marked” (step 38) |

Human/mouse can open events; pixel+SoM agent cannot target them. That is why identification ≠ edit for ~50 steps.

### Accidental open at step 78 (spatial collision — same pattern as cal_003)

cal_003 forensics: step 23 `Schedule` `[1096,131]` while search open → Ben editor.  
cal_001 step 78: identical mark/coord; `step_078.png` shows click glow on **Hold** search card labeled `CLICK: button:Schedule`; view remains **Week**. Search overlay (`w-80` right, `z-20`) occludes the view-menu **Schedule** hit target — Playwright center-click opens the unmarked search card underneath/at that pixel.

### Delete confirm (end of episode — not cal_003 race)

- Trash already renamed **`Delete event`** / confirm **`Confirm delete`** (cal_003 SoM fix live in this run).
- `step_079.png`: confirm dialog present after trash click; glow still on trash (annotation for that step’s action).
- No subsequent step — **confirm never issued**. Cannot attribute hold survival to the old `bridgePoll`/`deletePending` race (that race was fixed in Hub `EventModal` before this Day-fix re-run). Cap exhaustion after first successful open.

### Agent secondary behavior (not the root blocker)

Once openers failed, Sol pivoted to **Create / Quick-add** and produced junk `ev_4` instead of updating `ev_cal001_gym`. That is an execution compromise **after** the affordance wall — not evidence it failed to know what to change.

---

## 4. Clear verdict

| Hypothesis | Result |
|---|---|
| Reasoning never identified party/gym/overlap/BBQ | **False** — correct by step 23–26 |
| Agent never tried to edit/delete | **False** — many open/delete attempts; trash clicked at 79 |
| Day-view routing still the issue | **False** — 0 Day contact post-mitigation |
| cal_003 confirm-dialog race (poll clears `deletePending`) | **Not observed** — confirm never clicked; race already patched |
| **Unmarked search/event openers (SoM ARIA gap)** | **True — primary env bug** |
| Cap / Quick-add side effects | Secondary — burn after affordance wall; junk create |

**Env vs agent:** **(a)/(b) hybrid** — working calendar mutations exist (`/bridge/act`), but **view→edit SoM affordance is broken** for the intended UI path; Sol’s identification was adequate.

---

## 5. Fix class (relative to cal_003)

cal_003 §4 framed fixes as **SoM click-target / confirm affordance**. CAL001’s gap is the same family on a different control: **event openers must expose `role="button"` + accessible name** (and keyboard activators) so SoM numbers “Hold — gift wrap run” / “Saturday Gym” in Search, Schedule, and Week.

Confirm-dialog race/rename work from cal_003 stays; do not re-diagnose cal_001 incomplete as “never tried delete” or as Day-view.

**Patch applied (Hub):** `CUA-Gym-Hub/websites/google_calendar_mock` — `role="button"` + `tabIndex={0}` + `aria-label={title}` (+ Enter/Space) on search cards (`App.jsx`), Agenda rows, Week chips (timed + all-day), Month chips; `dist` rebuilt. SoM will number event titles for view→edit.

---

## 6. Re-run policy

- **Before opener SoM fix:** further Sol re-runs will keep stalling on search/Schedule/Week with the same unmarked complaints.
- **After opener SoM fix:** one Sol seed-0 re-run on exclusive stack is the right confirmation (open Hold by named mark → Confirm delete → edit gym times).
- Cap-80 alone was insufficient; Day-hide alone was insufficient.

---

## 7. Post–opener-SoM-fix Sol seed0 re-run (2026-08-02)

**Question:** With `role="button"` + `aria-label` on search/Agenda/Week/Month openers live in calendar dist, can Sol enter edit mode on the events it identified and finish?

| Field | Value |
|---|---|
| Dist | `index-5c413e62.js` (vite `:11601`; served HTML references this bundle; `aria-label` + `role:"button"` present) |
| Ports | gym **11578** / bridge **11591** / cal **11601** (`STACK_SLOT=35`, overrides) |
| Cap | **80** (`AGENT_MAX_STEPS=80`) |
| Suite | reused `trajectories/cal_001_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT + minimal-diff) |
| Trajectory | `trajectories/cal_001_opener_som_fix_sol_seed0/cal_001_fuzzy_weekend_conflict_cleanup__0__d2db3bca.jsonl` |
| Screenshots | `screenshots/cal_001_opener_som_fix_sol_seed0/cal_001_fuzzy_weekend_conflict_cleanup__0__d2db3bca/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**27** · wall≈213s |
| Harness | success=True score=1.0 |

### Confirmations

| Check | Result |
|---|---|
| Event openers SoM-markable | **Yes** — step 0 `click_mark` name=`Tommy's 8th Birthday Party` role=`button`; step 2 `Hold — gift wrap run`; step 5 `Saturday Gym` (Week chips) |
| Trajectory enters edit mode | **Yes** — Hold → `Delete` → `Confirm delete` (steps 2–4); Gym → `Edit` → datetime fields → `Save` (steps 5–6, 26) |
| Day view | **Never** — 0 `#/day` / `view=day`; 0 `Day` menu clicks; 0 Day-view observations |
| Disposition | **SUCCESS** |

### Durable final

- `ev_cal001_overlap` deleted
- `ev_cal001_gym` → 16:00–17:00
- Party + Sunday BBQ + Friday decoy intact (4 events)
- Disc: correctness PASS · forbidden_veto=False · minimal_diff PASS

**Env vs agent:** opener SoM affordance was the blocker; after fix Sol executes the plan it already had in the Day-fix forensics (identify → delete hold → push gym). Prior INCOMPLETE was not a reasoning miss.

Detail: `trajectories/cal_001_opener_som_fix_sol_seed0/scoring_report.json`
