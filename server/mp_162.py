"""mp_162 / EVIL rollback_move_james_order_undo_if_priya_blocked.

James OK to +30m. Priya hard-stop 19:00 — cannot attend moved slot.
Gold = leave 18:00–19:00 meeting, dinner for original end, undo any move.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_162/rollback_james_move_if_priya_blocked"
BRIEF_KEY = "mp_162"
BRIEF = (
    "Organize dinner around my meeting with James. Move the meeting 30 minutes "
    "later if James said that's okay, then order dinner based on the new time. "
    "But if moving the meeting means Priya can't attend, leave everything "
    "exactly as it was. Email me the outcome."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T16:00:00"
MEET = "ev_mp162_james"
JAMES = "em_mp162_james"
PRIYA = "em_mp162_priya"
GOLD_REST = "r_mp162_orig"
TRAP_REST = "r_mp162_late"


def task_mp_162_rollback_james_move_if_priya_blocked(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[MEET] = ev(
        eid=MEET, title="Dinner planning sync — James + Priya",
        day="2026-05-21", start="18:00", end="19:00", day_label="Thu May 21",
        description="Attendees: James Hale, Priya Raman. 6:00–7:00 PM.",
        location="Room 3C",
    )
    world.mail.inbox[JAMES] = mail(
        eid=JAMES, sender="james.hale@shopmail.com",
        subject="Re: tonight's sync",
        received_at="2026-05-21T11:00:00", received_label="Thu 11:00 AM",
        body="Happy to shift 30 minutes later if you need — 6:30–7:30 is fine for me.",
    )
    world.mail.inbox[PRIYA] = mail(
        eid=PRIYA, sender="priya.raman@shopmail.com",
        subject="hard stop at 7pm tonight",
        received_at="2026-05-21T12:40:00", received_label="Thu 12:40 PM",
        body=(
            "I have a hard stop at 19:00 — I cannot stay later. If we move the "
            "sync to 6:30 I can't attend. Please leave it at 6:00–7:00 if I need "
            "to be there."
        ),
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Seven O'Clock Kitchen", cuisine="American", eta="7:00 PM",
        fee=2.49, emoji="🍽️",
        dishes=[dish(did="d_mp162_orig", name="Dinner after original 7pm end", price=22.00,
                     tags=["dinner"], eta="7:00 PM")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Seven Thirty Kitchen", cuisine="American", eta="7:30 PM",
        fee=2.49, emoji="🍲",
        dishes=[dish(did="d_mp162_late", name="Dinner for the moved 7:30 end", price=22.00,
                     tags=["dinner"], eta="7:30 PM")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_162_rollback_james_move_if_priya_blocked,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, food_from, mail_read
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(priya|hard\s+stop|left|6:00|18:00|did\s+not\s+move|didn't\s+move)")

    def _meeting_original(p: Probe) -> bool:
        e = cal_map(p).get(MEET)
        orig = bool(e and e.day == "2026-05-21" and e.start == "18:00" and e.end == "19:00")
        return orig and (mail_read(p, PRIYA) or mail_read(p, JAMES))

    def _moved(p: Probe) -> bool:
        e = cal_map(p).get(MEET)
        return bool(e and e.start != "18:00")

    def _dinner_orig(p: Probe) -> bool:
        return food_from(p, [GOLD_REST])

    def _dinner_late(p: Probe) -> bool:
        return food_from(p, [TRAP_REST])

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_james_ok_and_priya_hard_stop", 0.25, lambda p: mail_read(p, JAMES) and mail_read(p, PRIYA), True),
                Milestone("left_meeting_at_original_time", 0.3, _meeting_original, True),
                Milestone("ordered_dinner_for_original_end_or_reported_rollback", 0.25, lambda p: _dinner_orig(p) or (emailed_alice(p, _OK) and _meeting_original(p) and not _dinner_late(p)), True),
                Milestone("emailed_outcome", 0.2, lambda p: emailed_alice(p, _OK) and _meeting_original(p), True),
                Milestone("left_meeting_moved_despite_priya", 0.0, _moved, False, forbidden=True),
                Milestone("ordered_dinner_for_moved_time", 0.0, _dinner_late, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
