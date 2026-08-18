"""mp_139 / flying_tomorrow_dinner_no_leftovers.

Flight Friday 6:40 AM. Gold = single-serve dinner tonight, not family size.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_139/flying_tomorrow_dinner_no_leftovers"
BRIEF_KEY = "mp_139"
BRIEF = (
    "I'm flying tomorrow. Check when I need to leave from my calendar and "
    "order dinner tonight, but make sure it's something that won't leave "
    "leftovers because I'm leaving in the morning. Email me the order."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T16:00:00"
FLIGHT = "ev_mp139_flight"
GOLD_REST = "r_mp139_solo"
TRAP_REST = "r_mp139_family"
GOLD_DISH = "d_mp139_solo"
TRAP_DISH = "d_mp139_pizza"


def task_mp_139_flying_tomorrow_dinner_no_leftovers(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[FLIGHT] = ev(
        eid=FLIGHT, title="Flight to Austin (AA 1420)",
        day="2026-05-22", start="06:40", end="10:15", day_label="Fri May 22",
        description="Leave for JFK around 4:30 AM. No leftovers wanted in the fridge.",
        location="JFK",
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Solo Supper", cuisine="American", eta="7:15 PM",
        fee=2.49, emoji="🍽️",
        dishes=[dish(did=GOLD_DISH, name="Single-serve roast chicken plate",
                     price=18.50, tags=["dinner", "single-serve", "no-leftovers"],
                     eta="7:15 PM", desc="Portion for one. No leftovers.")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Family Pie Co", cuisine="Pizza", eta="7:20 PM",
        fee=1.99, emoji="🍕",
        dishes=[dish(did=TRAP_DISH, name="Family pepperoni pizza (feeds 4)",
                     price=24.00, tags=["dinner", "family"], eta="7:20 PM",
                     desc="Large pie — leftover slices expected.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_139_flying_tomorrow_dinner_no_leftovers,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, food_from, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(solo|single|no\s+leftover|6:40|flight)")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_flight_calendar", 0.25, viewed_cal, True),
                Milestone("ordered_single_serve_dinner", 0.5, lambda p: food_from(p, [GOLD_REST]), True),
                Milestone("emailed_order", 0.25, lambda p: emailed_alice(p, _OK) and food_from(p, [GOLD_REST]), True),
                Milestone("ordered_family_size_leftovers", 0.0, lambda p: food_from(p, [TRAP_REST]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
