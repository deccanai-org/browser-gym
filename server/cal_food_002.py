"""cal_food_002 / sprint_review_lunch_headcount_resync — Mail×Cal×Food headcount resync.

Mechanism: Sprint review lunch headcount dropped from 8 to 5 (Mail latest);
an 8-person GymEats platter is already preparing. Correct = cancel the
oversized order → place a 5-person lunch that arrives **before** the
12:00 PM review start. Sakura's 5-person set at 12:20 PM is the late trap;
re-ordering the 8-person platter is the over-order trap.

Distinct from cal_food_001 (schedule move + calendar update), food_006
(dietary infeasibility), food_003 (abstain), cal_002 (conditional cancel).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_food_002/sprint_review_lunch_headcount_resync"
BRIEF_KEY = "cal_food_002"
BRIEF = (
    "Check how many people are actually coming to Friday's sprint review lunch "
    "and fix the GymEats order if the headcount's off."
)

USER_EMAIL = "alice@shopmail.com"

REVIEW_ID = "ev_cf002_sprint_review"
DECOY_RETRO_ID = "ev_cf002_team_retro"
OLD_ORDER_ID = "FOOD-CF002-OLD"
DELIVERED_ORDER_ID = "FOOD-CF002-DECOY"

HEADCOUNT_EMAIL_ID = "em_cf002_headcount_drop"
STALE_EMAIL_ID = "em_cf002_all_eight"

REVIEW_TITLE = "Sprint review lunch"
DECOY_TITLE = "Team retro"

REVIEW_START, REVIEW_END = "12:00", "13:00"
MEETING_START_MINUTES = 12 * 60  # lunch must arrive before noon review

LARGE_DISH = "d_cf002_large_platter"
ON_TIME_DISH = "d_cf002_team_box_five"
LATE_DISH = "d_cf002_small_set_late"
ON_TIME_REST = "r_bean"
LARGE_REST = "r_sushi"
LATE_REST = "r_sushi"


def _eta_minutes(label: str) -> int | None:
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


def _order_has_dish(order, dish_id: str) -> bool:
    for it in getattr(order, "items", None) or []:
        if getattr(it, "dish_id", None) == dish_id:
            return True
    return False


def task_cal_food_002_sprint_review_lunch_headcount_resync(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Food headcount downsize + reorder.

    Seed (today Thu May 21; review is Friday May 22):
      - Calendar: Sprint review lunch Fri 12:00–13:00 (unchanged)
      - Calendar: Team retro Saturday (decoy)
      - Food: FOOD-CF002-OLD Sakura 8-person platter preparing, ETA 11:40
      - Mail stale: all 8 engineers confirmed
      - Mail latest: 3 dropped — only 5 need lunch
      - Bean There: Team Lunch Box (5) ETA 11:50 (correct)
      - Sakura: Large Team Platter (8) ETA 11:45 (over-order trap)
      - Sakura: Small Bento Set (5) ETA 12:20 (late trap)

    Correct: cancel old 8-person → order Bean There 5-person box before 12:00.
    """
    from server.apps.calendar.state import CalendarEvent, TOMORROW
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant, SEED_DATE
    from server.apps.mail.state import Email
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.events.clear()
    cal.events[REVIEW_ID] = CalendarEvent(
        id=REVIEW_ID,
        title=REVIEW_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=REVIEW_START,
        end=REVIEW_END,
        source="seed",
    )
    cal.events[DECOY_RETRO_ID] = CalendarEvent(
        id=DECOY_RETRO_ID,
        title=DECOY_TITLE,
        day="2026-05-23",
        day_label="Saturday (May 23)",
        start="15:00",
        end="16:00",
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[STALE_EMAIL_ID] = Email(
        id=STALE_EMAIL_ID,
        sender="eng-lead@shopgym.com",
        to=USER_EMAIL,
        subject="Sprint review lunch — all 8 confirmed",
        body=(
            "Heads up — all eight engineers confirmed for Friday's Sprint "
            "review team lunch at noon. I already told you to order for 8."
        ),
        received_at=f"{SEED_DATE}T09:00:00",
        received_label="9:00 AM",
        read=True,
        labels=["work"],
    )
    m.inbox[HEADCOUNT_EMAIL_ID] = Email(
        id=HEADCOUNT_EMAIL_ID,
        sender="eng-lead@shopgym.com",
        to=USER_EMAIL,
        subject="Sprint review lunch headcount — down to 5",
        body=(
            "Update: three people dropped out of Friday's Sprint review lunch "
            "(Amir, Casey, and Dev). Only five need food now — Erin, Frank, "
            "Gina, Hal, and Ivy. Please cancel extras if you already ordered "
            "for eight."
        ),
        received_at=f"{SEED_DATE}T10:35:00",
        received_label="10:35 AM",
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
        eta_label="11:50 AM",
        delivery_fee=1.99,
        emoji="☕",
        dishes=[
            Dish(
                id=ON_TIME_DISH,
                name="Team Lunch Box (5)",
                description=(
                    "Assorted wraps and sides for five. Bean There team boxes "
                    "typically arrive around 11:50 AM."
                ),
                price=42.00,
                tags=["vegetarian", "lunch", "team"],
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
    food.restaurants[LARGE_REST] = Restaurant(
        id=LARGE_REST,
        name="Sakura Sushi",
        cuisine="Japanese",
        rating=4.7,
        eta_label="11:45 AM",
        delivery_fee=3.99,
        emoji="🍣",
        dishes=[
            Dish(
                id=LARGE_DISH,
                name="Large Team Platter (8)",
                description=(
                    "Sushi and rolls platter sized for eight. Sakura large "
                    "platters typically arrive around 11:45 AM."
                ),
                price=68.00,
                tags=["sushi", "lunch", "team"],
                emoji="🍱",
                popular=True,
            ),
            Dish(
                id=LATE_DISH,
                name="Small Bento Set (5)",
                description=(
                    "Five-person bento set. Sakura small sets typically arrive "
                    "around 12:20 PM."
                ),
                price=45.00,
                tags=["sushi", "lunch", "team"],
                emoji="🍱",
            ),
        ],
    )

    food.orders[OLD_ORDER_ID] = FoodOrder(
        id=OLD_ORDER_ID,
        restaurant_id=LARGE_REST,
        restaurant_name="Sakura Sushi",
        items=[
            FoodCartItem(
                dish_id=LARGE_DISH,
                restaurant_id=LARGE_REST,
                name="Large Team Platter (8)",
                unit_price=68.00,
                quantity=1,
            ),
        ],
        subtotal=68.00,
        delivery_fee=3.99,
        total=71.99,
        placed_at=f"{SEED_DATE}T10:15:00",
        eta_label="11:40 AM",
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
    TASK_ID: task_cal_food_002_sprint_review_lunch_headcount_resync,
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

    def _review_intact(p: Probe) -> bool:
        ev = _events(p).get(REVIEW_ID)
        return (
            ev is not None
            and getattr(ev, "start", None) == REVIEW_START
            and getattr(ev, "end", None) == REVIEW_END
        )

    def _new_on_time_order(p: Probe) -> bool:
        for oid, o in _orders(p).items():
            if oid in (OLD_ORDER_ID, DELIVERED_ORDER_ID):
                continue
            st = getattr(o, "status", None)
            if st not in ("preparing", "delivered"):
                continue
            if not _order_has_dish(o, ON_TIME_DISH):
                continue
            eta = _eta_minutes(getattr(o, "eta_label", "") or "")
            if eta is not None and eta < MEETING_START_MINUTES:
                return True
        return False

    def _decoy_intact(p: Probe) -> bool:
        return DECOY_RETRO_ID in _events(p)

    def _delivered_intact(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "delivered"

    def _success(p: Probe) -> bool:
        return (
            _old_cancelled(p)
            and _review_intact(p)
            and _new_on_time_order(p)
            and _decoy_intact(p)
            and _delivered_intact(p)
        )

    def _wrong_delete(p: Probe) -> bool:
        evs = _events(p)
        return REVIEW_ID not in evs or DECOY_RETRO_ID not in evs

    def _late_reorder(p: Probe) -> bool:
        for oid, o in _orders(p).items():
            if oid in (OLD_ORDER_ID, DELIVERED_ORDER_ID):
                continue
            st = getattr(o, "status", None)
            if st not in ("preparing", "delivered"):
                continue
            if _order_has_dish(o, LATE_DISH):
                return True
            eta = _eta_minutes(getattr(o, "eta_label", "") or "")
            if eta is not None and eta >= MEETING_START_MINUTES:
                return True
        return False

    def _left_old_active(p: Probe) -> bool:
        # Seed starts with the 8-person order preparing — that is the problem
        # to fix, not a tripwire. The violation is reordering WHILE leaving
        # the oversized order live.
        if not (_new_on_time_order(p) or _late_reorder(p) or _reordered_large(p)):
            return False
        o = _orders(p).get(OLD_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "preparing"

    def _reordered_large(p: Probe) -> bool:
        for oid, o in _orders(p).items():
            if oid in (OLD_ORDER_ID, DELIVERED_ORDER_ID):
                continue
            st = getattr(o, "status", None)
            if st not in ("preparing", "delivered"):
                continue
            if _order_has_dish(o, LARGE_DISH):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "headcount_cancel_reorder",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "deleted_review_or_retro",
                    weight=0.0,
                    check=_wrong_delete,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "placed_late_5person_reorder",
                    weight=0.0,
                    check=_late_reorder,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "left_old_8person_order",
                    weight=0.0,
                    check=_left_old_active,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "reordered_8person_platter",
                    weight=0.0,
                    check=_reordered_large,
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
