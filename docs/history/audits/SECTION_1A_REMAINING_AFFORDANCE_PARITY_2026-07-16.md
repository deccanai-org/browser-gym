# Section 1A remaining affordance parity — 2026-07-16

## Verdict

Browser-route/state parity for the four residual major affordances is
**CLOSED with one named structural exception**:

| Archetype | Result | Notes |
|---|---|---|
| Return initiation | **PASS** | Seeds 0/1/2; normalized return id / `created_at` / event payload |
| Shop order-cancel | **STRUCTURAL_EXCEPTION** | No rendered cancel control; no public cancel route |
| Payment method/default change | **PASS** | Seeds 0/1/2; raw semantic equality |
| Address/default change | **PASS** | Seeds 0/1/2; raw semantic equality |

Together with prior Shop/Food/Calendar/Xbay/Mail/subscription coverage,
major affordance parity is **12/13 PASS + 1 STRUCTURAL_EXCEPTION**
(`CLOSED_WITH_NAMED_EXCEPTIONS`).

No production UI/mutation/verifier changes were required. Existing rendered
routes already matched the direct mutation helpers for the three PASS
archetypes. Inventing an order-cancel button solely to check the 1A box
would fake-pass an affordance that reported M108/M211 tasks intentionally
lack.

## Route / mutation map

| Archetype | UI path | Direct mutation | Fixture |
|---|---|---|---|
| Return initiation | order detail → `/account/returns/new` → `POST /api/returns` | `mutations.initiate_return` + `shop_hooks.emit_return_filed` | M109 `ORD-KET-1` / `ln_kettle` defective → original payment |
| Payment default | `/account/payments` → `POST /api/account/payments/pay_personal/default` | `mutations.set_default_payment` | M213 flip default to `pay_personal` |
| Address default | `/account/addresses` → `POST /api/account/addresses/addr_work/default` | `mutations.set_default_address` | M220 flip default to `addr_work` |
| Shop order-cancel | **none** | `mutations.cancel_order` only | M211 `ORD-5501` (UI absence); mutation contract also checked on confirmed `ORD-6601` |

## Structural exception — shop order-cancel

Evidence collected in `affordance_parity.json` → `exceptions[0]`:

- Rendered `/account/orders/ORD-5501` exposes **Initiate return** + tracking only.
- Zero cancel-ish controls with cancel text / test-id / form action.
- FastAPI registers **no** public route matching order+cancel.
- Pure mutation rejects out-for-delivery (`ok: false`, status unchanged) and
  accepts confirmed unshipped (`ORD-6601` → `cancelled`).

This is an honest product-surface gap for browser agents, not a parity bug
between two existing paths. Documenting the exception preserves the M108/M211
trap (agents claim cancel/stoppage without a real UI cancel affordance).

### Reconciliation vs M291 (2026-07-16)

M291's factory/suite/oracle **claim** a list-row Cancel button and
`POST /api/orders/{id}/cancel`, but templates and FastAPI never received that
wiring (nor task-id gating). The gap is **global**, not “M291-only UI exists.”
Exception **stands**; score unchanged (**12/13 PASS + 1 STRUCTURAL_EXCEPTION**).
M291 marked **`broken-pending-infra-fix`** (Option 2):
[M291_BROKEN_PENDING_INFRA_FIX_2026-07-16.md](M291_BROKEN_PENDING_INFRA_FIX_2026-07-16.md).
Full evidence:
[SHOP_ORDER_CANCEL_AFFORDANCE_RECONCILIATION_2026-07-16.md](SHOP_ORDER_CANCEL_AFFORDANCE_RECONCILIATION_2026-07-16.md).

## Evidence

Focused tests: `tests/test_section1a_affordance_parity.py` (3 passed).

Machine artifact (regenerated):
`trajectories/prepublication_section1a_20260715/affordance_parity.json`

Notes:

- Return initiation normalizes random return ids, clock `created_at`, and
  `ReturnFiled` payload `return_id`; event id/step/type match raw.
- Payment/address default changes compare raw user payment_methods /
  addresses (default flags flip; unrelated state unchanged).
- Captured Chromium traffic for the three PASS flows contains no
  `/_harness/*` URLs and no control-plane headers.

## Protocol impact

Section 1A browser-route/state parity moves from **PARTIAL 9/13** to
**CLOSED 12/13 PASS + 1 named structural exception (`shop_order_cancel`)**.
Failed-action plausibility P1 remains partial (unchanged by this pass).
