"""ValueMart mutations.

Cart ops + coupon ops touch ONLY MarketState. ``place_order`` touches
MarketState (creates the order, clears the cart) and then EMITS a
``MarketOrderPlaced`` event on the shared bus — it does NOT write Mail
directly. The bus subscriber turns that event into a confirmation email, so the
cross-app effect is auditable in ``world.events`` (a missing receipt is
distinguishable from an unread one).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from server.apps import bus
from server import ambient
from server.apps.market.state import MarketCartItem, MarketOrder, MarketState, SEED_DATE

if TYPE_CHECKING:
    from server.apps.world import WorldState


def add_to_cart(market: MarketState, *, product_id: str,
                quantity: int = 1) -> dict[str, Any]:
    # The storefront shows the ambient catalog too — 158 of ValueMart's 167
    # listings are filler that exists only in the projection — and every one of
    # them had an Add-to-cart button the engine rejected. They are looked up
    # separately so they stay out of `market.products`, which is what the world
    # hash and every verifier read. See server/ambient.py.
    #
    # Only this lookup needs it: a MarketCartItem carries its own name and
    # unit_price, so nothing downstream consults the catalog again.
    p = market.products.get(product_id) or ambient.market(product_id)
    if p is None:
        return {"ok": False, "error": "no such product"}
    if not p.in_stock:
        return {"ok": False, "error": "out of stock"}
    if quantity < 1:
        return {"ok": False, "error": "quantity must be at least 1"}
    existing = next((i for i in market.cart.items
                     if i.product_id == product_id), None)
    if existing:
        existing.quantity += quantity
    else:
        market.cart.items.append(MarketCartItem(
            product_id=product_id, name=p.name, unit_price=p.price,
            quantity=quantity))
    return {"ok": True, "product_id": product_id, "cart_count": market.cart.count()}


def remove_from_cart(market: MarketState, product_id: str) -> dict[str, Any]:
    before = len(market.cart.items)
    market.cart.items = [i for i in market.cart.items
                         if i.product_id != product_id]
    return {"ok": len(market.cart.items) != before, "product_id": product_id}


def update_qty(market: MarketState, product_id: str,
               quantity: int) -> dict[str, Any]:
    it = next((i for i in market.cart.items if i.product_id == product_id), None)
    if it is None:
        return {"ok": False, "error": "not in cart"}
    if quantity <= 0:
        return remove_from_cart(market, product_id)
    it.quantity = quantity
    return {"ok": True, "product_id": product_id, "quantity": quantity}


def clear_cart(market: MarketState) -> dict[str, Any]:
    market.cart.items.clear()
    market.cart.applied_coupon = None
    return {"ok": True}


def apply_coupon(market: MarketState, code: str) -> dict[str, Any]:
    code = (code or "").strip().upper()
    c = market.coupons.get(code)
    if c is None:
        return {"ok": False, "error": "That coupon code isn't valid at ValueMart."}
    if c.expired:
        return {"ok": False, "error": "expired",
                "message": f"Coupon {code} has expired."}
    if market.cart.subtotal() < c.min_subtotal:
        return {"ok": False, "error": "min_subtotal_not_met",
                "min_subtotal": c.min_subtotal}
    market.cart.applied_coupon = code
    return {"ok": True, "code": code}


def remove_coupon(market: MarketState) -> dict[str, Any]:
    market.cart.applied_coupon = None
    return {"ok": True}


def place_order(world: "WorldState", address_id: str | None = None,
                payment_id: str | None = None) -> dict[str, Any]:
    """Place the current ValueMart cart as an order, then emit
    MarketOrderPlaced. Takes the WHOLE world (not just MarketState) because
    emitting a cross-app event needs the shared event log; it still only WRITES
    MarketState — the Mail write happens in the subscriber."""
    market = world.market
    if not market.cart.items:
        return {"ok": False, "error": "your ValueMart cart is empty"}
    # Ship-to + payment: use the caller's choice, else the account defaults.
    # Validate only when the store actually has addresses/payments on file, so a
    # world without them still checks out.
    addr_id = address_id or market.default_address_id()
    pay_id = payment_id or market.default_payment_id()
    if market.addresses and addr_id not in market.addresses:
        return {"ok": False, "error": "unknown shipping address"}
    if market.payments and pay_id not in market.payments:
        return {"ok": False, "error": "unknown payment method"}
    subtotal = market.cart.subtotal()
    q = market.quote(subtotal=subtotal, coupon_code=market.cart.applied_coupon)
    oid = market.new_order_id()
    order = MarketOrder(
        id=oid, items=list(market.cart.items), subtotal=q["subtotal"],
        discount=q["discount"], delivery_fee=q["delivery_fee"],
        total=q["total"], placed_at=f"{SEED_DATE}T12:30:00",
        coupon_code=market.cart.applied_coupon,
        shipping_address_id=addr_id, payment_id=pay_id)
    market.orders[oid] = order
    clear_cart(market)

    bus.emit(
        world, type="MarketOrderPlaced", source_app="market", target_app="mail",
        payload={
            "order_id": oid,
            "store": market.store_name,
            "subtotal": q["subtotal"],
            "discount": q["discount"],
            "delivery_fee": q["delivery_fee"],
            "total": q["total"],
            "coupon_code": order.coupon_code,
            "shipping_address_id": order.shipping_address_id,
            "payment_id": order.payment_id,
            "items": [{"name": i.name, "qty": i.quantity,
                       "product_id": i.product_id} for i in order.items],
        })
    return {"ok": True, "order_id": oid, "total": q["total"]}
