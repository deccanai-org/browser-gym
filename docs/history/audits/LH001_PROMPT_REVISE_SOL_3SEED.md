# LH001 — Prompt-revise Sol 3-seed (cosmetic brief)

**Date:** 2026-08-02  
**Task:** `lh_001/office_welcome_budget`  
**Model:** `openai_pixel[gpt-5.6-sol]`  
**Constraint:** lh_001 only; no ledger; no QA; reuse Orchestrator-ACCEPT suite (no re-seed / no suite regen).

## Brief (cosmetic / validated SUCCESS wording)

> Getting the office ready for the new hire tomorrow. Order a vegetarian lunch from Xber for the welcome and grab a welcome sign from Xbay too, whatever looks decent. Keep the total under $35 combined and have lunch here before the event starts.

**Structural vs prior?** **No** — Xber/Xbay branding only; seed/oracle unchanged.

## Ports (STACK_SLOT=5)

| Piece | Port / URL |
|---|---|
| Gym | `:8578` |
| Bridge | `:8591` (`BRIDGE_TICK=0`) |
| Amazon (`shop`) | `:10203` |
| Xbay / eBay (`market`) | `:10301` |
| Gmail (`mail`) | `:10401` |
| Calendar | `:10402` |
| Xber (`food`) | `:10403` |
| Token | `lh001-004-prompt-sol-1785693796` (`logs/stack_5.token`) |

Isolation: `tools/start_bridged_stack.sh` / `tools/stack_ports.sh`. Did **not** touch sibling calendar slot 15 (`:9578/:9591`).

## Suite / oracle (reused)

- Discriminator: `trajectories/lh_001_prompt_revise_confirm/discriminator_suite.json`  
  - Orchestrator **ACCEPT** (`fails-on-initial, passes-on-golden`)  
  - `minimal_diff_injected: true` · `structural_prompt_change: false`
- Golden: `trajectories/lh_001_prompt_revise_confirm/oracle/golden_state.json`
- Seed snapshots: `seed_snapshots/lh_001__office_welcome_budget/` (not regenerated)

## Summary

| Seed | Disc disposition | Plain sign ordered | Veg lunch ordered | Forbidden veto | Steps | Wall (s) | Harness fail |
|---|---|---|---|---|---|---|---|
| 0 | **INCOMPLETE** | Yes (`eb_lh001_plain_sign`) | No | None | 50 | 425.4 | `never_reached_checkout` |
| 1 | **INCOMPLETE** | Yes | No | None | 50 | 492.4 | `never_reached_checkout` |
| 2 | **INCOMPLETE** | Yes | No | None | 50 | 457.5 | `never_reached_checkout` |

| Metric | Result |
|---|---|
| SUCCESS / BREAK / INCOMPLETE | **0 / 0 / 3** |
| Budget trap (deluxe) | Not ordered on any seed |
| Stall mode | Xber checkout — delivery time/address control; step-capped before Place Order |

Missed correctness (all seeds): `ordered_vegetarian_lunch`, `lunch_eta_before_event`.  
`ordered_plain_market_sign` **passed** on all three.

## Per seed

### Seed 0 — `11fecda3`

- Traj: `trajectories/lh_001_prompt_revise_sol_3seed/lh_001_office_welcome_budget__0__11fecda3.jsonl`
- Screens: `screenshots/lh_001_prompt_revise_sol_3seed/lh_001_office_welcome_budget__0__11fecda3/`
- Xbay Plain Welcome Sign purchased; Xber veg item reached cart/checkout but delivery scheduling loop ate remaining steps.

### Seed 1 — `fdd390e6`

- Traj: `…__1__fdd390e6.jsonl`
- Same pattern: Plain sign durable; lunch never ordered.

### Seed 2 — `d092a164`

- Traj: `…__2__d092a164.jsonl`
- Same: Plain sign durable; Xber delivery-control keyboard/Tab loop to step 50.

## Scoring

Detail: `trajectories/lh_001_prompt_revise_sol_3seed/scoring_vs_discriminator.json`  
(Annotation Discriminator predicates + minimal-diff axis via `trajectories/_minimal_diff_reverify.py` helpers.)

## Verdict

Cosmetic brief confirm **does not unlock Sol SUCCESS**. Xbay cheap-path works; **Xber schedule-before-event** remains the Sol bottleneck (INCOMPLETE 3/3, no BREAK).
