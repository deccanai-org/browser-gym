"""mp_138 / clear_friday_afternoon_three_hours_protected.

Move internal 1:1s; do not move interview or urgent Northwind email thread.
Gold = Fri 16:00–19:00 clear (3h) after moving Jordan + Priya.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_138/clear_friday_afternoon_three_hours_protected"
BRIEF_KEY = "mp_138"
BRIEF = (
    "Clear up my Friday afternoon so I have three uninterrupted hours. Move "
    "whatever can reasonably be moved, but don't move meetings involving "
    "external people, interviews, or anything whose email thread indicates "
    "urgency. Email me what you moved."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T09:00:00"
JORDAN = "ev_mp138_jordan"
INTERVIEW = "ev_mp138_interview"
URGENT = "ev_mp138_northwind"
PRIYA = "ev_mp138_priya"
URGENT_MAIL = "em_mp138_urgent"
INTERVIEW_MAIL = "em_mp138_sam"


def task_mp_138_clear_friday_afternoon_three_hours_protected(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    cal.events[JORDAN] = ev(
        eid=JORDAN, title="1:1 with Jordan Blake", day="2026-05-22",
        start="13:00", end="13:30", day_label="Fri May 22",
        description="Internal 1:1. Can move.",
    )
    cal.events[INTERVIEW] = ev(
        eid=INTERVIEW, title="Candidate interview — Sam Okonkwo",
        day="2026-05-22", start="14:00", end="15:00", day_label="Fri May 22",
        description="External interview. Do not move.",
        location="Room 2A",
    )
    cal.events[URGENT] = ev(
        eid=URGENT, title="Northwind check-in", day="2026-05-22",
        start="15:00", end="16:00", day_label="Fri May 22",
        description="Board deck due Monday — see email.",
    )
    cal.events[PRIYA] = ev(
        eid=PRIYA, title="Priya sync", day="2026-05-22",
        start="16:00", end="16:30", day_label="Fri May 22",
        description="Internal sync. Can move.",
    )
    world.mail.inbox[URGENT_MAIL] = mail(
        eid=URGENT_MAIL, sender="helen.vasquez@shopmail.com",
        subject="Northwind check-in Friday — urgent board deck",
        received_at="2026-05-20T17:00:00", received_label="Wed 5:00 PM",
        body=(
            "Friday's Northwind check-in at 3pm is urgent — the board deck is "
            "due Monday. Please do not move this one."
        ),
    )
    world.mail.inbox[INTERVIEW_MAIL] = mail(
        eid=INTERVIEW_MAIL, sender="recruiting@shopmail.com",
        subject="Interview confirmed — Sam Okonkwo Friday 2pm",
        received_at="2026-05-19T10:00:00", received_label="Tue 10:00 AM",
        body="Sam is flying in for the 2:00 PM interview Friday. External candidate — keep the slot.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_138_clear_friday_afternoon_three_hours_protected,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, event_changed, mail_read, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(jordan|priya|three\s+hours|16:00|4:00)")

    def _protected_ok(p: Probe) -> bool:
        now = cal_map(p)
        iv = now.get(INTERVIEW)
        ug = now.get(URGENT)
        if iv is None or ug is None:
            return False
        return iv.day == "2026-05-22" and iv.start == "14:00" and ug.day == "2026-05-22" and ug.start == "15:00"

    def _moved_internal(p: Probe) -> bool:
        return event_changed(p, JORDAN) and event_changed(p, PRIYA)

    def _three_h(p: Probe) -> bool:
        now = cal_map(p)
        busy = []
        for e in now.values():
            if e.day != "2026-05-22":
                continue
            if (getattr(e, "status", "confirmed") or "").lower() == "cancelled":
                continue
            if e.start >= "13:00":
                busy.append((e.start, e.end))
        busy.sort()
        # After 16:00 should be clear if Priya moved
        priya = now.get(PRIYA)
        if priya and priya.day == "2026-05-22" and priya.start < "19:00" and priya.start >= "16:00":
            return False
        if priya and (priya.day != "2026-05-22" or priya.start >= "19:00" or priya.start < "13:00"):
            return _protected_ok(p)
        return False

    def _moved_protected(p: Probe) -> bool:
        return event_changed(p, INTERVIEW) or event_changed(p, URGENT)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_friday_calendar", 0.2, viewed_cal, True),
                Milestone("read_urgency_and_interview_emails", 0.2, lambda p: mail_read(p, URGENT_MAIL), True),
                Milestone("moved_internal_meetings_only", 0.3, _moved_internal, True),
                Milestone("left_three_hour_afternoon_block", 0.2, _three_h, True),
                Milestone("emailed_what_moved", 0.1, lambda p: emailed_alice(p, _OK), True),
                Milestone("moved_interview_or_urgent_external", 0.0, _moved_protected, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
