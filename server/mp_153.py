"""mp_153 / dinner_after_last_meeting_unless_virtual_home.

Last meeting is Zoom at home 17:00–18:00. Gold = dinner arriving 17:50
(last 10 minutes), not after 18:00.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_153/dinner_after_last_meeting_unless_virtual_home"
BRIEF_KEY = "mp_153"
BRIEF = (
    "Order dinner after my last meeting tonight, unless the meeting is virtual "
    "and I'm already home, in which case order it so it arrives during the last "
    "10 minutes. Email me the ETA."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T16:00:00"
LAST = "ev_mp153_zoom"
GOLD_REST = "r_mp153_early"
TRAP_REST = "r_mp153_after"
GOLD_DISH = "d_mp153_early"
TRAP_DISH = "d_mp153_after"


def task_mp_153_dinner_after_last_meeting_unless_virtual_home(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events["ev_mp153_day"] = ev(
        eid="ev_mp153_day", title="Team sync", day="2026-05-21",
        start="14:00", end="15:00", day_label="Thu May 21",
    )
    world.calendar.events[LAST] = ev(
        eid=LAST, title="Zoom — Northwind wrap (virtual)",
        day="2026-05-21", start="17:00", end="18:00", day_label="Thu May 21",
        description="Virtual Zoom from home office. Alice is already home.",
        location="Zoom (home office)",
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Early Plate", cuisine="American", eta="5:50 PM",
        fee=2.49, emoji="🍽️",
        dishes=[dish(did=GOLD_DISH, name="Dinner arriving 5:50 PM", price=19.00,
                     tags=["dinner"], eta="5:50 PM",
                     desc="Lands in the last 10 minutes of the 5–6pm Zoom.")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="After Six Kitchen", cuisine="American", eta="6:15 PM",
        fee=2.49, emoji="🍲",
        dishes=[dish(did=TRAP_DISH, name="Dinner arriving 6:15 PM", price=18.50,
                     tags=["dinner"], eta="6:15 PM",
                     desc="After the meeting ends.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_153_dinner_after_last_meeting_unless_virtual_home,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, food_from, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(5:50|17:50|last\s+10|zoom|home)")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_last_meeting_is_virtual_home", 0.25, viewed_cal, True),
                Milestone("ordered_dinner_for_last_ten_minutes", 0.5, lambda p: food_from(p, [GOLD_REST]), True),
                Milestone("emailed_eta", 0.25, lambda p: emailed_alice(p, _OK) and food_from(p, [GOLD_REST]), True),
                Milestone("ordered_dinner_after_meeting_ignoring_virtual_home", 0.0, lambda p: food_from(p, [TRAP_REST]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
