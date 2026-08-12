"""mp_118 / austin_aa1420_trip_prep_email — Cal×Shop×Food×VM×Mail.

Redesign of Eligible e28 mp_079. Named AA 1420 Austin flight Thu 6:40 AM,
Wed vendor sync + Fri local standup conflicts, TripPlug adapter arrives May 23
(after departure). Gold = flag both conflicts, catch late adapter + take action,
no food during travel, email Alice the details. mp_079 left untouched.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_118/austin_aa1420_trip_prep_email"
BRIEF_KEY = "mp_118"
BRIEF = (
    "I'm flying to Austin Thursday on AA 1420 for work — make sure food is "
    "covered while I'm gone, that my TripPlug travel adapter shipment arrives "
    "before I leave, and clear any calendar conflicts. Email me the details."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-20T16:00:00"
WED = "2026-05-20"
THU = "2026-05-21"
FRI = "2026-05-22"

FLIGHT_ID = "ev_mp118_flight"
WED_MEET = "ev_mp118_wed_meet"
FRI_MEET = "ev_mp118_fri_meet"
ADAPTER_ORDER = "ORD-MP118-ADAPTER"
ADAPTER_SKU = "p_mp118_travel_adapter"
VM_DISTRACTOR = "vm_mp118_souvenir"


def task_mp_118_austin_aa1420_trip_prep_email(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[FLIGHT_ID] = CalendarEvent(
        id=FLIGHT_ID,
        title="Flight to Austin (AA 1420)",
        day=THU,
        day_label="Thu May 21",
        start="06:40",
        end="10:15",
        source="seed",
        description="Depart JFK 6:40 AM Thursday on AA 1420. Return Sunday evening.",
        status="confirmed",
    )
    cal.events[WED_MEET] = CalendarEvent(
        id=WED_MEET,
        title="Vendor sync with Priya (conflicts with trip prep)",
        day=WED,
        day_label="Wed May 20",
        start="15:00",
        end="16:30",
        source="seed",
        description=(
            "Afternoon vendor sync with Priya — overlaps last work block before "
            "Austin departure tomorrow morning."
        ),
        status="confirmed",
    )
    cal.events[FRI_MEET] = CalendarEvent(
        id=FRI_MEET,
        title="Local standup — Brooklyn office",
        day=FRI,
        day_label="Fri May 22",
        start="09:00",
        end="09:30",
        source="seed",
        description="In-office Brooklyn standup — you will be in Austin; needs cancel/reschedule.",
        status="confirmed",
    )
    cal.events["ev_mp118_return"] = CalendarEvent(
        id="ev_mp118_return",
        title="Return flight from Austin (AA 1421)",
        day="2026-05-24",
        day_label="Sun May 24",
        start="17:00",
        end="21:00",
        source="seed",
        status="confirmed",
    )

    shop = world.shop
    shop.products[ADAPTER_SKU] = Product(
        id=ADAPTER_SKU,
        name="Universal Travel Adapter",
        brand="TripPlug",
        category="electronics",
        base_price=24.00,
        rating=4.3,
        review_count=200,
        stock=30,
        image_emoji="🔌",
        short_description="TripPlug travel adapter for Austin trip.",
        tags=["travel", "adapter"],
    )
    shop.orders[ADAPTER_ORDER] = Order(
        id=ADAPTER_ORDER,
        user_id="u_alice",
        placed_at="2026-05-18T11:00:00Z",
        items=[
            OrderItem(
                id="ln_mp118_adapter",
                product_id=ADAPTER_SKU,
                product_name="Universal Travel Adapter",
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=24.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=24.00,
        discount=0.0,
        tax=2.04,
        shipping=5.99,
        total=32.03,
        promo_code=None,
        payment_id="pay_visa",
        status="shipped",
        shipments=[
            Shipment(
                id="sh_mp118",
                carrier="USPS",
                tracking_number="9400MP118ADP",
                item_ids=["ln_mp118_adapter"],
                status="shipped",
                estimated_delivery="Friday May 23, 2026",
                events=[
                    ShipmentEvent(
                        timestamp="2026-05-19T12:00:00Z",
                        status="shipped",
                        detail=(
                            "Shipped — estimated delivery Friday May 23 "
                            "(after Thursday AA 1420 departure)."
                        ),
                    )
                ],
            )
        ],
    )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.orders.clear()
    food.cart.items.clear()
    food.restaurants["r_mp118_home"] = Restaurant(
        id="r_mp118_home",
        name="Harbor Grill",
        cuisine="American",
        rating=4.5,
        eta_label="7:00 PM",
        delivery_fee=2.99,
        emoji="🍔",
        dishes=[
            Dish(
                id="d_mp118_dinner",
                name="Weeknight Plate",
                price=15.00,
                description="Fine for home nights before/after travel.",
                tags=["dinner"],
                emoji="🍔",
                popular=True,
                eta_label="7:00 PM",
            )
        ],
        delivery_time_min=30,
        delivery_time_max=45,
    )

    market = world.market
    market.products.clear()
    market.products[VM_DISTRACTOR] = MarketProduct(
        id=VM_DISTRACTOR,
        name="Austin Skyline Mug",
        category="home",
        price=18.00,
        emoji="☕",
        description="Distractor souvenir listing — not needed for trip prep.",
        in_stock=True,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp118_ship"] = Email(
        id="em_mp118_ship",
        sender="orders@shopgym.com",
        to=USER_EMAIL,
        subject=f"Shipped: TripPlug Travel Adapter {ADAPTER_ORDER}",
        body=(
            f"Your TripPlug Universal Travel Adapter ({ADAPTER_ORDER}) shipped. "
            "Estimated delivery: Friday May 23 — after your Thursday AA 1420 "
            "Austin flight."
        ),
        received_at="2026-05-19T12:30:00",
        received_label="May 19",
        read=False,
        labels=["orders", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_118_austin_aa1420_trip_prep_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _FLIGHT = re.compile(r"(?ix)(austin|6:40|0640|flight|AA\s*1420)")
    _WED = re.compile(
        r"(?ix)(vendor\s+sync|priya|wednesday|wed\s+(afternoon|meeting)|May\s*20)"
    )
    _FRI = re.compile(
        r"(?ix)(standup|friday|fri\s+meeting|May\s*22|while\s+in\s+Austin|brooklyn\s+office)"
    )
    _LATE = re.compile(
        r"(?ix)(adapter|tripplug|May\s*23|after\s+(you\s+)?(leave|fly|depart)|"
        r"too\s+late|won'?t\s+arrive)"
    )
    _ACTION = re.compile(
        r"(?ix)(cancel(led)?\s+(the\s+)?(order|adapter|shipment)|expedite|pickup|"
        r"change\s+(delivery|address)|buy\s+(another|a\s+new|replacement)\s+adapter|"
        r"airport\s+shop|leave\s+it|reschedule\s+delivery|reorder\s+(the\s+)?adapter|"
        r"replacement\s+adapter|pick\s+one\s+up)"
    )
    _EMAIL = re.compile(
        r"(?ix)(aa\s*1420|austin|adapter|tripplug|vendor|standup|conflict)"
    )

    def _blob(p: Probe) -> str:
        parts = []
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail:
            for msg in (mail.sent or {}).values():
                parts.append(
                    f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
                )
        return "\n".join(parts)

    def _identified_flight(p: Probe) -> bool:
        if _log_has(p, "viewed_event_edit", event_id=FLIGHT_ID) or _log_has(
            p, "viewed_calendar"
        ):
            return True
        return _FLIGHT.search(_blob(p)) is not None

    def _flagged_both(p: Probe) -> bool:
        b = _blob(p)
        return bool(_WED.search(b) and _FRI.search(b))

    def _caught_late(p: Probe) -> bool:
        return bool(_LATE.search(_blob(p))) or _log_has(
            p, "view_order", order_id=ADAPTER_ORDER
        ) or _log_has(p, "view_order_detail", order_id=ADAPTER_ORDER)

    def _corrective(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop:
            o = shop.orders.get(ADAPTER_ORDER)
            if o and getattr(o, "status", "") == "cancelled":
                return True
            init = getattr(p, "initial_world", None)
            init_ids = set((init.shop.orders or {}) if init and init.shop else {})
            for oid, oo in (shop.orders or {}).items():
                if oid in init_ids:
                    continue
                if any(it.product_id == ADAPTER_SKU for it in oo.items):
                    return True
        return bool(_ACTION.search(_blob(p)))

    TRAVEL_DAYS = {THU, FRI, "2026-05-23", "2026-05-24"}

    def _no_food_travel(p: Probe) -> bool:
        if not (_flagged_both(p) or _caught_late(p) or _corrective(p)):
            return False
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return True
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.food.orders or {}) if init and getattr(init, "food", None) else {}
        )
        for oid, o in (food.orders or {}).items():
            if oid in init_ids:
                continue
            sd = getattr(o, "scheduled_delivery", None)
            if sd in TRAVEL_DAYS:
                return False
        return True

    def _emailed(p: Probe) -> bool:
        b = _blob(p)
        if not b.strip():
            return False
        if not _EMAIL.search(b):
            return False
        return _flagged_both(p) and (_caught_late(p) or _corrective(p))

    def _no_action_late(p: Probe) -> bool:
        return _caught_late(p) and not _corrective(p) and len(_blob(p)) > 40

    def _vm_engagement(p: Probe) -> bool:
        mkt = getattr(p.world, "market", None) if p.world else None
        if mkt is None:
            return False
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.market.orders or {})
            if init and getattr(init, "market", None)
            else {}
        )
        for oid in mkt.orders or {}:
            if oid not in init_ids:
                return True
        return any(i.product_id == VM_DISTRACTOR for i in (mkt.cart.items or []))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "identified_flight_window_from_calendar",
                    weight=0.1,
                    check=_identified_flight,
                    required_for_success=True,
                ),
                Milestone(
                    "flagged_both_conflicting_meetings",
                    weight=0.2,
                    check=_flagged_both,
                    required_for_success=True,
                ),
                Milestone(
                    "caught_late_arriving_shipment",
                    weight=0.15,
                    check=_caught_late,
                    required_for_success=True,
                ),
                Milestone(
                    "took_corrective_action_on_shipment",
                    weight=0.15,
                    check=_corrective,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_schedule_food_during_travel",
                    weight=0.15,
                    check=_no_food_travel,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_trip_details",
                    weight=0.25,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "missed_either_calendar_conflict",
                    weight=0.0,
                    check=lambda p: not _flagged_both(p) and len(_blob(p)) > 40,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "no_action_on_late_shipment",
                    weight=0.0,
                    check=_no_action_late,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "unnecessary_valuemart_engagement",
                    weight=0.0,
                    check=_vm_engagement,
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
