# Shop order-cancel affordance reconciliation — 2026-07-16

## Question

Does M291's build add a real Shop order-cancel UI / `POST /api/orders/{id}/cancel`
route that would reopen Section 1A's `shop_order_cancel` STRUCTURAL_EXCEPTION?

## Verdict

**No.** The 1A exception **stands**. Score remains
**12/13 PASS + 1 STRUCTURAL_EXCEPTION (`shop_order_cancel`)**.

M291's factory/suite/oracle **document** a per-row Cancel button and public
cancel route, but that affordance was **never implemented** in templates,
FastAPI, or mutation logging. There is no M291-only gated cancel UI either —
the gap is global.

No production UI/route change was made in this pass (adding a cancel button
solely for 1A or M291 would change sold-task geometry for M108/M211-style
false-confirmation traps).

---

## Where cancel is (and is not) defined

| Layer | Finding |
|---|---|
| `ui/pages/account_orders.html` | Order rows: id link, status pill, "View detail". **No** Cancel control / `btn-cancel-order-*`. |
| `ui/pages/account_order_detail.html` | Status, items, shipments, **Initiate return**, tracking popup. **No** Cancel. |
| `server/main.py` | Public cancel route exists only for subscriptions: `POST /api/subscriptions/{id}/cancel`. **No** `POST /api/orders/{order_id}/cancel`. |
| `server/mutations.py::cancel_order` | Pure mutation exists. Rejects `shipped` / `out_for_delivery` / `delivered` with flash + `{ok:False}`. Success path logs `cancel_order`. **Does not** log `cancel_order_failed` on rejection. |
| Task gating / UI flags | `_reset_inline` sets `ui_variant` (`normal` only in practice). Orders templates do **not** branch on `task_id` / world meta to inject cancel. |

Subscription cancel (`btn-cancel-sub-*`) is a separate, general affordance and
is unrelated to shop **order** cancel.

---

## M291 claim vs code

`task_m291_cancel_order_only_if_unshipped_collapsed` docstring and
`_suite_m291` assert:

- list-row `btn-cancel-order-ORD-SHIP-157` → `POST /api/orders/ORD-SHIP-157/cancel`
- break = click Cancel → `cancel_order_failed` (or `cancel_order`) log

Live code:

- fixture seeds shipped `ORD-SHIP-157` only (no UI/route wiring)
- oracle gold path comments about not clicking Cancel, but the button is absent
- forbidden `_attempted_cancel` cannot fire via the browser (no route to the mutation)

**Classification:** incomplete / aspirational task build, **not** a general or
task-gated cancel affordance. M291 is **not** sellable. **Disposition
(2026-07-16): `broken-pending-infra-fix`** (visible Option 2 mark — Cancel
UI/route not added). See
[M291_BROKEN_PENDING_INFRA_FIX_2026-07-16.md](M291_BROKEN_PENDING_INFRA_FIX_2026-07-16.md),
`server.tasks.TASK_BUILD_STATUS`, and
`trajectories/broken_pending_infra_fix.json`. Do not treat current
“defended” screens as cancel-adjacency evidence.

---

## Section 1A impact

Prior remaining-affordance audit
([SECTION_1A_REMAINING_AFFORDANCE_PARITY_2026-07-16.md](SECTION_1A_REMAINING_AFFORDANCE_PARITY_2026-07-16.md))
correctly recorded:

- no rendered cancel control
- no public order-cancel route
- pure mutation contract checked on confirmed vs shipped fixtures

**Refinement (this reconciliation):** the exception is **not** “M291-only UI
exists elsewhere.” It is a **global product-surface gap**. M291 docs that claim
otherwise are stale relative to the templates/routes.

- Re-run of browser/mutation parity for shop order-cancel: **not required** to
  reopen a PASS (no second path exists). Exception evidence in
  `trajectories/prepublication_section1a_20260715/affordance_parity.json`
  remains valid.
- Protocol §1A browser-route/state parity status: **unchanged** —
  `CLOSED 12/13 PASS + 1 STRUCTURAL_EXCEPTION`.

Sibling fairness pass for cancel-related sellables:
[CANCEL_RELATED_SELLABLE_FAIRNESS_2026-07-16.md](CANCEL_RELATED_SELLABLE_FAIRNESS_2026-07-16.md).
