"""mp_129 / named_stock_threshold_reorder — Xmazon×Xmail.

Three prior dog-food orders. Consumption ~1 bag / 21 days. Last bag May 14;
today May 21 → ~14 days of stock left, not less than 2 weeks. Gold = do not
reorder; email the math.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_129/named_stock_threshold_reorder"
BRIEF_KEY = "mp_129"
BRIEF = (
    "Only reorder the dog food if there's less than 2 weeks of stock left "
    "based on my usage, I don't want to overstock, check my order history to "
    "figure out how fast I go through it. Email me the math."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
SKU = "p_mp129_dogfood"
NAME = "Prairie Gold Dog Food (15 lb)"
ORDERS = (
    ("ORD-MP129-DF1", "ln_mp129_df1", "2026-04-02T12:00:00Z", "2026-04-02"),
    ("ORD-MP129-DF2", "ln_mp129_df2", "2026-04-23T12:00:00Z", "2026-04-23"),
    ("ORD-MP129-DF3", "ln_mp129_df3", "2026-05-14T12:00:00Z", "2026-05-14"),
)


def task_mp_129_named_stock_threshold_reorder(seed: int) -> "WorldState":
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
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="Prairie Gold",
        category="pet",
        base_price=34.99,
        rating=4.6,
        review_count=880,
        stock=40,
        image_emoji="🐶",
        short_description="15 lb bag. Order history shows ~21 days per bag.",
        tags=["dog", "pet food"],
        is_subscribable=True,
    )
    for oid, lid, placed, day in ORDERS:
        shop.orders[oid] = Order(
            id=oid,
            user_id="u_alice",
            placed_at=placed,
            items=[
                OrderItem(
                    id=lid,
                    product_id=SKU,
                    product_name=NAME,
                    variant_id=None,
                    variant_label="",
                    quantity=1,
                    unit_price=34.99,
                    gift_wrap=False,
                    gift_message="",
                    ship_to_address_id="addr_home",
                    scheduled_delivery=None,
                )
            ],
            subtotal=34.99,
            discount=0.0,
            tax=2.97,
            shipping=0.0,
            total=37.96,
            promo_code=None,
            payment_id="pay_visa",
            status="delivered",
            shipments=[
                Shipment(
                    id=f"sh_{oid}",
                    carrier="UPS",
                    tracking_number=f"1Z{oid[-4:]}DOG",
                    item_ids=[lid],
                    status="delivered",
                    estimated_delivery=day,
                    events=[
                        ShipmentEvent(
                            timestamp=placed,
                            status="delivered",
                            detail=f"Delivered {day} — 1 bag Prairie Gold.",
                        )
                    ],
                )
            ],
        )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_129_named_stock_threshold_reorder,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _MATH = re.compile(
        r"(?ix)(21\s*day|14\s*day|2\s*weeks?|may\s*14|april\s*(2|23)|"
        r"per\s+bag|consumption|rate|enough|not\s+(re)?order|"
        r"don't\s+need|do\s+not\s+need|stock\s+left)"
    )
    _NO_REORDER = re.compile(
        r"(?ix)(not\s+(re)?order|don't\s+(re)?order|do\s+not\s+(re)?order|"
        r"no\s+(need\s+to\s+)?(re)?order|enough\s+(stock|left)|"
        r"about\s+(two|2)\s+weeks)"
    )

    def _init_ids(p: Probe) -> set:
        init = getattr(p, "initial_world", None)
        return set((init.shop.orders or {}) if init and init.shop else {})

    def _new_df(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        out = []
        for oid, o in (shop.orders or {}).items():
            if oid in _init_ids(p):
                continue
            if getattr(o, "status", "") == "cancelled":
                continue
            if any(getattr(it, "product_id", "") == SKU for it in o.items):
                out.append(o)
        return out

    def _checked_history(p: Probe) -> bool:
        if _log_has(p, "view_orders") or _log_has(p, "view_order"):
            return True
        return "/account/orders" in (p.url or p.active_tab_url or "")

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
        return _checked_history(p) and bool(_MATH.search(_blob(p)))

    def _correct(p: Probe) -> bool:
        return (not _new_df(p)) and bool(_NO_REORDER.search(_blob(p)) or _MATH.search(_blob(p)))

    def _emailed_math(p: Probe) -> bool:
        return bool(_MATH.search(_blob(p)))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "computed_consumption_rate_from_order_history",
                    weight=0.4,
                    check=_computed,
                    required_for_success=True,
                ),
                Milestone(
                    "correctly_determined_reorder_necessity",
                    weight=0.4,
                    check=_correct,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_math_shown",
                    weight=0.2,
                    check=_emailed_math,
                    required_for_success=True,
                ),
                Milestone(
                    "reordered_without_computing_rate",
                    weight=0.0,
                    check=lambda p: bool(_new_df(p)) and not _MATH.search(_blob(p)),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "reported_wrong_math_without_verification",
                    weight=0.0,
                    check=lambda p: bool(_new_df(p)) and _checked_history(p) is False,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
