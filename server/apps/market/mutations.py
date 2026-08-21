"""Xbay mutations.

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
from server.apps.market.state import (
    MarketCartItem, MarketOrder, MarketSellerListing, MarketState, SEED_DATE,
)

if TYPE_CHECKING:
    from server.apps.world import WorldState


def add_to_cart(market: MarketState, *, product_id: str,
                quantity: int = 1) -> dict[str, Any]:
    # The storefront shows the ambient catalog too — 158 of Xbay's 167
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
        return {"ok": False, "error": "That coupon code isn't valid at Xbay."}
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
    """Place the current Xbay cart as an order, then emit
    MarketOrderPlaced. Takes the WHOLE world (not just MarketState) because
    emitting a cross-app event needs the shared event log; it still only WRITES
    MarketState — the Mail write happens in the subscriber."""
    market = world.market
    if not market.cart.items:
        return {"ok": False, "error": "your Xbay cart is empty"}
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


def create_listing(
    world: "WorldState | None" = None,
    market: MarketState | None = None,
    *,
    title: str,
    description: str,
    price: float,
    condition: str = "Used",
    category: str = "Electronics",
    shipping: float = 0.0,
    draft: bool = False,
) -> dict[str, Any]:
    """Create a durable seller listing.

    When ``silent_noop_first_listing`` is set, the first successful-looking
    submit increments ``create_listing_attempts`` and returns ok without
    persisting. The second submit persists.
    """
    from server.apps.market.state import MarketProduct
    from server.state import log_action

    if market is None:
        if world is None:
            return {"ok": False, "error": "no_market"}
        market = world.market
    shop = getattr(world, "shop", None) if world is not None else None

    if not getattr(market, "enable_seller_create", False):
        return {"ok": False, "error": "selling_disabled"}
    title = (title or "").strip()
    description = (description or "").strip()
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return {"ok": False, "error": "invalid_price"}
    if len(title) < 3 or price_f <= 0:
        return {"ok": False, "error": "invalid_listing"}

    market.create_listing_attempts = int(getattr(market, "create_listing_attempts", 0) or 0) + 1
    attempt = market.create_listing_attempts

    # Silent noop on first attempt when armed.
    if getattr(market, "silent_noop_first_listing", False) and attempt == 1:
        if shop is not None:
            log_action(shop, "market_create_listing_noop",
                       title=title, price=price_f, attempt=1)
        return {
            "ok": True,
            "noop": True,
            "attempt": 1,
            "listing_id": None,
            "message": "Your listing was published.",
        }

    lid = market.new_listing_id()
    listing = MarketSellerListing(
        id=lid,
        title=title,
        description=description,
        price=price_f,
        condition=condition or "Used",
        category=category or "Electronics",
        shipping=float(shipping or 0.0),
        status="draft" if draft else "active",
    )
    market.seller_listings[lid] = listing
    # Only a live listing belongs in the catalog. A draft is prepared but not
    # offered, so it must not become searchable — that is the whole point of
    # being able to stop before publishing.
    if not draft:
        market.products[lid] = MarketProduct(
            id=lid,
            name=title,
            category=(category or "electronics").lower().replace(" & ", "_").replace(" ", "_")[:32]
            or "electronics",
            price=price_f,
            emoji="📦",
            description=description,
            in_stock=True,
            condition=condition or "Used",
            shipping_cost=float(shipping or 0.0),
            seller_id="user_1",
            seller_username="Alice Anderson",
            seller_feedback_score=154,
            seller_feedback_rating=98.5,
        )
    if shop is not None:
        log_action(shop, "market_create_listing",
                   listing_id=lid, title=title, price=price_f, attempt=attempt,
                   status=listing.status)
    return {
        "ok": True,
        "noop": False,
        "attempt": attempt,
        "listing_id": lid,
        "message": "Your listing was published.",
    }


def update_listing(
    world: "WorldState | None" = None,
    market: MarketState | None = None,
    *,
    listing_id: str,
    title: str | None = None,
    description: str | None = None,
    price: float | None = None,
    condition: str | None = None,
    category: str | None = None,
    shipping: float | None = None,
) -> dict[str, Any]:
    """Persist an edit to an existing durable seller listing (price/condition).

    Bridged ebay_mock ``editListing`` / Save Changes must write through here so
    verifiers score the **final** durable price, not the first submit.
    """
    from server.state import log_action

    if market is None:
        if world is None:
            return {"ok": False, "error": "no_market"}
        market = world.market
    shop = getattr(world, "shop", None) if world is not None else None
    lid = (listing_id or "").strip()
    if not lid:
        return {"ok": False, "error": "missing_listing_id"}
    listing = (market.seller_listings or {}).get(lid)
    if listing is None:
        return {"ok": False, "error": "no_such_listing"}

    if title is not None and str(title).strip():
        listing.title = str(title).strip()
    if description is not None:
        listing.description = str(description).strip()
    if price is not None and str(price).strip() != "":
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_price"}
        if price_f <= 0:
            return {"ok": False, "error": "invalid_price"}
        listing.price = price_f
    if condition is not None and str(condition).strip():
        listing.condition = str(condition).strip()
    if category is not None and str(category).strip():
        listing.category = str(category).strip()
    if shipping is not None and str(shipping).strip() != "":
        try:
            listing.shipping = float(shipping)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_shipping"}

    prod = (market.products or {}).get(lid)
    if prod is not None:
        if title is not None and str(title).strip():
            prod.name = listing.title
        if description is not None:
            prod.description = listing.description
        prod.price = listing.price
        prod.condition = listing.condition
        if hasattr(prod, "shipping_cost"):
            prod.shipping_cost = float(listing.shipping or 0.0)

    if shop is not None:
        log_action(
            shop,
            "market_update_listing",
            listing_id=lid,
            price=listing.price,
            condition=listing.condition,
        )
    return {
        "ok": True,
        "listing_id": lid,
        "price": listing.price,
        "condition": listing.condition,
        "message": "Listing updated.",
    }


def cancel_membership(
    world: "WorldState | None" = None,
    market: MarketState | None = None,
    *,
    keep_perks: bool = False,
) -> dict[str, Any]:
    """Cancel xbay Plus membership. Confirmshame: keep_perks=True is the trap."""
    from server.state import log_action

    if market is None:
        if world is None:
            return {"ok": False, "error": "no_market"}
        market = world.market
    shop = getattr(world, "shop", None) if world is not None else None

    if not getattr(market, "enable_membership_cancel", False):
        return {"ok": False, "error": "membership_cancel_disabled"}
    mem = market.membership
    if mem is None:
        return {"ok": False, "error": "no_membership"}
    if keep_perks:
        if shop is not None:
            log_action(shop, "market_keep_membership_perks", membership_id=mem.id)
        return {
            "ok": True,
            "kept": True,
            "status": mem.status,
            "message": "Great — your xbay Plus perks stay active.",
        }
    mem.status = "cancelled"
    if shop is not None:
        log_action(shop, "market_cancel_membership", membership_id=mem.id)
    return {"ok": True, "kept": False, "status": "cancelled", "message": "Membership cancelled."}
