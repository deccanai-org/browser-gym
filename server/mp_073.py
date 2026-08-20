"""mp_073 / gymcal_recurring_series_vs_single_override — Xoogle×Xber.

Weekly Design Review noon series; tomorrow's instance overridden to 2pm
("moved for room conflict"). Order lunch ETA matching 2pm, not noon.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_073/gymcal_recurring_series_vs_single_override"
BRIEF_KEY = "mp_073"
BRIEF = "Order lunch for tomorrow's design review like we usually do."

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"  # Thu; tomorrow = Fri May 22

TOMORROW = "2026-05-22"
NEXT_WEEK = "2026-05-29"

INSTANCE_ID = "ev_mp073_design_tomorrow"
SERIES_ID = "ev_mp073_design_series"
TITLE = "Design Review"

SERIES_START, SERIES_END = "12:00", "13:00"
OVERRIDE_START, OVERRIDE_END = "14:00", "15:00"

GOLD_REST = "r_mp073_2pm"
GOLD_DISH = "d_mp073_2pm_lunch"
TRAP_REST = "r_mp073_noon"
TRAP_DISH = "d_mp073_noon_lunch"


def task_mp_073_gymcal_recurring_series_vs_single_override(seed: int) -> "WorldState":
    """Cal×Food: instance time override 2pm vs series noon."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, Restaurant
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
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
            "(not the usual noon). Series resumes next week at noon."
        ),
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
        description="Recurring weekly Design Review (noon).",
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.orders.clear()
    food.restaurants[TRAP_REST] = Restaurant(
        id=TRAP_REST, name="Noon Box Co", cuisine="American", rating=4.6,
        eta_label="12:00 PM", delivery_fee=1.99, emoji="🍱",
        delivery_time_min=20, delivery_time_max=35,
        dishes=[Dish(
            id=TRAP_DISH, name="Usual Noon Lunch Box",
            description="Arrives ~noon — matches the series default time.",
            price=13.50, tags=["lunch"], emoji="🥗", popular=True,
            eta_label="12:00 PM",
        )],
    )
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST, name="Two O'Clock Kitchen", cuisine="American", rating=4.5,
        eta_label="2:00 PM", delivery_fee=2.49, emoji="🍛",
        delivery_time_min=25, delivery_time_max=40,
        dishes=[Dish(
            id=GOLD_DISH, name="Design Review 2pm Plate",
            description="Timed for the moved 2:00 PM Design Review instance.",
            price=14.25, tags=["lunch"], emoji="🍽️", popular=True,
            eta_label="2:00 PM",
        )],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_073_gymcal_recurring_series_vs_single_override,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.food.orders or {}) if init and getattr(init, "food", None) else {})
        return [
            o for oid, o in (food.orders or {}).items()
            if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _checked_instance(p: Probe) -> bool:
        if _log_has(p, "viewed_event_edit", event_id=INSTANCE_ID):
            return True
        return _log_has(p, "viewed_calendar") or "/calendar" in (
            p.active_tab_url or p.url or ""
        )

    def _eta(o) -> str:
        return (getattr(o, "eta_label", "") or "").lower().replace(" ", "")

    def _matches_override(p: Probe) -> bool:
        for o in _new_orders(p):
            eta = _eta(o)
            if "2:00" in eta or "14:00" in eta or getattr(o, "dish_id", "") == GOLD_DISH:
                return True
            if getattr(o, "restaurant_id", "") == GOLD_REST:
                return True
            # dish list on order
            for it in getattr(o, "items", []) or []:
                if getattr(it, "dish_id", "") == GOLD_DISH:
                    return True
        return False

    def _matches_series_default(p: Probe) -> bool:
        for o in _new_orders(p):
            eta = _eta(o)
            if ("12:00" in eta or "noon" in eta) and "2:00" not in eta:
                return True
            if getattr(o, "restaurant_id", "") == TRAP_REST:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_specific_instance_not_series_default", weight=0.5,
                          check=_checked_instance, required_for_success=True),
                Milestone("order_time_matches_instance_override", weight=0.5,
                          check=_matches_override, required_for_success=True),
                Milestone("order_time_matches_series_default_ignoring_override", weight=0.0,
                          check=_matches_series_default, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
