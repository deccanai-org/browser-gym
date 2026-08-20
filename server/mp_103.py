"""mp_103 / annual_checkup_reschedule_and_prescription_refill — Mail×Cal×Shop.

User labeled this mp_097 originally; that ID is coffee_roaster — use mp_103.

Mechanism: Dr. Osei email has the NEW checkup date (June 19 9:00 AM). Xoogle still
shows a STALE older appointment. Vertane 30-Day Refill is an open Xmazon order on
standard shipping with ETA AFTER June 19; Express upgrade lands BEFORE the appointment.
Gold: trust email date (not calendar), upgrade shipping, email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_103/annual_checkup_reschedule_and_prescription_refill"
BRIEF_KEY = "mp_103"
BRIEF = (
    "My annual checkup with Dr. Osei got moved, check the email for the new date, "
    "then see if my Vertane prescription refill order will actually get here before "
    "that appointment so I don't run out. If it won't make it in time, switch to "
    "faster shipping. Email me the details once it's sorted."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-06-10T11:00:00"

NEW_APPT_DAY = "2026-06-19"
NEW_APPT_LABEL = "June 19"
STALE_APPT_DAY = "2026-06-05"
STALE_EVENT_ID = "ev_mp103_stale_checkup"

VERTANE_SKU = "p_mp103_vertane_30"
VERTANE_NAME = "Vertane 30-Day Refill"
ORDER_ID = "ORD-MP103-VERTANE"
LINE_ID = "ln_mp103_vertane"
DECOY_ORDER = "ORD-MP103-DECOY"
DECOY_SKU = "p_mp103_vitamins"

STANDARD_ETA = "June 22, 2026"
EXPRESS_ETA = "June 17, 2026"

_EMAIL_DATE_RE = re.compile(
    r"(?ix)\b(june\s*19|jun\.?\s*19|2026-06-19|6/19|06/19)\b"
)
_STALE_DATE_RE = re.compile(
    r"(?ix)\b(june\s*5|jun\.?\s*5|2026-06-05|6/5|06/05)\b"
)
_VERTANE_RE = re.compile(r"(?ix)\b(vertane|prescription|refill|ord-mp103-vertane)\b")
_EXPRESS_RE = re.compile(
    r"(?ix)\b(express|faster\s+ship|upgraded?\s+(the\s+)?ship|"
    r"overnight|expedit\w*|switched\s+to\s+(express|faster))\b"
)


def task_mp_103_annual_checkup_reschedule_and_prescription_refill(
    seed: int,
) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[STALE_EVENT_ID] = CalendarEvent(
        id=STALE_EVENT_ID,
        title="Annual checkup — Dr. Osei (OUTDATED)",
        day=STALE_APPT_DAY,
        day_label="Thu Jun 5",
        start="09:00",
        end="09:45",
        source="seed",
        description=(
            "STALE calendar copy — the appointment was moved. Check Xmail "
            "from Dr. Osei for the new date."
        ),
        location="Clinic A",
    )
    cal.events["ev_mp103_standup"] = CalendarEvent(
        id="ev_mp103_standup",
        title="Team standup",
        day="2026-06-11",
        day_label="Wed Jun 11",
        start="09:30",
        end="09:45",
        source="seed",
    )

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.subscriptions.clear()

    shop.products[VERTANE_SKU] = Product(
        id=VERTANE_SKU,
        name=VERTANE_NAME,
        brand="VertaneRx",
        category="health",
        base_price=42.00,
        rating=4.5,
        review_count=310,
        stock=40,
        image_emoji="💊",
        short_description="Prescription Vertane 30-day refill bottle.",
        tags=["vertane", "prescription", "refill"],
    )
    shop.products[DECOY_SKU] = Product(
        id=DECOY_SKU,
        name="Daily Multivitamin 90ct",
        brand="NutriDay",
        category="health",
        base_price=18.00,
        rating=4.2,
        review_count=900,
        stock=100,
        image_emoji="🧴",
        short_description="Unrelated open order decoy.",
        tags=["vitamins", "decoy"],
    )

    addr = shop.users["u_alice"].addresses["addr_home"]
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-06-08T10:00:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=VERTANE_SKU,
                product_name=VERTANE_NAME,
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=42.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id=addr.id,
                scheduled_delivery=None,
            )
        ],
        subtotal=42.00,
        discount=0.0,
        tax=3.57,
        shipping=5.99,
        total=51.56,
        promo_code=None,
        payment_id="pay_visa",
        status="confirmed",
        shipping_speed="standard",
        express_eta=EXPRESS_ETA,
        shipments=[
            Shipment(
                id="sh_mp103_vertane",
                tracking_number="1Z999MP103VERT",
                carrier="UPS",
                item_ids=[LINE_ID],
                status="confirmed",
                estimated_delivery=STANDARD_ETA,
                events=[
                    ShipmentEvent(
                        "2026-06-08T12:00:00Z",
                        "label_created",
                        "Pharmacy DC",
                        "Label created — standard shipping.",
                    ),
                ],
            )
        ],
    )
    shop.orders[DECOY_ORDER] = Order(
        id=DECOY_ORDER,
        user_id="u_alice",
        placed_at="2026-06-07T09:00:00Z",
        items=[
            OrderItem(
                id="ln_mp103_decoy",
                product_id=DECOY_SKU,
                product_name="Daily Multivitamin 90ct",
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=18.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id=addr.id,
                scheduled_delivery=None,
            )
        ],
        subtotal=18.00,
        discount=0.0,
        tax=1.53,
        shipping=5.99,
        total=25.52,
        promo_code=None,
        payment_id="pay_visa",
        status="confirmed",
        shipping_speed="standard",
        shipments=[
            Shipment(
                id="sh_mp103_decoy",
                tracking_number="1Z999MP103DEC",
                carrier="UPS",
                item_ids=["ln_mp103_decoy"],
                status="confirmed",
                estimated_delivery="June 16, 2026",
            )
        ],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp103_osei"] = Email(
        id="em_mp103_osei",
        sender="dr.osei@riversideclinic.example.com",
        to=USER_EMAIL,
        subject="Your annual checkup has been rescheduled",
        body=(
            "Hi Alice,\n\n"
            "Dr. Osei's office moved your annual checkup.\n\n"
            f"NEW appointment: {NEW_APPT_LABEL}, 2026 at 9:00 AM (plain).\n"
            "Please ignore any older date still on your calendar.\n\n"
            "— Riverside Clinic scheduling"
        ),
        received_at=f"{SEED_DATE}T08:40:00",
        received_label="8:40 AM",
        read=False,
        labels=["health"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_103_annual_checkup_reschedule_and_prescription_refill,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _blob(msg) -> str:
        return f"{getattr(msg, 'subject', '') or ''}\n{getattr(msg, 'body', '') or ''}"

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _vertane_order(p: Probe):
        shop = _shop(p)
        return (shop.orders or {}).get(ORDER_ID) if shop else None

    def _extracted_new_date(p: Probe) -> bool:
        # Durable: confirmation email cites the new June 19 date from Dr. Osei mail.
        for msg in _sent(p):
            if _to_alice(msg) and _EMAIL_DATE_RE.search(_blob(msg)):
                return True
        # Also accept view of the inbox email + later action.
        if _log_has(p, "mail.open") or _log_has(p, "mail.view"):
            return any(
                _EMAIL_DATE_RE.search(_blob(msg)) for msg in _sent(p) if _to_alice(msg)
            )
        return False

    def _did_not_trust_stale(p: Probe) -> bool:
        # Required: either never cites stale date as the appointment, or cites
        # new date while upgrading / confirming. Fail if only stale is treated
        # as the live appointment without the new date.
        alice = [m for m in _sent(p) if _to_alice(m)]
        if not alice:
            return False
        cites_new = any(_EMAIL_DATE_RE.search(_blob(m)) for m in alice)
        cites_stale_as_plan = False
        for m in alice:
            text = _blob(m)
            if _STALE_DATE_RE.search(text) and not _EMAIL_DATE_RE.search(text):
                # Mentions only stale date as the appointment plan.
                if re.search(r"(?ix)\b(appointment|checkup|visit|scheduled)\b", text):
                    cites_stale_as_plan = True
        return cites_new and not cites_stale_as_plan

    def _checked_eta(p: Probe) -> bool:
        if _log_has(p, "view_order") or _log_has(p, "view_orders") or _log_has(p, "view_tracking"):
            return True
        o = _vertane_order(p)
        # After upgrade, shipping_speed changed — implies they inspected the order.
        if o and (getattr(o, "shipping_speed", "") or "") == "express":
            return True
        for msg in _sent(p):
            if _to_alice(msg) and _VERTANE_RE.search(_blob(msg)):
                text = _blob(msg).lower()
                if any(x in text for x in ("eta", "arriv", "deliver", "june 22", "before")):
                    return True
        return False

    def _upgraded_shipping(p: Probe) -> bool:
        if _log_has(p, "change_order_shipping"):
            o = _vertane_order(p)
            return bool(o and (getattr(o, "shipping_speed", "") or "") == "express")
        o = _vertane_order(p)
        if not o:
            return False
        speed = (getattr(o, "shipping_speed", "") or "").lower()
        return speed == "express"

    def _emailed_confirmation(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg)
            if _VERTANE_RE.search(text) and (
                _EXPRESS_RE.search(text) or _EMAIL_DATE_RE.search(text)
            ):
                return True
        return False

    def _used_stale(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg)
            if _STALE_DATE_RE.search(text) and not _EMAIL_DATE_RE.search(text):
                if re.search(r"(?ix)\b(appointment|checkup|visit|on\s+june)\b", text):
                    return True
        return False

    def _left_shipping(p: Probe) -> bool:
        o = _vertane_order(p)
        if not o:
            return False
        speed = (getattr(o, "shipping_speed", "") or "standard").lower()
        if speed != "standard":
            return False
        # Must NOT be true at FOI (sticky fired_at_step=0). Only trip after the
        # agent engaged the order/email surface and still left standard shipping.
        engaged = (
            _log_has(p, "view_order")
            or _log_has(p, "view_orders")
            or _log_has(p, "view_tracking")
            or bool(_sent(p))
        )
        return engaged

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "extracted_new_appointment_date_from_email",
                    weight=0.2,
                    check=_extracted_new_date,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_trust_stale_calendar_date",
                    weight=0.15,
                    check=_did_not_trust_stale,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_prescription_order_eta",
                    weight=0.2,
                    check=_checked_eta,
                    required_for_success=True,
                ),
                Milestone(
                    "upgraded_shipping_because_eta_missed_deadline",
                    weight=0.3,
                    check=_upgraded_shipping,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_confirmation_of_actions",
                    weight=0.15,
                    check=_emailed_confirmation,
                    required_for_success=True,
                ),
                Milestone(
                    "used_stale_calendar_date",
                    weight=0.0,
                    check=_used_stale,
                    forbidden=True,
                ),
                Milestone(
                    "left_shipping_unchanged_despite_missed_deadline",
                    weight=0.0,
                    check=_left_shipping,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
