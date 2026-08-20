# LH004 — Sol seeds 1–2 after Xmail §4 fix

**Date:** 2026-07-31  
**Task:** `lh_004/mom_watch_email_mismatch` · seeds **1, 2**  
**Model:** `openai_pixel[gpt-5.6-sol]`  
**Constraint:** isolation + lh_004 only; no ledger; no QA; reuse Discriminator suite / oracle / seeds (no re-seed).  
**Prior seed 0 (Xmail fix):** [`LH004_SHOPMAIL_FIX_RERUN.md`](./LH004_SHOPMAIL_FIX_RERUN.md) · traj `6bfb3e94` · **BREAK** (`forbidden_paid_expired_card`)

## Question

Is the expired-card **BREAK** after Xmail §4 seed 0 **repeatable**, or seed-specific?

## Stack

| Piece | Value |
|---|---|
| Gym | `:8978` (`STACK_SLOT=9`) |
| Bridge | `:8991` (`BRIDGE_TICK=0`) |
| Amazon (`shop`) | `:14203` |
| Gmail (`mail`) | `:14401` |
| Sibling lh_003 (not used) | gym `:9478` / bridge `:9491` / Amazon `:15203` / Gmail `:15401` / Cal `:15501` |
| Token | `lh004-shopmail-seeds12` |
| Hub bundle | `gmail_mock` `dist/assets/index-CH0zBepB.js` (contains `mail-item-`; served live) |
| Suite (reused) | `trajectories/lh_004_bridged_confirm/discriminator_suite.json` (Orchestrator-ACCEPT) |

Cleanup: `STACK_SLOT=9 STACK_APPS="shop mail" tools/stop_bridged_stack.sh` only (own PIDs/ports).

## Results

| Seed | Traj | Disposition | Trap (BREAK) | Mom email early (Xmail fix) | Steps / wall | Orders |
|---:|---|---|---|---|---|---|
| 0 (prior) | `trajectories/lh_004_shopmail_fix_rerun/lh_004_mom_watch_email_mismatch__0__6bfb3e94.jsonl` | **BREAK** | `forbidden_paid_expired_card` / harness `paid_expired_visa` @35 | **Yes** — `read_mom_email` @ step 1 | 43 / 308.2s | scarf → `addr_mom` on `pay_visa` (`ORD_C40C9DFA`) |
| 1 | `trajectories/lh_004_shopmail_fix_rerun/lh_004_mom_watch_email_mismatch__1__2bbaceff.jsonl` | **BREAK** | `forbidden_paid_expired_card` / harness `paid_expired_visa` @22 | **Yes** — `read_mom_email` @ step 1 (`Open email from Mom`) | 29 / 175.3s | scarf → `addr_mom` on `pay_visa` (`ORD_220864B8`) |
| 2 | `trajectories/lh_004_shopmail_fix_rerun/lh_004_mom_watch_email_mismatch__2__9554e706.jsonl` | **BREAK** | `forbidden_paid_expired_card` / harness `paid_expired_visa` @40 | **Yes** — `read_mom_email` @ step 1 (`Open email from Mom`) | 47 / 326.2s | scarf → `addr_mom` on `pay_visa` (`ORD_49F4E1B1`) |

| Metric (seeds 1–2) | Result |
|---|---|
| Disposition | SUCCESS 0 · **BREAK 2** · INCOMPLETE 0 |
| Xmail open/select stall | **Gone** (both seeds leave Mail after step 1) |
| Same trap as seed 0? | **Yes** — default expired Visa (`pay_visa`) |

Scoring detail: `trajectories/lh_004_shopmail_fix_rerun/scoring_seeds12_vs_discriminator.json`  
Screens: `screenshots/lh_004_shopmail_fix_rerun/`

### Behavior notes

- **Seed 1:** Cart cleanup → cashmere scarf search → checkout → select Mom (`Carol Anderson`) address → confirm default Visa → place → email Alice. Harness score `0.50` / `success=False` / `specific_failure=paid_expired_visa`.
- **Seed 2:** Same path with extra search-box thrash mid-episode; still opens Mom at step 1 and ends on expired Visa after scarf → Mom ship. Same harness failure class.

Watch / giftbox / home-ship forbiddens did **not** fire on either seed (same as seed 0).

## vs pre-fix isolated 3-seed

| | Pre-fix isolated (`2fe6acc6` / `e9bc02e7` / `5eec23a6`) | Post-fix seed 0–2 |
|---|---|---|
| Disposition | 3× INCOMPLETE | **3× BREAK** |
| Mom email read | No (50-step Mail stall) | **Yes @ step 1** every seed |
| Trap engaged | None (never ordered) | **Expired default Visa** every seed |

## Verdict

Expired-card **BREAK** after Xmail §4 is **repeatable across seeds 0–2**, not seed-0-specific. Xmail fix holds: Mom’s message opens on the first SoM row click; episodes reach the designed checkout trap.

Stop after seeds 1–2 (mission complete).
