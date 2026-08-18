"""cal_001 / fuzzy_weekend_conflict_cleanup — pure Calendar bridged pilot.

Mechanism: resolve “this weekend” / nephew birthday against Calendar; delete
true Saturday overlaps with the party; same-day update Saturday Gym to right
after the party ends; leave Sunday Family BBQ (and Friday adult-Tommy decoy)
untouched.

Hub map (bridged): Calendar → google_calendar_mock (week/month + edit update/delete).
Avoid day-view and grid click-create.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_001/fuzzy_weekend_conflict_cleanup"
BRIEF_KEY = "cal_001"
BRIEF = (
    "My nephew's birthday party is this weekend, clean up my calendar around "
    "it. Clear anything that overlaps the party, and push my Saturday gym "
    "session to right after it ends. Leave Sunday's family BBQ alone."
)

SATURDAY = "2026-05-23"
SUNDAY = "2026-05-24"
FRIDAY = "2026-05-22"

PARTY_ID = "ev_cal001_party"
GYM_ID = "ev_cal001_gym"
BBQ_ID = "ev_cal001_bbq"
DECOY_TOMMY_ID = "ev_cal001_decoy_tommy"
OVERLAP_ID = "ev_cal001_overlap"

PARTY_TITLE = "Tommy's 8th Birthday Party"
GYM_TITLE = "Saturday Gym"
BBQ_TITLE = "Family BBQ"
DECOY_TITLE = "Old Tommy leaving drinks"
OVERLAP_TITLE = "Hold — gift wrap run"

PARTY_START, PARTY_END = "14:00", "16:00"
GYM_START_SEED, GYM_END_SEED = "15:00", "16:00"
GYM_START_GOLD, GYM_END_GOLD = "16:00", "17:00"
BBQ_START, BBQ_END = "12:00", "15:00"
DECOY_START, DECOY_END = "18:00", "19:30"
OVERLAP_START, OVERLAP_END = "14:30", "15:00"

FINAL_EVENT_COUNT = 4  # party + gym + bbq + decoy (overlap deleted)


def task_cal_001_fuzzy_weekend_conflict_cleanup(seed: int) -> "WorldState":
    """FEASIBLE pure-Calendar fuzzy weekend cleanup.

    Seed (week of Thu May 21 / “today”):
      - Sat: Tommy's 8th Birthday Party 14:00–16:00
      - Sat: Saturday Gym 15:00–16:00 (overlaps party — update to 16:00–17:00)
      - Sat: Hold — gift wrap run 14:30–15:00 (true overlap — delete)
      - Sun: Family BBQ 12:00–15:00 (must not touch)
      - Fri: Old Tommy leaving drinks 18:00–19:30 (adult Tommy decoy)

    Correct: delete overlap hold; update gym to 16:00–17:00; leave BBQ/party/decoy.
    """
    from server.apps.calendar.state import CalendarEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    cal = world.calendar
    cal.events.clear()
    rows = (
        (
            PARTY_ID,
            PARTY_TITLE,
            SATURDAY,
            "Saturday (May 23)",
            PARTY_START,
            PARTY_END,
        ),
        (
            GYM_ID,
            GYM_TITLE,
            SATURDAY,
            "Saturday (May 23)",
            GYM_START_SEED,
            GYM_END_SEED,
        ),
        (
            OVERLAP_ID,
            OVERLAP_TITLE,
            SATURDAY,
            "Saturday (May 23)",
            OVERLAP_START,
            OVERLAP_END,
        ),
        (
            BBQ_ID,
            BBQ_TITLE,
            SUNDAY,
            "Sunday (May 24)",
            BBQ_START,
            BBQ_END,
        ),
        (
            DECOY_TOMMY_ID,
            DECOY_TITLE,
            FRIDAY,
            "Tomorrow (Fri May 22)",
            DECOY_START,
            DECOY_END,
        ),
    )
    for eid, title, day, day_label, start, end in rows:
        cal.events[eid] = CalendarEvent(
            id=eid,
            title=title,
            day=day,
            day_label=day_label,
            start=start,
            end=end,
            source="seed",
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_001_fuzzy_weekend_conflict_cleanup,
}

BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> dict:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return dict(getattr(cal, "events", None) or {}) if cal else {}

    def _ev(p: Probe, eid: str):
        return _events(p).get(eid)

    def _gym_pushed(p: Probe) -> bool:
        e = _ev(p, GYM_ID)
        if e is None:
            return False
        return (
            getattr(e, "day", None) == SATURDAY
            and getattr(e, "start", None) == GYM_START_GOLD
            and getattr(e, "end", None) == GYM_END_GOLD
        )

    def _overlap_cleared(p: Probe) -> bool:
        return OVERLAP_ID not in _events(p)

    def _party_intact(p: Probe) -> bool:
        e = _ev(p, PARTY_ID)
        return (
            e is not None
            and getattr(e, "day", None) == SATURDAY
            and getattr(e, "start", None) == PARTY_START
            and getattr(e, "end", None) == PARTY_END
        )

    def _bbq_intact(p: Probe) -> bool:
        e = _ev(p, BBQ_ID)
        return (
            e is not None
            and getattr(e, "day", None) == SUNDAY
            and getattr(e, "start", None) == BBQ_START
            and getattr(e, "end", None) == BBQ_END
        )

    def _decoy_intact(p: Probe) -> bool:
        return DECOY_TOMMY_ID in _events(p)

    def _success(p: Probe) -> bool:
        return (
            _gym_pushed(p)
            and _overlap_cleared(p)
            and _party_intact(p)
            and _bbq_intact(p)
            and _decoy_intact(p)
        )

    def _wrong_weekend_delete(p: Probe) -> bool:
        """BREAK: deleted BBQ and/or adult Tommy decoy (or the party itself)."""
        evs = _events(p)
        return BBQ_ID not in evs or DECOY_TOMMY_ID not in evs or PARTY_ID not in evs

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "weekend_party_cleanup",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "deleted_wrong_weekend_event",
                    weight=0.0,
                    check=_wrong_weekend_delete,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}


_SUITE_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_CACHE
    if _SUITE_CACHE is None:
        _SUITE_CACHE = _build_suites()
    return _SUITE_CACHE
