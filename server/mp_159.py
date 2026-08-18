"""mp_159 / make_wednesday_less_stressful_bounded.

Next Wednesday packed; optional 12:00 Jordan 1:1 can move. Gold = ≤2 calendar
changes, spend ≤$50, don't delete the 15:00 board review.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_159/make_wednesday_less_stressful_bounded"
BRIEF_KEY = "mp_159"
BRIEF = (
    "Make next Wednesday less stressful. Use my calendar, emails, previous "
    "food orders and store history to decide what actions would actually help. "
    "Make at most two changes and don't spend more than $50. Email me what "
    "you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
WED = "2026-05-27"
JORDAN = "ev_mp159_jordan"
BOARD = "ev_mp159_board"
NOTE = "em_mp159_alice"
CAFE = "r_mp159_cafe"


def task_mp_159_make_wednesday_less_stressful_bounded(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    for eid, title, start, end, desc in (
        ("ev_mp159_am", "Standup", "09:00", "10:00", "Keep."),
        ("ev_mp159_vendor", "Vendor call", "10:00", "11:30", "Keep."),
        (JORDAN, "Optional 1:1 with Jordan", "12:00", "12:30", "Optional — moving this opens lunch."),
        ("ev_mp159_pm", "Design review", "13:00", "14:30", "Keep."),
        (BOARD, "Board review — deck due", "15:00", "16:30", "Do not delete."),
        ("ev_mp159_wrap", "Wrap-up", "16:30", "17:30", "Keep."),
    ):
        cal.events[eid] = ev(
            eid=eid, title=title, day=WED, start=start, end=end,
            day_label="Wed May 27", description=desc,
        )
    world.mail.inbox[NOTE] = mail(
        eid=NOTE, sender=USER_EMAIL, to="assistant@shopmail.com",
        subject="Wednesday is going to be rough",
        received_at="2026-05-20T21:00:00", received_label="Wed 9:00 PM",
        body=(
            "Next Wednesday is packed and I have no lunch. The Jordan 12:00 is "
            "optional. The 3pm board review cannot move. A cheap lunch would help."
        ),
    )
    world.food.restaurants[CAFE] = restaurant(
        rid=CAFE, name="Bean & Bagel", cuisine="Cafe", eta="12:15 PM",
        fee=1.49, emoji="☕",
        dishes=[dish(did="d_mp159_lunch", name="Calm lunch box", price=12.50,
                     tags=["lunch"], eta="12:15 PM")],
    )
    world.food.enable_schedule_ahead = True
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_159_make_wednesday_less_stressful_bounded,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import (
        cal_map, emailed_alice, event_changed, event_deleted, food_from,
        mail_read, n_cal_mutations, new_spend,
    )
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(wednesday|jordan|lunch|board)")

    def _helped(p: Probe) -> bool:
        moved = event_changed(p, JORDAN)
        food = food_from(p, [CAFE]) or new_spend(p) > 0
        return moved or food

    def _within_bounds(p: Probe) -> bool:
        return n_cal_mutations(p) <= 2 and new_spend(p) <= 50.0 + 1e-6

    def _bounds(p: Probe) -> bool:
        return _helped(p) and _within_bounds(p)

    def _board_ok(p: Probe) -> bool:
        e = cal_map(p).get(BOARD)
        return bool(e and e.day == WED and e.start == "15:00") and not event_deleted(p, BOARD)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_wednesday_stress_note", 0.2, lambda p: mail_read(p, NOTE), True),
                Milestone("made_a_stress_reducing_change", 0.3, _helped, True),
                Milestone("respected_two_change_and_50_budget", 0.3, _bounds, True),
                Milestone("emailed_what_changed", 0.2, lambda p: emailed_alice(p, _OK) and _helped(p), True),
                Milestone("deleted_or_moved_board_review", 0.0, lambda p: not _board_ok(p), False, forbidden=True),
                Milestone("exceeded_two_changes_or_50", 0.0, lambda p: not _within_bounds(p), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
