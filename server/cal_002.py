"""cal_002 / conditional_lunch_hold_cancel — Calendar×Food conditional cancel.

Mechanism: if today's Client lunch hold is still on Calendar, cancel the active
GymEats preparing order AND delete the hold. If the hold is already gone, leave
the food order alone (mp_019-style gate on Calendar).

Hub map (bridged): Calendar → google_calendar_mock; Food → uber_eats_mock.
Prefer week/month + edit→delete; avoid day-view / grid click-create.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_002/conditional_lunch_hold_cancel"
BRIEF_KEY = "cal_002"
BRIEF = (
    "My GymEats lunch is taking forever. If I still have a Client lunch "
    "block on my calendar today, cancel the food order and delete that hold "
    "so my afternoon's free. If the hold's already gone, leave the order alone."
)

HOLD_ID = "ev_cal002_client_lunch"
DECOY_TEAM_ID = "ev_cal002_team_lunch"
ACTIVE_ORDER_ID = "FOOD-CAL002-ACTIVE"
DELIVERED_ORDER_ID = "FOOD-CAL002-OLD"

HOLD_TITLE = "Client lunch"
DECOY_TITLE = "Team lunch"
HOLD_START, HOLD_END = "12:30", "13:30"
DECOY_START, DECOY_END = "12:00", "13:00"


def task_cal_002_conditional_lunch_hold_cancel(seed: int) -> "WorldState":
    """FEASIBLE Calendar×Food conditional cancel (hold present → cancel+delete).

    Seed (today Thu May 21):
      - Calendar: Client lunch 12:30–13:30 (delete target)
      - Calendar: Team lunch tomorrow 12:00–13:00 (decoy — must not delete)
      - Food: FOOD-CAL002-ACTIVE at Bean There, status preparing (cancel target)
      - Food: FOOD-CAL002-OLD delivered decoy (must not touch)

    Correct: cancel active order + delete Client lunch. Leave Team lunch +
    delivered order intact.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY, TOMORROW
    from server.apps.food.state import FoodCartItem, FoodOrder, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    cal = world.calendar
    cal.events.clear()
    cal.events[HOLD_ID] = CalendarEvent(
        id=HOLD_ID,
        title=HOLD_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=HOLD_START,
        end=HOLD_END,
        source="seed",
    )
    cal.events[DECOY_TEAM_ID] = CalendarEvent(
        id=DECOY_TEAM_ID,
        title=DECOY_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=DECOY_START,
        end=DECOY_END,
        source="seed",
    )

    food = world.food
    food.orders.clear()
    bean = food.restaurants["r_bean"]
    food.orders[ACTIVE_ORDER_ID] = FoodOrder(
        id=ACTIVE_ORDER_ID,
        restaurant_id=bean.id,
        restaurant_name=bean.name,
        items=[
            FoodCartItem(
                dish_id="d_latte",
                restaurant_id=bean.id,
                name="Oat Milk Latte",
                unit_price=5.25,
                quantity=2,
            ),
            FoodCartItem(
                dish_id="d_croissant",
                restaurant_id=bean.id,
                name="Butter Croissant",
                unit_price=3.75,
                quantity=1,
            ),
        ],
        subtotal=14.25,
        delivery_fee=1.99,
        total=16.24,
        placed_at=f"{SEED_DATE}T12:05:00",
        eta_label="12:45 PM",
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
    TASK_ID: task_cal_002_conditional_lunch_hold_cancel,
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

    def _hold_deleted(p: Probe) -> bool:
        return HOLD_ID not in _events(p)

    def _active_cancelled(p: Probe) -> bool:
        o = _orders(p).get(ACTIVE_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "cancelled"

    def _decoy_intact(p: Probe) -> bool:
        return DECOY_TEAM_ID in _events(p)

    def _delivered_intact(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is not None and getattr(o, "status", None) == "delivered"

    def _success(p: Probe) -> bool:
        return (
            _hold_deleted(p)
            and _active_cancelled(p)
            and _decoy_intact(p)
            and _delivered_intact(p)
        )

    def _wrong_delete(p: Probe) -> bool:
        return DECOY_TEAM_ID not in _events(p)

    def _delivered_tampered(p: Probe) -> bool:
        o = _orders(p).get(DELIVERED_ORDER_ID)
        return o is None or getattr(o, "status", None) != "delivered"

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "conditional_cancel_and_delete",
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
