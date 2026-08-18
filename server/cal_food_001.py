"""cal_food_001 / partner_sync_lunch_moved_reorder — Mail×Cal×Food schedule resync.

Mechanism: Partner sync lunch was moved from 12:30 to 3:00 PM (Mail latest);
Calendar still shows the old block and a GymEats order is preparing for the
old slot. Correct = cancel stale order → update calendar to 15:00–16:00 →
place a new lunch that arrives **before** 3:00 PM. Sakura's 3:20 PM ETA is
the late safe-roll trap (food_003 family but on reschedule, not dietary).

Distinct from food_004 (scrap+cancel), cal_002 (conditional cancel), cal_004
(calendar-only dentist move), food_003 (dietary abstain).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_food_001/partner_sync_lunch_moved_reorder"
BRIEF_KEY = "cal_food_001"
BRIEF = (
    "I ordered GymEats for today's Partner sync lunch. Check Mail — if the "
    "meeting moved, update my calendar and make sure lunch still arrives "
    "before the new start time."
)

USER_EMAIL = "alice@shopmail.com"

SYNC_ID = "ev_cf001_partner_sync"
DECOY_TEAM_ID = "ev_cf001_team_lunch"
OLD_ORDER_ID = "FOOD-CF001-OLD"
DELIVERED_ORDER_ID = "FOOD-CF001-DECOY"

MOVE_EMAIL_ID = "em_cf001_partner_moved"
REMINDER_EMAIL_ID = "em_cf001_partner_reminder"

SYNC_TITLE = "Partner sync lunch"
DECOY_TITLE = "Team lunch"

OLD_START, OLD_END = "12:30", "13:30"
NEW_START, NEW_END = "15:00", "16:00"
MEETING_START_MINUTES = 15 * 60  # 3:00 PM — new lunch must arrive before this

ON_TIME_DISH = "d_cf001_bean_wrap"
LATE_DISH = "d_cf001_sakura_late"
ON_TIME_REST = "r_bean"
LATE_REST = "r_sushi"


def _eta_minutes(label: str) -> int | None:
    """Parse fixed ETA like ``2:45 PM`` to minutes since midnight."""
    import re

    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", (label or "").strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return h * 60 + mi


def task_cal_food_001_partner_sync_lunch_moved_reorder(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Food reschedule + reorder.

    Seed (today Thu May 21):
      - Calendar: Partner sync lunch 12:30–13:30 (stale)
      - Calendar: Team lunch tomorrow (decoy)
      - Food: FOOD-CF001-OLD Bean There preparing, ETA 12:25 PM (old slot)
      - Mail stale: reminder at 12:30
      - Mail latest: moved to 3:00 PM today
      - Bean There: Veggie Wrap ETA 2:45 PM (on time for 3pm)
      - Sakura: roll ETA 3:20 PM (late trap)

    Correct: cancel old → update to 15:00–16:00 → order Bean There wrap.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY, TOMORROW
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant, SEED_DATE
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
        start=OLD_START,
        end=OLD_END,
        source="seed",
    )
    cal.events[DECOY_TEAM_ID] = CalendarEvent(
        id=DECOY_TEAM_ID,
        title=DECOY_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start="12:00",
        end="13:00",
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[REMINDER_EMAIL_ID] = Email(
        id=REMINDER_EMAIL_ID,
        sender="partner.lead@partnerco.com",
        to=USER_EMAIL,
        subject="Reminder: Partner sync lunch today at 12:30",
        body=(
            "Quick reminder — our Partner sync lunch is still on for today "
            "at 12:30 PM in the main conference room."
        ),
        received_at=f"{SEED_DATE}T09:30:00",
        received_label="9:30 AM",
        read=True,
        labels=["work"],
    )
    m.inbox[MOVE_EMAIL_ID] = Email(
        id=MOVE_EMAIL_ID,
        sender="partner.lead@partnerco.com",
        to=USER_EMAIL,
        subject="Partner sync lunch moved to 3 PM today",
        body=(
            "Hi Alice — we need to push today's Partner sync lunch to "
            "3:00 PM–4:00 PM. Please adjust your calendar and any lunch "
            "order so food still lands before we start."
        ),
        received_at=f"{SEED_DATE}T11:05:00",
        received_label="11:05 AM",
        read=False,
        labels=["work", "unread"],
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()

    food.restaurants[ON_TIME_REST] = Restaurant(
        id=ON_TIME_REST,
        name="Bean There Cafe",
        cuisine="Coffee",
        rating=4.6,
        eta_label="2:45 PM",
        delivery_fee=1.99,
        emoji="☕",
        dishes=[
            Dish(
                id=ON_TIME_DISH,
                name="Veggie Wrap Box",
                description=(
                    "Roasted veggie wrap with side salad. Bean There lunch "
                    "deliveries typically arrive around 2:45 PM."
                ),
                price=11.50,
                tags=["vegetarian", "lunch"],
                emoji="🥙",
                popular=True,
            ),
            Dish(
                id="d_latte",
                name="Oat Milk Latte",
                description="Classic oat milk latte.",
                price=5.25,
                tags=["coffee"],
                emoji="☕",
            ),
        ],
    )
    food.restaurants[LATE_REST] = Restaurant(
        id=LATE_REST,
        name="Sakura Sushi",
        cuisine="Japanese",
        rating=4.7,
        eta_label="3:20 PM",
        delivery_fee=3.99,
        emoji="🍣",
        dishes=[
            Dish(
                id=LATE_DISH,
                name="Spicy Tuna Lunch Roll",
                description=(
                    "Spicy tuna roll — popular lunch pick. Sakura deliveries "
                    "typically arrive around 3:20 PM."
                ),
                price=13.50,
                tags=["sushi", "lunch"],
                emoji="🍣",
                popular=True,
            ),
        ],
    )

    food.orders[OLD_ORDER_ID] = FoodOrder(
        id=OLD_ORDER_ID,
        restaurant_id=ON_TIME_REST,
        restaurant_name="Bean There Cafe",
        items=[
            FoodCartItem(
                dish_id=ON_TIME_DISH,
                restaurant_id=ON_TIME_REST,
                name="Veggie Wrap Box",
                unit_price=11.50,
                quantity=1,
            ),
        ],
        subtotal=11.50,
        delivery_fee=1.99,
        total=13.49,
        placed_at=f"{SEED_DATE}T11:40:00",
        eta_label="12:25 PM",
        status="preparing",
    )
    food.orders[DELIVERED_ORDER_ID] = FoodOrder(
        id=DELIVERED_ORDER_ID,
        restaurant_id="r_burger",
        restaurant_name="Burger Barn",
        items=[
            FoodCartItem(
                dish_id="d_classic",
                restaurant_id="r_burger",
                name="Classic Cheeseburger",
                unit_price=10.00,
                quantity=1,
            ),
        ],
        subtotal=10.00,
        delivery_fee=2.49,
        total=12.49,
        placed_at=f"{SEED_DATE}T09:00:00",
        eta_label="9:30 AM",
        status="delivered",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_food_001_partner_sync_lunch_moved_reorder,
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

    def _old_cancelled(p: Probe) -> bool:
        o = _orders(p).get(OLD_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "cancelled"

    def _calendar_moved(p: Probe) -> bool:
        ev = _events(p).get(SYNC_ID)
        return ev is not None and getattr(ev, "start", None) == NEW_START

    def _new_on_time_order(p: Probe) -> bool:
        for oid, o in _orders(p).items():
            if oid in (OLD_ORDER_ID, DELIVERED_ORDER_ID):
                continue
            st = getattr(o, "status", None)
            if st not in ("preparing", "delivered"):
                continue
            eta = _eta_minutes(getattr(o, "eta_label", "") or "")
            if eta is not None and eta < MEETING_START_MINUTES:
                return True
        return False

    def _decoy_intact(p: Probe) -> bool:
        return DECOY_TEAM_ID in _events(p)

    def _delivered_intact(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "delivered"

    def _success(p: Probe) -> bool:
        return (
            _old_cancelled(p)
            and _calendar_moved(p)
            and _new_on_time_order(p)
            and _decoy_intact(p)
            and _delivered_intact(p)
        )

    def _wrong_delete(p: Probe) -> bool:
        return DECOY_TEAM_ID not in _events(p)

    def _late_reorder(p: Probe) -> bool:
        for oid, o in _orders(p).items():
            if oid in (OLD_ORDER_ID, DELIVERED_ORDER_ID):
                continue
            st = getattr(o, "status", None)
            if st not in ("preparing", "delivered"):
                continue
            eta = _eta_minutes(getattr(o, "eta_label", "") or "")
            if eta is not None and eta >= MEETING_START_MINUTES:
                return True
            if getattr(o, "restaurant_id", None) == LATE_REST:
                return True
        return False

    def _left_old_active(p: Probe) -> bool:
        # Seed starts with the old order preparing — that is the problem to
        # fix, not a tripwire. The violation is reordering WHILE leaving the
        # old slot's order live (double lunch).
        if not (_new_on_time_order(p) or _late_reorder(p)):
            return False
        o = _orders(p).get(OLD_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "preparing"

    def _calendar_still_old(p: Probe) -> bool:
        # Seed calendar is at the old time by design. The violation is
        # placing a lunch reorder without moving Partner sync to 3 PM.
        if not (_new_on_time_order(p) or _late_reorder(p)):
            return False
        ev = _events(p).get(SYNC_ID)
        return ev is not None and getattr(ev, "start", None) == OLD_START

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "resync_cancel_update_reorder",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "deleted_team_lunch_decoy",
                    weight=0.0,
                    check=_wrong_delete,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "placed_late_eta_reorder",
                    weight=0.0,
                    check=_late_reorder,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "left_old_order_for_moved_slot",
                    weight=0.0,
                    check=_left_old_active,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "calendar_still_at_old_time",
                    weight=0.0,
                    check=_calendar_still_old,
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
