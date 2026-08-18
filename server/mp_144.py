"""mp_144 / usual_friday_lunch_unless_plans.

Friday already has lunch with Dana at Cafe Lumen. Gold = do not order usual.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_144/usual_friday_lunch_unless_plans"
BRIEF_KEY = "mp_144"
BRIEF = (
    "Order my usual Friday lunch, unless I already have lunch plans, someone "
    "invited me somewhere by email, or I'll be away from my normal location. "
    "Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T17:00:00"
PLANS = "ev_mp144_dana"
USUAL = "r_mp144_green"
USUAL_DISH = "d_mp144_bowl"
INVITE = "em_mp144_dana"


def task_mp_144_usual_friday_lunch_unless_plans(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, fitem, food_order, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[PLANS] = ev(
        eid=PLANS, title="Lunch with Dana — Cafe Lumen",
        day="2026-05-22", start="12:30", end="13:30", day_label="Fri May 22",
        description="Already have lunch plans Friday.",
        location="Cafe Lumen",
    )
    world.mail.inbox[INVITE] = mail(
        eid=INVITE, sender="dana.whitfield@shopmail.com",
        subject="Friday lunch at Cafe Lumen",
        received_at="2026-05-20T11:00:00", received_label="Wed 11:00 AM",
        body="Let's do Cafe Lumen Friday 12:30 — I'll see you there. Don't order delivery.",
    )
    world.food.restaurants[USUAL] = restaurant(
        rid=USUAL, name="Green Fork", cuisine="American", eta="12:15 PM",
        fee=1.99, emoji="🥗",
        dishes=[dish(did=USUAL_DISH, name="Friday Grain Bowl", price=13.75,
                     tags=["lunch"], eta="12:15 PM")],
    )
    world.food.orders["FOOD-MP144-LASTFRI"] = food_order(
        oid="FOOD-MP144-LASTFRI", rid=USUAL, rname="Green Fork",
        items=[fitem(did=USUAL_DISH, rid=USUAL, name="Friday Grain Bowl", price=13.75)],
        fee=1.99, placed_at="2026-05-15T11:50:00", eta="12:15 PM",
        note="Usual Friday lunch",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_144_usual_friday_lunch_unless_plans,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import any_new_food, emailed_alice, mail_read, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _SKIP = re.compile(r"(?ix)(already\s+(have|had)|lunch\s+plans|cafe\s+lumen|dana|did\s+not\s+order|didn't\s+order)")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_friday_calendar_for_lunch_plans", 0.3, viewed_cal, True),
                Milestone("saw_dana_invite", 0.2, lambda p: mail_read(p, INVITE) or viewed_cal(p), True),
                Milestone("did_not_order_usual_lunch", 0.3, lambda p: (not any_new_food(p)) and viewed_cal(p), True),
                Milestone("emailed_that_plans_exist", 0.2, lambda p: emailed_alice(p, _SKIP) and not any_new_food(p), True),
                Milestone("ordered_usual_despite_existing_plans", 0.0, any_new_food, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
