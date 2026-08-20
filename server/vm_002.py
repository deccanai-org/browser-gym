"""vm_002 / valuemart_list_desk_lamp_fair_price — seller fair-price listing.

Mechanism: Xbay already has 2–3 comparable used desk-lamp listings at
varying prices (including a high outlier). User asks to list their old desk
lamp at a fair price based on comps. Trap = list at an arbitrary/unfair price
(or never complete the Sell flow). Correct = check comps, list complete with
price inside the fair band derived from the non-outlier comps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "vm_002/valuemart_list_desk_lamp_fair_price"
BRIEF_KEY = "vm_002"
BRIEF = (
    "List my old desk lamp on Xbay, price it fairly based on what "
    "similar ones are going for."
)

USER_EMAIL = "alice@shopmail.com"
USER_SELLER_ID = "user_1"
USER_SELLER_NAME = "Alice Anderson"
USER_LAMP_ID = "vm_alice_desk_lamp"
USER_LAMP_TITLE = "AuroraGlow LED Desk Lamp"
USER_LAMP_CONDITION = "Used"
# Mid-band oracle price (comps at 18.99 / 24.99; outlier 54.99).
ORACLE_PRICE = 22.99

# Fair band from the two realistic comps (± a little), excluding the high outlier.
FAIR_MIN = 16.00
FAIR_MAX = 32.00

COMP_LOW = "vm_lamp_comp_low"
COMP_MID = "vm_lamp_comp_mid"
COMP_HIGH = "vm_lamp_comp_high"

COMPS = (
    {
        "id": COMP_LOW,
        "name": "AuroraGlow LED Desk Lamp — Used",
        "price": 18.99,
        "seller_id": "seller_budgetlamps",
        "seller_username": "BudgetLamps_Co",
        "seller_feedback_score": 412,
        "seller_feedback_rating": 96.2,
        "description": (
            "Used AuroraGlow LED desk lamp, adjustable arm, works great. "
            "Slight scuffs on base. Sold by BudgetLamps_Co."
        ),
    },
    {
        "id": COMP_MID,
        "name": "LED Desk Lamp Adjustable — Used",
        "price": 24.99,
        "seller_id": "seller_officeglow",
        "seller_username": "OfficeGlow_Finds",
        "seller_feedback_score": 1880,
        "seller_feedback_rating": 99.1,
        "description": (
            "Used adjustable LED desk lamp with USB port. Good working order. "
            "Sold by OfficeGlow_Finds."
        ),
    },
    {
        "id": COMP_HIGH,
        "name": "Premium LED Desk Lamp (New in Box)",
        "price": 54.99,
        "seller_id": "seller_premiumdesk",
        "seller_username": "PremiumDesk_Outlet",
        "seller_feedback_score": 88,
        "seller_feedback_rating": 91.0,
        "description": (
            "Brand-new sealed LED desk lamp — asking retail-ish. "
            "Sold by PremiumDesk_Outlet."
        ),
    },
)


def task_vm_002_valuemart_list_desk_lamp_fair_price(seed: int) -> "WorldState":
    """FEASIBLE Xbay seller fair-price listing.

    Seed: three desk-lamp comps (two realistic + one high outlier). Correct =
    complete Alice listing with price in [FAIR_MIN, FAIR_MAX].
    """
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"

    for row in COMPS:
        world.market.products[row["id"]] = MarketProduct(
            id=row["id"],
            name=row["name"],
            category="home",
            price=row["price"],
            emoji="💡",
            description=row["description"],
            in_stock=True,
            shop_sku=None,
            seller_id=row["seller_id"],
            seller_username=row["seller_username"],
            seller_feedback_score=row["seller_feedback_score"],
            seller_feedback_rating=row["seller_feedback_rating"],
            condition="Used" if row["id"] != COMP_HIGH else "New",
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_vm_002_valuemart_list_desk_lamp_fair_price,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _alice_lamp_products(p) -> list:
    if p.world is None or p.world.market is None:
        return []
    out = []
    for prod in (p.world.market.products or {}).values():
        sid = getattr(prod, "seller_id", None)
        name = (getattr(prod, "name", None) or "").lower()
        if sid == USER_SELLER_ID and "lamp" in name:
            out.append(prod)
        elif getattr(prod, "id", None) == USER_LAMP_ID:
            out.append(prod)
    return out


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _listed_fair(p: Probe) -> bool:
        for prod in _alice_lamp_products(p):
            price = float(getattr(prod, "price", 0) or 0)
            stamped = getattr(prod, "fair_priced", None)
            if stamped is True:
                return True
            if stamped is None and FAIR_MIN <= price <= FAIR_MAX:
                return True
        return False

    def _listed_unfair(p: Probe) -> bool:
        for prod in _alice_lamp_products(p):
            price = float(getattr(prod, "price", 0) or 0)
            stamped = getattr(prod, "fair_priced", None)
            if stamped is False:
                return True
            if stamped is None and not (FAIR_MIN <= price <= FAIR_MAX):
                return True
        return False

    def _build() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "listed_desk_lamp_fair_price",
                    weight=1.0,
                    check=_listed_fair,
                    required_for_success=True,
                ),
                Milestone(
                    "listed_desk_lamp_unfair_price",
                    weight=0.0,
                    check=_listed_unfair,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _build}
