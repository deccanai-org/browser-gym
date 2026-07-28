# Section 1A affordance parity and action-boundary audit — 2026-07-15

## Verdict

The 85 active sellables exercise **13 distinct mutation archetypes**. Nine
have representative rendered-Chromium/direct-mutation parity on independently
reset seeds 0/1/2: Shop checkout, Food order, Calendar create, Calendar update,
Calendar delete, ValueMart order, Mail send, subscription create, and
subscription cancel. Calendar/Mail/Food/ValueMart comparisons use raw semantic
equality; subscription create normalizes random IDs and clock-based
`next_delivery_date`.

Therefore browser-route/state parity remains **PARTIAL (9/13)**. Untested:
return initiation, Shop order-cancel contract, payment/default change, and
address/default change. Calendar update/delete and subscription create/cancel
were closed 2026-07-16
([Calendar/subscription parity](SECTION_1A_CALENDAR_SUBSCRIPTION_PARITY_2026-07-16.md)).

Cross-app propagation is **CLOSED for the active set**. The active sellables
use three source-to-destination order-event archetypes:
ShopGym→Mail (`ShopOrderPlaced`), Food→Mail (`FoodOrderPlaced`), and
ValueMart→Mail (`MarketOrderPlaced`). Checkout previously covered the first;
this pass covers the latter two on seeds 0/1/2. There is no Food→Calendar
subscriber in current production wiring, so claiming that path would invent a
contract. Each source action produced one `evt_1` at step 0, one matching
destination receipt, `delivered=true`, no preexisting matching receipt, and no
duplicate delivery.

The intended rendered paths use no privileged route: **P0 CLOSED**. Captured
Chromium traffic for all 12 new rendered runs contains no `/_harness/*`
request and no `X-Harness-Token` header. Public app form routes are the actual
UI contracts. Browser fetch/navigation to world/reset without the token returns
401, and the token is absent from DOM/source, cookies, local/session storage,
and captured URLs/headers.

Failed-action plausibility remains **P1 PARTIAL**. Five realistic current
failure classes pass visible-message and atomicity checks; three requested
classes are not implemented as rendered product failures and must not be
represented as if they were.

## Major-affordance inventory

Task IDs below are the active reported tasks whose requested, safe, or
forbidden path depends on the archetype. A task may appear in several rows.
The machine-readable mapping is in `affordance_parity.json`.

1. **Shop order/checkout and line configuration (tested):**
   M46, M57, M66, M68, M70, M72–M75, M77–M79, M81–M104, M111,
   M141, M142, M148, M207, M210, M214, M219, M227, M252, M271,
   M272, M307, M312.
2. **Mail send (tested):**
   M37, M39–M41, M47, M51, M57, M59, M76, M80, M105–M109, M111,
   M115–M117, M141, M142, M148, M164, M200, M211–M214, M217, M219,
   M220, M224, M227, M248, M252, M271, M272, M312, M343, M346,
   M348, M349, M354, M362, M366.
3. **Calendar create (tested):** M43, M57.
4. **Calendar update/reschedule (tested 2026-07-16):** M80, M200.
5. **Calendar delete (tested 2026-07-16):** M366.
6. **Food order (tested):** M248, M343, M346, M348, M349, M354, M362.
7. **ValueMart order (tested):** M354.
8. **Subscription create (tested 2026-07-16):** M61.
9. **Subscription cancel (tested 2026-07-16):** M76, M164, M212, M217.
10. **Return initiation (tested 2026-07-16):** M41, M47, M109.
11. **Shop order cancellation contract (STRUCTURAL_EXCEPTION 2026-07-16):**
    M108, M211 — no rendered cancel control / no public cancel route.
12. **Payment method/default change (tested 2026-07-16):** M117, M213.
13. **Address/default change (tested 2026-07-16):** M220.

## Rendered versus direct parity

Focused test:
`tests/test_section1a_affordance_parity.py`.

- **Food order (M362 fixture):** Burger Barn, two Classic Cheeseburgers,
  $20.00 subtotal + $2.49 fee = $22.49; generic leave-at-door instruction;
  cart clear; preparing order; matching Food receipt and
  `FoodOrderPlaced`; no inventory field exists in FoodState.
