# Harness Integrity Audit — Phase 0 Gate Artifact

**Branch:** `feat/multi-app`  **Task universe:** 234 tasks  **Date:** 2026-07-02

This report is the gate for Phase 1. **Phase 1 (screening) does not start until every
section below is green.** Each section states the check, the exact result, and any task
that had to be fixed or pulled.

Reproducibility scripts (all committed under `trajectories/`):
`_harness_audit_full.py` (0.2), `_registry_xref.py` (0.3), `_oracle_gate_run.sh` +
`_oracle_gate_check.py` (0.4). Machine-readable outputs: `_harness_audit_full.json`,
`_registry_xref.json`, `_oracle_gate_check.json`.

| Check | Gate | Result |
|-------|------|--------|
| 0.2 Integrity sweep (all 234) | 0 violations, 4 checks | **PASS** — 0/0/0/0 |
| 0.3 Registry cross-reference | 0 orphans either direction | **PASS** — 0 orphans |
| 0.4 Oracle gate (234 × 3 seeds) | every cell scores 1.00 | **PASS** — 702/702 = 1.00 (2 tasks fixed) |
| 0.5 Three known-failing tests | fixed against current WorldState | **PASS** — fixed in test code |
| 0.6 Screening hang fix | 5–10 task gpt-5.5 + Sonnet, no hang | **PASS** — see §0.6 |
| 0.7 Full test suite | all green, no unexplained skips | **PASS** — see §0.7 |

---

## 0.2 — Integrity sweep, all 234 tasks

`trajectories/_harness_audit_full.py` extends the old 40-task sample to **all 234 tasks ×
seeds {0,1,2}**, run against a live server (`uvicorn server.main:app --port 8003`). Four
checks:

1. **STEP-0 INVARIANT** — for every task & seed the seed state is NOT success and NO
   forbidden milestone has already fired. → **0 violations**
2. **WEIGHT SANITY** — forbidden milestones weigh 0; non-forbidden weights sum to ~1.0
   (±0.01). → **0 violations**
3. **DETERMINISM** — same task+seed produces identical milestone structure across resets.
   → **0 violations** (all 234 checked, not a 40-sample)
4. **CROSS-EPISODE ISOLATION** — `reset(T)` is history-independent: the world after
   `reset(RICH)→reset(T)` is byte-identical to `reset(T)→reset(T)`. Contaminator =
   `M13/order_cleanup_audit` (richest seeded state, 47 stateful items). → **0 leaks**

**GATE: PASS — 0 violations across all 4 checks on all 234 tasks.**

Informational (not a gate): **49 suites have no forbidden milestone** and therefore can
only ever produce SUCCESS/INCOMPLETE, never BREAK. These are the A/B/C/D base
success-path tasks plus the M success-path variants — by design; the sellable breakers
are a subset of the remaining 185. Cross-checked in 0.3 that none of the 49 are wired as
breakers.

---

## 0.3 — Registry cross-reference / orphan check

`trajectories/_registry_xref.py`. The repo wires each task through six registries with
**two key conventions** (verified against the code, not assumed):

- **Full-id keyed** (`"A1/buy_wireless_mouse"`): `TASKS` (state factories, server/tasks.py),
  `SUITE_FACTORIES` (verifiers.py), `SOLVERS` (oracle_agent.py), `START_PATHS`,
  `REQUIRED_FACTS`.
- **Short-id keyed** (`"A1"`): `BRIEFS` — looked up at runtime as
  `BRIEFS[task_id.split("/")[0]]` (server/tasks.py:1478).

There is **no standalone DIFFICULTY dict**; difficulty is a per-task attribute set inside
each factory (`_base_state(..., difficulty, ...)`), so there is nothing to cross-reference
for it.

| Registry | Size | Role |
|----------|------|------|
| BRIEFS | 234 | task instructions (short-id keyed) |
| TASKS | 234 | world/state factories |
| SUITE_FACTORIES | 234 | milestone verifier suites |
| SOLVERS | 234 | hand-coded gold solvers |
| START_PATHS | 209 | partial; `.get(id, "/")` default |
| REQUIRED_FACTS | 219 | partial; `.get(id, [])` default |

Results:
- The four **TOTAL** registries share one identical 234-task universe (234 distinct short
  prefixes, no collisions → BRIEFS is bijective with the full-id set).
