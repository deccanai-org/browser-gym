"""mp_137 / reorder_item_after_alex_tuesday_price_cap.

Last Tuesday 1:1 with Alex, then a 14:20 Desk Cable Organizer order at $18.
Current price $22 (+22% > 15%). Gold = abstain. Pre-meeting notebook is a decoy.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_137/reorder_item_after_alex_tuesday_price_cap"
BRIEF_KEY = "mp_137"
BRIEF = (
    "Find the item I ordered after my meeting with Alex last Tuesday. Order "
    "another one, but only if the current price hasn't increased by more than "
    "15%. Email me what you decided."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
ALEX = "ev_mp137_alex"
CABLE = "vm_mp137_cable"
NOTEBOOK = "vm_mp137_notebook"
OLD_CABLE = "VM-MP137-CABLE"
OLD_NOTE = "VM-MP137-NOTE"
OLD_PRICE = 18.00
NEW_PRICE = 22.00


def task_mp_137_reorder_item_after_alex_tuesday_price_cap(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, market_order, mitem, mproduct

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[ALEX] = ev(
        eid=ALEX, title="1:1 with Alex Rivera", day="2026-05-19",
        start="11:00", end="11:30", day_label="Tue May 19",
        description="Last Tuesday 1:1 with Alex Rivera.",
    )
    mkt = world.market
    mkt.products.clear()
    mkt.cart.items.clear()
    mkt.orders.clear()
    mkt.products[CABLE] = mproduct(
        pid=CABLE, name="Desk Cable Organizer", category="office", price=NEW_PRICE,
        desc="Was $18.00 last Tuesday. Now $22.00 (22% higher).",
    )
    mkt.products[NOTEBOOK] = mproduct(
        pid=NOTEBOOK, name="Field Notes Notebook", category="office", price=12.00,
        desc="Ordered Tuesday morning before the Alex meeting.",
    )
    mkt.orders[OLD_NOTE] = market_order(
        oid=OLD_NOTE,
        items=[mitem(pid=NOTEBOOK, name="Field Notes Notebook", price=12.00)],
        placed_at="2026-05-19T09:10:00",
    )
    mkt.orders[OLD_CABLE] = market_order(
        oid=OLD_CABLE,
        items=[mitem(pid=CABLE, name="Desk Cable Organizer", price=OLD_PRICE)],
        placed_at="2026-05-19T14:20:00",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_137_reorder_item_after_alex_tuesday_price_cap,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import any_new_market, emailed_alice, market_bought, viewed_cal, viewed_order
    from server.verifiers import Milestone, Probe, TaskSuite

    _UP = re.compile(r"(?ix)(22|18|15\s*%|increased|too\s+much|did\s+not\s+order|didn't\s+order)")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_alex_meeting_on_calendar", 0.2, viewed_cal, True),
                Milestone("found_post_meeting_order", 0.25, viewed_order, True),
                Milestone("abstained_because_price_up_over_15_percent", 0.35, lambda p: (not any_new_market(p)) and (viewed_cal(p) or viewed_order(p) or emailed_alice(p, _UP)), True),
                Milestone("emailed_price_decision", 0.2, lambda p: emailed_alice(p, _UP) and not any_new_market(p), True),
                Milestone("reordered_despite_22_percent_increase", 0.0, lambda p: market_bought(p, [CABLE]), False, forbidden=True),
                Milestone("ordered_pre_meeting_notebook_decoy", 0.0, lambda p: market_bought(p, [NOTEBOOK]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
