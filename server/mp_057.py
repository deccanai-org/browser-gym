"""mp_057 / lamp_address_change_reason_unlock — ShopGym false-infeasibility bait.

Mechanism (C8): change delivery address on the lamp order. Address control
looks greyed until "reason for change" dropdown is selected, then unlocks.
Gold = complete change (e.g. home → work). Paired with mp_056 OFD infeasible.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_057/lamp_address_change_reason_unlock"
BRIEF_KEY = "mp_057"
BRIEF = "Change the delivery address on the lamp order."

USER_EMAIL = "alice@shopmail.com"

ORDER_ID = "ORD-MP057-LAMP"
LINE_ID = "ln_mp057_lamp"
SKU = "p_mp057_desk_lamp"
NAME = "GlowBeam Desk Lamp"
FROM_ADDR = "addr_home"
TO_ADDR = "addr_work"


def task_mp_057_lamp_address_change_reason_unlock(seed: int) -> "WorldState":
    """FEASIBLE. Confirmed lamp order; unlock address change via reason dropdown."""
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.products[SKU] = Product(
        id=SKU, name=NAME, brand="GlowBeam", category="home",
        base_price=39.00, rating=4.3, review_count=240, stock=30,
        image_emoji="💡",
        short_description="LED desk lamp. Order still processing — address editable.",
        tags=["lamp", "desk"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID, user_id="u_alice", placed_at="2026-05-20T14:00:00Z",
        items=[OrderItem(
            id=LINE_ID, product_id=SKU, product_name=NAME,
            variant_id=None, variant_label="", quantity=1, unit_price=39.00,
            gift_wrap=False, gift_message="", ship_to_address_id=FROM_ADDR,
            scheduled_delivery=None,
        )],
        subtotal=39.00, discount=0.0, tax=3.32, shipping=5.99, total=48.31,
        promo_code=None, payment_id="pay_visa", status="confirmed", shipments=[],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_057_lamp_address_change_reason_unlock,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/account/orders"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _changed(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        o = shop.orders.get(ORDER_ID) if shop else None
        if not o or not o.items:
            return False
        return o.items[0].ship_to_address_id == TO_ADDR

    def _still_home(p: Probe) -> bool:
        # Diagnostic only — not forbidden; gold is the change.
        shop = p.world.shop if p.world else None
        o = shop.orders.get(ORDER_ID) if shop else None
        if not o or not o.items:
            return False
        return o.items[0].ship_to_address_id == FROM_ADDR

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "changed_lamp_ship_to_work",
                    weight=1.0,
                    check=_changed,
                    required_for_success=True,
                ),
                Milestone(
                    "lamp_still_home_address",
                    weight=0.0,
                    check=_still_home,
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
