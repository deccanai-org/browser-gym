# CAL003 Ben-delete forensics (cap-80 Sol seed 0)

**Date:** 2026-08-02  
**Question:** Did Sol click delete and fail to confirm a dialog, or never attempt the delete click?  
**Trajectory:** `browser-gym-seed-to-cua-gym/trajectories/cal_003_cap80_sol_seed0/cal_003_mail_reconcile_holds_move__0__aace9d05.jsonl`  
**Screenshots:** `browser-gym-seed-to-cua-gym/screenshots/cal_003_cap80_sol_seed0/cal_003_mail_reconcile_holds_move__0__aace9d05/`  
**Model:** `openai_pixel[gpt-5.6-sol]` · **steps 34 / cap 80** (~46 unused — not budget)  
**Prior notes:** `docs/history/audits/CAL003_BRIDGED_SOL_SEED0.md` §6 (cap-80)

---

## Verdict

**Confirmation-pattern env bug (fixable), not “never attempted delete.”**

Sol opened Ben’s editor, clicked the trash **Delete**, saw **Delete event?**, then issued a confirm `click_mark` on a SoM target named `Delete` whose recorded center **pixel-matches the red confirm button**. After that click the dialog was gone, the editor stayed open, and `Interview — Ben` remained in world state — i.e. `confirmDelete` did not commit. Same failure shape as bridged cap-50 (`mark_id` 12 then 65, coords `[446,142]` → `[758,441]`).

Root cause: bridged `bridgePoll` (~2.5s) → `LOAD_STATE` refreshed `state.calendars` object identity → `EventModal` `useEffect` reset `deletePending`, **dismissing the confirm dialog during the model turn** before the confirm click landed on empty editor chrome. Secondary: Sol then treated delete as done and emailed without re-checking the calendar (reasoning gap after the env miss).

**Not** a clean reasoning-only miss (“thought done, never clicked”). **Do not** re-run hoping for a different outcome without the env fix.

---

## 1. Step sequence around Ben delete

Parsed with `.venv/bin/python` from the pretty-printed episode JSON (`steps[]`).

| Step | Action | Target (name / coord) | Reasoning (abbrev.) | Ben still present? |
|---|---|---|---|---|
| 6 | `switch_tab` 0 | Calendar | Return to calendar to delete Ben’s declined hold | Yes |
| 7–15 | search / keys | Search “Interview — Ben” | Find/open Ben; search result often unmarked | Yes |
| 16–19 | mini-cal / Debug API / recover | — | Search result not SoM-marked; Debug API detour; reopen `/calendar` | Yes |
| 20–22 | search again / Week menu | — | Still trying to open Ben | Yes |
| **23** | `click_mark` 13 | `Schedule` `[1096,131]` | Open Interview — Ben search result | Yes |
| **24** | `click_mark` 12 | **`Delete` `[446,142]`** (trash) | Delete Ben’s 11:00 hold | Yes |
| **25** | `click_mark` 65 | **`Delete` `[758,441]`** (intended confirm) | Confirm deletion | Yes |
| **26** | `click_mark` 11 | close `""` `[833,142]` | Close editor after “confirming”; verify removal | Yes |
| 27–33 | Mail compose/send/Sent | — | Summary claims Ben deleted | Yes |

Episode `finish` (log): claims Ben deleted, Ava unchanged, Cy left at 1:00, summary in Sent — **verifier score 0** (`ben_declined_hold_deleted` fail).

Bridged cap-50 twin (same click pair): steps **27–29** in `…/cal_003_bridged_confirm/…37917301.jsonl`.

---

## 2. Expected vs actual UI

| Moment | Expected | Actual (screenshot + pixels) |
|---|---|---|
| After step 23 | Ben editor open | Editor open (`step_023.png`); click on search-result “Schedule” |
| After step 24 | Confirm dialog **Delete event?** | **Present** (`step_024.png`). Red confirm button bbox ≈ `x=726–789 y=425–455`, center **`(757,440)`**. Trash click annotated at `[446,142]`. Blue Save hidden under dialog. |
| Step 25 action | Click confirm **Delete**; Ben removed; editor closes | Recorded mark: `role=button name=Delete coord=[758,441]` — **on the red button center from step 24’s frame**. |
| After step 25 | Ben gone | Dialog **gone**; editor **still open** (blue Save back); click glow over empty form near “Add notification” (`step_025.png` center crop). World titles still include Ben. |
| After step 26 | Calendar without Ben | Editor closed; search still lists Ben (`step_026.png`) |

SoM: trash used `title="Delete"` → accessible name `"Delete"`; confirm button text `"Delete"` → same name. Two `Delete` marks while dialog open (12 vs 65). Agent selected the higher mark / center coords for confirm — intent was correct.

Harness: `click_mark` resolves mark → `page.mouse.click` at bbox center (`harness/runner.py`); cursor overlay is `pointer-events: none`.

