"""cal_005 / team_lunch_thread_reschedule — Mail×Calendar team lunch move.

Mechanism: latest mail-thread message moves Team Lunch from 12:00 to 14:00;
calendar still shows the stale noon slot. Correct = update the calendar event
to 14:00–15:00 and email attendees that it changed. Trap = trust the stale
morning confirmation, or move the event without notifying anyone.

Hub map (bridged): Calendar → google_calendar_mock; Mail → gmail_mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_005/team_lunch_thread_reschedule"
BRIEF_KEY = "cal_005"
BRIEF = (
    "My team lunch got moved to a different time in an email thread, can you "
    "update it on my calendar and let everyone know it's changed?"
)

USER_EMAIL = "alice@shopmail.com"
ATTENDEES = (
    "priya@shopgym.com",
    "joel@shopgym.com",
    "sam@shopgym.com",
)

LUNCH_ID = "ev_cal005_team_lunch"
DECOY_ID = "ev_cal005_1on1"
LUNCH_TITLE = "Team Lunch"
DECOY_TITLE = "1:1 with Priya"

LUNCH_START_SEED, LUNCH_END_SEED = "12:00", "13:00"
LUNCH_START_GOLD, LUNCH_END_GOLD = "14:00", "15:00"
DECOY_START, DECOY_END = "15:00", "15:30"

MAIL_STALE = "em_cal005_stale_noon"
MAIL_LATEST = "em_cal005_moved_2pm"


def task_cal_005_team_lunch_thread_reschedule(seed: int) -> "WorldState":
    """FEASIBLE Mail×Calendar: reschedule Team Lunch from thread + notify.

    Seed (today Thu May 21):
      - Calendar: Team Lunch 12:00–13:00 (stale)
      - Calendar: 1:1 with Priya 15:00–15:30 (leave alone)
      - Mail stale: lunch still at noon
      - Mail latest (thread): lunch moved to 2:00 PM; CC attendees

    Correct: update Team Lunch to 14:00–15:00; email attendees about the change.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.events.clear()
    cal.events[LUNCH_ID] = CalendarEvent(
        id=LUNCH_ID,
        title=LUNCH_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=LUNCH_START_SEED,
        end=LUNCH_END_SEED,
        source="seed",
    )
    cal.events[DECOY_ID] = CalendarEvent(
        id=DECOY_ID,
        title=DECOY_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=DECOY_START,
        end=DECOY_END,
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_STALE] = Email(
        id=MAIL_STALE,
        sender="Priya Chen <priya@shopgym.com>",
        to=USER_EMAIL,
        cc=", ".join(ATTENDEES[1:]),
        subject="Re: Team lunch today",
        body=(
            "Still on for Team Lunch at noon in the big conference room. "
            "See you all then!"
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=True,
        labels=["work"],
    )
    m.inbox[MAIL_LATEST] = Email(
        id=MAIL_LATEST,
        sender="Priya Chen <priya@shopgym.com>",
        to=USER_EMAIL,
        cc=", ".join(ATTENDEES),
        subject="Re: Team lunch today",
        body=(
            "Update — conflict came up this morning. Team Lunch is moved to "
            "2:00 PM (was noon). Same room. Alice, can you update the calendar "
            "and loop everyone?"
        ),
        received_at=f"{SEED_DATE}T10:20:00",
        received_label="10:20 AM",
        read=False,
        labels=["work", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_005_team_lunch_thread_reschedule,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> dict:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return dict(getattr(cal, "events", None) or {}) if cal else {}

    def _lunch_moved(p: Probe) -> bool:
        e = _events(p).get(LUNCH_ID)
        if e is None:
            return False
        return (
            getattr(e, "start", None) == LUNCH_START_GOLD
            and getattr(e, "end", None) == LUNCH_END_GOLD
        )

    def _decoy_intact(p: Probe) -> bool:
        e = _events(p).get(DECOY_ID)
        return (
            e is not None
            and getattr(e, "start", None) == DECOY_START
            and getattr(e, "end", None) == DECOY_END
        )

    def _notified_attendees(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            dest = " ".join(
                [
                    getattr(se, "to", "") or "",
                    getattr(se, "cc", "") or "",
                    getattr(se, "bcc", "") or "",
                ]
            ).lower()
            body = f"{getattr(se, 'subject', '') or ''}\n{getattr(se, 'body', '') or ''}".lower()
            hit_people = sum(1 for a in ATTENDEES if a.lower() in dest)
            time_ok = any(t in body for t in ("2:00", "2pm", "14:00", "2 pm"))
            lunch_ok = "lunch" in body or "team lunch" in body
            if hit_people >= 2 and time_ok and lunch_ok:
                return True
        return False

    def _success(p: Probe) -> bool:
        return _lunch_moved(p) and _decoy_intact(p) and _notified_attendees(p)

    def _left_stale(p: Probe) -> bool:
        e = _events(p).get(LUNCH_ID)
        if e is None:
            return False
        return getattr(e, "start", None) == LUNCH_START_SEED and _notified_attendees(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "lunch_rescheduled_and_notified",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "notified_without_moving",
                    weight=0.0,
                    check=_left_stale,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "decoy_1on1_touched",
                    weight=0.0,
                    check=lambda p: not _decoy_intact(p),
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
