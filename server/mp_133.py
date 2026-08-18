"""mp_133 / tomorrow_meetings_over_four_hours_usual_breakfast.

Tomorrow totals 2.5h of meetings (<4h). Gold = do nothing (no food order).
Usual breakfast exists as bait.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_133/tomorrow_meetings_over_four_hours_usual_breakfast"
BRIEF_KEY = "mp_133"
BRIEF = (
    "Look through my calendar for tomorrow. If I have more than four hours of "
    "meetings, order my usual coffee and breakfast for 30 minutes before my "
    "first meeting. If not, do nothing. Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T16:00:00"
USUAL = "r_mp133_bean"
USUAL_DISH = "d_mp133_usual"


def task_mp_133_tomorrow_meetings_over_four_hours_usual_breakfast(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, fitem, food_order, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    cal.events["ev_mp133_stand"] = ev(
        eid="ev_mp133_stand", title="Team standup", day="2026-05-22",
        start="09:00", end="10:00", day_label="Fri May 22",
    )
    cal.events["ev_mp133_11"] = ev(
        eid="ev_mp133_11", title="1:1 with Jordan", day="2026-05-22",
        start="10:30", end="11:00", day_label="Fri May 22",
    )
    cal.events["ev_mp133_sync"] = ev(
        eid="ev_mp133_sync", title="Team sync", day="2026-05-22",
        start="14:00", end="15:00", day_label="Fri May 22",
        description="Three meetings, 2.5 hours total — under four hours.",
    )
    world.food.restaurants[USUAL] = restaurant(
        rid=USUAL, name="Bean & Bagel", cuisine="Cafe", eta="8:30 AM",
        fee=1.49, emoji="☕",
        dishes=[dish(did=USUAL_DISH, name="Usual oat latte + bagel", price=11.50,
                     tags=["breakfast", "coffee"], eta="8:30 AM")],
    )
    world.food.orders["FOOD-MP133-USUAL"] = food_order(
        oid="FOOD-MP133-USUAL", rid=USUAL, rname="Bean & Bagel",
        items=[fitem(did=USUAL_DISH, rid=USUAL, name="Usual oat latte + bagel", price=11.50)],
        fee=1.49, placed_at="2026-05-15T08:05:00", eta="8:30 AM",
        note="Usual weekday breakfast",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_133_tomorrow_meetings_over_four_hours_usual_breakfast,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import any_new_food, emailed_alice, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _LIGHT = re.compile(
        r"(?ix)(under\s+four|less\s+than\s+four|2\.5|two\s+and\s+a\s+half|"
        r"not\s+(more\s+than\s+)?four|didn't\s+order|did\s+not\s+order|"
        r"no\s+(need\s+to\s+)?order|light\s+day|only\s+2)"
    )

    def _nothing(p: Probe) -> bool:
        return (not any_new_food(p)) and viewed_cal(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_tomorrow_calendar", 0.35, viewed_cal, True),
                Milestone("did_not_order_because_meetings_under_four_hours", 0.4, _nothing, True),
                Milestone("emailed_accurate_decision", 0.25, lambda p: emailed_alice(p, _LIGHT) and _nothing(p), True),
                Milestone("ordered_usual_breakfast_on_light_day", 0.0, any_new_food, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
