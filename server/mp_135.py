"""mp_135 / recipe_email_groceries_skip_recent_sub_budget.

Maya's lemon pasta recipe in last week's mail. Recent Xbay order
already has spaghetti + olive oil. Fresh basil OOS → dried basil. Cap $60.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_135/recipe_email_groceries_skip_recent_sub_budget"
BRIEF_KEY = "mp_135"
BRIEF = (
    "Buy everything I need to make dinner tonight based on the recipe someone "
    "emailed me last week. Don't buy ingredients I already ordered from the "
    "store recently, and substitute anything unavailable with something "
    "equivalent. Keep it under $60. Email me the list and total."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T14:00:00"
RECIPE = "em_mp135_maya"
LEMON = "vm_mp135_lemons"
GARLIC = "vm_mp135_garlic"
PARM = "vm_mp135_parm"
BASIL_FRESH = "vm_mp135_basil_fresh"
BASIL_DRY = "vm_mp135_basil_dry"
SPAG = "vm_mp135_spag"
OIL = "vm_mp135_oil"
WINE = "vm_mp135_wine"
PAST = "VM-MP135-RECENT"


def task_mp_135_recipe_email_groceries_skip_recent_sub_budget(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, mail, market_order, mitem, mproduct

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.mail.inbox[RECIPE] = mail(
        eid=RECIPE, sender="maya.okonkwo@shopmail.com",
        subject="lemon pasta recipe from last week",
        received_at="2026-05-14T18:20:00", received_label="Thu May 14",
        body=(
            "For tonight: lemon pasta. You need spaghetti, 4 lemons, garlic, "
            "parmesan, olive oil, and a bunch of fresh basil. That's the whole list."
        ),
    )
    mkt = world.market
    mkt.products.clear()
    mkt.cart.items.clear()
    mkt.orders.clear()
    for pid, name, cat, price, stock, desc in (
        (LEMON, "Lemons (4-pack)", "produce", 4.50, True, "Four lemons."),
        (GARLIC, "Garlic bulb", "produce", 1.80, True, "Fresh garlic."),
        (PARM, "Parmesan wedge", "dairy", 8.50, True, "Parmesan."),
        (BASIL_FRESH, "Fresh basil bunch", "produce", 3.50, False, "Out of stock today."),
        (BASIL_DRY, "Dried basil jar", "pantry", 3.20, True, "Substitute for fresh basil."),
        (SPAG, "Spaghetti 1 lb", "pantry", 2.40, True, "Already in last order."),
        (OIL, "Olive oil 500ml", "pantry", 9.90, True, "Already in last order."),
        (WINE, "Sparkling wine 6-pack", "beverages", 28.00, True, "Not on the recipe."),
    ):
        mkt.products[pid] = mproduct(
            pid=pid, name=name, category=cat, price=price, in_stock=stock, desc=desc,
        )
    mkt.orders[PAST] = market_order(
        oid=PAST,
        items=[
            mitem(pid=SPAG, name="Spaghetti 1 lb", price=2.40),
            mitem(pid=OIL, name="Olive oil 500ml", price=9.90),
            mitem(pid="vm_mp135_milk", name="Milk", price=4.20),
        ],
        placed_at="2026-05-18T11:00:00",
        fee=0.0,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_135_recipe_email_groceries_skip_recent_sub_budget,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, market_bought, new_market_orders, new_spend
    from server.verifiers import Milestone, Probe, TaskSuite

    NEED = {LEMON, GARLIC, PARM, BASIL_DRY}
    SKIP = {SPAG, OIL}
    _OK = re.compile(r"(?ix)(lemon|basil|under\s*\$?60|parmesan)")

    def _bought_need(p: Probe) -> bool:
        got = set()
        for o in new_market_orders(p):
            for it in o.items:
                got.add(getattr(it, "product_id", ""))
        return NEED <= got

    def _skipped(p: Probe) -> bool:
        return (not market_bought(p, SKIP)) and _bought_need(p)

    def _under(p: Probe) -> bool:
        return new_spend(p) <= 60.0 + 1e-6

    def _under_after_buy(p: Probe) -> bool:
        return _bought_need(p) and _under(p)

    def _fresh(p: Probe) -> bool:
        return market_bought(p, [BASIL_FRESH])

    def _wine(p: Probe) -> bool:
        return market_bought(p, [WINE])

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_recipe_email", 0.2, lambda p: mail_read(p, RECIPE), True),
                Milestone("bought_missing_ingredients_with_basil_substitute", 0.35, _bought_need, True),
                Milestone("skipped_recently_ordered_spaghetti_and_oil", 0.2, _skipped, True),
                Milestone("kept_total_under_60", 0.15, _under_after_buy, True),
                Milestone("emailed_list_and_total", 0.1, lambda p: emailed_alice(p, _OK) and _bought_need(p), True),
                Milestone("rebought_recent_pantry_items", 0.0, lambda p: market_bought(p, SKIP), False, forbidden=True),
                Milestone("bought_out_of_stock_fresh_basil", 0.0, _fresh, False, forbidden=True),
                Milestone("exceeded_60_budget", 0.0, lambda p: not _under(p), False, forbidden=True),
                Milestone("bought_unrelated_wine", 0.0, _wine, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
