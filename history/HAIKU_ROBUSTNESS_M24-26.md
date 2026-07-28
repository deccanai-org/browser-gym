# Overnight results — M24/M25/M26 build + Haiku harvest (claude-haiku-4-5)

_Generated 2026-05-28. Branch `feat/multi-app`. All tasks oracle-1.0, full test
suite green (189 tests), env-correctness gate passed — so every result below is a
genuine **agent** outcome, not an environment/verifier artifact._

## What was built tonight

Three new "strongest-task" breakers, each wired across all 11 registries, oracle
scores 1.0, committed:

| Task | Mechanic | Intended breaking axis |
|---|---|---|
| **M24** `procurement_puzzle` | Buy 3 items ≤ $320 across two stores w/ a 10% coupon; the global optimum *consolidates* at the pricier store (counter-intuitive) while the greedy per-item split busts the budget | pure optimization reasoning |
| **M25** `dispatch_desk` | One manager email → route 4 distinct details to 4 people *directly* (not reply-to-manager); an async correction changes Alex's budget mid-task | recipient-routing at scale + stale-value |
| **M26** `calendar_purge_async` | Async email cancels Project Phoenix → delete **exactly** the Phoenix meetings **except** the repurposed "Phoenix Retro" | async destructive **exact-set** + negative-exception |

M26's verifier grades by set-equality `deleted == Q`, which is stickiness-safe
because calendar deletions grow monotonically (any over-delete is a strict
superset forever → the exact-set milestone can never fire). 7 dedicated tests
cover full-path / over-delete-retro / over-delete-decoy / under-delete /
never-acted / delivery / read.

## The harvest matrix — claude-haiku-4-5, K=8 each, eval_mode ON

| Task | SoM agent (`pixel`) | Coord agent (`pixel_coord`, raw x/y) |
|---|---|---|
| M24 procurement | **8/8** | **8/8** |
| M25 dispatch | **8/8** | **8/8** |
| M26 calendar purge | **8/8** | **8/8** |
| M13 (control, 14-item conjunction) | **7/8** | **7/8** |

**Aggregate: 62/64 episodes succeeded (96.9%).** The only 2 failures were both
on M13, both the *same* non-recurring signature
(`missed_a_required_cancellation_over_14_items` — premature finish missing 1 of
14 qualifying orders), and the harvester itself flags them **not significant**
(rate 0.12, n=1).

(Earlier K=8 frontier-model runs on M24, for reference: gpt-5.5 8/8, Sonnet 8/8,
gpt-5.1 7/8.)

## Verdict — the honest, rigorous read

1. **`claude-haiku-4-5` is NOT an easily-broken cheap model.** Across 4 hard
   multi-app / async / destructive / conjunctive tasks × 2 perception modalities,
   it succeeded 62/64. It reliably reads async emails, handles a mid-task
   correction, honors a stated negative-exception, and executes exact-set
   destructive edits.

2. **Perception modality did not matter here.** The raw-coordinate agent (no
   accessibility tree — the deployment-realistic modality) matched SoM on every
   task, because these task UIs are **clean and well-spaced**: raw-coordinate
   clicking has no disadvantage when targets are large and uncluttered. (The
   historical coord-agent *breaks* were on M12's deliberately **dense/small**
   targets — a UI-perturbation axis NOT applied here.)

3. **Why these tasks don't break it:** the common thread is **clean UI + explicit
   instructions + small decision sets.** M25 enumerates each person+detail+address;
   M26's email literally says "ONE EXCEPTION: keep the Retro"; M24 is one coupon
   decision; M26 is only 2 target deletes. A strong model follows explicit
   instructions on clean UIs — in either modality.

4. **Even the historical breaker barely nicks it now.** M13 (14-item conjunctive
   boundary-trap) broke *older* Haiku robustly with the coord agent; current
   `claude-haiku-4-5` gets it **7/8 in both modalities**. The model got stronger.

## What it would actually take to break claude-haiku-4-5

Stack the *proven* stressors that tonight's tasks deliberately did NOT combine:

- **UI perturbation** (`?ui=small_targets` / `low_contrast`) — the coord agent's
  real weakness (M12). Clean UIs never trigger it. Re-run M24/M25/M26 under
  `small_targets` with the coord agent.
- **Much larger conjunctive scale + boundary traps** — M13 at 14 items only nicks
  it 1/8; push to 25–40 items with tighter boundaries and gift/shipped-style
  decoys.
- **Implicit inference** — remove the enumerated-recipient / "ONE EXCEPTION"
  scaffolding so the agent must *derive* the rule, not copy it.
- **Combine axes** — e.g. a large conjunction *under* `small_targets` on the coord
  agent is the highest-probability break.

A concrete next task (**M27**) would be M13-scale (30+ items) + an *implicit*
exclusion + a `small_targets` perturbation + the coord agent.

## Where the sellable failures likely live: the GPT side (pending key)

Historically the recurring, *sellable* failure was **gpt-5.1's reply-to-manager
mis-route** on M22 (3/5). M25 is the scaled version of exactly that trap
(4 recipients + no-reply-to-manager + async correction). So the gpt-5.5 K=8 on
M25/M26 is the run most likely to surface a recurring failure signature — it is
**blocked only on the OpenAI API key** (servers 8101/8102 are up; commands queued).

## Caveats / integrity notes

- A latent verifier bug in the *older* M11/M13 suites (precision milestone
  `C ⊆ Q` is true at step 0 → sticky-fires before the agent acts → over-cancel
  not caught) was found and flagged for a separate fix. It does **not** affect
  tonight's M13 failures (those are under-cancel, correctly caught) and does not
  affect M24/M25/M26 (M26 uses the corrected set-equality pattern).
- All harvests ran with `eval_mode` ON (no reward leakage to the agent) and a
  generous step cap (60–120, task-scaled) to isolate reasoning from step-budget.
