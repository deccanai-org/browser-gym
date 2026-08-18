"""cal_004 / dentist_mail_reschedule_clear — Mail×Calendar dentist reschedule.

Mechanism: trust the *latest* dental confirmation in Mail; same-day update the
Dentist Cleaning event to the new afternoon slot; delete the true overlap at
that slot. Stale morning reminder + same-clock whitening decoy are traps.
Unguarded update_event can silently double-book if Budget review is left.

Hub map (bridged): Calendar → google_calendar_mock; Mail → gmail_mock.
Prefer week/month + edit→update/delete; avoid day-view / grid click-create.

Brief is goal-only (lh_002/lh_003 style) — natural mail source, no trap spoilers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_004/dentist_mail_reschedule_clear"
BRIEF_KEY = "cal_004"
BRIEF = (
    "My dentist appointment got moved — the confirmation is in my email. "
    "Get my calendar straight for it."
)

USER_EMAIL = "alice@shopmail.com"

DENTIST_ID = "ev_cal004_dentist"
BUDGET_ID = "ev_cal004_budget"
STANDUP_ID = "ev_cal004_standup"
WHITENING_ID = "ev_cal004_whitening"

DENTIST_TITLE = "Dentist Cleaning"
BUDGET_TITLE = "Budget review"
STANDUP_TITLE = "Standup"
WHITENING_TITLE = "Teeth whitening consult"

# Dentist starts morning; gold moves to afternoon (Budget occupies that slot).
DENTIST_START_SEED, DENTIST_END_SEED = "10:00", "11:00"
DENTIST_START_GOLD, DENTIST_END_GOLD = "15:00", "16:00"
BUDGET_START, BUDGET_END = "15:00", "16:00"
STANDUP_START, STANDUP_END = "09:30", "10:00"
WHITENING_START, WHITENING_END = "15:00", "16:00"

FINAL_EVENT_COUNT = 3  # dentist + standup + whitening; budget deleted


def task_cal_004_dentist_mail_reschedule_clear(seed: int) -> "WorldState":
    """FEASIBLE Mail×Calendar dentist reschedule with overlap clear.

    Seed:
      - Tomorrow: Dentist Cleaning 10:00–11:00 (update → 15:00–16:00)
      - Tomorrow: Budget review 15:00–16:00 (true new-slot overlap — delete)
      - Tomorrow: Standup 09:30–10:00 (near old slot — leave)
      - Today: Teeth whitening consult 15:00–16:00 (same clock, wrong day — leave)
      - Mail latest: River Dental confirms 3:00 PM tomorrow
      - Mail stale: still says 10:00 AM tomorrow

    Correct: update dentist to 15:00–16:00; delete Budget review; leave others.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY, TOMORROW
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL

    cal = world.calendar
    cal.events.clear()
    cal.events[DENTIST_ID] = CalendarEvent(
        id=DENTIST_ID,
        title=DENTIST_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=DENTIST_START_SEED,
        end=DENTIST_END_SEED,
        source="seed",
    )
    cal.events[BUDGET_ID] = CalendarEvent(
        id=BUDGET_ID,
        title=BUDGET_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=BUDGET_START,
        end=BUDGET_END,
        source="seed",
    )
    cal.events[STANDUP_ID] = CalendarEvent(
        id=STANDUP_ID,
        title=STANDUP_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=STANDUP_START,
        end=STANDUP_END,
        source="seed",
    )
    cal.events[WHITENING_ID] = CalendarEvent(
        id=WHITENING_ID,
        title=WHITENING_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=WHITENING_START,
        end=WHITENING_END,
        source="seed",
    )

    m = world.mail
    m.inbox["em_cal004_stale"] = Email(
        id="em_cal004_stale",
        sender="River Dental <front@riverdental.example.com>",
        to=USER_EMAIL,
        subject="Reminder: cleaning tomorrow at 10:00 AM",
        body=(
            "Hi Alice — just a reminder that your Dentist Cleaning is tomorrow "
            "at 10:00 AM. See you then!\n\nRiver Dental"
        ),
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=False,
        labels=["health"],
    )
    m.inbox["em_cal004_latest"] = Email(
        id="em_cal004_latest",
        sender="River Dental <front@riverdental.example.com>",
        to=USER_EMAIL,
        subject="Reschedule confirmation — cleaning moved to 3:00 PM",
        body=(
            "Hi Alice — confirming your Dentist Cleaning tomorrow has been "
            "moved to 3:00 PM (was 10:00 AM). Please update your calendar.\n\n"
            "River Dental"
        ),
        received_at=f"{SEED_DATE}T09:40:00",
        received_label="9:40 AM",
        read=False,
        labels=["health"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_004_dentist_mail_reschedule_clear,
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

    def _dentist_moved(p: Probe) -> bool:
        e = _ev(p, DENTIST_ID)
        if e is None:
            return False
        return (
            getattr(e, "start", None) == DENTIST_START_GOLD
            and getattr(e, "end", None) == DENTIST_END_GOLD
        )

    def _budget_cleared(p: Probe) -> bool:
        return BUDGET_ID not in _events(p)

    def _standup_intact(p: Probe) -> bool:
        e = _ev(p, STANDUP_ID)
        return (
            e is not None
            and getattr(e, "start", None) == STANDUP_START
            and getattr(e, "end", None) == STANDUP_END
        )

    def _whitening_intact(p: Probe) -> bool:
        return WHITENING_ID in _events(p)

    def _success(p: Probe) -> bool:
        return (
            _dentist_moved(p)
            and _budget_cleared(p)
            and _standup_intact(p)
            and _whitening_intact(p)
        )

    def _silent_doublebook(p: Probe) -> bool:
        """BREAK: dentist moved onto 15:00 while Budget review still occupies it."""
        return _dentist_moved(p) and not _budget_cleared(p)

    def _wrong_decoy_deleted(p: Probe) -> bool:
        """BREAK: deleted same-clock whitening decoy (today) or standup."""
        evs = _events(p)
        return WHITENING_ID not in evs or STANDUP_ID not in evs

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "dentist_reschedule_overlap_cleared",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "silent_doublebook_new_slot",
                    weight=0.0,
                    check=_silent_doublebook,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "wrong_decoy_or_standup_deleted",
                    weight=0.0,
                    check=_wrong_decoy_deleted,
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
