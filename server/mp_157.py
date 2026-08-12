"""mp_157 / lunch_least_recent_of_three_most_emailed.

Most emailed: Priya, Ben, Marcus. Least-recent meeting is Marcus (Apr 10).
Both like Harbor Sushi. Gold = lunch with Marcus from Harbor Sushi.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_157/lunch_least_recent_of_three_most_emailed"
BRIEF_KEY = "mp_157"
BRIEF = (
    "I want lunch with whoever I haven't met with in the longest time among "
    "the three people I email most frequently. Figure out who that is, find "
    "an open day, and order from somewhere we both appear to like. Email me "
    "the plan."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
GOLD_REST = "r_mp157_sushi"
TRAP_REST = "r_mp157_thai"
OPEN = "2026-05-22"


def task_mp_157_lunch_least_recent_of_three_most_emailed(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, fitem, food_order, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    cal.events["ev_mp157_priya"] = ev(
        eid="ev_mp157_priya", title="1:1 with Priya Raman",
        day="2026-05-20", start="11:00", end="11:30", day_label="Wed May 20",
    )
    cal.events["ev_mp157_ben"] = ev(
        eid="ev_mp157_ben", title="1:1 with Ben Ortiz",
        day="2026-05-18", start="15:00", end="15:30", day_label="Mon May 18",
    )
    cal.events["ev_mp157_marcus"] = ev(
        eid="ev_mp157_marcus", title="1:1 with Marcus Lee",
        day="2026-04-10", start="10:00", end="10:30", day_label="Fri Apr 10",
        description="Oldest of the three frequent contacts.",
    )
    cal.events["ev_mp157_dana"] = ev(
        eid="ev_mp157_dana", title="1:1 with Dana Whitfield",
        day="2026-03-02", start="09:00", end="09:30", day_label="Mon Mar 2",
        description="Dana is not in the top-3 emailed set.",
    )
    # Frequency: Priya 4, Ben 3, Marcus 3, Dana 1
    people = [
        ("priya.raman@shopmail.com", "Priya", 4, "2026-05-1"),
        ("ben.ortiz@shopmail.com", "Ben", 3, "2026-05-1"),
        ("marcus.lee@shopmail.com", "Marcus", 3, "2026-05-0"),
        ("dana.whitfield@shopmail.com", "Dana", 1, "2026-04-2"),
    ]
    n = 0
    for addr, name, count, prefix in people:
        for i in range(count):
            n += 1
            eid = f"em_mp157_{name.lower()}_{i}"
            world.mail.inbox[eid] = mail(
                eid=eid, sender=addr,
                subject=f"thread with {name} #{i+1}",
                received_at=f"{prefix}{i+1}T10:00:00",
                received_label=f"{name} mail {i+1}",
                body=f"Work thread with {name}. Counted toward email frequency.",
            )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Harbor Sushi", cuisine="Japanese", eta="12:15 PM",
        fee=2.49, emoji="🍣",
        dishes=[dish(did="d_mp157_sushi", name="Salmon avocado roll", price=14.00,
                     tags=["lunch"], eta="12:15 PM")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Bangkok Bowl", cuisine="Thai", eta="12:15 PM",
        fee=2.49, emoji="🍜",
        dishes=[dish(did="d_mp157_thai", name="Pad Thai", price=13.50,
                     tags=["lunch"], eta="12:15 PM")],
    )
    world.food.orders["FOOD-MP157-ALICE"] = food_order(
        oid="FOOD-MP157-ALICE", rid=GOLD_REST, rname="Harbor Sushi",
        items=[fitem(did="d_mp157_sushi", rid=GOLD_REST, name="Salmon avocado roll", price=14.00)],
        fee=2.49, placed_at="2026-04-10T12:05:00", eta="12:15 PM",
        note="After Marcus 1:1 — both liked Harbor Sushi.",
    )
    world.food.enable_schedule_ahead = True
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_157_lunch_least_recent_of_three_most_emailed,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, food_from, new_cal_events, new_food_orders
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(marcus|harbor\s+sushi|sushi)")

    def _marcus_lunch(p: Probe) -> bool:
        if not food_from(p, [GOLD_REST]):
            return False
        for e in new_cal_events(p):
            if "marcus" in (e.title or "").lower():
                return True
        blob = emailed_alice(p, _OK)
        return bool(blob)

    def _wrong_person(p: Probe) -> bool:
        for e in new_cal_events(p):
            t = (e.title or "").lower()
            if "priya" in t or "ben" in t or "dana" in t:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("identified_marcus_as_least_recent_frequent", 0.3, lambda p: emailed_alice(p, re.compile(r"(?ix)marcus")) or _marcus_lunch(p), True),
                Milestone("ordered_from_shared_harbor_sushi", 0.4, lambda p: food_from(p, [GOLD_REST]), True),
                Milestone("emailed_plan", 0.3, lambda p: emailed_alice(p, _OK) and food_from(p, [GOLD_REST]), True),
                Milestone("picked_more_recent_or_infrequent_person", 0.0, _wrong_person, False, forbidden=True),
                Milestone("ordered_from_unshared_restaurant", 0.0, lambda p: food_from(p, [TRAP_REST]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