- **Calendar create (M43 fixture):** exact title, today, 19:00–20:00,
  `source=user`, same deterministic event identity; no overlap on this
  half-open boundary; no Mail/event-bus side effect exists for create.
- **Calendar update (M200 fixture, 2026-07-16):** Dentist retimed to
  10:15–11:00 via `/calendar/update`; same event id preserved.
- **Calendar delete (M366 fixture, 2026-07-16):** `cal_m366_vendor_review`
  removed via `/calendar/delete`.
- **ValueMart order (M354 fixture):** two Welcome Signs, VALUE10,
  item/quantity/subtotal/discount/delivery/total, cart and coupon clear,
  matching ValueMart receipt and `MarketOrderPlaced`.
- **Mail send (M37 fixture):** exact recipient, subject, body, Sent-folder
  state, and one `MailSent` trigger. The current Mail model has no cc/bcc,
  thread, or reply mutation fields, so none were silently normalized away.
- **Subscription create (M61 fixture, 2026-07-16):** monthly×4 `p_pet_food`
  on PayPal via product Subscribe & Save form; IDs/dates normalized.
- **Subscription cancel (M76 fixture, 2026-07-16):** `sub_dogfood` cancelled
  via account control; `sub_coffee` unchanged.
- **Return initiation (M109 fixture, 2026-07-16):** kettle line return via
  order detail → return form → `POST /api/returns`; `ReturnFiled` event;
  return id / `created_at` normalized.
- **Payment default (M213 fixture, 2026-07-16):** `pay_personal` set default
  via account payments; `pay_visa` / `pay_paypal` non-default.
- **Address default (M220 fixture, 2026-07-16):** `addr_work` set default via
  account addresses; `addr_home` non-default.
- **Shop order-cancel (STRUCTURAL_EXCEPTION, 2026-07-16):** no rendered cancel
  control and no public cancel route; see remaining-affordance audit.
- **Shop checkout:** prior audit covers order line, quantity, total,
  inventory decrement, payment/address, cart clear, receipt and event.

Only Shop’s random order/shipment/tracking IDs and timestamps were normalized
in the earlier checkout artifact. Subscription create and return initiation
normalize minted IDs/timestamps; other affordance comparisons normalize
nothing.

Artifacts:

- `trajectories/prepublication_section1a_20260715/checkout_parity.json`
- `trajectories/prepublication_section1a_20260715/affordance_parity.json`
- `trajectories/prepublication_section1a_20260715/privileged_route_network_evidence.json`
- `trajectories/prepublication_section1a_20260715/failed_action_plausibility.json`

## Failure-path results

PASS through rendered UI and current route/mutation boundary:

- Calendar overlap: names `Team sync` and its 14:00–15:00 window; no event
  created; owned by `calendar.create_event`.
- Invalid ValueMart coupon: visible “isn't valid” reason; coupon/cart unchanged;
  owned by `market.apply_coupon`.
- Cross-restaurant Food cart: tells the user to clear the other restaurant;
  original cart unchanged; owned by `food.add_dish`.
- Out-of-stock Shop product: explicit OOS label and disabled Add/Buy controls;
  cart/orders unchanged; rendered pre-submit validation.
- Invalid Mail recipient: explicit valid-recipient error; no Sent row or event;
  owned by `mail.send_email`.

Current mechanics that remain gaps:

- card expiry/decline is not validated by Shop `place_order`;
- Shop checkout does not re-check stock at commit (OOS is add-time only);
- shipped-order cancellation is rejected by the pure mutation, but the current
  rendered order detail has no cancel form/control (**named structural
  exception** for route/mutation parity as of 2026-07-16).

These are documented as controlled/adversarial mechanics or product-mechanics
gaps, not passed off as realistic rendered failures. The P1 remains partial
until major failure classes attached to all active affordances are exercised,
including subscription/return/account-setting boundaries.

## Validation

- `pytest -q tests/test_section1a_affordance_parity.py` — **3 passed**
  (regenerated 2026-07-16 with return/payment/address + cancel exception).
- No production code changed for the remaining-archetype pass, so a full-suite
  rerun was not required.
- The fixture server used an ephemeral port and stopped cleanly.
- No paid model, commit, or push was used.
