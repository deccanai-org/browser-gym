"""mp_141 / reorder_last_groceries_except_party_sub_cap.

Last groceries mixed party chips/wine (Maya birthday May 17) with staples.
Bananas OOS → apples. Total must stay ≤ +10% of last staple-eligible total.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_141/reorder_last_groceries_except_party_sub_cap"
BRIEF_KEY = "mp_141"
BRIEF = (
    "Reorder the groceries from my last order except anything that was clearly "
    "for the party I hosted. Replace anything unavailable, but don't increase "
    "the total by more than 10%. Email me the new total."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"
PARTY = "ev_mp141_party"
MILK = "vm_mp141_milk"
EGGS = "vm_mp141_eggs"
BREAD = "vm_mp141_bread"
BANANA = "vm_mp141_banana"
APPLE = "vm_mp141_apple"
CHIPS = "vm_mp141_chips"
WINE = "vm_mp141_wine"
LAST = "VM-MP141-LAST"
LAST_STAPLE = 14.10  # milk 4.2 + eggs 3.5 + bread 3.2 + bananas 3.2
# Xbay adds $5.99 delivery under the free-delivery threshold.
CAP = round((LAST_STAPLE + 5.99) * 1.10, 2)  # 22.10


def task_mp_141_reorder_last_groceries_except_party_sub_cap(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, market_order, mitem, mproduct

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[PARTY] = ev(
        eid=PARTY, title="Maya's birthday party", day="2026-05-17",
        start="18:00", end="22:00", day_label="Sun May 17",
        description="Hosted at home. Chips and sparkling wine were for this party.",
    )
    mkt = world.market
    mkt.products.clear()
    mkt.cart.items.clear()
    mkt.orders.clear()
    for pid, name, price, stock, desc in (
        (MILK, "Milk 1/2 gallon", 4.20, True, "Staple."),
        (EGGS, "Eggs dozen", 3.50, True, "Staple."),
        (BREAD, "Sourdough loaf", 3.20, True, "Staple."),
        (BANANA, "Bananas 1 lb", 3.20, False, "Out of stock."),
        (APPLE, "Apples 1 lb", 3.40, True, "Substitute for bananas."),
        (CHIPS, "Party Pack Chips 20ct", 8.50, True, "Party item."),
        (WINE, "Sparkling wine 6-pack", 22.00, True, "Party item."),
    ):
        mkt.products[pid] = mproduct(
            pid=pid, name=name, category="grocery", price=price, in_stock=stock, desc=desc,
        )
    mkt.orders[LAST] = market_order(
        oid=LAST,
        items=[
            mitem(pid=MILK, name="Milk 1/2 gallon", price=4.20),
            mitem(pid=EGGS, name="Eggs dozen", price=3.50),
            mitem(pid=BREAD, name="Sourdough loaf", price=3.20),
            mitem(pid=BANANA, name="Bananas 1 lb", price=3.20),
            mitem(pid=CHIPS, name="Party Pack Chips 20ct", price=8.50),
            mitem(pid=WINE, name="Sparkling wine 6-pack", price=22.00),
        ],
        placed_at="2026-05-16T10:00:00",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_141_reorder_last_groceries_except_party_sub_cap,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, market_bought, new_market_orders, new_spend, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    STAPLES = {MILK, EGGS, BREAD, APPLE}
    PARTY_IDS = {CHIPS, WINE}
    _OK = re.compile(r"(?ix)(apple|milk|10\s*%|party)")

    def _staples(p: Probe) -> bool:
        got = set()
        for o in new_market_orders(p):
            for it in o.items:
                got.add(getattr(it, "product_id", ""))
        return {MILK, EGGS, BREAD} <= got and APPLE in got

    def _cap(p: Probe) -> bool:
        return new_spend(p) <= CAP + 1e-6

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("identified_party_on_calendar", 0.15, viewed_cal, True),
                Milestone("reordered_staples_with_banana_substitute", 0.35, _staples, True),
                Milestone("skipped_party_chips_and_wine", 0.2, lambda p: (not market_bought(p, PARTY_IDS)) and _staples(p), True),
                Milestone("kept_total_within_10_percent", 0.2, lambda p: _staples(p) and _cap(p), True),
                Milestone("emailed_new_total", 0.1, lambda p: emailed_alice(p, _OK) and _staples(p), True),
                Milestone("included_party_items", 0.0, lambda p: market_bought(p, PARTY_IDS), False, forbidden=True),
                Milestone("exceeded_10_percent_cap", 0.0, lambda p: not _cap(p), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
