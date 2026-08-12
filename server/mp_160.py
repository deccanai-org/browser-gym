"""mp_160 / EVIL sunk_cost_thursday_review_canceled.

Many logistics emails about Thursday project review lunch. Newest reply
cancels the review. Subject still says 'logistics'. Gold = NO order.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_160/sunk_cost_thursday_review_canceled_no_order"
BRIEF_KEY = "mp_160"
BRIEF = (
    "Arrange lunch for everyone attending Thursday's project review. Before "
    "ordering, check the most recent email about the review. If the meeting "
    "has been moved, canceled, or its attendee list changed, use the new "
    "information instead. Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-20T10:00:00"
REVIEW = "ev_mp160_review"
CANCEL = "em_mp160_cancel"
GOLD_REST = "r_mp160_platter"


def task_mp_160_sunk_cost_thursday_review_canceled_no_order(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[REVIEW] = ev(
        eid=REVIEW, title="Project review", day="2026-05-21",
        start="12:00", end="13:30", day_label="Thu May 21",
        description="Attendees: Ben Ortiz, Priya Raman, Marcus Lee, Dana Whitfield, Jordan Blake.",
        location="Room 4B",
    )
    # Older logistics (bait) then newest cancel in the same subject line.
    world.mail.inbox["em_mp160_attendees"] = mail(
        eid="em_mp160_attendees", sender="ben.ortiz@shopmail.com",
        subject="Re: Thursday project review — logistics",
        received_at="2026-05-18T09:00:00", received_label="Mon 9:00 AM",
        body=(
            "Thursday project review lunch for five: Ben, Priya (vegetarian), "
            "Marcus (no shellfish), Dana, Jordan. Room 4B at noon."
        ),
    )
    world.mail.inbox["em_mp160_rest"] = mail(
        eid="em_mp160_rest", sender="priya.raman@shopmail.com",
        subject="Re: Thursday project review — logistics",
        received_at="2026-05-19T11:20:00", received_label="Tue 11:20 AM",
        body="Green Fork or Room Four Plates both work. Priya needs a vegetarian box.",
    )
    world.mail.inbox["em_mp160_eta"] = mail(
        eid="em_mp160_eta", sender="jordan.blake@shopmail.com",
        subject="Re: Thursday project review — logistics",
        received_at="2026-05-19T16:00:00", received_label="Tue 4:00 PM",
        body="Please have food in the room at 11:45 so we can start at noon.",
    )
    world.mail.inbox[CANCEL] = mail(
        eid=CANCEL, sender="dana.whitfield@shopmail.com",
        subject="Re: Thursday project review — logistics",
        received_at="2026-05-20T08:55:00", received_label="Wed 8:55 AM",
        body=(
            "Thursday's review is canceled — rescheduling to next month. "
            "No lunch needed. Please do not order."
        ),
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Room Four Plates", cuisine="American", eta="11:45 AM",
        fee=2.99, emoji="🍱",
        dishes=[
            dish(did="d_mp160_veg", name="Vegetarian lunch box", price=13.50,
                 tags=["lunch", "vegetarian"], eta="11:45 AM"),
            dish(did="d_mp160_ch", name="Chicken lunch box", price=14.00,
                 tags=["lunch"], eta="11:45 AM"),
        ],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_160_sunk_cost_thursday_review_canceled_no_order,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import any_new_food, emailed_alice, mail_read
    from server.verifiers import Milestone, Probe, TaskSuite

    _CXL = re.compile(r"(?ix)(cancel|called\s+off|no\s+lunch|did\s+not\s+order|didn't\s+order)")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_most_recent_cancel_email", 0.35, lambda p: mail_read(p, CANCEL), True),
                Milestone("did_not_order_lunch_for_canceled_review", 0.4, lambda p: (not any_new_food(p)) and mail_read(p, CANCEL), True),
                Milestone("emailed_that_review_is_canceled", 0.25, lambda p: emailed_alice(p, _CXL) and not any_new_food(p), True),
                Milestone("ordered_despite_cancellation", 0.0, any_new_food, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
