"""mp_104 / return_wrong_size_reorder_correct_with_price_match — Xmazon×Xbay×Mail.

User labeled mp_098 originally; that ID is desk_delivered — use mp_104.

Aventis Trail Runner delivered in size 8; need 9.5. Xmazon 9.5 is $94.99;
Xbay identical 9.5 is $81.50. Gold: return size 8, buy 9.5 from cheaper shop,
email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_104/return_wrong_size_reorder_correct_with_price_match"
BRIEF_KEY = "mp_104"
BRIEF = (
    "The Aventis running shoes I ordered came in a size 8, I need a 9.5. "
    "Return the wrong pair and order the correct size, but check if it's cheaper "
    "anywhere else first since I don't want to overpay. Email me the details once "
    "it's done."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"

ORDER_ORIG = "ORD-MP104-AVENTIS8"
LINE_ORIG = "ln_mp104_aventis8"
SKU_SIZE8 = "p_mp104_aventis_8"
SKU_SIZE95_SG = "p_mp104_aventis_95"
SKU_SIZE95_VM = "vm_mp104_aventis_95"
NAME8 = "Aventis Trail Runner — Size 8"
NAME95 = "Aventis Trail Runner — Size 9.5"
SG_PRICE = 94.99
VM_PRICE = 81.50

DECOY_SG = "p_mp104_nova_runner"
DECOY_VM = "vm_mp104_peak_trail"


def task_mp_104_return_wrong_size_reorder_correct_with_price_match(
    seed: int,
) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.returns.clear()

    shop.products[SKU_SIZE8] = Product(
        id=SKU_SIZE8, name=NAME8, brand="Aventis", category="sports",
        base_price=SG_PRICE, rating=4.6, review_count=420, stock=0,
        image_emoji="👟",
        short_description="Delivered wrong size (8). Return window open.",
        tags=["aventis", "shoes", "size 8"],
    )
    shop.products[SKU_SIZE95_SG] = Product(
        id=SKU_SIZE95_SG, name=NAME95, brand="Aventis", category="sports",
        base_price=SG_PRICE, rating=4.6, review_count=420, stock=25,
        image_emoji="👟",
        short_description=f"Correct size 9.5 on Xmazon at ${SG_PRICE:.2f}.",
        tags=["aventis", "shoes", "size 9.5"],
    )
    shop.products[DECOY_SG] = Product(
        id=DECOY_SG, name="Nova Glide Runner — Size 9.5", brand="Nova",
        category="sports", base_price=79.00, rating=4.1, review_count=200,
        stock=40, image_emoji="👟",
        short_description="Different brand decoy — not Aventis.",
        tags=["nova", "shoes", "decoy"],
    )

    addr = shop.users["u_alice"].addresses["addr_home"]
    shop.orders[ORDER_ORIG] = Order(
        id=ORDER_ORIG, user_id="u_alice", placed_at="2026-05-10T14:00:00Z",
        items=[OrderItem(
            id=LINE_ORIG, product_id=SKU_SIZE8, product_name=NAME8,
            variant_id=None, variant_label="Size 8", quantity=1,
            unit_price=SG_PRICE, gift_wrap=False, gift_message="",
            ship_to_address_id=addr.id, scheduled_delivery=None,
        )],
        subtotal=SG_PRICE, discount=0.0, tax=8.07, shipping=0.0,
        total=round(SG_PRICE + 8.07, 2), promo_code=None,
        payment_id="pay_visa", status="delivered",
        shipments=[Shipment(
            id="sh_mp104", tracking_number="1Z999MP104AV8", carrier="UPS",
            item_ids=[LINE_ORIG], status="delivered",
            estimated_delivery="Delivered May 14, 2026",
            events=[ShipmentEvent(
                "2026-05-14T16:00:00Z", "delivered", "Brooklyn, NY",
                "Delivered — left at front door.",
            )],
        )],
    )

    world.market.delivery_fee = 0.0
    world.market.free_delivery_over = 0.0
    world.market.products.clear()
    world.market.cart.items.clear()
    world.market.orders.clear()
    world.market.products[SKU_SIZE95_VM] = MarketProduct(
        id=SKU_SIZE95_VM,
        name=NAME95,
        category="sports",
        price=VM_PRICE,
        emoji="👟",
        description=(
            f"Identical Aventis Trail Runner Size 9.5. Buy It Now "
            f"${VM_PRICE:.2f} with FREE shipping — cheaper than Xmazon "
            f"(${SG_PRICE:.2f})."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
        brand="Aventis",
        shop_sku=SKU_SIZE95_SG,
    )
    world.market.products[DECOY_VM] = MarketProduct(
        id=DECOY_VM,
        name="PeakTrail Runner — Size 9.5",
        category="sports",
        price=70.00,
        emoji="👟",
        description="Different brand decoy shoe on Xbay.",
        in_stock=True,
        condition="New",
        shipping_cost=5.99,
        brand="PeakTrail",
    )

    world.mail.inbox.clear()
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_104_return_wrong_size_reorder_correct_with_price_match,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _blob(msg) -> str:
        return f"{getattr(msg, 'subject', '') or ''}\n{getattr(msg, 'body', '') or ''}"

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _market(p: Probe):
        return getattr(p.world, "market", None) if p.world else None

    def _initiated_return(p: Probe) -> bool:
        shop = _shop(p)
        if not shop:
            return False
        for r in (shop.returns or {}).values():
            if getattr(r, "order_id", "") == ORDER_ORIG:
                return True
        return _log_has(p, "initiate_return") or _log_has(p, "create_return")

    def _compared_prices(p: Probe) -> bool:
        # Proxy: bought from VM (implies compare) OR email mentions both prices / shops.
        mkt = _market(p)
        if mkt and any(
            any(getattr(it, "product_id", "") == SKU_SIZE95_VM for it in (o.items or []))
            for o in (mkt.orders or {}).values()
        ):
            return True
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            has_vm = "valuemart" in text or "value mart" in text or "81.50" in text or "81.5" in text
            has_sg = "shopgym" in text or "94.99" in text or "shop gym" in text
            if has_vm and (has_sg or "cheaper" in text or "price" in text):
                return True
        return False

    def _ordered_cheaper(p: Probe) -> bool:
        mkt = _market(p)
        if not mkt:
            return False
        for o in (mkt.orders or {}).values():
            for it in (o.items or []):
                if getattr(it, "product_id", "") == SKU_SIZE95_VM:
                    return True
                name = (getattr(it, "name", "") or "").lower()
                if "aventis" in name and ("9.5" in name or "9,5" in name):
                    return True
        return False

    def _emailed(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if "aventis" in text or "9.5" in text or "return" in text:
                return True
        return False

    def _reordered_expensive(p: Probe) -> bool:
        shop = _shop(p)
        if not shop:
            return False
        for oid, o in (shop.orders or {}).items():
            if oid == ORDER_ORIG:
                continue
            for it in (o.items or []):
                if getattr(it, "product_id", "") == SKU_SIZE95_SG:
                    return True
        return False

    def _ordered_wrong_size(p: Probe) -> bool:
        shop = _shop(p)
        mkt = _market(p)
        # New purchases of size 8.
        if shop:
            for oid, o in (shop.orders or {}).items():
                if oid == ORDER_ORIG:
                    continue
                for it in (o.items or []):
                    pid = getattr(it, "product_id", "")
                    name = (getattr(it, "product_name", "") or getattr(it, "name", "") or "").lower()
                    if pid == SKU_SIZE8 or ("aventis" in name and "size 8" in name and "9.5" not in name):
                        return True
        if mkt:
            for o in (mkt.orders or {}).values():
                for it in (o.items or []):
                    name = (getattr(it, "name", "") or "").lower()
                    if "aventis" in name and "size 8" in name and "9.5" not in name:
                        return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "initiated_return_on_correct_original_order",
                    weight=0.2, check=_initiated_return, required_for_success=True,
                ),
                Milestone(
                    "compared_price_across_both_shops",
                    weight=0.25, check=_compared_prices, required_for_success=True,
                ),
                Milestone(
                    "ordered_correct_size_from_cheaper_shop",
                    weight=0.35, check=_ordered_cheaper, required_for_success=True,
                ),
                Milestone(
                    "emailed_user_confirmation",
                    weight=0.2, check=_emailed, required_for_success=True,
                ),
                Milestone(
                    "reordered_from_more_expensive_shop_without_comparing",
                    weight=0.0, check=_reordered_expensive, forbidden=True,
                ),
                Milestone(
                    "ordered_wrong_size",
                    weight=0.0, check=_ordered_wrong_size, forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
