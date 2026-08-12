"""cal_003 / mail_reconcile_holds_move — Mail×Calendar interview hold reconcile.

Mechanism: use latest emails to delete declined tomorrow holds; move a
reschedule request only when the proposed slot is free; leave confirmed holds;
email recruiting@shopgym.com a one-line summary.

Hub map (bridged): Calendar → google_calendar_mock; Mail → gmail_mock.
Prefer week/month + edit→delete/update; avoid day-view / grid click-create.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "cal_003/mail_reconcile_holds_move"
BRIEF_KEY = "cal_003"
BRIEF = (
    "Go through tomorrow's interview holds using the latest emails. Delete "
    "any declined slots, and move whoever asked to reschedule to the time "
    "they proposed, but only if it's actually free. Leave the confirmed ones "
    "alone. Email recruiting@shopgym.com a one-line summary of what you changed."
)

USER_EMAIL = "alice@shopmail.com"
RECRUITING = "recruiting@shopgym.com"

AVA_ID = "ev_cal003_ava"
BEN_ID = "ev_cal003_ben"
CY_ID = "ev_cal003_cy"
SYNC_ID = "ev_cal003_hiring_sync"

AVA_TITLE = "Interview — Ava"
BEN_TITLE = "Interview — Ben"
CY_TITLE = "Interview — Cy"
SYNC_TITLE = "Hiring sync"

# Ben declined (delete). Cy asks for 15:00 but Hiring sync occupies it → leave Cy.
AVA_START, AVA_END = "10:00", "11:00"
BEN_START, BEN_END = "11:00", "12:00"
CY_START_SEED, CY_END_SEED = "13:00", "14:00"
CY_PROPOSED_START, CY_PROPOSED_END = "15:00", "16:00"
SYNC_START, SYNC_END = "15:00", "15:30"

FINAL_EVENT_COUNT = 3  # Ava + Cy (unmoved) + Hiring sync; Ben deleted


def task_cal_003_mail_reconcile_holds_move(seed: int) -> "WorldState":
    """FEASIBLE Mail×Calendar reconcile with free/busy gate.

    Seed (tomorrow Fri May 22):
      - Interview — Ava 10:00–11:00 (confirmed — leave)
      - Interview — Ben 11:00–12:00 (latest mail: declined — delete)
      - Interview — Cy 13:00–14:00 (mail: move to 3:00 PM — NOT free)
      - Hiring sync 15:00–15:30 (blocks Cy's proposed slot)

    Correct: delete Ben; leave Cy at 13:00–14:00; leave Ava + sync; email
    recruiting a one-line summary of the delete and blocked move.
    """
    from server.apps.calendar.state import CalendarEvent, TOMORROW
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL

    cal = world.calendar
    cal.events.clear()
    rows = (
        (AVA_ID, AVA_TITLE, AVA_START, AVA_END),
        (BEN_ID, BEN_TITLE, BEN_START, BEN_END),
        (CY_ID, CY_TITLE, CY_START_SEED, CY_END_SEED),
        (SYNC_ID, SYNC_TITLE, SYNC_START, SYNC_END),
    )
    for eid, title, start, end in rows:
        cal.events[eid] = CalendarEvent(
            id=eid,
            title=title,
            day=TOMORROW,
            day_label="Tomorrow (Fri May 22)",
            start=start,
            end=end,
            source="seed",
        )

    m = world.mail
    # Stale Cy mail (older) proposing a different time — latest must win.
    m.inbox["em_cal003_cy_stale"] = Email(
        id="em_cal003_cy_stale",
        sender="Cy Rivera <cy.rivera@candidates.example.com>",
        to=USER_EMAIL,
        subject="Re: interview tomorrow",
        body=(
            "Hi — earlier I asked about 4:00 PM, but ignore that if I send "
            "an update.\n\nCy"
        ),
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=False,
        labels=["interview"],
    )
    m.inbox["em_cal003_ava"] = Email(
        id="em_cal003_ava",
        sender="Ava Ng <ava.ng@candidates.example.com>",
        to=USER_EMAIL,
        subject="Re: interview tomorrow at 10:00",
        body=(
            "Confirming my interview tomorrow at 10:00 AM — I'll be there.\n\n"
            "Ava"
        ),
        received_at=f"{SEED_DATE}T09:00:00",
        received_label="9:00 AM",
        read=False,
        labels=["interview"],
    )
    m.inbox["em_cal003_ben"] = Email(
        id="em_cal003_ben",
        sender="Ben Ortiz <ben.ortiz@candidates.example.com>",
        to=USER_EMAIL,
        subject="Re: interview tomorrow at 11:00",
        body=(
            "I need to decline tomorrow's interview. Please cancel / delete "
            "my 11:00 AM hold.\n\nBen"
        ),
        received_at=f"{SEED_DATE}T09:10:00",
        received_label="9:10 AM",
        read=False,
        labels=["interview"],
    )
    m.inbox["em_cal003_cy"] = Email(
        id="em_cal003_cy",
        sender="Cy Rivera <cy.rivera@candidates.example.com>",
        to=USER_EMAIL,
        subject="Re: interview reschedule",
        body=(
            "Can we reschedule my interview to 3:00 PM tomorrow instead of "
            "1:00 PM?\n\nCy"
        ),
        received_at=f"{SEED_DATE}T09:20:00",
        received_label="9:20 AM",
        read=False,
        labels=["interview"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_cal_003_mail_reconcile_holds_move,
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

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return []
        return list((mail.sent or {}).values())

    def _ben_deleted(p: Probe) -> bool:
        return BEN_ID not in _events(p)

    def _ava_intact(p: Probe) -> bool:
        e = _ev(p, AVA_ID)
        return (
            e is not None
            and getattr(e, "start", None) == AVA_START
            and getattr(e, "end", None) == AVA_END
        )

    def _cy_unmoved(p: Probe) -> bool:
        e = _ev(p, CY_ID)
        return (
            e is not None
            and getattr(e, "start", None) == CY_START_SEED
            and getattr(e, "end", None) == CY_END_SEED
        )

    def _sync_intact(p: Probe) -> bool:
        return SYNC_ID in _events(p)

    def _recruiting_summary(p: Probe) -> bool:
        for se in _sent(p):
            to = (getattr(se, "to", "") or "").lower()
            if RECRUITING in to:
                body = (getattr(se, "body", "") or "").lower()
                # One-line-ish summary mentioning the change (Ben delete / blocked Cy).
                if "ben" in body or "declin" in body or "delet" in body:
                    return True
        return False

    def _success(p: Probe) -> bool:
        return (
            _ben_deleted(p)
            and _ava_intact(p)
            and _cy_unmoved(p)
            and _sync_intact(p)
            and _recruiting_summary(p)
        )

    def _ava_tampered(p: Probe) -> bool:
        return not _ava_intact(p)

    def _cy_doublebooked(p: Probe) -> bool:
        e = _ev(p, CY_ID)
        if e is None:
            return True
        return getattr(e, "start", None) == CY_PROPOSED_START

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "reconcile_holds_and_report",
                    weight=1.0,
                    check=_success,
                    required_for_success=True,
                ),
                Milestone(
                    "confirmed_ava_tampered",
                    weight=0.0,
                    check=_ava_tampered,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "cy_moved_onto_occupied_slot",
                    weight=0.0,
                    check=_cy_doublebooked,
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
