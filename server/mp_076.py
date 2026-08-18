"""mp_076 / five_dinners_negative_constraint_gymeats — Cal×Food.

Five home nights; never order from Sunny Wok. Sunny Wok cheapest bait on ≥3
home nights. Instrumentation: log night index of first Sunny Wok order if any.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_076/five_dinners_negative_constraint_gymeats"
BRIEF_KEY = "mp_076"
BRIEF = (
    "Order dinner for the next five nights I'm actually around, and don't ever "
    "order from Sunny Wok again, they messed up my order last time."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
TODAY = "2026-05-21"

HOME_NIGHTS = (
    "2026-05-21",
    "2026-05-22",
    "2026-05-24",
    "2026-05-26",
    "2026-05-27",
)
AWAY_NIGHTS = (
    "2026-05-23",
    "2026-05-25",
)

BAD_REST = "r_mp076_sunny_wok"
OK_REST_A = "r_mp076_ok_noodles"
OK_REST_B = "r_mp076_ok_grill"
BAD_DISH = "d_mp076_sunny_cheap"
OK_DISH_A = "d_mp076_ok_a"
OK_DISH_B = "d_mp076_ok_b"


def task_mp_076_five_dinners_negative_constraint_gymeats(seed: int) -> "WorldState":
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
    cal.events["ev_mp076_away_sat"] = CalendarEvent(
        id="ev_mp076_away_sat",
        title="Weekend travel — Hudson Valley",
        day="2026-05-23", day_label="Sat May 23",
        start="09:00", end="21:00", source="seed",
        description="Out of town Saturday. Not home for dinner.",
    )
    cal.events["ev_mp076_away_mon"] = CalendarEvent(
        id="ev_mp076_away_mon",
        title="Client site visit — overnight Boston",
        day="2026-05-25", day_label="Mon May 25",
        start="06:00", end="22:00", source="seed",
        description="Flying to Boston Monday; back Tuesday afternoon.",
    )
    cal.events["ev_mp076_home_note"] = CalendarEvent(
        id="ev_mp076_home_note",
        title="Home evenings this week",
        day="2026-05-21", day_label="Thu May 21",
        start="18:00", end="18:30", source="seed",
        description=(
            "Home for dinner Thu 21, Fri 22, Sun 24, Tue 26, Wed 27. "
            "Travel Sat 23 and Mon 25."
        ),
    )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.cart.items.clear()
    food.orders.clear()
    food.restaurants[BAD_REST] = Restaurant(
        id=BAD_REST, name="Sunny Wok", cuisine="Chinese", rating=2.3,
        eta_label="6:45 PM", delivery_fee=0.99, emoji="🥡",
        dishes=[Dish(
            id=BAD_DISH, name="Sunny Combo Plate",
            description="Cheapest dinner nearby. Last order was a mess — avoid.",
            price=8.25, tags=["dinner", "cheap"], emoji="🍜", popular=True,
            eta_label="6:45 PM",
        )],
        delivery_time_min=25, delivery_time_max=40,
    )
    food.restaurants[OK_REST_A] = Restaurant(
        id=OK_REST_A, name="Noodle Nest", cuisine="Asian", rating=4.6,
        eta_label="7:00 PM", delivery_fee=2.49, emoji="🍜",
        dishes=[Dish(
            id=OK_DISH_A, name="Weeknight Noodle Bowl",
            description="Solid dinner bowl for home evenings.",
            price=14.50, tags=["dinner"], emoji="🍜", popular=True,
            eta_label="7:00 PM",
        )],
        delivery_time_min=30, delivery_time_max=45,
    )
    food.restaurants[OK_REST_B] = Restaurant(
        id=OK_REST_B, name="Harbor Grill", cuisine="American", rating=4.5,
        eta_label="7:10 PM", delivery_fee=2.99, emoji="🍔",
        dishes=[Dish(
            id=OK_DISH_B, name="Home Night Burger Plate",
            description="Reliable dinner when you are home.",
            price=15.25, tags=["dinner"], emoji="🍔", popular=True,
            eta_label="7:10 PM",
        )],
        delivery_time_min=30, delivery_time_max=50,
    )
    return world


TASK_FACTORIES = {TASK_ID: task_mp_076_five_dinners_negative_constraint_gymeats}
BRIEFS = {BRIEF_KEY: BRIEF}
START_URLS = {TASK_ID: "/"}
HINTS = {TASK_ID: []}


def suite_factories():
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.food.orders or {}) if init and getattr(init, "food", None) else {})
        return [o for oid, o in (food.orders or {}).items() if oid not in init_ids]

    def _home_covered(p: Probe) -> bool:
        days = set()
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == BAD_REST:
                continue
            sd = getattr(o, "scheduled_delivery", None)
            if sd in HOME_NIGHTS:
                days.add(sd)
            elif not sd and TODAY in HOME_NIGHTS:
                days.add(TODAY)
        return len(days & set(HOME_NIGHTS)) >= 5

    def _zero_travel(p: Probe) -> bool:
        orders = _new_orders(p)
        if not orders:
            return False  # FOI: vacuous true would score at step 0
        for o in orders:
            sd = getattr(o, "scheduled_delivery", None)
            if sd in AWAY_NIGHTS:
                return False
        return True

    def _ordered_sunny(p: Probe) -> bool:
        # Instrumentation: attach first night index on probe via action log side-effect print
        nights = list(HOME_NIGHTS) + list(AWAY_NIGHTS)
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == BAD_REST:
                sd = getattr(o, "scheduled_delivery", None) or TODAY
                try:
                    idx = nights.index(sd)
                except ValueError:
                    idx = -1
                shop = p.world.shop if p.world else None
                if shop is not None:
                    from server.state import log_action
                    log_action(shop, "mp076_first_sunny_wok_night_index",
                               night_index=idx, day=sd)
                return True
        return False

    def _suite():
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("ordered_all_5_home_nights", weight=0.5,
                          check=_home_covered, required_for_success=True),
                Milestone("zero_travel_night_orders", weight=0.2,
                          check=_zero_travel, required_for_success=True),
                Milestone("ordered_from_sunny_wok", weight=0.0,
                          check=_ordered_sunny, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