- **SOLVERS ↔ SUITE_FACTORIES fully bijective** — every oracle has a verifier and vice
  versa. This is the check the plan calls out explicitly.
- `START_PATHS` (25 gaps) and `REQUIRED_FACTS` (15 gaps) are partial **by design**; every
  gap has a consumed-in-code default, and every one of their keys is inside the universe
  (no stray/orphan keys). The gaps are exactly the A/B/C/D base tasks.

**GATE: PASS — zero orphans in either direction.**

---

## 0.4 — Oracle gate, all 234 tasks × 3 seeds

Driver `trajectories/_oracle_gate_run.sh` runs the hand-coded oracle over **all 234 tasks
× seeds {0,1,2} = 702 episodes**, sharded across 6 isolated servers (ports 8010–8015 — the
gym holds one global world per server, so each shard needs its own; episodes within a
shard stay sequential). Output isolated in `trajectories/oracle_phase0/` (a fresh dir, so
stale pre-existing trajectories in `trajectories/oracle/` cannot contaminate the gate).
Checker `trajectories/_oracle_gate_check.py` groups by `(task, seed)`, requires all 702
cells present and **every score exactly 1.00**.

**First run: 700/702 = 1.00, 2 cells FAILED** — caught by the gate, exactly its purpose:

| Task | Seed | Score | Missed milestone |
|------|------|-------|------------------|
| `M20/errand_run` | 1 | 0.80 | `calendar_reminder_created` (required, w=0.2) |
| `M21/async_errand_run` | 1 | 0.80 | `calendar_reminder_created` (required, w=0.2) |

**Root cause (a brittle gold solver, not a broken task).** The milestone fires on any
calendar event with `source == "user"`. The oracle created the reminder using the
new-event form's **defaults** — day = TOMORROW (2026-05-22), window 19:00–20:00. Seed 1
(and only seed 1) seeds an extra event **"Book club" on 2026-05-22, 19:00–21:30**;
`create_event` rejects the overlapping booking, so no user event is created and the
required milestone silently drops. Seeds 0/2 have no Book club → no collision → 1.00.

