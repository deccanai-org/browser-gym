"""mp_148 / fix_next_week_doublebook_move_easier.

Tue 14:00 double-book: Jordan 1:1 (already moved once) vs Northwind legal
with Ava (external, only slot). Gold = move Jordan, keep Ava.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_148/fix_next_week_doublebook_move_easier"
BRIEF_KEY = "mp_148"
BRIEF = (
    "I accidentally double-booked myself sometime next week. Fix it. Move the "
    "meeting that is easier to reschedule, based on attendees, email context "
    "and whether it has already been moved before. Email me what you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
JORDAN = "ev_mp148_jordan"
LEGAL = "ev_mp148_legal"
AVA = "em_mp148_ava"
JMAIL = "em_mp148_jordan"


def task_mp_148_fix_next_week_doublebook_move_easier(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[JORDAN] = ev(
        eid=JORDAN, title="1:1 with Jordan Blake",
        day="2026-05-26", start="14:00", end="15:00", day_label="Tue May 26",
        description="Internal 1:1. Already rescheduled once from Monday 11:00.",
    )
    world.calendar.events[LEGAL] = ev(
        eid=LEGAL, title="Northwind legal review — Ava Brooks",
        day="2026-05-26", start="14:00", end="15:00", day_label="Tue May 26",
        description="External counsel Ava Brooks. Never moved.",
        location="Zoom",
    )
    world.mail.inbox[AVA] = mail(
        eid=AVA, sender="ava.brooks@northwind.example",
        subject="Tuesday 2pm is the only slot I have",
        received_at="2026-05-19T15:00:00", received_label="Tue 3:00 PM",
        body=(
            "Alice — Tuesday May 26 at 2:00 PM Eastern is the only window I have "
            "this month for the Northwind legal review. Please don't move it."
        ),
    )
    world.mail.inbox[JMAIL] = mail(
        eid=JMAIL, sender="jordan.blake@shopmail.com",
        subject="Re: 1:1 moved from Monday",
        received_at="2026-05-18T10:00:00", received_label="Mon 10:00 AM",
        body="Fine to slide the 1:1 again if Tuesday gets messy — I'm flexible.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_148_fix_next_week_doublebook_move_easier,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, event_changed, mail_read
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(jordan|ava|legal|double)")

    def _jordan_moved(p: Probe) -> bool:
        e = cal_map(p).get(JORDAN)
        if e is None:
            return True
        return event_changed(p, JORDAN) and not (e.day == "2026-05-26" and e.start == "14:00")

    def _legal_kept(p: Probe) -> bool:
        e = cal_map(p).get(LEGAL)
        return bool(e and e.day == "2026-05-26" and e.start == "14:00") and _jordan_moved(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_ava_only_slot_email", 0.25, lambda p: mail_read(p, AVA), True),
                Milestone("moved_easier_jordan_1on1", 0.4, _jordan_moved, True),
                Milestone("kept_external_legal_review", 0.2, _legal_kept, True),
                Milestone("emailed_resolution", 0.15, lambda p: emailed_alice(p, _OK) and _jordan_moved(p) and _legal_kept(p), True),
                Milestone("moved_external_legal_review", 0.0, lambda p: event_changed(p, LEGAL), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
