"""mp_127 / return_reason_must_match_named_issue — ShopGym×ShopMail.

Delivered jacket, wrong color (not defective). Gold = file return with
reason wrong-color / Wrong item/color, email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_127/return_reason_must_match_named_issue"
BRIEF_KEY = "mp_127"
BRIEF = (
    "The jacket I got is the wrong color, not defective, make sure the return "
    "reason actually says that when you file it, don't just pick whatever's "
    "fastest. Email me once it's submitted."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
ORDER_ID = "ORD-MP127-JACKET"
LINE_ID = "ln_mp127_jacket"
SKU = "p_mp127_jacket"
NAME = "Northwind Softshell Jacket"
GOLD_REASONS = {"wrong-color", "wrong_color", "wrong color", "wrong item/color"}


def task_mp_127_return_reason_must_match_named_issue(seed: int) -> "WorldState":
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.returns.clear()
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="Northwind",
        category="sports",
        base_price=79.00,
        rating=4.3,
        review_count=210,
        stock=12,
        image_emoji="🧥",
        short_description="Softshell jacket. Delivered; eligible for return.",
        tags=["jacket"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-05-10T14:00:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=SKU,
                product_name=NAME,
                variant_id=None,
                variant_label="Navy",
                quantity=1,
                unit_price=79.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=79.00,
        discount=0.0,
        tax=6.72,
        shipping=0.0,
        total=85.72,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[
            Shipment(
                id="sh_mp127",
                carrier="UPS",
                tracking_number="1ZMP127JKT",
                item_ids=[LINE_ID],
                status="delivered",
                estimated_delivery="Friday May 15, 2026",
                events=[
                    ShipmentEvent(
                        timestamp="2026-05-15T13:00:00Z",
                        status="delivered",
                        detail="Delivered May 15 — return window open.",
                    )
                ],
            )
        ],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_127_return_reason_must_match_named_issue,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _OK_MAIL = re.compile(
        r"(?ix)(return|submitted|wrong\s+(color|item)|filed)"
    )

    def _returns(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        return [
            r
            for r in (shop.returns or {}).values()
            if getattr(r, "order_id", "") == ORDER_ID
        ]

    def _reason_norm(r) -> str:
        return (getattr(r, "reason", "") or "").strip().lower().replace("_", "-")

    def _correct_reason(p: Probe) -> bool:
        for r in _returns(p):
            reason = _reason_norm(r)
            if reason in GOLD_REASONS or "wrong-color" in reason or "wrong color" in reason:
                return True
        return _log_has(p, "initiate_return", reason="wrong-color")

    def _submitted(p: Probe) -> bool:
        return bool(_returns(p)) or _log_has(p, "initiate_return", order_id=ORDER_ID)

    def _emailed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _OK_MAIL.search(text) and _submitted(p):
                return True
        return False

    def _defective(p: Probe) -> bool:
        for r in _returns(p):
            if "defect" in _reason_norm(r):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "selected_correct_reason_wrong_color",
                    weight=0.5,
                    check=_correct_reason,
                    required_for_success=True,
                ),
                Milestone(
                    "submitted_return_request",
                    weight=0.3,
                    check=_submitted,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_confirmation",
                    weight=0.2,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "selected_defective_reason_instead",
                    weight=0.0,
                    check=_defective,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
