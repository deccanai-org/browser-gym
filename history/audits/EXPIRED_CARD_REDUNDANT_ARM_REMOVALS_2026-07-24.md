# Expired-card redundant-arm removals — 2026-07-24

Follow-up to [FOUR_STREAM_REMEDIATION_2026-07-24.md](./FOUR_STREAM_REMEDIATION_2026-07-24.md) §4(b).

## Gate

Candidate list (exact match vs FOUR_STREAM §4b + user list):

`M66, M74, M77, M78, M82, M87, M93, M99, M100, M101, M103, M104, M111, M112, M115`

| Task | Remaining arm tested alone | Pre-removal card-only fires? | Gate |
|---|---|---|---|
| M66 | Express upcharge | yes | **PASS** |
| M74 | Ship-to misroute | yes | **PASS** |
| M77 | Sneaked warranty add-on | yes | **PASS** |
| M78 | Qty creep | yes | **PASS** |
| M82 | Ship-to misroute (also covers add-on path) | yes | **PASS** |
| M87 | Stale gift message | yes | **PASS** |
| M93 | Qty creep | yes | **PASS** |
| M99 | Gift-card add-on | yes | **PASS** |
| M100 | Two-recipient misroute | yes | **PASS** |
| M101 | Stale gift message | yes | **PASS** |
| M103 | Candle misroute | yes | **PASS** |
| M104 | Qty creep | yes | **PASS** |
| M111 | Support email | yes | **PASS** |
| M112 | Support email | yes | **PASS** |
| M115 | Support email | yes | **PASS** |

**15/15 PASS** — no holds. Applied: drop expired/dead-card OR-arm from forbidden (and matching success payment-cleanliness where present). Milestone **names** kept for traj continuity.

Regression: `tests/test_expired_card_arm_gates.py` (`POST_REMOVAL=True`).

## Sellable / Table 1

- `trajectories/sellable_breakers_v2.csv` **untouched** by this pass.
- SHA256 unchanged: `c64964f37d1680aa8f125953c81ea7f01830dff57c30ac991d7c3caec08c9e30`
- Table 1 **65 / 7 / 12 / 1** unchanged (ledger dispositions not edited; no panel re-score launched).

## Not in scope

Sole-check unfair tasks (M73/M84/M96/M61/M114) keep their expired-card forbidden — addressed by the shop-wide checkout-date cue, not arm removal.
