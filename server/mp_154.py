"""mp_154 / cook_for_visitor_recipe_from_convo.

Told cousin Leo shakshuka Saturday 6pm. Buy ingredients + 2h cook block
16:00–18:00 before arrival.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_154/cook_for_visitor_recipe_from_convo"
BRIEF_KEY = "mp_154"
BRIEF = (
    "Someone is coming to visit and I told them I'd cook. Find the conversation, "
    "figure out what I said I'd make, buy the ingredients, and schedule two "
    "hours to cook before they arrive. Email me the plan."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
ARRIVE = "ev_mp154_leo"
CONV = "em_mp154_leo"
EGGS = "vm_mp154_eggs"
TOMS = "vm_mp154_tomatoes"
PEPP = "vm_mp154_peppers"
CUMIN = "vm_mp154_cumin"
BREAD = "vm_mp154_bread"
CAKE = "vm_mp154_cake"


def task_mp_154_cook_for_visitor_recipe_from_convo(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail, mproduct

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[ARRIVE] = ev(
        eid=ARRIVE, title="Leo arrives", day="2026-05-23",
        start="18:00", end="18:30", day_label="Sat May 23",
        description="Cousin Leo Patel arrives 6:00 PM Saturday.",
    )
    world.mail.inbox[CONV] = mail(
        eid=CONV, sender=USER_EMAIL, to="leo.patel@shopmail.com",
        subject="I'll cook Saturday",
        received_at="2026-05-18T20:00:00", received_label="Mon 8:00 PM",
        body=(
            "Leo — I'll make shakshuka when you get here Saturday 6pm. "
            "Need eggs, tomatoes, peppers, cumin, and bread."
        ),
    )
    mkt = world.market
    mkt.products.clear()
    mkt.cart.items.clear()
    mkt.orders.clear()
    for pid, name, price in (
        (EGGS, "Eggs dozen", 3.50),
        (TOMS, "Tomatoes 1 lb", 3.20),
        (PEPP, "Bell peppers", 2.80),
        (CUMIN, "Cumin jar", 4.10),
        (BREAD, "Crusty bread", 3.40),
        (CAKE, "Celebration cake", 28.00),
    ):
        mkt.products[pid] = mproduct(
            pid=pid, name=name, category="grocery", price=price,
            desc="Shakshuka ingredient" if pid != CAKE else "Not the promised dish.",
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_154_cook_for_visitor_recipe_from_convo,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, market_bought, new_cal_events
    from server.verifiers import Milestone, Probe, TaskSuite

    NEED = {EGGS, TOMS, PEPP, CUMIN, BREAD}
    _OK = re.compile(r"(?ix)(shakshuka|leo|16:00|4:00|cook)")

    def _bought(p: Probe) -> bool:
        return all(market_bought(p, [pid]) for pid in NEED)

    def _cook_block(p: Probe) -> bool:
        for e in new_cal_events(p):
            title = (e.title or "").lower()
            if "cook" not in title and "shakshuka" not in title:
                continue
            if e.day == "2026-05-23" and e.start <= "16:00" and e.end >= "18:00":
                return True
            if e.day == "2026-05-23" and e.start < "18:00":
                # 2h block ending at arrival
                return e.end <= "18:00"
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_leo_shakshuka_conversation", 0.2, lambda p: mail_read(p, CONV), True),
                Milestone("bought_shakshuka_ingredients", 0.4, _bought, True),
                Milestone("scheduled_two_hour_cook_block_before_arrival", 0.25, _cook_block, True),
                Milestone("emailed_plan", 0.15, lambda p: emailed_alice(p, _OK) and _bought(p), True),
                Milestone("bought_unrelated_cake", 0.0, lambda p: market_bought(p, [CAKE]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
