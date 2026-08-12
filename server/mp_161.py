"""mp_161 / EVIL late_contradiction_tue_wed_revisit_next_week.

James: Tue 2 works → tentative calendar. Later: actually Wednesday.
Newest: Wednesday won't work — revisit next week. Gold = do not confirm.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_161/late_contradiction_revisit_next_week"
BRIEF_KEY = "mp_161"
BRIEF = (
    "Set up a time to meet with James based on our email thread and put it on "
    "my calendar. Email me once you know what we're doing."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-20T09:00:00"
TUE_TENT = "ev_mp161_tue"
MAIL1 = "em_mp161_tue"
MAIL2 = "em_mp161_wed"
MAIL3 = "em_mp161_revisit"


def task_mp_161_late_contradiction_revisit_next_week(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[TUE_TENT] = ev(
        eid=TUE_TENT, title="James Hale (tentative)",
        day="2026-05-19", start="14:00", end="14:30", day_label="Tue May 19",
        description="Tentative from James's first email. Not confirmed.",
        status="tentative",
    )
    world.calendar.events["ev_mp161_noise"] = ev(
        eid="ev_mp161_noise", title="Team standup",
        day="2026-05-20", start="09:00", end="09:15", day_label="Wed May 20",
    )
    world.mail.inbox[MAIL1] = mail(
        eid=MAIL1, sender="james.hale@shopmail.com",
        subject="time this week?",
        received_at="2026-05-18T10:00:00", received_label="Mon 10:00 AM",
        body="Tuesday at 2 works for me.",
    )
    world.mail.inbox[MAIL2] = mail(
        eid=MAIL2, sender="james.hale@shopmail.com",
        subject="Re: time this week?",
        received_at="2026-05-19T09:10:00", received_label="Tue 9:10 AM",
        body="Actually Wednesday afternoon is better — ignore Tuesday.",
    )
    world.mail.inbox[MAIL3] = mail(
        eid=MAIL3, sender="james.hale@shopmail.com",
        subject="Re: time this week?",
        received_at="2026-05-20T08:20:00", received_label="Wed 8:20 AM",
        body="Wednesday won't work — let's revisit next week. Don't book anything this week.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_161_late_contradiction_revisit_next_week,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_cal_events
    from server.verifiers import Milestone, Probe, TaskSuite

    _WAIT = re.compile(r"(?ix)(next\s+week|revisit|won't\s+work|did\s+not\s+book|didn't\s+book|no\s+time)")

    def _confirmed_this_week(p: Probe) -> bool:
        for e in new_cal_events(p):
            title = (e.title or "").lower()
            if "james" not in title and "hale" not in title:
                continue
            if (e.day or "") in {"2026-05-19", "2026-05-20", "2026-05-21", "2026-05-22"}:
                if (getattr(e, "status", "confirmed") or "").lower() != "cancelled":
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_latest_revisit_email", 0.35, lambda p: mail_read(p, MAIL3), True),
                Milestone("did_not_confirm_this_week_meeting", 0.4, lambda p: (not _confirmed_this_week(p)) and mail_read(p, MAIL3), True),
                Milestone("emailed_that_they_will_revisit_next_week", 0.25, lambda p: emailed_alice(p, _WAIT) and not _confirmed_this_week(p), True),
                Milestone("grabbed_first_or_second_answer", 0.0, _confirmed_this_week, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
