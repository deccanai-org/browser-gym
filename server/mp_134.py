"""mp_134 / manager_meet_travel_timezone.

No CalendarEvent.timezone field — substitute: manager email names Denver
Mountain Time; gold slot is Alice-local 16:00 ET (2pm MT). Trap is 14:00 ET.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_134/manager_meet_travel_timezone"
BRIEF_KEY = "mp_134"
BRIEF = (
    "My manager emailed me asking to meet. Find a time that satisfies what "
    "they asked for and tentatively put it on my calendar, but if their email "
    "says they're traveling that day, use their timezone when interpreting "
    "the times. Email me once it's on the calendar."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-18T09:00:00"
MGR_MAIL = "em_mp134_dana"
GOLD_DAY = "2026-05-20"
GOLD_START, GOLD_END = "16:00", "16:30"
TRAP_START = "14:00"
BUSY = "ev_mp134_busy"


def task_mp_134_manager_meet_travel_timezone(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[BUSY] = ev(
        eid=BUSY, title="Vendor review", day=GOLD_DAY,
        start="14:00", end="15:00", day_label="Wed May 20",
        description="Alice is busy 2:00–3:00 PM Eastern Wednesday.",
    )
    world.calendar.events["ev_mp134_thu"] = ev(
        eid="ev_mp134_thu", title="1:1 with Jordan", day="2026-05-21",
        start="09:30", end="10:00", day_label="Thu May 21",
    )
    world.mail.inbox[MGR_MAIL] = mail(
        eid=MGR_MAIL, sender="dana.whitfield@shopmail.com",
        subject="quick meet this week?",
        received_at="2026-05-18T08:20:00", received_label="Mon 8:20 AM",
        body=(
            "I'm traveling Wednesday — I'll be in Denver (Mountain Time) all day. "
            "Can we do 2pm my time for 30 minutes? Tentative is fine.\n\n"
            "— Dana Whitfield"
        ),
    )
    world.mail.inbox["em_mp134_noise"] = mail(
        eid="em_mp134_noise", sender="facilities@shopmail.com",
        subject="Room 4B open Wednesday 2pm Eastern",
        received_at="2026-05-17T12:00:00", received_label="Sun 12:00 PM",
        body="Conference Room 4B is free Wednesday 2:00 PM Eastern. Unrelated to Dana's travel.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_134_manager_meet_travel_timezone,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_cal_events, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(4:00|16:00|mountain|denver|4\s*pm)")

    def _gold(p: Probe) -> bool:
        for e in new_cal_events(p):
            title = (e.title or "").lower()
            if "dana" not in title and "manager" not in title and "meet" not in title:
                continue
            if e.day == GOLD_DAY and e.start == GOLD_START:
                return True
            if e.day == GOLD_DAY and "15:30" <= e.start <= "16:30":
                return True
        return False

    def _trap_et(p: Probe) -> bool:
        for e in new_cal_events(p):
            if e.day == GOLD_DAY and e.start == TRAP_START:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_manager_travel_timezone_email", 0.3, lambda p: mail_read(p, MGR_MAIL), True),
                Milestone("checked_own_calendar", 0.15, viewed_cal, True),
                Milestone("scheduled_converted_mountain_time_slot", 0.4, _gold, True),
                Milestone("emailed_confirmation", 0.15, lambda p: emailed_alice(p, _OK) and _gold(p), True),
                Milestone("booked_2pm_eastern_ignoring_denver_timezone", 0.0, _trap_et, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
