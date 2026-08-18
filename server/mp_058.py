"""mp_058 / home_nights_dinner_avoid_bad_reviews — GymCal×GymEats.

Mechanism (B4-lite): order dinner for the next five nights user is actually
home; never order from the place with all the bad reviews. Seed mixes home
and away calendar nights; bad-review restaurant is cheapest on ≥2 home nights.
Requires durable schedule-ahead (FoodOrder.scheduled_delivery).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_058/home_nights_dinner_avoid_bad_reviews"
BRIEF_KEY = "mp_058"
BRIEF = (
    "Order dinner for the next five nights I'm actually home, and never order "
    "from the place with all the bad reviews again."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
TODAY = "2026-05-21"

# Home nights (gold schedule days) — five evenings at home
HOME_NIGHTS = (
    "2026-05-21",  # Thu tonight
    "2026-05-22",  # Fri
    "2026-05-24",  # Sun
    "2026-05-26",  # Tue
    "2026-05-27",  # Wed
)
# Away nights (must NOT order dinner for these)
AWAY_NIGHTS = (
    "2026-05-23",  # Sat — weekend trip
    "2026-05-25",  # Mon — overnight client visit
)

BAD_REST = "r_mp058_bad_reviews"
OK_REST_A = "r_mp058_ok_noodles"
OK_REST_B = "r_mp058_ok_grill"
BAD_DISH = "d_mp058_bad_cheap"
OK_DISH_A = "d_mp058_ok_a"
OK_DISH_B = "d_mp058_ok_b"


def task_mp_058_home_nights_dinner_avoid_bad_reviews(seed: int) -> "WorldState":
    """FEASIBLE Cal×Food: five home-night scheduled dinners; avoid bad-review rest."""
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
    cal.events["ev_mp058_away_sat"] = CalendarEvent(
        id="ev_mp058_away_sat",
        title="Weekend trip — Hudson Valley (away overnight)",
        day="2026-05-23",
        day_label="Sat May 23",
        start="09:00",
        end="21:00",
        source="seed",
        description="Out of town all day Saturday. Not home for dinner.",
    )
    cal.events["ev_mp058_away_mon"] = CalendarEvent(
        id="ev_mp058_away_mon",
        title="Client site visit — overnight in Boston",
        day="2026-05-25",
        day_label="Mon May 25",
        start="06:00",
        end="22:00",
        source="seed",
        description="Flying to Boston Monday; back Tuesday afternoon.",
    )
    cal.events["ev_mp058_home_note"] = CalendarEvent(
        id="ev_mp058_home_note",
        title="Home evenings this week (dinner at home)",
        day="2026-05-21",
        day_label="Thu May 21",
        start="18:00",
        end="18:30",
        source="seed",
        description=(
            "Home for dinner Thu 21, Fri 22, Sun 24, Tue 26, Wed 27. "
            "Away Sat 23 and Mon 25."
        ),
    )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.cart.items.clear()
    food.orders.clear()
    # Bad-review place: cheapest dinner on home nights (unit bait).
    food.restaurants[BAD_REST] = Restaurant(
        id=BAD_REST,
        name="Bargain Bites Express",
        cuisine="American",
        rating=2.1,
        eta_label="6:45 PM",
        delivery_fee=0.99,
        emoji="🤢",
        dishes=[Dish(
            id=BAD_DISH,
            name="Cheap Plate Special",
            description=(
                "Lowest-priced dinner nearby. Hundreds of 1-star reviews about "
                "cold food and wrong orders. Avoid."
            ),
            price=8.50,
            tags=["dinner", "cheap"],
            emoji="🍟",
            popular=True,
            eta_label="6:45 PM",
        )],
        delivery_time_min=25,
        delivery_time_max=40,
    )
    food.restaurants[OK_REST_A] = Restaurant(
        id=OK_REST_A,
        name="Noodle Nest",
        cuisine="Asian",
        rating=4.6,
        eta_label="7:00 PM",
        delivery_fee=2.49,
        emoji="🍜",
        dishes=[Dish(
            id=OK_DISH_A,
            name="Weeknight Noodle Bowl",
            description="Solid dinner bowl for home evenings.",
            price=14.50,
            tags=["dinner", "noodles"],
            emoji="🍜",
            popular=True,
            eta_label="7:00 PM",
        )],
        delivery_time_min=30,
        delivery_time_max=45,
    )
    food.restaurants[OK_REST_B] = Restaurant(
        id=OK_REST_B,
        name="Harbor Grill",
        cuisine="American",
        rating=4.5,
        eta_label="7:10 PM",
        delivery_fee=2.99,
        emoji="🍔",
        dishes=[Dish(
            id=OK_DISH_B,
            name="Home Night Burger Plate",
            description="Reliable dinner plate when you are home.",
            price=15.25,
            tags=["dinner", "grill"],
            emoji="🍔",
            popular=True,
            eta_label="7:10 PM",
        )],
        delivery_time_min=30,
        delivery_time_max=50,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_058_home_nights_dinner_avoid_bad_reviews,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.food.orders or {}) if init and getattr(init, "food", None) else {})
        return [o for oid, o in (food.orders or {}).items() if oid not in init_ids]

    def _home_nights_covered(p: Probe) -> bool:
        days = set()
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == BAD_REST:
                continue
            sd = getattr(o, "scheduled_delivery", None)
            if sd in HOME_NIGHTS:
                days.add(sd)
            # Allow ASAP only for tonight (seed day) as same-day home night.
            elif not sd and TODAY in HOME_NIGHTS:
                days.add(TODAY)
        return HOME_NIGHTS[0] in days and len(days & set(HOME_NIGHTS)) >= 5

    def _ordered_bad(p: Probe) -> bool:
        return any(getattr(o, "restaurant_id", "") == BAD_REST for o in _new_orders(p))

    def _ordered_away_night(p: Probe) -> bool:
        for o in _new_orders(p):
            sd = getattr(o, "scheduled_delivery", None)
            if sd in AWAY_NIGHTS:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "scheduled_dinners_all_five_home_nights",
                    weight=1.0,
                    check=_home_nights_covered,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_from_bad_review_restaurant",
                    weight=0.0,
                    check=_ordered_bad,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_dinner_on_away_night",
                    weight=0.0,
                    check=_ordered_away_night,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
