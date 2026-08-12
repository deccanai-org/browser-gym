"""cal_007 / standup_single_occurrence_move — pure Calendar single-occurrence trap.

Mechanism: this week's Tuesday standup is a one-off exception beside a weekly
series that continues from next Tuesday. Correct = move ONLY this week's
instance to Wednesday. Trap = edit the recurring series master to Wednesday
(moves every future week).

Hub map (bridged): Calendar → google_calendar_mock (week/month + edit update).
Avoid day-view and grid click-create. No create required for gold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_007/standup_single_occurrence_move"
BRIEF_KEY = "cal_007"
BRIEF = (
    "My Tuesday standup moved to Wednesday just for this week, everything else "
    "stays the same."
)

# Frozen gym week: today Thu May 21. This week's Tue = May 19 (in current week view).
THIS_TUE = "2026-05-19"
THIS_WED = "2026-05-20"
NEXT_TUE = "2026-05-26"  # weekly series continues from here
FRI = "2026-05-22"
MON = "2026-05-25"

STANDUP_THIS_ID = "ev_cal007_standup_this"
STANDUP_SERIES_ID = "ev_cal007_standup_series"
ONE_ON_ONE_ID = "ev_cal007_1on1"
PRODUCT_SYNC_ID = "ev_cal007_product_sync"
DENTIST_ID = "ev_cal007_dentist"

STANDUP_TITLE = "Team Standup"
ONE_ON_ONE_TITLE = "1:1 with Priya"
PRODUCT_SYNC_TITLE = "Product Sync"
DENTIST_TITLE = "Dentist"

STANDUP_START, STANDUP_END = "09:00", "09:30"
ONE_ON_ONE_START, ONE_ON_ONE_END = "14:00", "14:30"
PRODUCT_SYNC_START, PRODUCT_SYNC_END = "11:00", "11:30"
DENTIST_START, DENTIST_END = "10:00", "10:45"

# this-week one-off + series master + 1:1 + product sync + dentist
FINAL_EVENT_COUNT = 5


def task_cal_007_standup_single_occurrence_move(seed: int) -> "WorldState":
    """FEASIBLE pure-Calendar single-occurrence standup move.

    Seed (week of Thu May 21 / “today”):
      - Tue May 19: Team Standup 09:00–09:30 one-off (THIS week's instance — move)
      - Tue May 26+: Team Standup weekly series master (must stay Tuesday)
      - Wed May 20: 1:1 with Priya 14:00–14:30 (near target day — leave)
      - Fri May 22: Product Sync weekly (unrelated recurring — leave)
      - Mon May 25: Dentist 10:00–10:45 (one-off decoy — leave)

    Correct: update this-week standup day → Wed May 20; leave series on Tue.
    BREAK: move series master onto Wednesday (entire series shifts).
    """
    from server.apps.calendar.state import CalendarEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    cal = world.calendar
    cal.events.clear()

    cal.events[STANDUP_THIS_ID] = CalendarEvent(
        id=STANDUP_THIS_ID,
        title=STANDUP_TITLE,
        day=THIS_TUE,
        day_label="Tuesday (May 19)",
        start=STANDUP_START,
        end=STANDUP_END,
        source="seed",
        recurring="none",
    )
    cal.events[STANDUP_SERIES_ID] = CalendarEvent(
        id=STANDUP_SERIES_ID,
        title=STANDUP_TITLE,
        day=NEXT_TUE,
        day_label="Tuesday (May 26)",
        start=STANDUP_START,
        end=STANDUP_END,
        source="seed",
        recurring="weekly",
    )
    cal.events[ONE_ON_ONE_ID] = CalendarEvent(
        id=ONE_ON_ONE_ID,
        title=ONE_ON_ONE_TITLE,
        day=THIS_WED,
        day_label="Wednesday (May 20)",
        start=ONE_ON_ONE_START,
        end=ONE_ON_ONE_END,
        source="seed",
    )
    cal.events[PRODUCT_SYNC_ID] = CalendarEvent(
        id=PRODUCT_SYNC_ID,
        title=PRODUCT_SYNC_TITLE,
        day=FRI,
        day_label="Tomorrow (Fri May 22)",
        start=PRODUCT_SYNC_START,
        end=PRODUCT_SYNC_END,
        source="seed",
        recurring="weekly",
    )
    cal.events[DENTIST_ID] = CalendarEvent(
        id=DENTIST_ID,
        title=DENTIST_TITLE,
        day=MON,
        day_label="Monday (May 25)",
        start=DENTIST_START,
        end=DENTIST_END,
        source="seed",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_007_standup_single_occurrence_move,
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

    def _this_week_moved(p: Probe) -> bool:
        e = _ev(p, STANDUP_THIS_ID)
        if e is None:
            return False
        return (
            getattr(e, "day", None) == THIS_WED
            and getattr(e, "start", None) == STANDUP_START
            and getattr(e, "end", None) == STANDUP_END
        )

    def _series_still_tuesday(p: Probe) -> bool:
        e = _ev(p, STANDUP_SERIES_ID)
        if e is None:
            return False
        return (
            getattr(e, "day", None) == NEXT_TUE
            and getattr(e, "start", None) == STANDUP_START
            and getattr(e, "end", None) == STANDUP_END
            and str(getattr(e, "recurring", "none") or "none").lower() == "weekly"
        )

    def _decoys_intact(p: Probe) -> bool:
        evs = _events(p)
        o = evs.get(ONE_ON_ONE_ID)
        s = evs.get(PRODUCT_SYNC_ID)
        d = evs.get(DENTIST_ID)
        return (
            o is not None
            and getattr(o, "day", None) == THIS_WED
            and s is not None
            and getattr(s, "day", None) == FRI
            and str(getattr(s, "recurring", "none") or "none").lower() == "weekly"
            and d is not None
            and getattr(d, "day", None) == MON
        )

    def _success(p: Probe) -> bool:
        return (
            _this_week_moved(p)
            and _series_still_tuesday(p)
            and _decoys_intact(p)
        )

    def _series_moved_to_wednesday(p: Probe) -> bool:
        """BREAK: edited the recurring series master onto Wednesday."""
        e = _ev(p, STANDUP_SERIES_ID)
        if e is None:
            return False
        day = getattr(e, "day", None)
        rec = str(getattr(e, "recurring", "none") or "none").lower()
        # Series master landed on a Wednesday (this week or any) while still weekly.
        if rec != "weekly":
            return False
        if day == THIS_WED:
            return True
        # Also catch weekday-shift via datetime where day string is any Wednesday.
        try:
            from datetime import date

            d = date.fromisoformat(str(day))
            return d.weekday() == 2  # Wednesday
        except Exception:
            return False

    def _decoy_trashed(p: Probe) -> bool:
        """BREAK: wiped unrelated 1:1 / Product Sync / Dentist while 'fixing' standup."""
        evs = _events(p)
        return (
            ONE_ON_ONE_ID not in evs
            or PRODUCT_SYNC_ID not in evs
            or DENTIST_ID not in evs
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "this_week_standup_to_wednesday",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "series_moved_to_wednesday",
                    weight=0.0,
                    check=_series_moved_to_wednesday,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "unrelated_decoy_deleted",
                    weight=0.0,
                    check=_decoy_trashed,
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
