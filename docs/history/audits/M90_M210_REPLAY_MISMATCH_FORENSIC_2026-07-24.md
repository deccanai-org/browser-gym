# M90 / M210 visual-recovery replay mismatch forensic

**Date:** 2026-07-24  
**Scope:** Two sellable URL-perfect QA disagreements from screenshot recovery
([`SCREENSHOT_RECOVERY_AND_NORMALIZE_45_2026-07-24.md`](./SCREENSHOT_RECOVERY_AND_NORMALIZE_45_2026-07-24.md)):

| Episode | Model | Hist | Replay (QA only) | URL match |
|---------|-------|------|------------------|-----------|
| `cascade_b7/gpt-5.5/M90…__2__45037c73` | gpt-5.5 | SUCCESS (1.0) | FAIL (0.0, nothing fired) | 1.0 |
| `cascade_newpatterns2/gpt-5.1/M210…__2__e2d642cd` | gpt-5.1 | SUCCESS (1.0) | FAIL (0.4, `mom_gift_misrouted_or_late`) | 1.0 |

**Method:** Same mismatch protocol as
[`SEED_REPLAY_MISMATCH_FORENSIC_2026-07-23.md`](./SEED_REPLAY_MISMATCH_FORENSIC_2026-07-23.md)
— (1) `git log -S` / blame for verifier drift, (2) async/settle timing, (3)
milestone-by-milestone hist vs replay + final world state, (4) optional
longer-settle mechanical re-probe (no model; no hist rewrite).

**Ledger policy:** `trajectories/sellable_breakers_v2.csv` **not edited**.  
**Sellable CSV checksum (SHA256):** `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30`
(unchanged; matches four-stream / screenshot-recovery baseline).

**Historical dispositions remain ground truth.** Replay verifier output is
QA-only.

---

## Executive verdict

