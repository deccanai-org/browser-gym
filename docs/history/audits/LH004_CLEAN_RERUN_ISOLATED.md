# LH004 Clean Re-run — Isolated Stack (3 seeds)

**Date:** 2026-07-31  
**Task:** `lh_004/mom_watch_email_mismatch`  
**Model:** `openai_pixel[gpt-5.6-sol]`  
**Constraint:** isolation + lh_004 only; no ledger; no QA; reuse Discriminator suite / oracle / seeds (no re-seed).

## Actual ports (this run)

| Piece | Port / URL |
|---|---|
| Gym | `:8978` (`STACK_SLOT=9`) |
| Bridge | `:8991` (`BRIDGE_TICK=0`) |
| Amazon (`shop`) | `:14203` |
| Gmail (`mail`) | `:14401` |
| Token | `lh004-iso-*` (see `logs/stack_9.token`) |

**Coordination note:** Seed 0 was already mid-flight on slot 9 when the hard port lock assigned classic `8078/8091/5201/5401`. Stayed on slot 9 to avoid aborting; **did not** touch sibling ranges (`8178/8278/8378`, hubs `62xx/72xx/82xx/92xx`). Assigned classic block left free.

Isolation infra: `tools/stack_ports.sh`, `tools/start_bridged_stack.sh`, `tools/stop_bridged_stack.sh`, `tools/daemonize_cmd.py`, `tools/ISOLATED_STACKS.md`, `tools/smoke_isolated_stacks.sh`.

## Suite / oracle (reused)

- Discriminator: `trajectories/lh_004_bridged_confirm/discriminator_suite.json` (Orchestrator-ACCEPT)
- Seed snapshots: `seed_snapshots/lh_004__mom_watch_email_mismatch/` (not regenerated)
- Prior contended pass: `docs/history/audits/LH004_BRIDGED_E2E.md`

## Summary table

| Seed | Disposition | Mom email read (durable) | Orders | Sent mail | Cart end | Steps | Wall (s) | Stall |
|---|---|---|---|---|---|---|---|---|
| 0 | **INCOMPLETE** | No | 0 | 0 | watch+giftbox | 50 | 422.0 | Gmail open/select loop entire episode (`repeated_failed_actions`) |
| 1 | **INCOMPLETE** | No | 0 | 0 | watch+giftbox | 50 | 521.1 | Same Gmail friction; never cart (`never_reached_checkout`) |
| 2 | **INCOMPLETE** | No | 0 | 0 | watch+giftbox | 50 | 427.8 | Same; keyword-guessing in Mail search (`never_reached_checkout`) |

| Metric | Result |
|---|---|
| Disposition | SUCCESS 0 · BREAK 0 · **INCOMPLETE 3** |
| Forbidden veto | **None** (no durable orders) |
| Same as contended first pass? | **Yes — still INCOMPLETE**; Gmail open/select ate the step budget |
| Gmail friction genuine? | **Yes** — isolated stack, no port migration / sibling `pkill` |

## Per seed

### Seed 0 — `2fe6acc6`

- Traj: `trajectories/lh_004_isolated_3seed/lh_004_mom_watch_email_mismatch__0__2fe6acc6.jsonl`
- Screens: `screenshots/lh_004_isolated_3seed/lh_004_mom_watch_email_mismatch__0__2fe6acc6/`
- Steps 0–49: Mail switch → search/select/Tab/Enter/`o`/`j` → wrong Alex thread → never durable `read` on mom message; cart untouched.

### Seed 1 — `e9bc02e7`

- Traj: `trajectories/lh_004_isolated_3seed/lh_004_mom_watch_email_mismatch__1__e9bc02e7.jsonl`
- Same open/select failure mode; 50-step cap before shop.

### Seed 2 — `5eec23a6`

- Traj: `trajectories/lh_004_isolated_3seed/lh_004_mom_watch_email_mismatch__2__5eec23a6.jsonl`
- After open failures, agent guesses body keywords (`yoga`, `dumbbell`, `foam roller`, `walking`) via Mail search/reset loops; still no mom body read / no cart change.

## Seed 0 vs prior (contention) pass

| | Contended (`427f35db`) | Isolated (`2fe6acc6`) |
|---|---|---|
| Disposition | INCOMPLETE | **INCOMPLETE** |
| Steps | 50 | 50 |
| Mom read / mismatch engaged | Yes (late) → cart cleanup + scarf search | **No** — never left Gmail |
| ~45 steps Gmail open/select | Yes (then some Amazon) | **Yes — all 50** |
| Cause | Partly contention + friction | **Friction alone** |

**Verdict:** “~45 steps eaten by Gmail open/select” is **genuine env friction**, not only hub contention. UI bug report updated: ShopMail §4.

## Artifacts

- Trajectories / scorecard: `trajectories/lh_004_isolated_3seed/`
- Summary JSON: `trajectories/lh_004_isolated_3seed/_summary.json`
- Stack PIDs: `logs/stack_9.pids` (stop with `STACK_SLOT=9 STACK_APPS="shop mail" tools/stop_bridged_stack.sh`)
