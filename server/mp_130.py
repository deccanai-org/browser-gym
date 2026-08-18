"""mp_130 / atlas_90min_slot_prior_restaurant_veg_lunch.

Project Atlas thread names attendees + availability. Alice calendar has
personal/focus blocks. Last team lunch was Thai; gold lunch is prior
American veg restaurant, ETA 15 min before the Wed 13:00 slot.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_130/atlas_90min_slot_prior_restaurant_veg_lunch"
BRIEF_KEY = "mp_130"
BRIEF = (
    "Find a 90-minute time next week when everyone from the last email thread "
    "about Project Atlas is available. Don't schedule over anything marked "
    "personal or focus time. Order lunch from a restaurant we've ordered from "
    "before, but not the same cuisine as our last team lunch. Make sure there's "
    "at least one vegetarian option. Schedule the meeting and have the food "
    "arrive 15 minutes beforehand. Email me when it's set."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
GOLD_DAY = "2026-05-27"
GOLD_START, GOLD_END = "13:00", "14:30"
GOLD_REST = "r_mp130_greenfork"
TRAP_THAI = "r_mp130_bangkok"
TRAP_NEW = "r_mp130_newplace"
GOLD_DISH = "d_mp130_veg"
THREAD = "em_mp130_atlas"
DECOY = "em_mp130_atlas_supply"
FOCUS = "ev_mp130_focus"
PERSONAL = "ev_mp130_personal"


def task_mp_130_atlas_90min_slot_prior_restaurant_veg_lunch(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, fitem, food_order, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.food.enable_schedule_ahead = True
    cal = world.calendar
    cal.events[FOCUS] = ev(
        eid=FOCUS, title="Focus time", day="2026-05-26",
        start="09:00", end="12:00", day_label="Tue May 26",
        description="Focus time — do not schedule over this.",
    )
    cal.events[PERSONAL] = ev(
        eid=PERSONAL, title="Personal — dentist", day="2026-05-28",
        start="09:00", end="11:00", day_label="Thu May 28",
        description="Personal calendar. Do not schedule work over this.",
    )
    cal.events["ev_mp130_standup"] = ev(
        eid="ev_mp130_standup", title="Team standup", day=GOLD_DAY,
        start="09:00", end="09:15", day_label="Wed May 27",
    )
    cal.events["ev_mp130_fri"] = ev(
        eid="ev_mp130_fri", title="Vendor sync", day="2026-05-29",
        start="13:00", end="15:00", day_label="Fri May 29",
    )

    world.mail.inbox[THREAD] = mail(
        eid=THREAD, sender="ben.ortiz@shopmail.com",
        subject="Re: Project Atlas — next week working session",
        received_at="2026-05-20T16:40:00", received_label="Wed 4:40 PM",
        body=(
            "Last Atlas thread — we need 90 minutes next week with Ben Ortiz, "
            "Priya Raman, Marcus Lee, and Dana Whitfield.\n\n"
            "Ben: free Tue afternoon after 1, and all day Wednesday.\n"
            "Priya: Wednesday 11:00–16:00 only; traveling Thursday.\n"
            "Marcus: Wednesday all day; Thursday blocked on Contoso.\n"
            "Dana: Wednesday 11:00–15:00; Friday is the Denver flight.\n\n"
            "Please pick one 90-minute window that works for all four."
        ),
    )
    world.mail.inbox[DECOY] = mail(
        eid=DECOY, sender="billing@atlas-supply.example",
        subject="Atlas Supply invoice",
        received_at="2026-05-19T11:00:00", received_label="Tue 11:00 AM",
        body="Your Atlas Supply order #A-8821 is paid. Not a meeting thread.",
    )
    world.mail.inbox["em_mp130_old_atlas"] = mail(
        eid="em_mp130_old_atlas", sender="helen.vasquez@shopmail.com",
        subject="Project Atlas kickoff (April)",
        received_at="2026-04-08T09:00:00", received_label="Apr 8",
        body="Old kickoff with Helen and Jordan only — not the current working group.",
    )

    world.food.restaurants[TRAP_THAI] = restaurant(
        rid=TRAP_THAI, name="Bangkok Bowl", cuisine="Thai", eta="12:45 PM",
        fee=2.49, emoji="🍜",
        dishes=[dish(did="d_mp130_thai", name="Pad Thai", price=14.50, tags=["lunch"],
                     eta="12:45 PM", desc="Last team-lunch cuisine.")],
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Green Fork", cuisine="American", eta="12:45 PM",
        fee=1.99, emoji="🥗",
        dishes=[dish(did=GOLD_DISH, name="Veg Grain Bowl", price=13.75,
                     tags=["lunch", "vegetarian"], eta="12:45 PM",
                     desc="Vegetarian bowl. We've ordered here before.")],
    )
    world.food.restaurants[TRAP_NEW] = restaurant(
        rid=TRAP_NEW, name="New Harbor Poke", cuisine="Hawaiian", eta="12:45 PM",
        fee=3.49, emoji="🐟",
        dishes=[dish(did="d_mp130_poke", name="Poke Bowl", price=16.00, tags=["lunch"],
                     eta="12:45 PM", desc="Never ordered from here.")],
    )
    world.food.orders["FOOD-MP130-TEAM"] = food_order(
        oid="FOOD-MP130-TEAM", rid=TRAP_THAI, rname="Bangkok Bowl",
        items=[fitem(did="d_mp130_thai", rid=TRAP_THAI, name="Pad Thai", price=14.50, qty=4)],
        fee=2.49, placed_at="2026-05-14T11:40:00", eta="12:00 PM",
        note="Team lunch — Thai",
    )
    world.food.orders["FOOD-MP130-SOLO"] = food_order(
        oid="FOOD-MP130-SOLO", rid=GOLD_REST, rname="Green Fork",
        items=[fitem(did=GOLD_DISH, rid=GOLD_REST, name="Veg Grain Bowl", price=13.75)],
        fee=1.99, placed_at="2026-05-08T12:10:00", eta="12:30 PM",
        note="Solo lunch",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_130_atlas_90min_slot_prior_restaurant_veg_lunch,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import (
        alice_blob, emailed_alice, food_from, mail_read, new_cal_events,
        new_food_orders, viewed_cal,
    )
    from server.verifiers import Milestone, Probe, TaskSuite

    _ATLAS = re.compile(r"(?ix)(atlas|ben|priya|marcus|dana)")
    _WED = re.compile(r"(?ix)(wednesday|may\s*27|2026-05-27|13:00|1\s*:?\s*00\s*pm)")

    def _gold_meet(p: Probe) -> bool:
        for e in new_cal_events(p):
            title = (e.title or "").lower()
            if "atlas" not in title and "working" not in title:
                continue
            if e.day == GOLD_DAY and e.start <= "13:30" and e.start >= "11:00":
                # 90 min-ish and not over focus/personal days
                return e.end > e.start
        return False

    def _over_protected(p: Probe) -> bool:
        for e in new_cal_events(p):
            if e.day == "2026-05-26" and e.start < "12:00":
                return True
            if e.day == "2026-05-28" and e.start < "11:00":
                return True
        return False

    def _lunch_ok(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", "") != GOLD_REST:
                continue
            sched = getattr(o, "scheduled_delivery", None) or ""
            eta = (getattr(o, "eta_label", "") or "").lower()
            if sched == GOLD_DAY or "12:45" in eta or "12:30" in eta:
                return True
            if _gold_meet(p):
                return True
        return False

    def _same_cuisine(p: Probe) -> bool:
        return food_from(p, [TRAP_THAI])

    def _new_place(p: Probe) -> bool:
        return food_from(p, [TRAP_NEW])

    def _emailed(p: Probe) -> bool:
        return emailed_alice(p, _ATLAS) and _gold_meet(p) and (
            _WED.search(alice_blob(p)) is not None or _lunch_ok(p)
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_atlas_thread", 0.2, lambda p: mail_read(p, THREAD), True),
                Milestone("checked_calendar_for_protected_blocks", 0.15, viewed_cal, True),
                Milestone("scheduled_90min_all_attendee_slot", 0.3, _gold_meet, True),
                Milestone("ordered_prior_restaurant_not_last_cuisine_veg", 0.25, _lunch_ok, True),
                Milestone("emailed_confirmation", 0.1, _emailed, True),
                Milestone("scheduled_over_personal_or_focus", 0.0, _over_protected, False, forbidden=True),
                Milestone("ordered_same_cuisine_as_last_team_lunch", 0.0, _same_cuisine, False, forbidden=True),
                Milestone("ordered_from_never_before_restaurant", 0.0, _new_place, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
