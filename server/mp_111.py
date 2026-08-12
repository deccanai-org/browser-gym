"""mp_111 / design_review_maya_override_lunch_email — GymCal×GymEats×ShopMail.

Redesign of Eligible e20 mp_073. Weekly Design Review with Maya is usually noon;
tomorrow's instance (Fri May 22) is overridden to 2:00 PM. Gold = order lunch
timed for 2pm (not noon series default) and email Alice the details.
mp_073 left untouched.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_111/design_review_maya_override_lunch_email"
BRIEF_KEY = "mp_111"
BRIEF = (
    "Order lunch for tomorrow's Design Review with Maya like we usually do, "
    "and email me the details."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"

TOMORROW = "2026-05-22"
NEXT_WEEK = "2026-05-29"
PAST = "2026-05-15"

INSTANCE_ID = "ev_mp111_design_tomorrow"
SERIES_ID = "ev_mp111_design_series"
PAST_ID = "ev_mp111_design_past"
TITLE = "Design Review with Maya"

SERIES_START, SERIES_END = "12:00", "13:00"
OVERRIDE_START, OVERRIDE_END = "14:00", "15:00"

GOLD_REST = "r_mp111_2pm"
GOLD_DISH = "d_mp111_2pm_lunch"
GOLD_REST_NAME = "Two O'Clock Kitchen"
TRAP_REST = "r_mp111_noon"
TRAP_DISH = "d_mp111_noon_lunch"
TRAP_REST_NAME = "Noon Box Co"
HIST_ORDER = "FOOD-MP111-MAY15"


def task_mp_111_design_review_maya_override_lunch_email(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[PAST_ID] = CalendarEvent(
        id=PAST_ID,
        title=TITLE,
        day=PAST,
        day_label="Fri May 15",
        start=SERIES_START,
        end=SERIES_END,
        source="seed",
        recurring="none",
        description="Weekly Design Review with Maya (noon). Lunch ordered for the room.",
        status="confirmed",
    )
    cal.events[INSTANCE_ID] = CalendarEvent(
        id=INSTANCE_ID,
        title=TITLE,
        day=TOMORROW,
        day_label="Fri May 22",
        start=OVERRIDE_START,
        end=OVERRIDE_END,
        source="seed",
        recurring="none",
        description=(
            "Moved for room conflict — this instance only at 2:00 PM "
            "(not the usual noon). Series resumes next Friday at noon."
        ),
        status="confirmed",
    )
    cal.events[SERIES_ID] = CalendarEvent(
        id=SERIES_ID,
        title=TITLE,
        day=NEXT_WEEK,
        day_label="Fri May 29",
        start=SERIES_START,
        end=SERIES_END,
        source="seed",
        recurring="weekly",
        description="Recurring weekly Design Review with Maya (noon).",
        status="confirmed",
    )
    cal.events["ev_mp111_noise"] = CalendarEvent(
        id="ev_mp111_noise",
        title="1:1 with Priya",
        day="2026-05-23",
        day_label="Sat May 23",
        start="11:00",
        end="11:30",
        source="seed",
        status="confirmed",
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.orders.clear()
    food.restaurants[TRAP_REST] = Restaurant(
        id=TRAP_REST,
        name=TRAP_REST_NAME,
        cuisine="American",
        rating=4.6,
        eta_label="12:00 PM",
        delivery_fee=1.99,
        emoji="🍱",
        delivery_time_min=20,
        delivery_time_max=35,
        dishes=[
            Dish(
                id=TRAP_DISH,
                name="Usual Noon Lunch Box",
                description="Arrives ~noon — matches the series default time.",
                price=13.50,
                tags=["lunch"],
                emoji="🥗",
                popular=True,
                eta_label="12:00 PM",
            )
        ],
    )
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name=GOLD_REST_NAME,
        cuisine="American",
        rating=4.5,
        eta_label="2:00 PM",
        delivery_fee=2.49,
        emoji="🍛",
        delivery_time_min=25,
        delivery_time_max=40,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name="Design Review 2pm Plate",
                description="Timed for a 2:00 PM Design Review instance.",
                price=14.25,
                tags=["lunch"],
                emoji="🍽️",
                popular=True,
                eta_label="2:00 PM",
            )
        ],
    )
    food.orders[HIST_ORDER] = FoodOrder(
        id=HIST_ORDER,
        restaurant_id=TRAP_REST,
        restaurant_name=TRAP_REST_NAME,
        items=[
            FoodCartItem(
                dish_id=TRAP_DISH,
                restaurant_id=TRAP_REST,
                name="Usual Noon Lunch Box",
                unit_price=13.50,
                quantity=3,
            )
        ],
        subtotal=40.50,
        delivery_fee=1.99,
        total=42.49,
        placed_at=f"{PAST}T11:20:00",
        eta_label="12:00 PM",
        status="delivered",
        delivery_note="Design Review with Maya — conference room C",
        scheduled_delivery=PAST,
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_111_design_review_maya_override_lunch_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


_EMAIL_OK = re.compile(
    r"(?ix)(2\s*:?\s*00|14:00|two\s*o.?clock|override|moved).{0,80}"
    r"(design\s+review|maya|lunch)|"
    r"(design\s+review|maya|lunch).{0,80}(2\s*:?\s*00|14:00|two\s*o.?clock)"
)


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.food.orders or {}) if init and getattr(init, "food", None) else {}
        )
        return [
            o
            for oid, o in (food.orders or {}).items()
            if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _checked_instance(p: Probe) -> bool:
        if _log_has(p, "viewed_event_edit", event_id=INSTANCE_ID):
            return True
        return _log_has(p, "viewed_calendar") or "/calendar" in (
            p.active_tab_url or p.url or ""
        )

    # Compact ETA for matching. "12:00 PM" → "12:00pm".
    # Do NOT use naive `"2:00" in eta` — that is a substring of "12:00pm".
    _OVERRIDE_ETA = re.compile(r"(?<!\d)(?:2:00|2pm|14:00)")
    _NOON_ETA = re.compile(r"(?:12:00|12pm|noon)")

    def _eta(o) -> str:
        return (getattr(o, "eta_label", "") or "").lower().replace(" ", "")

    def _matches_override(p: Probe) -> bool:
        """Genuine 2pm instance match — not date-only, not 12:00-as-2:00."""
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == GOLD_REST:
                return True
            for it in getattr(o, "items", []) or []:
                if getattr(it, "dish_id", "") == GOLD_DISH:
                    return True
            eta = _eta(o)
            if _OVERRIDE_ETA.search(eta) and not _NOON_ETA.search(eta):
                return True
        return False

    def _matches_series_default(p: Probe) -> bool:
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == TRAP_REST:
                return True
            eta = _eta(o)
            if _NOON_ETA.search(eta) and not _OVERRIDE_ETA.search(eta):
                return True
        return False

    def _emailed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _EMAIL_OK.search(text) and _matches_override(p):
                return True
            if _matches_override(p) and (
                "two o'clock" in text.lower()
                or "2:00" in text
                or GOLD_REST_NAME.lower() in text.lower()
            ):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_specific_instance_not_series_default",
                    weight=0.3,
                    check=_checked_instance,
                    required_for_success=True,
                ),
                Milestone(
                    "order_time_matches_instance_override",
                    weight=0.4,
                    check=_matches_override,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_lunch_details",
                    weight=0.3,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "order_time_matches_series_default_ignoring_override",
                    weight=0.0,
                    check=_matches_series_default,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
