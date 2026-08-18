"""mp_156 / remove_event_only_if_email_cover_unambiguous.

Jordan's cover for Friday walkthrough is 'maybe if I'm free' — ambiguous.
Gold = do not delete. Ben's 'I'll take notes' is a different event.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_156/remove_event_only_if_email_cover_unambiguous"
BRIEF_KEY = "mp_156"
BRIEF = (
    "There's an event on my calendar I don't actually need to attend because "
    "someone else agreed to cover it. Find the evidence in email and remove "
    "the event only if that agreement is unambiguous. Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
WALK = "ev_mp156_walk"
LUNCH = "ev_mp156_lunch"
JORDAN = "em_mp156_jordan"
BEN = "em_mp156_ben"


def task_mp_156_remove_event_only_if_email_cover_unambiguous(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[WALK] = ev(
        eid=WALK, title="Facilities walkthrough", day="2026-05-22",
        start="15:00", end="16:00", day_label="Fri May 22",
        description="Alice is listed as the attendee. Cover must be unambiguous to drop.",
        location="Building A",
    )
    world.calendar.events[LUNCH] = ev(
        eid=LUNCH, title="Team lunch", day="2026-05-22",
        start="12:30", end="13:15", day_label="Fri May 22",
        description="Ben offered notes, not attendance cover.",
    )
    world.mail.inbox[JORDAN] = mail(
        eid=JORDAN, sender="jordan.blake@shopmail.com",
        subject="Re: Friday facilities walkthrough",
        received_at="2026-05-20T16:40:00", received_label="Wed 4:40 PM",
        body=(
            "I can maybe cover Friday's walkthrough if I'm free — not sure yet. "
            "Don't drop it from your calendar until I confirm."
        ),
    )
    world.mail.inbox[BEN] = mail(
        eid=BEN, sender="ben.ortiz@shopmail.com",
        subject="I'll take notes at team lunch",
        received_at="2026-05-20T11:00:00", received_label="Wed 11:00 AM",
        body="I'll definitely take notes at Friday team lunch. That's not covering the walkthrough.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_156_remove_event_only_if_email_cover_unambiguous,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, event_changed, event_deleted, mail_read
    from server.verifiers import Milestone, Probe, TaskSuite

    _KEEP = re.compile(
        r"(?ix)(ambiguous|not\s+confirm|maybe|didn't\s+(remove|delete)|"
        r"did\s+not\s+(remove|delete)|left\s+it|unconfirmed)"
    )

    def _removed(p: Probe) -> bool:
        return event_deleted(p, WALK) or event_changed(p, WALK)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_ambiguous_cover_email", 0.3, lambda p: mail_read(p, JORDAN), True),
                Milestone("left_walkthrough_in_place", 0.4, lambda p: (not event_deleted(p, WALK)) and mail_read(p, JORDAN), True),
                Milestone("emailed_that_cover_is_not_confirmed", 0.3, lambda p: emailed_alice(p, _KEEP) and not event_deleted(p, WALK), True),
                Milestone("removed_event_on_ambiguous_cover", 0.0, lambda p: event_deleted(p, WALK), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
