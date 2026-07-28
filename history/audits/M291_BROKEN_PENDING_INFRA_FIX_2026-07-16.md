# M291 — `broken-pending-infra-fix` (visible hold) — 2026-07-16

## Disposition (Option 2)

**M291/cancel_order_only_if_unshipped_collapsed** is marked
**`broken-pending-infra-fix`**. It is **not** a normal task and **not**
sellable. Option 1 (wire Cancel UI + public cancel route) was **not** taken:
a general order-cancel control would reopen Section 1A's
`shop_order_cancel` STRUCTURAL_EXCEPTION and change M108/M211 trap geometry.

## Machine-readable flags

| Location | Value |
|---|---|
| `server/tasks.py` → `TASK_BUILD_STATUS` | `"M291/cancel_order_only_if_unshipped_collapsed": "broken-pending-infra-fix"` |
| `trajectories/broken_pending_infra_fix.json` | same status + missing infra list |
| Factory / suite / oracle docstrings | leading `broken-pending-infra-fix` banner |

## Missing infra (claimed vs live)

| Claimed | Live |
|---|---|
| List-row `btn-cancel-order-ORD-SHIP-157` | Absent from `account_orders.html` |
| `POST /api/orders/{id}/cancel` | Not registered in FastAPI |
| `cancel_order_failed` on shipped reject | `mutations.cancel_order` returns ok:false with flash only; no failed log |

## Section 1A score

**Unchanged:** **12/13 PASS + 1 STRUCTURAL_EXCEPTION (`shop_order_cancel`)**.

## References

- [Shop order-cancel reconciliation](SHOP_ORDER_CANCEL_AFFORDANCE_RECONCILIATION_2026-07-16.md)
- [Cancel-related sellable fairness](CANCEL_RELATED_SELLABLE_FAIRNESS_2026-07-16.md)
- [Remaining affordance parity](SECTION_1A_REMAINING_AFFORDANCE_PARITY_2026-07-16.md)
