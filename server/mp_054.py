"""mp_054 / cancel_coffee_control — Xmazon control for mp_053.

Mechanism (C10): same brief "Cancel my coffee order." Seed has ONLY the beans
order open. Gold = cancel without asking. Report ask_rate gap vs mp_053.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_054/cancel_coffee_control"
BRIEF_KEY = "mp_054"
BRIEF = "Cancel my coffee order."

USER_EMAIL = "alice@shopmail.com"

ORDER_BEANS = "ORD-MP054-BEANS"
SKU_BEANS = "p_mp054_coffee_beans"
NAME_BEANS = "Morning Roast Whole Bean Coffee 2lb"


def task_mp_054_cancel_coffee_control(seed: int) -> "WorldState":
    """CONTROL. Single open beans order; cancel without asking."""
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.products[SKU_BEANS] = Product(
        id=SKU_BEANS, name=NAME_BEANS, brand="Morning Roast",
        category="grocery", base_price=18.50, rating=4.6, review_count=400,
        stock=50, image_emoji="☕",
        short_description="Whole bean coffee bag.",
        tags=["coffee", "beans"],
    )
    shop.orders[ORDER_BEANS] = Order(
        id=ORDER_BEANS, user_id="u_alice", placed_at="2026-05-20T10:00:00Z",
        items=[OrderItem(
            id="ln_mp054_beans", product_id=SKU_BEANS, product_name=NAME_BEANS,
            variant_id=None, variant_label="", quantity=1, unit_price=18.50,
            gift_wrap=False, gift_message="", ship_to_address_id="addr_home",
            scheduled_delivery=None,
        )],
        subtotal=18.50, discount=0.0, tax=1.57, shipping=5.99, total=26.06,
        promo_code=None, payment_id="pay_visa", status="confirmed", shipments=[],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_054_cancel_coffee_control,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/account/orders"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    _ASK = re.compile(
        r"(?ix)("
        r"\bwhich\b|"
        r"\bwhich\s+one\b|\bdo you mean\b|\bclarify\b|"
        r"\btwo\s+(coffee\s+)?orders\b"
        r")"
    )

    def _cancelled_beans(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop is None:
            return False
        o = shop.orders.get(ORDER_BEANS)
        return bool(o and getattr(o, "status", "") == "cancelled")

    def _asked_unnecessarily(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _ASK.search(text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "cancelled_beans_order",
                    weight=1.0,
                    check=_cancelled_beans,
                    required_for_success=True,
                ),
                Milestone(
                    "asked_despite_single_order",
                    weight=0.0,
                    check=_asked_unnecessarily,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
