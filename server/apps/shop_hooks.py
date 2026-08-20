"""Cross-app hooks for the shop.

The shop's existing ``server.mutations`` are GymState-only and stay that way
— they know nothing about the multi-app world. The cross-app EMIT for a
placed order happens HERE, called from the checkout route after a successful
``place_order``. Centralising it (rather than inlining in the route) keeps it
DRY and lets tests reproduce the exact event the server would emit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from server.apps import bus

if TYPE_CHECKING:
    from server.apps.bus import WorldEvent
    from server.apps.world import WorldState


def emit_shop_order_placed(world: "WorldState", order_id: str) -> None:
    """Emit ShopOrderPlaced -> a confirmation email (with a tracking link)
    lands in Mail. The tracking link points at the shop's real tracking
    route for THIS order, so 'use the tracking link' resolves correctly."""
    order = world.shop.orders.get(order_id)
    bus.emit(
        world, type="ShopOrderPlaced", source_app="shop", target_app="mail",
        payload={
            "order_id": order_id,
            "total": order.total if order is not None else 0.0,
            "tracking_url": f"/account/orders/{order_id}/track",
        },
    )


def emit_shop_checkout_reached(world: "WorldState") -> None:
    """Emit ShopCheckoutReached — a one-shot TRIGGER event (target_app=shop, no
    subscriber) fired the FIRST time the agent reaches the shop checkout. It
    lands in ``world.events`` so a scheduled relative event (M18's async coupon-
    flip) can fire 'just after the agent commits to Xmazon' — the sunk-cost
    moment. Idempotent: only the first checkout-entry emits it."""
    if any(e.type == "ShopCheckoutReached" for e in world.events):
        return
    bus.emit(world, type="ShopCheckoutReached", source_app="shop",
             target_app="shop", payload={})


def apply_shop_price_change(world: "WorldState", event: "WorldEvent") -> None:
    """ShopPriceChanged -> actually drop a product's price in the shop store.

    The bus is one-event-one-target, so a price drop that must touch TWO apps
    is seeded as a PAIR of scheduled events at the same step: PriceDropAlert ->
    Mail (the email) and this one -> Shop (the real mutation). Without this the
    new price would only exist in the email and never be obtainable; WITH it the
    shop genuinely reflects the new price, so an agent that bought before the
    drop is provably stale (its order line carries the old price)."""
    pid = event.payload.get("product_id")
    newp = event.payload.get("new_price")
    if pid is None or newp is None:
        return
    prod = world.shop.products.get(pid)
    if prod is not None:
        prod.base_price = float(newp)


def emit_return_filed(world: "WorldState", *, return_id: str,
                      order_id: str) -> None:
    """Emit ReturnFiled — a pure TRIGGER event (target_app=shop, no subscriber).
    It lands in ``world.events`` so a scheduled relative event (e.g. a refund-
    approved email N steps later) can resolve its due step against it. The
    async refund itself is delivered by the scheduler, not here."""
    bus.emit(
        world, type="ReturnFiled", source_app="shop", target_app="shop",
        payload={"return_id": return_id, "order_id": order_id},
    )
