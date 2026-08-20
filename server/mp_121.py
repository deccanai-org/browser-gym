"""mp_121 / dentist_reschedule_email_vs_calendar — Xmail×Xoogle.

Replaces the ephemeral ``diag_email_current_date`` diagnostic (see version
history). Calendar still shows 10:00 AM Thursday; Xmail Dr. Osei update
moves the appointment to 3:30 PM. Gold = trust the email, update Xoogle,
email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_121/dentist_reschedule_email_vs_calendar"
BRIEF_KEY = "mp_121"
BRIEF = (
    "My dentist appointment got moved, don't trust the calendar blindly, "
    "check my email for the real time and update the calendar to match. "
    "Email me once it's fixed."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
THU = "2026-05-21"
DENTIST_ID = "ev_mp121_dentist"
MAIL_ID = "em_mp121_osei"
STALE_START, STALE_END = "10:00", "11:00"
GOLD_START, GOLD_END = "15:30", "16:30"


def task_mp_121_dentist_reschedule_email_vs_calendar(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[DENTIST_ID] = CalendarEvent(
        id=DENTIST_ID,
        title="Dentist — Dr. Osei",
        day=THU,
        day_label="Thu May 21",
        start=STALE_START,
        end=STALE_END,
        source="seed",
        description="Hold from the original booking — may be stale.",
        location="River Dental",
        status="confirmed",
    )
    cal.events["ev_mp121_standup"] = CalendarEvent(
        id="ev_mp121_standup",
        title="Morning standup",
        day=THU,
        day_label="Thu May 21",
        start="09:00",
        end="09:30",
        source="seed",
        status="confirmed",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MAIL_ID] = Email(
        id=MAIL_ID,
        sender="office@riverdental.example",
        to=USER_EMAIL,
        subject="Appointment Update — Dr. Osei",
        body=(
            "Hi Alice,\n\nYour appointment with Dr. Osei has been moved to "
            "3:30 PM Thursday (May 21, 2026). Please ignore the 10:00 AM time "
            "on any earlier reminder.\n\n— River Dental"
        ),
        received_at="2026-05-21T08:40:00",
        received_label="8:40 AM",
        read=False,
        labels=["unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_121_dentist_reschedule_email_vs_calendar,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _CONFIRM = re.compile(
        r"(?ix)(3\s*:?\s*30|15:30|updated|moved|calendar.{0,20}(match|fixed))"
    )

    def _mail_opened(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail and MAIL_ID in (mail.inbox or {}) and mail.inbox[MAIL_ID].read:
            return True
        return _log_has(p, "view_email", email_id=MAIL_ID) or _log_has(
            p, "open_email", email_id=MAIL_ID
        )

    def _cal_gold(p: Probe) -> bool:
        cal = getattr(p.world, "calendar", None) if p.world else None
        e = (cal.events or {}).get(DENTIST_ID) if cal else None
        if e is None:
            return False
        return (
            getattr(e, "day", "") == THU
            and getattr(e, "start", "") == GOLD_START
        )

    def _stale(p: Probe) -> bool:
        cal = getattr(p.world, "calendar", None) if p.world else None
        e = (cal.events or {}).get(DENTIST_ID) if cal else None
        if e is None:
            return False
        return getattr(e, "start", "") == STALE_START

    def _emailed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _CONFIRM.search(text) and _cal_gold(p):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_email_for_new_time",
                    weight=0.3,
                    check=lambda p: _mail_opened(p) or _cal_gold(p),
                    required_for_success=True,
                ),
                Milestone(
                    "updated_calendar_to_match_email",
                    weight=0.4,
                    check=_cal_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_confirmation",
                    weight=0.3,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "left_calendar_showing_stale_time",
                    weight=0.0,
                    check=lambda p: _stale(p) and len(
                        (getattr(getattr(p.world, "mail", None), "sent", None) or {})
                    ) > 0,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
