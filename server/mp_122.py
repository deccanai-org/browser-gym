"""mp_122 / return_window_named_in_email — ShopGym×ShopMail.

Trailhead Boots delivered >30 days ago. Gym_now is just past the window.
Gold = read the delivery date, refuse the return, email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_122/return_window_named_in_email"
BRIEF_KEY = "mp_122"
BRIEF = (
    "These boots don't fit, I know returns have to happen within 30 days of "
    "delivery, can you check if I'm still inside that window and start the "
    "return if so, tell me if I'm not. Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
ORDER_ID = "ORD-MP122-BOOTS"
LINE_ID = "ln_mp122_boots"
SKU = "p_mp122_trailhead_boots"
NAME = "Trailhead Boots"
DELIVERED = "2026-04-20"
DELIVERED_LABEL = "Monday April 20, 2026"


def task_mp_122_return_window_named_in_email(seed: int) -> "WorldState":
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
        brand="Trailhead",
        category="sports",
        base_price=89.00,
        rating=4.4,
        review_count=310,
        stock=8,
        image_emoji="🥾",
        short_description="Waterproof hiking boots. Delivered April 20, 2026.",
        tags=["boots", "trailhead"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-04-16T11:00:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=SKU,
                product_name=NAME,
                variant_id=None,
                variant_label="Size 8",
                quantity=1,
                unit_price=89.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=89.00,
        discount=0.0,
        tax=7.56,
        shipping=0.0,
        total=96.56,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[
            Shipment(
                id="sh_mp122",
                carrier="UPS",
                tracking_number="1ZMP122BOOT",
                item_ids=[LINE_ID],
                status="delivered",
                estimated_delivery=DELIVERED_LABEL,
                events=[
                    ShipmentEvent(
                        timestamp="2026-04-20T16:10:00Z",
                        status="delivered",
                        detail=f"Delivered {DELIVERED_LABEL} — 31 days before today May 21.",
                    )
                ],
            )
        ],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_122_return_window_named_in_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _CLOSED = re.compile(
        r"(?ix)(outside|past|expired|closed|too\s+late|over\s+30|"
        r"31\s+days|not\s+(still\s+)?(in|inside)|window\s+(is\s+)?(closed|over))"
    )
    _APR = re.compile(r"(?ix)(april\s*20|2026-04-20|apr\s*20)")

    def _checked_date(p: Probe) -> bool:
        if _log_has(p, "view_order", order_id=ORDER_ID):
            return True
        if _log_has(p, "view_order_detail", order_id=ORDER_ID):
            return True
        return _log_has(p, "view_orders") or "/account/orders" in (p.url or "")

    def _has_return(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop is None:
            return False
        return any(
            getattr(r, "order_id", "") == ORDER_ID
            for r in (shop.returns or {}).values()
        ) or _log_has(p, "initiate_return", order_id=ORDER_ID)

    def _blob(p: Probe) -> str:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return ""
        parts = []
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            parts.append(f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}")
        return "\n".join(parts)

    def _computed(p: Probe) -> bool:
        b = _blob(p)
        return bool(_CLOSED.search(b) or _APR.search(b))

    def _no_return(p: Probe) -> bool:
        return (not _has_return(p)) and (
            _checked_date(p) or _computed(p) or bool(_blob(p).strip())
        )

    def _emailed(p: Probe) -> bool:
        return bool(_CLOSED.search(_blob(p))) and not _has_return(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_delivery_date",
                    weight=0.3,
                    check=_checked_date,
                    required_for_success=True,
                ),
                Milestone(
                    "computed_30_day_window_correctly",
                    weight=0.3,
                    check=_computed,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_initiate_return_since_window_closed",
                    weight=0.2,
                    check=_no_return,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_accurate_status",
                    weight=0.2,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "initiated_return_after_window_closed",
                    weight=0.0,
                    check=_has_return,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
