# Section 1A Calendar update/delete + subscription create/cancel — 2026-07-16

## Verdict

Browser-route/state parity for four previously untested archetypes is **CLOSED**
on seeds 0/1/2:

1. Calendar update/reschedule (`M200/dentist_move_doublebook`)
2. Calendar delete (`M366/delete_event_but_preserve_same_event_id`)
3. Subscription create (`M61/auto_refill_dead_card`)
4. Subscription cancel (`M76/ambiguous_subscription_cancel`)

Together with the prior Shop/Food/Calendar-create/ValueMart/Mail pass, this
wave closed four archetypes and left four residual. Those residuals were
closed 2026-07-16 (3 PASS + 1 STRUCTURAL_EXCEPTION for shop order-cancel);
see [remaining affordance parity](SECTION_1A_REMAINING_AFFORDANCE_PARITY_2026-07-16.md).
Final score: **12/13 PASS + 1 STRUCTURAL_EXCEPTION**.

No production UI/mutation changes were required for the calendar/subscription
wave — rendered routes already matched the direct mutation helpers used by
oracles and pure-logic tests.

## Route / mutation map

| Archetype | UI path | Direct mutation | Fixture |
|---|---|---|---|
| Calendar update | `GET /calendar/edit/{id}` → `POST /calendar/update` | `calendar.mutations.update_event` | M200 Dentist event retimed to 10:15–11:00 |
| Calendar delete | `GET /calendar/edit/{id}` → `POST /calendar/delete` | `calendar.mutations.delete_event` | M366 `cal_m366_vendor_review` |
| Subscription create | product Subscribe & Save form → `POST /api/subscriptions` | `mutations.create_subscription` | M61 `p_pet_food` monthly×4 on PayPal |
| Subscription cancel | account subscriptions → `POST /api/subscriptions/{id}/cancel` | `mutations.cancel_subscription` | M76 `sub_dogfood` |

## Evidence

Focused test: `tests/test_section1a_affordance_parity.py`.

Machine artifact (regenerated):  
`trajectories/prepublication_section1a_20260715/affordance_parity.json`

Notes:

- Calendar update/delete compare raw calendar semantic equality (deterministic IDs).
- Subscription create normalizes random `subscription_id` (`secrets.token_hex`) and
  clock-based `next_delivery_date`; all other subscription fields match.
- Subscription cancel compares raw status transitions (`sub_dogfood` cancelled,
  `sub_coffee` remains active).
- Captured Chromium traffic for these flows contains no `/_harness/*` URLs and no
  control-plane headers.

## Protocol impact

Superseded by the 2026-07-16 remaining-archetype pass: Section 1A
browser-route/state parity is now **CLOSED** at 12/13 PASS + 1 named
structural exception (`shop_order_cancel`). Failed-action plausibility P1
remains partial.
