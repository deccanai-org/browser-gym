"""mp_046 / dentist_triple_reschedule_latest_wins — GymCal×ShopMail.

Mechanism: dentist appointment shuffled across multiple emails; calendar still
shows the oldest slot. Latest confirmation wins. Differentiated from cal_004:
three escalating reschedule emails (not one move + overlap delete), and no
Budget-review collision to clear — just update the dentist event to the latest.

Forbidden: leave the stale morning slot; update to the middle (superseded) time.
Gold: dentist event reflects the latest email time (4:00–5:00 PM).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_046/dentist_triple_reschedule_latest_wins"
BRIEF_KEY = "mp_046"
BRIEF = (
    "My dentist appointment keeps getting shuffled around, there's been a "
    "couple emails about it. Make sure my calendar actually reflects "
    "wherever it landed."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:20:00"

DENTIST_ID = "ev_mp046_dentist"
DENTIST_TITLE = "Dentist checkup"
APPT_DAY = "2026-05-22"  # tomorrow Fri

# Seed calendar = oldest
SEED_START, SEED_END = "09:00", "10:00"
# Middle email (trap if agent stops here)
MID_START, MID_END = "13:00", "14:00"
# Latest email = gold
GOLD_START, GOLD_END = "16:00", "17:00"

MAIL_OLD = "em_mp046_old_9am"
MAIL_MID = "em_mp046_mid_1pm"
MAIL_LATEST = "em_mp046_latest_4pm"


def task_mp_046_dentist_triple_reschedule_latest_wins(seed: int) -> "WorldState":
    """FEASIBLE Cal×Mail: three dentist reschedule emails; latest (4pm) wins.

    Seed:
      - Calendar tomorrow: Dentist checkup still at 9:00–10:00 (oldest)
      - Mail oldest: confirmed 9:00 AM Friday
      - Mail middle: moved to 1:00 PM Friday
      - Mail latest: moved again to 4:00 PM Friday
      - Unrelated standup decoy stays
    Correct: update dentist to 16:00–17:00; leave decoys.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.mail.state import Email, SEED_DATE
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
        title=DENTIST_TITLE,
        day=APPT_DAY,
        day_label="Tomorrow (Fri May 22)",
        start=SEED_START,
        end=SEED_END,
        source="seed",
        description="Stale morning hold — check latest River Dental emails.",
        location="River Dental",
    )
    cal.events["ev_mp046_standup"] = CalendarEvent(
        id="ev_mp046_standup",
        title="Morning standup",
        day=APPT_DAY,
        day_label="Tomorrow (Fri May 22)",
        start="09:30",
        end="09:45",
        source="seed",
        description="Unrelated — leave intact.",
    )
    cal.events["ev_mp046_today_note"] = CalendarEvent(
        id="ev_mp046_today_note",
        title="Teeth whitening brochure pickup",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="16:00",
        end="16:30",
        source="seed",
        description="Same clock as gold dentist, wrong day — leave intact.",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MAIL_OLD] = Email(
        id=MAIL_OLD,
        sender="frontdesk@riverdental.example.com",
        to=USER_EMAIL,
        subject="Appointment confirmed — Friday 9:00 AM",
        body=(
            "Hi Alice — your dentist checkup is confirmed for Friday May 22 "
            "at 9:00–10:00 AM at River Dental."
        ),
        received_at="2026-05-18T10:00:00",
        received_label="May 18",
        read=True,
        labels=["personal"],
    )
    mail.inbox[MAIL_MID] = Email(
        id=MAIL_MID,
        sender="frontdesk@riverdental.example.com",
        to=USER_EMAIL,
        subject="Update: dentist moved to Friday 1:00 PM",
        body=(
            "Quick change — your checkup is now Friday May 22 at 1:00–2:00 PM "
            "(was 9:00 AM). Please update your calendar."
        ),
        received_at="2026-05-19T15:30:00",
        received_label="May 19",
        read=True,
        labels=["personal"],
    )
    mail.inbox[MAIL_LATEST] = Email(
        id=MAIL_LATEST,
        sender="frontdesk@riverdental.example.com",
        to=USER_EMAIL,
        subject="Final update: dentist now Friday 4:00 PM",
        body=(
            "Sorry for another shuffle — final time is Friday May 22 at "
            "4:00–5:00 PM. Please ignore the earlier 9:00 AM and 1:00 PM notes; "
            "4:00 PM is where it landed."
        ),
        received_at=f"{SEED_DATE}T09:40:00",
        received_label="9:40 AM",
        read=False,
        labels=["personal", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_046_dentist_triple_reschedule_latest_wins,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> dict:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return dict(getattr(cal, "events", None) or {}) if cal else {}

    def _dentist(p: Probe):
        return _events(p).get(DENTIST_ID)

    def _at_gold(p: Probe) -> bool:
        e = _dentist(p)
        if not e:
            return False
        return (
            getattr(e, "day", "") == APPT_DAY
            and getattr(e, "start", "") == GOLD_START
            and getattr(e, "end", "") == GOLD_END
        )

    def _at_middle(p: Probe) -> bool:
        e = _dentist(p)
        if not e:
            return False
        return getattr(e, "start", "") == MID_START

    def _still_stale_morning(p: Probe) -> bool:
        e = _dentist(p)
        if not e:
            return False
        return getattr(e, "start", "") == SEED_START

    def _deleted_decoy(p: Probe) -> bool:
        ev = _events(p)
        return ("ev_mp046_standup" not in ev) or ("ev_mp046_today_note" not in ev)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "dentist_matches_latest_4pm",
                    weight=1.0,
                    check=_at_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "updated_to_superseded_1pm",
                    weight=0.0,
                    check=_at_middle,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "deleted_unrelated_decoy",
                    weight=0.0,
                    check=_deleted_decoy,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
