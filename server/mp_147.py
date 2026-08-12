"""mp_147 / workday_food_tomorrow_not_during_meetings_no_repeat_budget.

Meetings 9–10, 11–12, 14–15. This week already Thai/Pizza/Salad.
Gold = breakfast ~8:30 + lunch ~12:30 from Cafe/Mexican, combined < $45 fees in.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_147/workday_food_tomorrow_not_during_meetings_no_repeat_budget"
BRIEF_KEY = "mp_147"
BRIEF = (
    "Plan food for my workday tomorrow. Don't order anything during meetings, "
    "avoid repeating anything I ate this week, and keep the combined total "
    "below $45 including fees. Email me the plan."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T18:00:00"
CAFE = "r_mp147_cafe"
MEX = "r_mp147_mex"
THAI = "r_mp147_thai"
PIZZA = "r_mp147_pizza"
SALAD = "r_mp147_salad"


def task_mp_147_workday_food_tomorrow_not_during_meetings_no_repeat_budget(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, dish, ev, fitem, food_order, restaurant

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    cal = world.calendar
    for eid, title, start, end in (
        ("ev_mp147_a", "Standup", "09:00", "10:00"),
        ("ev_mp147_b", "Vendor call", "11:00", "12:00"),
        ("ev_mp147_c", "QBR", "14:00", "15:00"),
    ):
        cal.events[eid] = ev(
            eid=eid, title=title, day="2026-05-22",
            start=start, end=end, day_label="Fri May 22",
        )
    world.food.restaurants[CAFE] = restaurant(
        rid=CAFE, name="Bean & Bagel", cuisine="Cafe", eta="8:30 AM",
        fee=1.49, emoji="☕",
        dishes=[dish(did="d_mp147_bfast", name="Oat latte + egg sandwich", price=12.50,
                     tags=["breakfast"], eta="8:30 AM")],
    )
    world.food.restaurants[MEX] = restaurant(
        rid=MEX, name="Casa Verde", cuisine="Mexican", eta="12:30 PM",
        fee=2.49, emoji="🌮",
        dishes=[dish(did="d_mp147_lunch", name="Veg burrito", price=13.00,
                     tags=["lunch", "vegetarian"], eta="12:30 PM")],
    )
    world.food.restaurants[THAI] = restaurant(
        rid=THAI, name="Bangkok Bowl", cuisine="Thai", eta="12:30 PM",
        fee=2.49, emoji="🍜",
        dishes=[dish(did="d_mp147_thai", name="Pad Thai", price=14.50, tags=["lunch"], eta="12:30 PM")],
    )
    world.food.restaurants[PIZZA] = restaurant(
        rid=PIZZA, name="Slice House", cuisine="Pizza", eta="12:30 PM",
        fee=1.99, emoji="🍕",
        dishes=[dish(did="d_mp147_pizza", name="Margherita", price=15.00, tags=["lunch"], eta="12:30 PM")],
    )
    world.food.restaurants[SALAD] = restaurant(
        rid=SALAD, name="Leaf & Co", cuisine="Salad", eta="12:30 PM",
        fee=1.99, emoji="🥗",
        dishes=[dish(did="d_mp147_salad", name="Cobb salad", price=14.00, tags=["lunch"], eta="12:30 PM")],
    )
    for oid, rid, rname, did, name, price, when, eta in (
        ("FOOD-MP147-MON", THAI, "Bangkok Bowl", "d_mp147_thai", "Pad Thai", 14.50, "2026-05-18T12:10:00", "12:30 PM"),
        ("FOOD-MP147-TUE", PIZZA, "Slice House", "d_mp147_pizza", "Margherita", 15.00, "2026-05-19T12:05:00", "12:30 PM"),
        ("FOOD-MP147-WED", SALAD, "Leaf & Co", "d_mp147_salad", "Cobb salad", 14.00, "2026-05-20T12:00:00", "12:30 PM"),
    ):
        world.food.orders[oid] = food_order(
            oid=oid, rid=rid, rname=rname,
            items=[fitem(did=did, rid=rid, name=name, price=price)],
            fee=2.00, placed_at=when, eta=eta,
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_147_workday_food_tomorrow_not_during_meetings_no_repeat_budget,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, food_from, new_food_orders, new_spend, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(bean|casa|8:30|12:30|45)")
    REPEAT = {THAI, PIZZA, SALAD}
    DURING = re.compile(r"(?ix)(9:00|9:30|10:00|11:00|11:30|2:00|14:00|14:30)")

    def _good_places(p: Probe) -> bool:
        rids = {getattr(o, "restaurant_id", "") for o in new_food_orders(p)}
        return bool(rids) and rids <= {CAFE, MEX}

    def _not_during(p: Probe) -> bool:
        for o in new_food_orders(p):
            eta = getattr(o, "eta_label", "") or ""
            if DURING.search(eta.replace(" ", "")):
                # 12:30 should not match 2:00; compact carefully
                compact = eta.lower().replace(" ", "")
                if any(x in compact for x in ("9:00am", "9:30", "10:00am", "11:00am", "11:30", "2:00pm", "14:00")):
                    return False
        return bool(new_food_orders(p))

    def _under(p: Probe) -> bool:
        return 0 < new_spend(p) <= 45.0 + 1e-6

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("checked_tomorrow_meetings", 0.2, viewed_cal, True),
                Milestone("ordered_from_non_repeat_restaurants", 0.3, _good_places, True),
                Milestone("timed_orders_outside_meetings", 0.2, _not_during, True),
                Milestone("kept_combined_total_under_45_with_fees", 0.2, _under, True),
                Milestone("emailed_plan", 0.1, lambda p: emailed_alice(p, _OK) and _good_places(p), True),
                Milestone("repeated_this_weeks_cuisine", 0.0, lambda p: food_from(p, REPEAT), False, forbidden=True),
                Milestone("exceeded_45_including_fees", 0.0, lambda p: new_spend(p) > 45.0, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
