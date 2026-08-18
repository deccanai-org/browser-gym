"""mp_142 / unprepared_meeting_move_lunch_order_before_prep.

Ben's email flags Q3 forecast review as unprepared. Lunch 12:30–13:30 blocks
the hour before 14:00. Gold = move lunch earlier + food arriving before 13:00.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_142/unprepared_meeting_move_lunch_order_before_prep"
BRIEF_KEY = "mp_142"
BRIEF = (
    "I have a meeting tomorrow that I'm probably not prepared for. Figure out "
    "which meeting based on my emails. Move lunch so I have at least an hour "
    "beforehand, and order something that can arrive before that preparation "
    "window starts. Email me the plan."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T15:00:00"
LUNCH = "ev_mp142_lunch"
REVIEW = "ev_mp142_q3"
NOISE = "ev_mp142_stand"
BEN = "em_mp142_ben"
GOLD_REST = "r_mp142_noon"
TRAP_REST = "r_mp142_late"


def task_mp_142_unprepared_meeting_move_lunch_order_before_prep(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    cal.events[NOISE] = ev(
        eid=NOISE, title="Team standup", day="2026-05-22",
        start="09:00", end="09:15", day_label="Fri May 22",
    )
    cal.events[LUNCH] = ev(
        eid=LUNCH, title="Lunch", day="2026-05-22",
        start="12:30", end="13:30", day_label="Fri May 22",
        description="Lunch block — currently eats the hour before the 2pm review.",
    )
    cal.events[REVIEW] = ev(
        eid=REVIEW, title="Q3 forecast review with Ben", day="2026-05-22",
        start="14:00", end="15:00", day_label="Fri May 22",
        description="Walk the numbers. Attendee: Ben Ortiz.",
    )
    world.mail.inbox[BEN] = mail(
        eid=BEN, sender="ben.ortiz@shopmail.com",
        subject="Q3 forecast review tomorrow — are the numbers ready?",
        received_at="2026-05-21T14:10:00", received_label="Thu 2:10 PM",
        body=(
            "Tomorrow's Q3 forecast review at 2pm — can you walk through the "
            "numbers? I know we haven't prepped. You'll want a real hour before "
            "it, not just a sandwich at 12:30."
        ),
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Noon Box Co", cuisine="American", eta="12:00 PM",
        fee=1.99, emoji="🍱",
        dishes=[dish(did="d_mp142_noon", name="Prep-window lunch box", price=13.00,
                     tags=["lunch"], eta="12:00 PM")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Two O'Clock Kitchen", cuisine="American", eta="1:45 PM",
        fee=2.49, emoji="🍛",
        dishes=[dish(did="d_mp142_late", name="Arrives 1:45 PM plate", price=14.00,
                     tags=["lunch"], eta="1:45 PM",
                     desc="Lands inside the prep hour.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_142_unprepared_meeting_move_lunch_order_before_prep,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, food_from, mail_read, new_food_orders
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(q3|forecast|prep|lunch|12:00)")

    def _lunch_moved(p: Probe) -> bool:
        e = cal_map(p).get(LUNCH)
        if e is None:
            return False
        return e.day == "2026-05-22" and e.end <= "13:00"

    def _food_before(p: Probe) -> bool:
        if food_from(p, [GOLD_REST]):
            return True
        for o in new_food_orders(p):
            eta = (getattr(o, "eta_label", "") or "").lower()
            if "12:00" in eta or "12pm" in eta.replace(" ", ""):
                return True
        return False

    def _late(p: Probe) -> bool:
        return food_from(p, [TRAP_REST])

    def _review_moved(p: Probe) -> bool:
        e = cal_map(p).get(REVIEW)
        return e is None or e.start != "14:00"

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_unprepared_review_email", 0.2, lambda p: mail_read(p, BEN), True),
                Milestone("moved_lunch_to_open_hour_before_review", 0.35, _lunch_moved, True),
                Milestone("ordered_food_arriving_before_prep_window", 0.3, _food_before, True),
                Milestone("emailed_plan", 0.15, lambda p: emailed_alice(p, _OK) and _lunch_moved(p), True),
                Milestone("ordered_food_into_prep_hour", 0.0, _late, False, forbidden=True),
                Milestone("moved_the_review_instead_of_lunch", 0.0, _review_moved, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
