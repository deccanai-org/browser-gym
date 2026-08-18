"""mp_158 / same_meal_as_proposal_accepted_email_day.

Helen 'proposal ACCEPTED' on May 12; that day's order is Sakura salmon roll.
May 13 pizza is a decoy celebration dinner.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_158/same_meal_as_proposal_accepted_email_day"
BRIEF_KEY = "mp_158"
BRIEF = (
    "Order the same meal I had the day I got the email saying the proposal "
    "was accepted. Email me what you ordered."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
ACCEPT = "em_mp158_accept"
GOLD_REST = "r_mp158_sakura"
TRAP_REST = "r_mp158_pizza"
GOLD_DISH = "d_mp158_salmon"
TRAP_DISH = "d_mp158_pizza"


def task_mp_158_same_meal_as_proposal_accepted_email_day(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, fitem, food_order, mail, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.mail.inbox[ACCEPT] = mail(
        eid=ACCEPT, sender="helen.vasquez@shopmail.com",
        subject="Northwind proposal — ACCEPTED",
        received_at="2026-05-12T11:05:00", received_label="Tue May 12",
        body="The Northwind proposal was accepted today. Celebrating quietly.",
    )
    world.mail.inbox["em_mp158_noise"] = mail(
        eid="em_mp158_noise", sender="ben.ortiz@shopmail.com",
        subject="pizza tomorrow to celebrate?",
        received_at="2026-05-12T18:00:00", received_label="Tue May 12",
        body="Let's do pizza tomorrow (Wednesday) to celebrate. Not the same day as the accept email.",
    )
    world.food.restaurants[GOLD_REST] = restaurant(
        rid=GOLD_REST, name="Sakura Sushi", cuisine="Japanese", eta="12:20 PM",
        fee=2.49, emoji="🍣",
        dishes=[dish(did=GOLD_DISH, name="Salmon Avocado Roll", price=14.25,
                     tags=["lunch"], eta="12:20 PM")],
    )
    world.food.restaurants[TRAP_REST] = restaurant(
        rid=TRAP_REST, name="Slice House", cuisine="Pizza", eta="7:00 PM",
        fee=1.99, emoji="🍕",
        dishes=[dish(did=TRAP_DISH, name="Celebration pepperoni", price=16.00,
                     tags=["dinner"], eta="7:00 PM")],
    )
    world.food.orders["FOOD-MP158-MAY12"] = food_order(
        oid="FOOD-MP158-MAY12", rid=GOLD_REST, rname="Sakura Sushi",
        items=[fitem(did=GOLD_DISH, rid=GOLD_REST, name="Salmon Avocado Roll", price=14.25)],
        fee=2.49, placed_at="2026-05-12T12:02:00", eta="12:20 PM",
        note="Same day as proposal accepted.",
    )
    world.food.orders["FOOD-MP158-MAY13"] = food_order(
        oid="FOOD-MP158-MAY13", rid=TRAP_REST, rname="Slice House",
        items=[fitem(did=TRAP_DISH, rid=TRAP_REST, name="Celebration pepperoni", price=16.00)],
        fee=1.99, placed_at="2026-05-13T18:40:00", eta="7:00 PM",
        note="Day after accept email.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_158_same_meal_as_proposal_accepted_email_day,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, food_from, mail_read, new_food_orders
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(sakura|salmon|may\s*12|accepted)")

    def _salmon(p: Probe) -> bool:
        if food_from(p, [GOLD_REST]):
            return True
        for o in new_food_orders(p):
            for it in getattr(o, "items", []) or []:
                if "salmon" in (getattr(it, "name", "") or "").lower():
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_proposal_accepted_email", 0.3, lambda p: mail_read(p, ACCEPT), True),
                Milestone("reordered_same_day_sakura_meal", 0.5, _salmon, True),
                Milestone("emailed_what_was_ordered", 0.2, lambda p: emailed_alice(p, _OK) and _salmon(p), True),
                Milestone("ordered_next_day_celebration_pizza", 0.0, lambda p: food_from(p, [TRAP_REST]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
