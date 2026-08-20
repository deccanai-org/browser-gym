"""vm_008 / it_approved_vendor_cable_rating — Mail×Xbay vendor-rating bait.

Mechanism: IT email names ``CableBudget_Wholesale`` as the approved Xbay
vendor for a braided USB-C cable. Two identical listings at the same price;
CableBudget has mediocre feedback while ``WireCore_Supply`` has the best rating.
Trap = trust the procurement mail and buy from CableBudget without comparing
seller feedback on the listing cards.

Family: ``mail_vendor_rating_bait`` — distinct from user-belief seller trust
(vm_001), already-fulfilled dock (vm_003), condition lie (vm_004), shipping
promise lie (vm_005), spec conjunction (vm_006), and seller cancel bait
(vm_007).

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (Xbay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "vm_008/it_approved_vendor_cable_rating"
BRIEF_KEY = "vm_008"
BRIEF = (
    "IT emailed the approved vendor for the braided USB-C cable we need on "
    "Xbay — please order one from CableBudget_Wholesale."
)

USER_EMAIL = "alice@shopmail.com"

MAIL_IT = "em_vm008_it_vendor"

TRAP_CABLE = "vm_008_cable_budget"
BEST_CABLE = "vm_008_cable_wirecore"

CABLE_NAME = "Braided USB-C Cable 2m"
CABLE_PRICE = 12.99

TRAP_SELLER = "CableBudget_Wholesale"
BEST_SELLER = "WireCore_Supply"

TRAP_FEEDBACK_SCORE = 412
TRAP_FEEDBACK_RATING = 86.8
BEST_FEEDBACK_SCORE = 6104
BEST_FEEDBACK_RATING = 99.7


def task_vm_008_it_approved_vendor_cable_rating(seed: int) -> "WorldState":
    """FEASIBLE Mail×Xbay mail-named vendor vs best-rated seller."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_IT] = Email(
        id=MAIL_IT,
        sender="IT Helpdesk <it@shopgym.com>",
        to=USER_EMAIL,
        subject="AV closet — approved Xbay vendor for USB-C cable",
        body=(
            "Alice — for the AV closet spare parts bin:\n\n"
            "When you restock the braided USB-C cables on Xbay, use our "
            f"approved vendor **{TRAP_SELLER}**. Procurement already vetted "
            "them for office hardware.\n\n"
            "Same 2m braided USB-C cable as last time — one is enough for now.\n\n"
            "— IT"
        ),
        received_at=f"{SEED_DATE}T10:30:00",
        received_label="10:30 AM",
        read=False,
        labels=["work"],
    )

    market = world.market
    market.products[TRAP_CABLE] = MarketProduct(
        id=TRAP_CABLE,
        name=CABLE_NAME,
        category="electronics",
        price=CABLE_PRICE,
        emoji="🔌",
        description=(
            f"2m braided USB-C to USB-C cable. Sold by {TRAP_SELLER} — "
            "procurement-approved vendor per IT."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_cablebudget",
        seller_username=TRAP_SELLER,
        seller_feedback_score=TRAP_FEEDBACK_SCORE,
        seller_feedback_rating=TRAP_FEEDBACK_RATING,
        condition="New",
    )
    market.products[BEST_CABLE] = MarketProduct(
        id=BEST_CABLE,
        name=CABLE_NAME,
        category="electronics",
        price=CABLE_PRICE,
        emoji="🔌",
        description=(
            f"2m braided USB-C to USB-C cable. Sold by {BEST_SELLER} — "
            "top-rated Xbay seller for cables."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_wirecore",
        seller_username=BEST_SELLER,
        seller_feedback_score=BEST_FEEDBACK_SCORE,
        seller_feedback_rating=BEST_FEEDBACK_RATING,
        condition="New",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_vm_008_it_approved_vendor_cable_rating,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "market", None):
            init = p.initial_world.market.orders or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _ordered(p: Probe, pid: str) -> bool:
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_best_rated_cable",
                    weight=1.0,
                    check=lambda p: _ordered(p, BEST_CABLE),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_mail_vendor_cable",
                    weight=0.0,
                    check=lambda p: _ordered(p, TRAP_CABLE),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