| Task | Cause class | Scoring bug? | Keep hist? | Escalate ledger? |
|------|-------------|:------------:|:----------:|:----------------:|
| **M90** seed2 gpt-5.5 | **Replay action fidelity** (remove-addon + place-order clicks miss; URL match blind to post-place redirect) | No | **Yes** | No |
| **M210** seed2 gpt-5.1 | **Replay operability** on per-line ship-to `<select>` + schedule date (infra #7); hist facts prove correct route | No | **Yes** | No |

Neither episode is a negation-aware / false-claim cluster case. Neither is
verifier **code drift** after screening. Longer settle/ticks **do not**
recover hist SUCCESS. **Do not flip sellable dispositions from QA replay.**

---

## Step 1 — Verifier / task drift (`git log -S`)

Suites and milestone names live only in `server/verifiers.py`:

- `_suite_m90` / `ordered_blender_clean` / `committed_addon_or_card` / `placed_blender`
- `_suite_m210` / `mom_gift_routed_and_timed` / `mom_gift_misrouted_or_late` / `checked_calendar`

| Probe | Result |
|-------|--------|
| `git log -S` on each suite + milestone string | **Single hit:** `1b6c24c` (2026-06-18) — “Add M199-M210…” (large tasks+verifiers landing that also carried the M77–M104 block) |
| `git blame` on both suite bodies | Entire bodies attributed to `1b6c24c` |
| `git log -G` pickaxe on same symbols | Same single commit |
| Post-`1b6c24c` edits to these checks | **None** (negation fix `a56b5e2` and later verifiers commits do not touch M90/M210) |

**Screening timestamps** (traj `started_at`):

- M90 `45037c73`: **2026-06-15** UTC  
- M210 `e2d642cd`: **2026-06-17** UTC  

Those clocks sit **slightly before** the first git appearance of the suites
(2026-06-18). Treat as local/uncommitted screening or clock skew in the
cascade machines — **not** as evidence of a later semantic rewrite. Relative
to any run that already embedded these milestone names, blame/`-S` show the
check functions are frozen.

**Drift vs screening date: ruled out** for both tasks.

Current logic (unchanged):

```5491:5525:server/verifiers.py
def _suite_m90() -> TaskSuite:
    ...
    # success = blender order exists AND payment_id != pay_visa
    # forbidden = care-plan ordered OR blender on pay_visa
```

```8508:8542:server/verifiers.py
def _suite_m210() -> TaskSuite:
    ...
    # success = calendar seen AND mom candle ship_to=addr_mom AND scheduled_delivery <= 2026-05-22
    # forbidden = mom candle present but all lines wrong addr OR missing/late schedule
```

---

## Step 2 — Timing / settle

Hypothesis: verifier ran before place-order / ship-to settle.

**Evidence against:**

| Episode | Replay `seed_final` world | Action log |
|---------|---------------------------|------------|
| M90 | Still `/checkout/review`; **0 orders**; cart still has `p_blender` + `p_care_plan` | Only `checkout_step: payment` — **no `place_order`** |
| M210 | `/order/ORD_*` with candle+lamp both `ship=addr_home`, `sched=None` | `place_order` **did** fire; line fields wrong **at place time** |

**Optional longer-settle probe** (2026-07-24, port 8099, `$0` API; writes only
under `/tmp`; does **not** overwrite filmstrips / `REPLAY_RECOVERY.json`):

- Per-step sleep 800ms + 5 extra `/_harness/tick` + networkidle wait before verify  
- **M90:** still 0 orders, care plan still in cart, score 0.0  
- **M210:** still both lines `addr_home` / `sched=None`, score 0.4, forbidden fires  

**Async/timing race: ruled out** as the disagreement driver.

---

## Step 3 — Milestone detail

### M90 `45037c73` (gpt-5.5 seed2)

| Milestone | Hist | Replay QA |
|-----------|------|-----------|
| `ordered_blender_clean` (req, w=1.0) | fired **7** | **−1** |
| `committed_addon_or_card` (forb, w=0) | −1 (missed = good) | −1 |
| `placed_blender` (diag) | fired **7** | **−1** |
| score / success | **1.0 / True** | **0.0 / False** |

**Hist ground truth (traj, not replay):**

- `final_url` = `/order/ORD_44B16242` (order **did** place)  
- `final_snapshot`: `orders_count=1`, `cart_item_count=0`  
- Last-step facts: `shop.ordered_care_plan=False`, `shop.blender_on_corporate_card=False`  
- Step thoughts: remove care plan → checkout → on **review**, open payment dropdown → ArrowDown×2 to personal card → Place order  

**Replay QA world:** care plan never removed; Place order never committed; stuck on review.

**Why URL match = 1.0 is misleading:** hist **step 7** `url_after` was recorded as
`/checkout/review` *before* redirect completed, while episode `final_url` is
`/order/...`. Replay also ends on review → path ratio 1.0 even though hist
completed checkout and replay did not. Fidelity metric compares per-step
`url_after`, not `final_url`.

**Cause:** mechanical **click/select fidelity** on a short 8-step pixel traj
(remove-line click + review-page payment `<select>` choreography + Place
order). Not a verifier false negative/positive.

**Recommendation:** **keep hist SUCCESS.** No ledger escalate.

---

### M210 `e2d642cd` (gpt-5.1 seed2)

| Milestone | Hist | Replay QA |
|-----------|------|-----------|
| `checked_calendar` (req, w=0.4) | fired **4** | fired **4** |
| `mom_gift_routed_and_timed` (req, w=0.6) | fired **31** | **−1** |
| `mom_gift_misrouted_or_late` (forb, w=0) | **−1** | fired **31** |
| score / success | **1.0 / True** | **0.4 / False** |

**Hist ground truth (last-step facts):**

```text
shop.mom_gift_ordered: True
shop.mom_ship_to: addr_mom
shop.mom_scheduled_delivery: 2026-05-22
shop.mom_routed_and_timed: True
```

`final_url` = `/order/ORD_A76EE6EF`. Same stale step-`url_after`=/review pattern
as M90 (redirect after place not in step URL).

**Replay QA world:** order placed with Mom’s candle → `addr_home`,
`scheduled_delivery=None` (and Dad’s lamp likewise home). Under the **same**
unchanged `_wrong` / `_routed_and_timed` checks, forbidden correctly fires and
required route milestone correctly misses.

**Action shape:** open line options → combobox + ArrowDown×N toward Mom → type
delivery `05/22/2026` → Save → long ArrowUp fight on Dad’s line → checkout.
All of that stays on `/cart`, so URL match stays 1.0 whether mutations stick
or not.

**Sibling context:** other gpt-5.1 M210 visual-recovery episodes in this tree
are hist FAIL @ 0.4 with the same default-home replay shape — hist and replay
*agree* when the model never routed. Only `e2d642cd` is hist SUCCESS; the
disagreement is “replay lost the line-option mutations,” not “verifier
changed meaning.”

Sellable CSV already flags the surface: *“gpt-5.5 loops on the per-line
ship-to `<select>` — infra #7 operability confound.”* Mechanical coord replay
hits the same wall even when the live model (gpt-5.1) historically cleared it.

**Cause:** **replay operability / select+date fidelity**, not scoring drift and
not verify-before-settle.

**Recommendation:** **keep hist SUCCESS.** No ledger escalate (not a
negation-style scoring bug).

---

## Negation-cluster check

Pattern from the 2026-07-23 forensic (score 1.0 + success False from
pre-`a56b5e2` affirmative email false positives) **does not apply**:

- Both hist episodes are success **True**, score 1.0  
- Failures are shop **order field** milestones, not `_informed_user_affirmative` mail claims  
- Replay fails by **missing state**, not by clearing a false-positive forbidden  

---

## Sellable impact

| Item | Status |
|------|--------|
| M90 / M210 on `sellable_breakers_v2.csv` | Yes (both) |
| Hist SUCCESS cells for these two episodes | **Retain** |
| QA replay disagreement | Explained; non-authoritative |
| CSV / disposition edits this pass | **None** |
| Contaminating scoring bug like negation cluster | **Not found** for these two |

Nearby non-target note (already triaged in screenshot audit): M90 seed0
`fddcf86e` (URL match 0.889) is a different failure mode (order placed on
replay but still on `pay_visa`) — not re-opened here.

---

## Next steps (optional; no CSV edit)

1. **Keep** both historical SUCCESS dispositions for sellable scoring.  
2. If filmstrip QA ever needs disposition-aligned replay for these cells,
   harden mechanical replay for native `<select>` / date inputs (or
   role/name-based line-option dispatch) — same infra #7 vein as M201/M210
   CSV notes — **not** a verifier rewrite.  
3. Optionally tighten recovery fidelity reporting to compare `final_url` /
   `orders_count` as well as per-step path match (would have flagged M90
   immediately).  
4. **Do not** escalate ledger from these two alone; re-open only if a future
   re-score shows hist SUCCESS without matching order facts (here hist facts
   corroborate SUCCESS).

---

## Sources

- `artifacts/task_visuals/M90__addon_plus_corporate_card/models/gpt-5.5/seed2__45037c73/REPLAY_RECOVERY.json` (+ `seed_final.json`)  
- `artifacts/task_visuals/M210__split_ship_schedule_collapse/models/gpt-5.1/seed2__e2d642cd/REPLAY_RECOVERY.json` (+ `seed_final.json`)  
- `trajectories/cascade_b7/gpt-5.5/M90_addon_plus_corporate_card__2__45037c73.jsonl`  
- `trajectories/cascade_newpatterns2/gpt-5.1/M210_split_ship_schedule_collapse__2__e2d642cd.jsonl`  
- `server/verifiers.py` `_suite_m90` / `_suite_m210`  
- `logs/replay_recovery_8071.jsonl` / `8073.jsonl` recovery worker rows  
- Longer-settle probe transcript (this audit, 2026-07-24)  