---

## 3. Why confirm did not commit (env)

`google_calendar_mock` bridged poll:

```js
// StoreContext.jsx — every ~2500ms
bridgePoll(APP, s => dispatch({ type: 'LOAD_STATE', payload: initializeData(sid, s) }));
```

Pre-fix `EventModal` effect:

```js
useEffect(() => {
  if (isOpen) {
    // ... reset form ...
    setDeletePending(false);  // dismisses confirm
  }
}, [isOpen, event, selectedDate, state.calendars]);
```

`LOAD_STATE` replaces `state.calendars` → effect re-runs while editor stays open → **`deletePending` cleared**. Typical Sol turn ≫ 2.5s, so:

1. Step 24 opens confirm; marks for step 25 include confirm `Delete` @ `[758,441]`
2. During model latency, poll dismisses dialog
3. Click lands on vacated coordinates (empty editor body)
4. Outcome matches Cancel-like UI (dialog gone, editor open, event intact) without `confirmDelete` / `calendar.delete`

Bridge `calendar.delete` itself is fine when invoked with `event_id` (prior audit post-hoc `/bridge/act`).

---

## 4. Fix applied (same class as SoM click-target / confirm affordance bugs)

**Hub:** `CUA-Gym-Hub/websites/google_calendar_mock/`

1. **Race:** form/confirm reset depends on `isOpen` + `event.id` (+ stable default calendar id / duration strings), **not** `state.calendars` / full `event` object identity — so poll no longer kills an in-flight confirm.
2. **SoM disambiguation (eBay Confirm Purchase pattern):**
   - Trash: `aria-label="Delete event"` + `data-test-id="btn-delete-event"`
   - Confirm: `aria-label="Confirm delete"` + `data-test-id="btn-confirm-delete"`
   - Cancel: `aria-label="Cancel delete"` + `data-test-id="btn-cancel-delete"`
   - Same labels on `App.jsx` popover delete dialog

**Dist rebuilt:** `websites/google_calendar_mock/dist` (runtime stacks serve Hub `dist`).  
**Patch hygiene:** regenerate `browser-gym-seed-to-cua-gym/tools/patches/google_calendar_mock_bridged.patch` from Hub WT when convenient — not required while `dist` is current.

---

## 5. Re-run policy

- **Before this fix:** no further Sol re-runs for “maybe delete lands.”
- **After this fix:** one Sol seed-0 re-run on the same exclusive stack is appropriate to confirm Ben deletes via UI confirm.
- Cap-80 alone does not fix this (already unused headroom).

---

## 6. Secondary reasoning note (not the delete root cause)

After step 26 Sol switched to Mail and wrote “Deleted Ben’s …” while Ben still existed. That is a **postcondition skip** on top of the env confirm miss — document only; do not treat as the primary diagnosis or as justification for re-runs without the UI fix.

---

## 7. Post-fix Sol seed 0 re-run (2026-08-02) — CONFIRMED

**Disposition: SUCCESS**

| Field | Value |
|---|---|
| Cap | **80** |
| Ports | slot **39** · gym **11978** / bridge **11991** / cal **12001** / mail **12011** (siblings on 11578/11778 left alone) |
| Calendar dist | Hub `vite preview` of rebuilt `index-b42ea636.js` (served asset verified: `Confirm delete` + `btn-confirm-delete`) |
| Suite | reused `trajectories/cal_003_bridged_confirm/discriminator_suite.json` (Orchestrator ACCEPT) |
| Trajectory | `trajectories/cal_003_ben_delete_fix_sol_seed0/cal_003_mail_reconcile_holds_move__0__c5410268.jsonl` |
| Screenshots | `screenshots/cal_003_ben_delete_fix_sol_seed0/cal_003_mail_reconcile_holds_move__0__c5410268/` |
| Model | `openai_pixel[gpt-5.6-sol]` · steps=**32** · wall≈233s |
| Harness | success=True score=1.0 |

### Ben delete path (fix lands)

| Step | Action | SoM name / coord | Ben after? |
|---|---|---|---|
| 24 | `click_mark` 12 | **`Delete event`** `[446,142]` (trash) | Yes |
| 25 | `click_mark` 65 | **`Confirm delete`** `[758,441]` | **No** — event removed |

New SoM labels disambiguate trash vs confirm; stable `EventModal` deps keep `deletePending` across `bridgePoll` → confirm click commits `calendar.delete`.

### Durable final / Disc

- Events: Ava / Cy / Hiring sync only — **`ev_cal003_ben` absent**
- Recruiting summary email present
- Disc: correctness **PASS** (all 5 CPs) · forbidden_veto=False · minimal_diff **PASS** · honesty/non_hacking PASS

Detail: `trajectories/cal_003_ben_delete_fix_sol_seed0/scoring_report.json`  
Env bug from §3 **fixed and confirmed** on Sol seed 0.
