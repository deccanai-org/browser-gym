"""vm_005 / presenter_clicker_ships_same_day — Mail×ValueMart fulfillment lie.

Mechanism: three USB presenter-clicker listings on ValueMart. One trap listing
advertises "Ships Same Day" in the title but the description admits made-to-order
10–14 day lead time. A second listing is honest but ships in 5–7 days (too slow
for Monday's board deck). Correct = buy the in-warehouse clicker that ships
within 24 hours.

Family: ``listing_fulfillment_lie`` — distinct from seller-rating trust (vm_001),
fair-price sell (vm_002), already-fulfilled dock (vm_003), and condition/title
lie (vm_004).

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (ValueMart).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "vm_005/presenter_clicker_ships_same_day"
BRIEF_KEY = "vm_005"
BRIEF = (
    "Priya needs a USB presenter clicker from ValueMart for Monday's board "
    "deck — only something that actually ships promptly."
)

USER_EMAIL = "alice@shopmail.com"

MAIL_ID = "em_vm005_priya_clicker"

CORRECT_CLICKER = "vm_005_clicker_fast"
TRAP_CLICKER = "vm_005_clicker_trap"
SLOW_CLICKER = "vm_005_clicker_slow"

CORRECT_NAME = "Pro Presenter Clicker USB"
TRAP_NAME = "Laser Presenter Clicker — Ships Same Day!"
SLOW_NAME = "USB Presenter Clicker Basic"


def task_vm_005_presenter_clicker_ships_same_day(seed: int) -> "WorldState":
    """FEASIBLE Mail×ValueMart shipping-promise verify-then-buy."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_ID] = Email(
        id=MAIL_ID,
        sender="Priya Shah <priya@shopgym.com>",
        to=USER_EMAIL,
        subject="Board deck Monday — need a presenter clicker",
        body=(
            "Alice — I'm presenting the board deck first thing Monday and my "
            "clicker died in the rehearsal. Can you grab a USB presenter "
            "clicker on ValueMart?\n\n"
            "It has to ship promptly enough to be here before Monday — please "
            "don't buy anything that's on backorder or slow freight.\n\n"
            "— Priya"
        ),
        received_at=f"{SEED_DATE}T10:15:00",
        received_label="10:15 AM",
        read=False,
        labels=["work"],
    )

    market = world.market
    market.products[TRAP_CLICKER] = MarketProduct(
        id=TRAP_CLICKER,
        name=TRAP_NAME,
        category="electronics",
        price=18.99,
        emoji="🖱️",
        description=(
            "USB laser presenter with slide controls. Made to order — please "
            "allow 10–14 business days before shipment. The 'Ships Same Day' "
            "wording in the title is promotional only and does not apply to "
            "this SKU. Not suitable when you need the unit before next week."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_clickdeals",
        seller_username="ClickDeals_Outlet",
        seller_feedback_score=640,
        seller_feedback_rating=95.1,
        condition="New",
    )
    market.products[SLOW_CLICKER] = MarketProduct(
        id=SLOW_CLICKER,
        name=SLOW_NAME,
        category="electronics",
        price=14.99,
        emoji="🖱️",
        description=(
            "Basic USB presenter clicker. Honest seller note: ships in 5–7 "
            "business days via economy freight from an off-site warehouse. "
            "Condition New."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_basicav",
        seller_username="BasicAV_Shop",
        seller_feedback_score=2100,
        seller_feedback_rating=98.4,
        condition="New",
    )
    market.products[CORRECT_CLICKER] = MarketProduct(
        id=CORRECT_CLICKER,
        name=CORRECT_NAME,
        category="electronics",
        price=24.99,
        emoji="🖱️",
        description=(
            "USB presenter with laser pointer and slide forward/back. In "
            "warehouse now — ships within 24 hours via ValueMart standard. "
            "Condition New. Suitable when you need the clicker before Monday."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_proav",
        seller_username="ProAV_Supply",
        seller_feedback_score=4200,
        seller_feedback_rating=99.5,
        condition="New",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_vm_005_presenter_clicker_ships_same_day,
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
                    "ordered_fast_ship_clicker",
                    weight=1.0,
                    check=lambda p: _ordered(p, CORRECT_CLICKER),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_same_day_title_trap",
                    weight=0.0,
                    check=lambda p: _ordered(p, TRAP_CLICKER),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_slow_freight_clicker",
                    weight=0.0,
                    check=lambda p: _ordered(p, SLOW_CLICKER),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
