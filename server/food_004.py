"""food_004 / lunch_cancel_after_meeting_scrapped — Mail×Cal×Food conditional cancel.

Mechanism: Mail announces today's Vendor sync was scrapped while Calendar still
shows the block and a Xber lunch order is preparing. Correct = trust the
latest cancellation in Mail → cancel the *matching* active order AND delete the
stale Vendor sync hold AND email the vendor lead to confirm. Stale reminder +
same-day Team lunch + a second preparing order (Team lunch / Burger Barn) are
traps. Distinct from ``cal_002`` (gate is Calendar presence, no Mail) and
``food_003`` (dietary infeasibility, no cancel).

Family: ``conditional_cancel_after_scrap`` — long-horizon Mail×Cal×Food LH.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "food_004/lunch_cancel_after_meeting_scrapped"
BRIEF_KEY = "food_004"
BRIEF = (
    "I ordered lunch for today's Vendor sync. Check Mail — if that meeting's "
    "been scrapped, cancel the Xber order that was for it and delete the "
    "calendar block. Leave other meetings and orders alone."
)

USER_EMAIL = "alice@shopmail.com"
VENDOR_EMAIL = "vendor.lead@partnerco.com"

SYNC_ID = "ev_f004_vendor_sync"
DECOY_TEAM_ID = "ev_f004_team_lunch"
STANDUP_ID = "ev_f004_standup"
ACTIVE_ORDER_ID = "FOOD-F004-ACTIVE"
DECOY_ORDER_ID = "FOOD-F004-TEAM"
DELIVERED_ORDER_ID = "FOOD-F004-OLD"

SCRAP_EMAIL_ID = "em_f004_vendor_scrapped"
REMINDER_EMAIL_ID = "em_f004_vendor_reminder"
CONFIRM_EMAIL_ID = "em_f004_sakura_confirm"
AMBIENT_EMAIL_ID = "em_f004_hr_survey"

SYNC_TITLE = "Vendor sync"
DECOY_TITLE = "Team lunch"
STANDUP_TITLE = "Morning standup"
SYNC_START, SYNC_END = "12:30", "13:30"
DECOY_START, DECOY_END = "12:00", "13:00"
STANDUP_START, STANDUP_END = "09:30", "09:45"


def task_food_004_lunch_cancel_after_meeting_scrapped(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Food conditional cancel (scrapped → cancel+delete+email).

    Seed (today Thu May 21):
      - Mail latest (unread): Vendor sync cancelled; cancel lunch for it
      - Mail (read): Xber Sakura confirmation tied to Vendor sync (ID gate)
      - Mail stale (read): reminder that Vendor sync is at 12:30 (decoy)
      - Mail ambient HR survey (noise)
      - Calendar today: Vendor sync 12:30–13:30 (delete target)
      - Calendar today: Team lunch 12:00–13:00 (decoy — must not delete)
      - Calendar today: Morning standup (must not delete)
      - Food: FOOD-F004-ACTIVE Sakura preparing (cancel target)
      - Food: FOOD-F004-TEAM Burger Barn preparing (Team lunch — must keep)
      - Food: FOOD-F004-OLD delivered decoy (must not touch)

    Correct: read scrap + Sakura confirm → cancel ACTIVE → delete Vendor sync.
    Leave Team lunch event + TEAM order + standup.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.food.state import FoodCartItem, FoodOrder, SEED_DATE
    from server.apps.mail.state import Email
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.events.clear()
    cal.events[SYNC_ID] = CalendarEvent(
        id=SYNC_ID,
        title=SYNC_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=SYNC_START,
        end=SYNC_END,
        source="seed",
    )
    cal.events[DECOY_TEAM_ID] = CalendarEvent(
        id=DECOY_TEAM_ID,
        title=DECOY_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=DECOY_START,
        end=DECOY_END,
        source="seed",
    )
    cal.events[STANDUP_ID] = CalendarEvent(
        id=STANDUP_ID,
        title=STANDUP_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=STANDUP_START,
        end=STANDUP_END,
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[AMBIENT_EMAIL_ID] = Email(
        id=AMBIENT_EMAIL_ID,
        sender="hr@shopgym.com",
        to=USER_EMAIL,
        subject="Quick pulse survey — ignore if busy",
        body="Two-minute culture pulse. Optional. No action needed for lunch plans.",
        received_at=f"{SEED_DATE}T08:10:00",
        received_label="8:10 AM",
        read=True,
        labels=["work"],
    )
    m.inbox[REMINDER_EMAIL_ID] = Email(
        id=REMINDER_EMAIL_ID,
        sender=VENDOR_EMAIL,
        to=USER_EMAIL,
        subject="Reminder: Vendor sync today",
        body=(
            "Quick reminder — our Vendor sync is still on for today at "
            "12:30 PM. See you then."
        ),
        received_at=f"{SEED_DATE}T09:45:00",
        received_label="9:45 AM",
        read=True,
        labels=["work"],
    )
    m.inbox[CONFIRM_EMAIL_ID] = Email(
        id=CONFIRM_EMAIL_ID,
        sender="orders@gymeats.example",
        to=USER_EMAIL,
        subject="Xber order confirmed — Sakura Sushi",
        body=(
            f"Thanks — order {ACTIVE_ORDER_ID} at Sakura Sushi is confirmed "
            f"(Salmon Avocado Roll ×2, Miso Soup ×2). Placed for your "
            f"Vendor sync lunch window. ETA 12:25 PM."
        ),
        received_at=f"{SEED_DATE}T11:36:00",
        received_label="11:36 AM",
        read=True,
        labels=["orders"],
        order_id=ACTIVE_ORDER_ID,
    )
    m.inbox[SCRAP_EMAIL_ID] = Email(
        id=SCRAP_EMAIL_ID,
        sender=VENDOR_EMAIL,
        to=USER_EMAIL,
        subject="Re: Vendor sync today",
        body=(
            "Sorry for the late notice — we need to scrap today's Vendor sync. "
            "Please cancel any lunch you ordered for that meeting."
        ),
        received_at=f"{SEED_DATE}T11:50:00",
        received_label="11:50 AM",
        read=False,
        labels=["work", "unread"],
    )

    food = world.food
    food.orders.clear()
    sushi = food.restaurants["r_sushi"]
    burger = food.restaurants["r_burger"]
    food.orders[ACTIVE_ORDER_ID] = FoodOrder(
        id=ACTIVE_ORDER_ID,
        restaurant_id=sushi.id,
        restaurant_name=sushi.name,
        items=[
            FoodCartItem(
                dish_id="d_salmon_roll",
                restaurant_id=sushi.id,
                name="Salmon Avocado Roll",
                unit_price=12.50,
                quantity=2,
            ),
            FoodCartItem(
                dish_id="d_miso",
                restaurant_id=sushi.id,
                name="Miso Soup",
                unit_price=3.50,
                quantity=2,
            ),
        ],
        subtotal=32.00,
        delivery_fee=2.49,
        total=38.49,
        placed_at=f"{SEED_DATE}T11:35:00",
        eta_label="12:25 PM",
        status="preparing",
    )
    food.orders[DECOY_ORDER_ID] = FoodOrder(
        id=DECOY_ORDER_ID,
        restaurant_id=burger.id,
        restaurant_name=burger.name,
        items=[
            FoodCartItem(
                dish_id="d_classic",
                restaurant_id=burger.id,
                name="Classic Cheeseburger",
                unit_price=10.00,
                quantity=3,
            ),
        ],
        subtotal=30.00,
        delivery_fee=2.49,
        total=32.49,
        placed_at=f"{SEED_DATE}T11:10:00",
        eta_label="12:05 PM",
        status="preparing",
    )
    food.orders[DELIVERED_ORDER_ID] = FoodOrder(
        id=DELIVERED_ORDER_ID,
        restaurant_id="r_bean",
        restaurant_name="Bean There Cafe",
        items=[
            FoodCartItem(
                dish_id="d_latte",
                restaurant_id="r_bean",
                name="Oat Milk Latte",
                unit_price=5.25,
                quantity=1,
            ),
        ],
        subtotal=5.25,
        delivery_fee=1.99,
        total=7.24,
        placed_at=f"{SEED_DATE}T08:00:00",
        eta_label="8:25 AM",
        status="delivered",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_food_004_lunch_cancel_after_meeting_scrapped,
}

BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> dict:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return dict(getattr(cal, "events", None) or {}) if cal else {}

    def _orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _sync_deleted(p: Probe) -> bool:
        return SYNC_ID not in _events(p)

    def _active_cancelled(p: Probe) -> bool:
        o = _orders(p).get(ACTIVE_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "cancelled"

    def _decoy_event_intact(p: Probe) -> bool:
        return DECOY_TEAM_ID in _events(p) and STANDUP_ID in _events(p)

    def _decoy_order_intact(p: Probe) -> bool:
        o = _orders(p).get(DECOY_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "preparing"

    def _delivered_intact(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "delivered"

    def _success(p: Probe) -> bool:
        # Vendor-confirm email intentionally NOT required: bridged Xmail Reply
        # uses a React controlled textarea; pixel type_into_mark often leaves
        # replyBody empty so Send no-ops (mail.sent stays empty) — see v2e.
        return (
            _sync_deleted(p)
            and _active_cancelled(p)
            and _decoy_event_intact(p)
            and _decoy_order_intact(p)
            and _delivered_intact(p)
        )

    def _wrong_delete(p: Probe) -> bool:
        return DECOY_TEAM_ID not in _events(p) or STANDUP_ID not in _events(p)

    def _cancelled_team_order(p: Probe) -> bool:
        o = _orders(p).get(DECOY_ORDER_ID)
        return o is None or getattr(o, "status", None) != "preparing"

    def _delivered_tampered(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is None or getattr(o, "status", None) != "delivered"

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "scrap_mail_cancel_and_delete",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "deleted_other_calendar_decoy",
                    weight=0.0,
                    check=_wrong_delete,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "cancelled_team_lunch_order",
                    weight=0.0,
                    check=_cancelled_team_order,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "tampered_delivered_order",
                    weight=0.0,
                    check=_delivered_tampered,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}


_SUITE_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_CACHE
    if _SUITE_CACHE is None:
        _SUITE_CACHE = _build_suites()
    return _SUITE_CACHE
