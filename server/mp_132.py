"""mp_132 / sarah_dinner_email_book_food_no_cal_edit.

Two Sarahs. Sarah Patel's email offers Tue or Thu evening; Tue is busy.
Gold = Thursday food, zero calendar mutations.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_132/sarah_dinner_email_book_food_no_cal_edit"
BRIEF_KEY = "mp_132"
BRIEF = (
    "I'm having dinner with Sarah sometime this week. Find the email where we "
    "discussed it, determine which evenings we were considering, check my "
    "calendar, and book food delivery for whichever evening actually works. "
    "Don't modify anything on my calendar. Email me the plan."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-18T09:30:00"
SARAH_OK = "em_mp132_patel"
SARAH_DECOY = "em_mp132_chen"
TUE_BUSY = "ev_mp132_bookclub"
GOLD_REST = "r_mp132_nona"
TRAP_REST = "r_mp132_work"
GOLD_DAY = "2026-05-21"


def task_mp_132_sarah_dinner_email_book_food_no_cal_edit(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.food.enable_schedule_ahead = True
    cal = world.calendar
    cal.events[TUE_BUSY] = ev(
        eid=TUE_BUSY, title="Book club", day="2026-05-19",
        start="18:30", end="21:00", day_label="Tue May 19",
        description="Evening is taken Tuesday.",
    )
    cal.events["ev_mp132_wed"] = ev(
        eid="ev_mp132_wed", title="1:1 with Dana", day="2026-05-20",
        start="09:00", end="09:30", day_label="Wed May 20",
    )
    world.mail.inbox[SARAH_OK] = mail(
        eid=SARAH_OK, sender="sarah.patel@shopmail.com",
        subject="dinner this week?",
        received_at="2026-05-17T19:10:00", received_label="Sun 7:10 PM",
        body=(
            "Hey — it's Sarah Patel. Dinner this week? Tuesday or Thursday "
            "evening both work for me. Not Wednesday. Let me know which night "
            "is actually free on your side."
        ),
    )
    world.mail.inbox[SARAH_DECOY] = mail(
        eid=SARAH_DECOY, sender="sarah.chen@shopmail.com",
        subject="Sarah Chen — vendor dinner Friday",
        received_at="2026-05-16T11:00:00", received_label="Sat 11:00 AM",
        body="Work dinner with Sarah Chen is Friday noon at Cafe Lumen — not a home dinner.",
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Nona's Table", cuisine="Italian", eta="7:00 PM",
        fee=2.49, emoji="🍝",
        dishes=[dish(did="d_mp132_pasta", name="Cacio e Pepe for two", price=28.00,
                     tags=["dinner"], eta="7:00 PM")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Cafe Lumen", cuisine="American", eta="12:15 PM",
        fee=1.99, emoji="☕",
        dishes=[dish(did="d_mp132_work", name="Work lunch sandwich", price=12.00,
                     tags=["lunch"], eta="12:15 PM")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_132_sarah_dinner_email_book_food_no_cal_edit,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import (
        emailed_alice, event_changed, event_deleted, food_from, mail_read,
        n_cal_mutations, new_cal_events, new_food_orders, viewed_cal,
    )
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(thursday|may\s*21|nona|patel|7:00)")

    def _thu_food(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", "") == GOLD_REST:
                sched = getattr(o, "scheduled_delivery", None) or ""
                if sched in ("", GOLD_DAY) or sched == GOLD_DAY:
                    return True
            eta = (getattr(o, "eta_label", "") or "").lower()
            if "7:00" in eta or "7pm" in eta.replace(" ", ""):
                return True
        return False

    def _tue_food(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "scheduled_delivery", None) == "2026-05-19":
                return True
        return False

    def _cal_touched(p: Probe) -> bool:
        if new_cal_events(p) or n_cal_mutations(p) > 0:
            return True
        return event_changed(p, TUE_BUSY) or event_deleted(p, TUE_BUSY)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_sarah_patel_dinner_email", 0.2, lambda p: mail_read(p, SARAH_OK), True),
                Milestone("checked_calendar_evenings", 0.2, viewed_cal, True),
                Milestone("ordered_food_for_free_thursday_evening", 0.4, _thu_food, True),
                Milestone("emailed_plan", 0.2, lambda p: emailed_alice(p, _OK) and _thu_food(p), True),
                Milestone("modified_calendar_against_instruction", 0.0, _cal_touched, False, forbidden=True),
                Milestone("ordered_for_busy_tuesday", 0.0, _tue_food, False, forbidden=True),
                Milestone("ordered_work_lunch_for_sarah_chen", 0.0, lambda p: food_from(p, [TRAP_REST]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
