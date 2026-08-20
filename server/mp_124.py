"""mp_124 / two_person_calendar_named_conflict — Xoogle×Xmail.

Alice has two plausible open slots this week; Priya's email names Tue after 2
or Thu morning. Tue 2:30 overlaps Alice's own block. Gold = Thu morning call,
email both.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_124/two_person_calendar_named_conflict"
BRIEF_KEY = "mp_124"
BRIEF = (
    "Set up a call with Priya sometime this week, avoid double-booking either "
    "of us, check both calendars before picking a time. Email us both once "
    "it's set."
)

USER_EMAIL = "alice@shopmail.com"
PRIYA_EMAIL = "priya@shopmail.com"
GYM_NOW = "2026-05-18T09:30:00"  # Mon
TUE = "2026-05-19"
THU = "2026-05-21"
ALICE_BUSY = "ev_mp124_alice_tue_block"
PRIYA_MAIL = "em_mp124_priya"
GOLD_DAY = THU
GOLD_START, GOLD_END = "09:30", "10:00"
TRAP_START = "14:30"


def task_mp_124_two_person_calendar_named_conflict(seed: int) -> "WorldState":
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
    cal.events[ALICE_BUSY] = CalendarEvent(
        id=ALICE_BUSY,
        title="Vendor review (Alice)",
        day=TUE,
        day_label="Tue May 19",
        start="14:00",
        end="16:00",
        source="seed",
        description="Alice is in a vendor review 2:00–4:00 PM Tuesday.",
        status="confirmed",
    )
    cal.events["ev_mp124_wed"] = CalendarEvent(
        id="ev_mp124_wed",
        title="All-hands workshop",
        day="2026-05-20",
        day_label="Wed May 20",
        start="09:00",
        end="17:00",
        source="seed",
        status="confirmed",
    )
    cal.events["ev_mp124_fri"] = CalendarEvent(
        id="ev_mp124_fri",
        title="1:1 with Dana",
        day="2026-05-22",
        day_label="Fri May 22",
        start="09:00",
        end="09:30",
        source="seed",
        status="confirmed",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[PRIYA_MAIL] = Email(
        id=PRIYA_MAIL,
        sender=PRIYA_EMAIL,
        to=USER_EMAIL,
        subject="Re: time for a call this week",
        body=(
            "I'm free Tue after 2 or Thu morning — those are the only windows "
            "I can do. Pick whichever works on your side.\n\n— Priya"
        ),
        received_at="2026-05-18T08:15:00",
        received_label="Mon 8:15 AM",
        read=False,
        labels=["unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_124_two_person_calendar_named_conflict,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_events(p: Probe) -> list:
        cal = getattr(p.world, "calendar", None) if p.world else None
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.calendar.events or {})
            if init and getattr(init, "calendar", None)
            else {}
        )
        if cal is None:
            return []
        return [
            e
            for eid, e in (cal.events or {}).items()
            if eid not in init_ids
        ]

    def _checked_cal(p: Probe) -> bool:
        return _log_has(p, "viewed_calendar") or _log_has(
            p, "viewed_event_edit"
        ) or "/calendar" in (p.active_tab_url or p.url or "")

    def _checked_priya(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail and PRIYA_MAIL in (mail.inbox or {}) and mail.inbox[PRIYA_MAIL].read:
            return True
        return _log_has(p, "view_email", email_id=PRIYA_MAIL)

    def _gold_call(p: Probe) -> bool:
        for e in _new_events(p):
            title = (getattr(e, "title", "") or "").lower()
            if "priya" not in title and "call" not in title:
                continue
            if getattr(e, "day", "") == GOLD_DAY and getattr(e, "start", "") <= "10:30":
                start = getattr(e, "start", "")
                if start >= "08:00" and start < "12:00":
                    return True
        return False

    def _over_alice(p: Probe) -> bool:
        for e in _new_events(p):
            if getattr(e, "day", "") != TUE:
                continue
            start = getattr(e, "start", "") or ""
            if start >= "14:00" and start < "16:00":
                return True
        return False

    def _outside_priya(p: Probe) -> bool:
        for e in _new_events(p):
            title = (getattr(e, "title", "") or "").lower()
            if "priya" not in title and "call" not in title:
                continue
            day = getattr(e, "day", "")
            start = getattr(e, "start", "") or ""
            tue_ok = day == TUE and start >= "14:00"
            thu_ok = day == GOLD_DAY and start < "12:00"
            if not (tue_ok or thu_ok):
                return True
        return False

    def _emailed_both(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        saw_alice = saw_priya = False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            cc = (getattr(msg, "cc", "") or "").lower()
            blob = f"{to} {cc}"
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if USER_EMAIL in blob or "alice" in blob:
                saw_alice = True
            if PRIYA_EMAIL in blob or "priya" in blob:
                saw_priya = True
            if "priya" in text and ("alice" in blob or USER_EMAIL in blob):
                saw_priya = True
        return saw_alice and saw_priya and _gold_call(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_own_calendar",
                    weight=0.25,
                    check=_checked_cal,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_priyas_stated_availability_from_email",
                    weight=0.25,
                    check=_checked_priya,
                    required_for_success=True,
                ),
                Milestone(
                    "selected_time_with_no_conflict",
                    weight=0.3,
                    check=_gold_call,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_both_parties",
                    weight=0.2,
                    check=_emailed_both,
                    required_for_success=True,
                ),
                Milestone(
                    "scheduled_over_own_calendar_conflict",
                    weight=0.0,
                    check=_over_alice,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "scheduled_outside_priyas_stated_availability",
                    weight=0.0,
                    check=_outside_priya,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
