"""mp_152 / packed_tomorrow_min_calendar_moves_for_lunch.

Priya 12:00–13:00 is the single blocker. Gold = move only that event.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_152/packed_tomorrow_min_calendar_moves_for_lunch"
BRIEF_KEY = "mp_152"
BRIEF = (
    "Tomorrow is packed. Reschedule anything that doesn't need to happen "
    "tomorrow so I have time for lunch, but make the minimum number of "
    "calendar changes possible. Email me what you moved."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T18:00:00"
PRIYA = "ev_mp152_priya"
IDS = {
    "stand": "ev_mp152_stand",
    "jordan": "ev_mp152_jordan",
    "vendor": "ev_mp152_vendor",
    "priya": PRIYA,
    "marcus": "ev_mp152_marcus",
    "qbr": "ev_mp152_qbr",
}


def task_mp_152_packed_tomorrow_min_calendar_moves_for_lunch(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    rows = (
        (IDS["stand"], "Team standup", "09:00", "10:00", "Recurring standup — needs to stay tomorrow."),
        (IDS["jordan"], "1:1 with Jordan", "10:00", "11:00", "Needed tomorrow."),
        (IDS["vendor"], "Northwind vendor call", "11:00", "12:00", "External — keep tomorrow."),
        (IDS["priya"], "Quick sync Priya", "12:00", "13:00", "Internal optional. Move this one for lunch."),
        (IDS["marcus"], "1:1 with Marcus", "13:00", "14:00", "Needed tomorrow."),
        (IDS["qbr"], "QBR", "14:00", "15:00", "Needed tomorrow."),
    )
    for eid, title, start, end, desc in rows:
        world.calendar.events[eid] = ev(
            eid=eid, title=title, day="2026-05-22",
            start=start, end=end, day_label="Fri May 22", description=desc,
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_152_packed_tomorrow_min_calendar_moves_for_lunch,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import cal_map, emailed_alice, event_changed, n_cal_mutations, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(priya|lunch|minimum|one\s+change)")

    def _priya_moved(p: Probe) -> bool:
        e = cal_map(p).get(PRIYA)
        if e is None:
            return True
        return event_changed(p, PRIYA) and not (e.day == "2026-05-22" and e.start == "12:00")

    def _min(p: Probe) -> bool:
        return n_cal_mutations(p) == 1 and _priya_moved(p)

    def _too_many(p: Probe) -> bool:
        return n_cal_mutations(p) > 2

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_packed_tomorrow", 0.2, viewed_cal, True),
                Milestone("moved_only_optional_priya_sync", 0.5, _min, True),
                Milestone("emailed_what_moved", 0.3, lambda p: emailed_alice(p, _OK) and _priya_moved(p), True),
                Milestone("made_more_than_two_calendar_changes", 0.0, _too_many, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
