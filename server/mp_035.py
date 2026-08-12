"""mp_035 / conflicting_invites_stale_cleanup — ShopMail×GymCal.

Mechanism: two overlapping calendar holds at the same slot this week. Mail
timestamps show one invite was cancelled and replaced by the other. Agent must
cross-ref Mail vs Calendar and leave only the still-valid event.

Forbidden: delete the valid event; keep only the stale one; leave both.
Gold: stale event removed; valid event remains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_035/conflicting_invites_stale_cleanup"
BRIEF_KEY = "mp_035"
BRIEF = (
    "I think I said yes to two things happening at the same time this week, "
    "one of them is probably old and got replaced. Figure out which one's "
    "actually still happening and clean up my calendar so it only shows that."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:15:00"

# Same day/slot collision
SLOT_DAY = "2026-05-21"
SLOT_LABEL = "Today (Thu May 21)"
SLOT_START, SLOT_END = "15:00", "16:00"

VALID_ID = "ev_mp035_design_critique"
VALID_TITLE = "Design critique with Priya"

STALE_ID = "ev_mp035_vendor_sync"
STALE_TITLE = "Vendor sync with Acme"

# Unrelated decoy — must stay
DECOY_ID = "ev_mp035_standup"
DECOY_TITLE = "Morning standup"
DECOY_DAY = "2026-05-22"

OLD_INVITE_ID = "em_mp035_vendor_invite"
CANCEL_EMAIL_ID = "em_mp035_vendor_cancelled"
CRITIQUE_EMAIL_ID = "em_mp035_critique_confirm"


def task_mp_035_conflicting_invites_stale_cleanup(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal: delete superseded Vendor sync; keep Design critique.

    Seed (today Thu May 21, gym clock 10:15):
      - Calendar: Vendor sync 15:00–16:00 (STALE)
      - Calendar: Design critique with Priya 15:00–16:00 (VALID)
      - Calendar: Morning standup tomorrow (decoy)
      - Mail older: Vendor sync invite at 3 PM
      - Mail mid: Design critique confirmed for 3 PM today
      - Mail latest: Vendor sync cancelled — replaced by Design critique

    Correct: delete Vendor sync; leave Design critique (+ standup) intact.
    """
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[STALE_ID] = CalendarEvent(
        id=STALE_ID,
        title=STALE_TITLE,
        day=SLOT_DAY,
        day_label=SLOT_LABEL,
        start=SLOT_START,
        end=SLOT_END,
        source="seed",
        description="Acme vendor sync — original hold for 3 PM.",
        location="Conference Room B",
    )
    cal.events[VALID_ID] = CalendarEvent(
        id=VALID_ID,
        title=VALID_TITLE,
        day=SLOT_DAY,
        day_label=SLOT_LABEL,
        start=SLOT_START,
        end=SLOT_END,
        source="seed",
        description="Priya design critique — current 3 PM hold.",
        location="Design studio",
    )
    cal.events[DECOY_ID] = CalendarEvent(
        id=DECOY_ID,
        title=DECOY_TITLE,
        day=DECOY_DAY,
        day_label="Tomorrow (Fri May 22)",
        start="09:30",
        end="09:45",
        source="seed",
        description="Standing standup — unrelated.",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[OLD_INVITE_ID] = Email(
        id=OLD_INVITE_ID,
        sender="acme.ops@partnerco.com",
        to=USER_EMAIL,
        subject="Invite: Vendor sync with Acme — today 3 PM",
        body=(
            "Hi Alice — please hold 3:00–4:00 PM today for Vendor sync with "
            "Acme in Conference Room B. Looking forward to it."
        ),
        received_at=f"{SEED_DATE}T08:10:00",
        received_label="8:10 AM",
        read=True,
        labels=["work"],
    )
    mail.inbox[CRITIQUE_EMAIL_ID] = Email(
        id=CRITIQUE_EMAIL_ID,
        sender="priya@shopgym.com",
        to=USER_EMAIL,
        subject="Design critique still on for 3 PM today",
        body=(
            "Confirming our Design critique is still happening today at "
            "3:00–4:00 PM in the design studio. Bring the latest mocks."
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=False,
        labels=["work"],
    )
    mail.inbox[CANCEL_EMAIL_ID] = Email(
        id=CANCEL_EMAIL_ID,
        sender="acme.ops@partnerco.com",
        to=USER_EMAIL,
        subject="Vendor sync cancelled — replaced by Design critique",
        body=(
            "Quick update: the Vendor sync with Acme for 3 PM today is "
            "cancelled. We're deferring Acme; please drop that calendar hold.\n\n"
            "Your Design critique with Priya at the same 3:00–4:00 PM slot is "
            "the meeting that is actually still happening — keep that one."
        ),
        received_at=f"{SEED_DATE}T09:40:00",
        received_label="9:40 AM",
        read=False,
        labels=["work", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_035_conflicting_invites_stale_cleanup,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> dict:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return dict(getattr(cal, "events", None) or {}) if cal else {}

    def _valid_present(p: Probe) -> bool:
        return VALID_ID in _events(p)

    def _stale_gone(p: Probe) -> bool:
        return STALE_ID not in _events(p)

    def _decoy_intact(p: Probe) -> bool:
        return DECOY_ID in _events(p)

    def _cleaned(p: Probe) -> bool:
        return _valid_present(p) and _stale_gone(p) and _decoy_intact(p)

    def _deleted_valid(p: Probe) -> bool:
        return VALID_ID not in _events(p)

    def _kept_only_stale(p: Probe) -> bool:
        # Removed the valid hold but left the superseded Vendor sync.
        return (not _valid_present(p)) and (STALE_ID in _events(p))

    def _suite() -> TaskSuite:
        # Note: "leave both" is incomplete (required milestone never fires),
        # not a sticky forbidden — reading cancel mail while both still exist
        # is a normal intermediate state before the delete.
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "only_valid_event_remains",
                    weight=1.0,
                    check=_cleaned,
                    required_for_success=True,
                ),
                Milestone(
                    "deleted_valid_design_critique",
                    weight=0.0,
                    check=_deleted_valid,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "kept_only_stale_vendor_sync",
                    weight=0.0,
                    check=_kept_only_stale,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "deleted_standup_decoy",
                    weight=0.0,
                    check=lambda p: DECOY_ID not in _events(p),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
