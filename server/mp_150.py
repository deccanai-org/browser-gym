"""mp_150 / unresolved_agreed_meet_email_still_relevant.

April coffee (first week of May) is stale. Helen May 18 thread is still
relevant; Alice busy Thursday afternoon; gold = Mon May 25 morning.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_150/unresolved_agreed_meet_email_still_relevant"
BRIEF_KEY = "mp_150"
BRIEF = (
    "Find an email where I agreed to meet someone but never actually scheduled "
    "it. If that commitment is still relevant, find a mutually reasonable time "
    "and put it on my calendar. Email me once it's set."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T09:00:00"
STALE = "em_mp150_april"
HELEN = "em_mp150_helen"
BUSY = "ev_mp150_thu_pm"
GOLD_DAY = "2026-05-25"


def task_mp_150_unresolved_agreed_meet_email_still_relevant(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[BUSY] = ev(
        eid=BUSY, title="Vendor review", day="2026-05-21",
        start="14:00", end="17:00", day_label="Thu May 21",
        description="Busy this afternoon.",
    )
    world.calendar.events["ev_mp150_fri"] = ev(
        eid="ev_mp150_fri", title="Team sync", day="2026-05-22",
        start="09:00", end="09:30", day_label="Fri May 22",
    )
    world.mail.inbox[STALE] = mail(
        eid=STALE, sender="marcus.lee@shopmail.com",
        subject="coffee first week of May?",
        received_at="2026-04-10T11:00:00", received_label="Apr 10",
        body="Let's get coffee the first week of May — I agreed. (That week is already past.)",
    )
    world.mail.inbox[HELEN] = mail(
        eid=HELEN, sender="helen.vasquez@shopmail.com",
        subject="still want to do that coffee this month?",
        received_at="2026-05-18T16:40:00", received_label="Mon 4:40 PM",
        body=(
            "Still want to do that coffee this month? I'm free Thursday May 21 "
            "afternoon or Monday May 25 morning. You said yes last week but we "
            "never put it on the calendar."
        ),
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_150_unresolved_agreed_meet_email_still_relevant,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_cal_events, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(helen|monday|may\s*25|coffee)")

    def _gold(p: Probe) -> bool:
        for e in new_cal_events(p):
            title = (e.title or "").lower()
            if "helen" not in title and "coffee" not in title:
                continue
            if e.day == GOLD_DAY and e.start < "12:00":
                return True
        return False

    def _stale_or_conflict(p: Probe) -> bool:
        for e in new_cal_events(p):
            if e.day == "2026-05-21" and e.start >= "14:00":
                return True
            if (e.day or "").startswith("2026-05-0"):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_still_relevant_helen_thread", 0.25, lambda p: mail_read(p, HELEN), True),
                Milestone("checked_calendar_conflicts", 0.15, viewed_cal, True),
                Milestone("scheduled_monday_morning_coffee", 0.4, _gold, True),
                Milestone("emailed_confirmation", 0.2, lambda p: emailed_alice(p, _OK) and _gold(p), True),
                Milestone("scheduled_stale_or_conflicted_slot", 0.0, _stale_or_conflict, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
