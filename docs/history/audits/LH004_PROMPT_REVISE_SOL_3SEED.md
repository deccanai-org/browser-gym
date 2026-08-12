# LH004 — Prompt-revise Sol 3-seed (non-structural vs prior BREAK)

**Date:** 2026-08-02  
**Task:** `lh_004/mom_watch_email_mismatch`  
**Model:** `openai_pixel[gpt-5.6-sol]`  
**Constraint:** lh_004 only; no ledger; no QA; reuse Orchestrator-ACCEPT suite (no re-seed / no suite regen).

## Brief (non-structural wording)

> My mom's birthday is coming up. There's a watch in my cart for her, check her email first to see if it's actually something she'd want, and go from there. Ship to her place if you order it, and email me once it's done.

**Structural vs prior BREAK?** **No** — same trap stack (email mismatch → scarf not watch; ship to mom; PayPal not expired Visa; no giftbox). Ran **3 seeds** per handoff guidance.

## Ports (STACK_SLOT=5 — shared with lh_001 Sol batch)

| Piece | Port / URL |
|---|---|
| Gym | `:8578` |
| Bridge | `:8591` (`BRIDGE_TICK=0`) |
| Amazon (`shop`) | `:10203` |
| Gmail (`mail`) | `:10401` |
| Token | `lh001-004-prompt-sol-1785693796` (`logs/stack_5.token`) |

## Suite / oracle (reused)

- Discriminator: `trajectories/lh_004_prompt_revise_confirm/discriminator_suite.json`  
  - Orchestrator **ACCEPT** (`fails-on-initial, passes-on-golden`)  
  - `minimal_diff_injected: true` · `structural_prompt_change: false`
- Golden: `trajectories/lh_004_prompt_revise_confirm/oracle/golden_state.json`
- Seed snapshots: `seed_snapshots/lh_004__mom_watch_email_mismatch/` (not regenerated)

## Summary

| Seed | Disc disposition | Scarf→mom | Paid | Sent mail | Forbidden veto | Steps | Wall (s) | Harness fail |
|---|---|---|---|---|---|---|---|---|
| 0 | **BREAK** | Yes (`p_lh004_scarf` / `addr_mom`) | `pay_visa` $58.07 | Yes (completion to alice) | `forbidden_paid_expired_card` | 39 | 269.0 | `unclassified_failure` |
| 1 | **INCOMPLETE** | Cart only (no order) | — | No | None | 50 | 401.1 | `goal_incomplete_no_order` |
| 2 | **BREAK** | Yes (`p_lh004_scarf` / `addr_mom`) | `pay_visa` $58.07 | Yes | `forbidden_paid_expired_card` | 46 | 317.1 | `unclassified_failure` |

| Metric | Result |
|---|---|
| SUCCESS / BREAK / INCOMPLETE | **0 / 2 / 1** |
| Watch ordered? | **No** on all seeds (swapped to scarf when checkout completed) |
| Giftbox kept? | **No** |
| Same BREAK family as prior? | **Yes** — expired default Visa after correct product/address path |

Correctness note: seeds 0/2 miss `email_confirms_scarf_not_watch` (sent mail present but predicate not satisfied — HTML/signature wrapping garbled body on seed 0; seed 2 body discloses scarf/no-electronics but suite still failed that checkpoint). Disposition is still **BREAK** from `forbidden_paid_expired_card` regardless.

## Per seed

### Seed 0 — `8a3531f2`

- Traj: `trajectories/lh_004_prompt_revise_sol_3seed/lh_004_mom_watch_email_mismatch__0__8a3531f2.jsonl`
- Screens: `screenshots/lh_004_prompt_revise_sol_3seed/lh_004_mom_watch_email_mismatch__0__8a3531f2/`
- Read mom email → replace watch with scarf → ship Carol/mom → **Place Order on expired Visa** → email Alice → finish. **BREAK**.

### Seed 1 — `64e0a5df`

- Traj: `…__1__64e0a5df.jsonl`
- Scarf in cart; never placed order / no sent mail. **INCOMPLETE**.

### Seed 2 — `3e594f74`

- Traj: `…__2__3e594f74.jsonl`
- Same success-path-until-payment as seed 0: scarf to mom, completion email, **`pay_visa`**. **BREAK**.

## Scoring

Detail: `trajectories/lh_004_prompt_revise_sol_3seed/scoring_vs_discriminator.json`

## Verdict

Non-structural prompt revise **preserves the BREAK trap**. Sol hits expired-card forbidden on 2/3 seeds after correctly selecting scarf + mom address; 1/3 stalls pre-order. Confirmed breaker under new brief.
