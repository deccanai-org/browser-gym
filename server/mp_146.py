"""mp_146 / recurring_missed_meeting_move_future_skip_emailed_date.

Ops standup Fri 8:00 conflicts with gym. Priya emailed to keep May 22.
Gold = move May 29 (+ Jun 5) only; leave May 15 and May 22.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_146/recurring_missed_meeting_move_future_skip_emailed_date"
BRIEF_KEY = "mp_146"
BRIEF = (
    "There's a recurring meeting I keep missing. Find it and move future "
    "instances to a time I'm usually available, but don't modify past instances "
    "or any occurrence where someone has already emailed about that specific "
    "date. Email me what you changed."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
PAST = "ev_mp146_may15"
THIS = "ev_mp146_may22"
NEXT = "ev_mp146_may29"
JUN = "ev_mp146_jun5"
GYM_BLK = "ev_mp146_gym"
PRIYA = "em_mp146_priya"
TITLE = "Ops standup"


def task_mp_146_recurring_missed_meeting_move_future_skip_emailed_date(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    cal.events[GYM_BLK] = ev(
        eid=GYM_BLK, title="Gym — usually 8:00–8:45 Fridays",
        day="2026-05-22", start="08:00", end="08:45", day_label="Fri May 22",
        description="Alice is at the gym Friday mornings. Ops standup at 8am is why she keeps missing it.",
    )
    cal.events[PAST] = ev(
        eid=PAST, title=TITLE, day="2026-05-15",
        start="08:00", end="08:30", day_label="Fri May 15",
        description="Past instance. Do not modify.",
    )
    cal.events[THIS] = ev(
        eid=THIS, title=TITLE, day="2026-05-22",
        start="08:00", end="08:30", day_label="Fri May 22",
        description="This Friday — Priya emailed to keep this date at 8:00.",
    )
    cal.events[NEXT] = ev(
        eid=NEXT, title=TITLE, day="2026-05-29",
        start="08:00", end="08:30", day_label="Fri May 29",
        recurring="weekly",
        description="Future instance. Move to 10:00 when Alice is usually free.",
    )
    cal.events[JUN] = ev(
        eid=JUN, title=TITLE, day="2026-06-05",
        start="08:00", end="08:30", day_label="Fri Jun 5",
        description="Future instance.",
    )
    world.mail.inbox[PRIYA] = mail(
        eid=PRIYA, sender="priya.raman@shopmail.com",
        subject="Keep Friday May 22 Ops standup at 8:00",
        received_at="2026-05-20T09:00:00", received_label="Wed 9:00 AM",
        body=(
            "Please keep this Friday May 22 Ops standup at 8:00 — I have a hard "
            "stop after that. Future weeks we can move."
        ),
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_146_recurring_missed_meeting_move_future_skip_emailed_date,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, event_changed, mail_read
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(may\s*29|10:00|future|ops\s+standup)")

    def _future_moved(p: Probe) -> bool:
        nxt = cal_map(p).get(NEXT)
        return bool(nxt and nxt.start >= "10:00" and nxt.day == "2026-05-29")

    def _past_ok(p: Probe) -> bool:
        return (not event_changed(p, PAST)) and _future_moved(p)

    def _this_ok(p: Probe) -> bool:
        return (not event_changed(p, THIS)) and _future_moved(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_priya_keep_may22_email", 0.2, lambda p: mail_read(p, PRIYA), True),
                Milestone("moved_future_instance_off_8am", 0.4, _future_moved, True),
                Milestone("left_past_instance_untouched", 0.15, _past_ok, True),
                Milestone("left_emailed_may22_untouched", 0.15, _this_ok, True),
                Milestone("emailed_what_changed", 0.1, lambda p: emailed_alice(p, _OK) and _future_moved(p), True),
                Milestone("modified_past_or_emailed_date", 0.0, lambda p: event_changed(p, PAST) or event_changed(p, THIS), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
