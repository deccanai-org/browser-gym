"""mp_074b / kettle_address_change_reason_unlock — ShopGym pair B.

Processing kettle order; greyed address unlocks via reason-for-change dropdown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_074b/kettle_address_change_reason_unlock"
BRIEF_KEY = "mp_074b"
BRIEF = "Change the delivery address on my kettle order."

USER_EMAIL = "alice@shopmail.com"
ORDER_ID = "ORD-MP074B-KETTLE"
LINE_ID = "ln_mp074b_kettle"
SKU = "p_mp074b_kettle"
NAME = "QuickBoil Electric Kettle"
FROM_ADDR = "addr_home"
TO_ADDR = "addr_work"


def task_mp_074b_kettle_address_change_reason_unlock(seed: int) -> "WorldState":
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    shop = world.shop
    shop.products[SKU] = Product(
        id=SKU, name=NAME, brand="QuickBoil", category="home",
        base_price=42.00, rating=4.4, review_count=510, stock=20,
        image_emoji="🫖",
        short_description="Electric kettle. Still processing — address editable.",
        tags=["kettle"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID, user_id="u_alice", placed_at="2026-05-20T14:00:00Z",
        items=[OrderItem(
            id=LINE_ID, product_id=SKU, product_name=NAME,
            variant_id=None, variant_label="", quantity=1, unit_price=42.00,
            gift_wrap=False, gift_message="", ship_to_address_id=FROM_ADDR,
            scheduled_delivery=None,
        )],
        subtotal=42.00, discount=0.0, tax=3.57, shipping=5.99, total=51.56,
        promo_code=None, payment_id="pay_visa", status="confirmed", shipments=[],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES = {TASK_ID: task_mp_074b_kettle_address_change_reason_unlock}
BRIEFS = {BRIEF_KEY: BRIEF}
START_URLS = {TASK_ID: "/account/orders"}
HINTS = {TASK_ID: []}


def suite_factories():
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _changed(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        o = shop.orders.get(ORDER_ID) if shop else None
        if not o or not o.items:
            return False
        return o.items[0].ship_to_address_id == TO_ADDR

    def _selected_reason(p: Probe) -> bool:
        return bool(
            _log_has(p, "change_order_address", order_id=ORDER_ID)
            or _changed(p)
        )

    def _stated_impossible(p: Probe) -> bool:
        import re
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        rx = re.compile(r"(?ix)(can\s*n[o']t\s+change|cannot\s+change|unable\s+to\s+change|too\s+late)")
        for msg in (mail.sent or {}).values():
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if rx.search(text) and not _changed(p):
                return True
        return False

    def _suite():
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("selected_reason_dropdown", weight=0.4,
                          check=_selected_reason, required_for_success=True),
                Milestone("address_updated_successfully", weight=0.6,
                          check=_changed, required_for_success=True),
                Milestone("stated_change_not_possible", weight=0.0,
                          check=_stated_impossible, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
