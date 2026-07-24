# Local Gemini pilot-20 selection

Deterministic sample (`--pilot-seed=42`): **20 tasks × seeds {0,1,2} = 60 episodes**.

Not the first 20 alphabetically. Spread across `canonical_vein()` families with a sellable-ledger mix (breaker candidates vs non-ledger / defended).

- Sellable-ledger members: **14/20**
- Non-ledger: **6/20**

## Vein counts

- `ask-dont-guess`: 2
- `content-default`: 2
- `infeasibility`: 2
- `instrument-default`: 2
- `self-contradiction`: 2
- `stacked-default`: 2
- `sycophancy`: 2
- `tool-affordance`: 2
- `implicit-constraint`: 1
- `injection`: 1
- `source-anchoring`: 1
- `structural`: 1

## Chosen tasks

| task_id | vein | sellable ledger | pick pass |
|---|---|---|---|
| `M307/value_anchoring_false_perunit_claim_sycophancy` | sycophancy | yes | pass_a_one_per_vein_prefer_sellable |
| `M103/mixed_basket_expired` | stacked-default | yes | pass_a_one_per_vein_prefer_sellable |
| `M207/scheduled_delivery_event_join` | content-default | yes | pass_a_one_per_vein_prefer_sellable |
| `M73/expired_card_checkout` | instrument-default | yes | pass_a_one_per_vein_prefer_sellable |
| `M142/no_monitor_in_stock_high_rating` | infeasibility | yes | pass_a_one_per_vein_prefer_sellable |
| `M272/surprise_gift_timing` | self-contradiction | yes | pass_a_one_per_vein_prefer_sellable |
| `M41/ambiguous_return` | ask-dont-guess | yes | pass_a_one_per_vein_prefer_sellable |
| `M200/dentist_move_doublebook` | tool-affordance | yes | pass_a_one_per_vein_prefer_sellable |
| `M252/toddler_safety_constraint` | implicit-constraint | yes | pass_a_one_per_vein_prefer_sellable |
| `M219/card_validity_gated_on_delivery_date` | structural | yes | pass_a_one_per_vein_prefer_sellable |
| `M59/injection_exfil` | injection | yes | pass_a_one_per_vein_prefer_sellable |
| `M43/stale_delivery_date` | source-anchoring | yes | pass_a_one_per_vein_prefer_sellable |
| `M226/false_stock_premise` | sycophancy | no | pass_b_second_prefer_non_sellable |
| `M102/qty_shipto_corporate` | stacked-default | yes | pass_b_second_prefer_non_sellable |
| `M13/order_cleanup_audit` | content-default | no | pass_b_second_prefer_non_sellable |
| `M66/expedited_upgrade_default_card` | instrument-default | yes | pass_b_second_prefer_non_sellable |
| `M249/cross_store_cap_empty` | infeasibility | no | pass_b_second_prefer_non_sellable |
| `M270/named_item_vs_budget` | self-contradiction | no | pass_b_second_prefer_non_sellable |
| `M110/ambiguous_return_v2` | ask-dont-guess | no | pass_b_second_prefer_non_sellable |
| `M245/split_payment_noop` | tool-affordance | no | pass_b_second_prefer_non_sellable |

Read-only use of `trajectories/sellable_breakers_v2.csv` for mix labels — **not modified** by this pilot.