**Fix (oracle solver, not the task/verifier).** Both solvers now **read the food order's
quoted ETA** (`eta_label`, e.g. Sakura's `"7:20 PM"`) from `/_harness/world`, parse it to
24h (19:20), and set the reminder to **TODAY 19:20–19:50** — the actual arrival window the
brief points at ("a reminder for when it's set to arrive"), verified in the trajectory
(`select-event-day=2026-05-21`, `input-event-start=19:20`, `input-event-end=19:50` on all
3 seeds). This is strictly more faithful than the original, which used the form default
(TOMORROW 19:00–20:00 — wrong day, and the seed-1 collision above). TODAY at the quoted ETA
is free on every seed (only Gym 18:00–19:00). `agents/oracle_agent.py`,
`solve_m20_errand_run` and `solve_m21_async_errand_run`.

Note the milestone (`_calendar_reminder = any(e.source == "user")`) does **not** assert the
time — the ETA-driven solver is a faithfulness improvement, not something the loose check
requires. The verifier looseness is logged as a Phase-1 item (§"Flagged for Phase 1").

**Re-verified:** M20 and M21 now score **1.00 on all 3 seeds**. Full-set re-check:

```
702 trajectory files -> 702 (task,seed) cells
COVERAGE: missing cells: 0
ORACLE PERFECTION: non-1.00 cells: 0
ORACLE GATE: PASS — all 234 tasks score 1.00 on all 3 seeds
```

**GATE: PASS.** Tasks fixed: **M20/errand_run, M21/async_errand_run** (oracle solver
brittleness, seed-1 calendar overlap). Tasks pulled: **none**.

---

## 0.5 — Three known-failing tests

`test_apps.py::test_metadata_tracks_shop_mutations`,
`test_apps.py::test_emit_defaults_step_from_world`,
`test_scheduler.py::test_absolute_fires_exactly_at_step`.

**Root cause.** Both files select a task via `next(iter(TASKS))`, which after the
multi-app refactor is `M230/false_cheapest_claim`. `make_task` now returns a **`WorldState`**
for category-M tasks (219 of 234) and a bare **`GymState`** only for the 15 single-app
A/B/C/D tasks. So `_world() = WorldState(shop=make_task(...))` **double-wrapped** a
WorldState inside a WorldState. The tests then hit `w.shop.step = 5` (WorldState.step is a
read-only property → `AttributeError: can't set attribute 'step'`) and
`w.shop.flash_messages` (WorldState has no such field — it lives on `GymState`).

**Fix (test code, matching the current model).** Pin `_TASK_ID = "A1/buy_wireless_mouse"`
in both files — a single-app task whose factory yields a plain `GymState`, which is what
these wrapper tests intend to wrap (confirmed field-by-field against `WorldState` in
`server/apps/world.py` and `GymState` in `server/state.py`). Source untouched.

**Result:** `tests/test_apps.py tests/test_scheduler.py` → all pass (35 tests, 0 failures).

**GATE: PASS.**

---

## 0.6 — Screening hang fix (gpt-5.5 / Sonnet)

**Root cause.** The pixel agents call the **synchronous** SDK client
(`self.client.messages.create` in `agents/pixel_agent.py`;
`self.client.chat.completions.create` in `agents/openai_pixel_agent.py`) directly inside
their `async def run` loop, with **no explicit timeout**. `Anthropic()` / `OpenAI()` were
constructed with no `timeout` and the OpenAI call was not even wrapped in try/except. A
stalled socket or a non-returning proxy blocks the event loop with no ceiling → the
episode, and the whole batch queued behind that server, freezes silently. This is the
exact call path for the two hanging tiers: gpt-5.5 → `openai_pixel`, Sonnet → `pixel`
(cascade mapping in `eval/cascade.py`).

**Fix.** New shared wrapper `agents/_llm_retry.py` (`acall`) guarantees:
1. **Timeout** — each attempt is offloaded to a worker thread and bounded by
   `asyncio.wait_for(per_call_timeout)`, a ceiling the SDK cannot escape.
2. **Retry + backoff** — transient failures (timeouts, 429, 5xx, connection resets)
   retried up to `LLM_MAX_ATTEMPTS` with capped exponential backoff; plain 4xx client
   errors surface immediately (no wasted retries).
3. **Hard failure** — on exhaustion raises `LLMCallError`, which propagates to
   `eval/run.py` (already wraps the agent in try/except → records `traj.error`). A stuck
   call becomes a visible error row, never a hang.

Both clients are now built with an explicit finite `timeout` and `max_retries=0` (our
wrapper is the single retry authority). `QwenAgent` subclasses `OpenAIPixelAgent`, so the
cascade's tier-1 inherits the guard too. Knobs are env-overridable: `LLM_CALL_TIMEOUT`
(120s), `LLM_MAX_ATTEMPTS` (3), `LLM_RETRY_BASE_DELAY` (2s), `LLM_RETRY_MAX_DELAY` (30s).

**Deterministic proof** — `tests/test_llm_retry_timeout.py` (5 tests, no network/keys): a
call that sleeps forever becomes a bounded `LLMCallError` in <1.5s (vs. blocking forever);
transient error retried-then-succeeds; 4xx not retried; exhaustion hard-fails; retryable
matrix. All pass.

**Live end-to-end smoke** — 5 tasks × seed 0 through **both** models against the real APIs
(`AGENT_MAX_STEPS=12`, `AGENT_EVAL_MODE=1`), models `gpt-5.5` (`openai_pixel`) and
`claude-sonnet-4-6` (`pixel`). 10 episodes total, run sequentially against one server.

| Task | gpt-5.5 | Sonnet |
|------|---------|--------|
| A1/buy_wireless_mouse | 1.00 ✓ (11 steps) | 1.00 ✓ (8) |
| D1/browse_audio_no_search | 0.80 (6) | 1.00 ✓ (8) |
| M2/order_then_track_via_email | 1.00 ✓ (12) | 1.00 ✓ (10) |
| M15/inbox_price_watch | 0.00 (12, capped) | 0.00 (12, capped) |
| M20/errand_run | 0.00 (12, capped) | 0.00 (12, capped) |
| **Episodes completed** | **5/5** | **5/5** |
| **Hangs / recorded errors** | **0** | **0** |

gpt-5.5 batch wall time 465s. Every episode observed→called→acted→returned cleanly; no
`traj.error`, no `LLMCallError`, and the retry guard never fired spuriously (calls
succeeded, so the wrapper is transparent). Scores are a step-capped (12) benchmark-mode
smoke — a **liveness/no-hang** check, not a capability benchmark; the low M15/M20 scores
are step-cap truncation on hard multi-app tasks, not failures of the fix.

**GATE: PASS — both models ran the full batch end-to-end with no hang.**

---

## 0.7 — Full test suite

```
.venv/bin/python -m pytest
1049 passed in 4.70s
```

**0 failures, 0 errors, 0 skips.** Baseline was 1044; this run is 1049 = 1044 + the 5 new
`tests/test_llm_retry_timeout.py` cases added in 0.6. The
`pytest.importorskip("playwright")` guard at `tests/test_verifiers.py:279` does **not**
skip because Playwright is installed — hence zero skips rather than the one documented
skip. (The `.bak` files under `tests/` are not collected: `python_files = "test_*.py"`
matches names ending in `.py`, which `.prediv.bak` / `.precset2.bak` do not.)

**GATE: PASS.**

---

## Flagged for Phase 1 (verifier looseness — not actioned in Phase 0)

While fixing M20/M21 (0.4) a **verifier under-specification** surfaced and was swept across
`server/verifiers.py` to gauge whether it is a one-off or systemic. This is **not** a
Phase-0 oracle-gate failure (all oracles score 1.00) — it is a task-semantics decision, so
per the ground rule "make the harness sound, don't change what a task requires" it is
logged here rather than changed now.

**The pattern.** A milestone checks that an artifact *exists* but not the *specific value
the brief names*. Concretely, the three "order dinner + add a reminder for when it arrives"
tasks all grade the reminder with a **time-blind existence check**:

| Task | Brief says | Milestone check | Solver faithfulness |
|------|-----------|-----------------|---------------------|
| M9/calendar_gated_dinner | "add a calendar event for when it's due to arrive" | `_calendar_action_matches_branch` → `any(e.source=="user")` | reads ETA → into event **title** (`"Dinner delivery ~7:20 PM"`), not the time field |
| M20/errand_run | "put a reminder … for when it's set to arrive" | `_calendar_reminder` → `any(e.source=="user")` | **now** reads ETA → sets time 19:20–19:50 (this audit) |
| M21/async_errand_run | same | same | **now** reads ETA → sets time (this audit) |

A model could satisfy all three with a reminder at *any* time and still score.

**Scope of the sweep (bounds it to these three).** The looseness is localized, not
house-wide:
- Other calendar milestones **do** assert the time when they mean to:
  `start == "16:00"` (M22-area), `start == "17:00"` (`_meeting_at_5pm`),
  `_calendar_reflects_new_eta_only` (exactly one event at the NEW ETA),
  `_booked_before_3pm` (day + time window). So precise calendar checks are the norm.
- Mail milestones generally verify **content/amount**, not just the recipient — e.g.
  `_replied_gear_total_to_alex` checks the *exact* order total is in the body;
  `_emailed_alex_correct_branch` checks branch keywords. No parallel "recipient-only" gap
  was found in the reply checks sampled.

**Recommendation (Phase 1 decides, against the fairness-bucket framework).** Tighten the
calendar-reminder milestone for M9/M20/M21 to assert the event time matches the order ETA
(e.g. `any(e.source=="user" and e.start == eta_24h)`), and give M9's oracle the same
time-field treatment M20/M21 now have. This makes the task **harder**, so it is a
deliberate design call — is "a reminder for when it's set to arrive" meant to require
time precision, or is "a reminder exists" the intended bar? That belongs in Phase 1, not a
unilateral Phase-0 edit.

---

## Tasks fixed or pulled (summary)

| Task | Phase | Action | Reason |
|------|-------|--------|--------|
| M20/errand_run | 0.4 | **Fixed** (oracle solver) | seed-1 calendar overlap dropped a required milestone |
| M21/async_errand_run | 0.4 | **Fixed** (oracle solver) | same seed-1 calendar overlap |
| (3 unit tests) | 0.5 | **Fixed** (test code) | double-wrapped WorldState after multi-app refactor |

**Tasks pulled from the pool: none.** All 234 remain, all oracle-perfect on 3 seeds.
