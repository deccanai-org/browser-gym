"""Food mutations.

``add_dish`` and ``track_food_order`` touch ONLY FoodState. ``place_food_order``
touches FoodState (creates the order, clears the cart) and then EMITS a
``FoodOrderPlaced`` event — it does NOT write Mail directly. The bus
subscriber turns that event into a receipt email (and a calendar slot in
Phase 2). That indirection is the whole point: cross-app effects are
auditable in ``world.events`` and a missing receipt is distinguishable from
an unread one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from server.apps import bus
from server.apps.food.state import (
    FoodCartItem,
    FoodOrder,
    FoodState,
    Restaurant,
    SEED_DATE,
)

if TYPE_CHECKING:
    from server.apps.world import WorldState


def add_dish(food: FoodState, *, restaurant_id: str, dish_id: str,
             quantity: int = 1) -> dict[str, Any]:
    """Add a dish to the food cart. Food carts are SINGLE-restaurant (like
    real delivery apps): adding from a different restaurant is rejected so
    the agent has to clear the cart first — a realistic friction point."""
    r = food.restaurants.get(restaurant_id)
    if r is None:
        return {"ok": False, "error": "no such restaurant"}
    d = r.dish(dish_id)
    if d is None:
        return {"ok": False, "error": "no such dish"}
    if quantity < 1:
        return {"ok": False, "error": "quantity must be at least 1"}
    if food.cart.restaurant_id and food.cart.restaurant_id != restaurant_id:
        return {"ok": False, "error": "cart_has_other_restaurant",
                "current_restaurant_id": food.cart.restaurant_id}

    food.cart.restaurant_id = restaurant_id
    existing = next(
        (i for i in food.cart.items if i.dish_id == dish_id), None,
    )
    if existing:
        existing.quantity += quantity
    else:
        food.cart.items.append(FoodCartItem(
            dish_id=dish_id, restaurant_id=restaurant_id,
            name=d.name, unit_price=d.price, quantity=quantity,
        ))
    return {"ok": True, "dish_id": dish_id, "cart_count": food.cart.count()}


def clear_cart(food: FoodState) -> dict[str, Any]:
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.cart.delivery_note = ""
    food.cart.scheduled_delivery = None
    return {"ok": True}


def set_scheduled_delivery(food: FoodState, day: str | None) -> dict[str, Any]:
    """Set cart schedule-ahead day (YYYY-MM-DD) or clear for ASAP."""
    day = (day or "").strip() or None
    if day is not None and len(day) != 10:
        return {"ok": False, "error": "invalid_scheduled_delivery"}
    food.cart.scheduled_delivery = day
    return {"ok": True, "scheduled_delivery": day}


def remove_dish(food: FoodState, *, dish_id: str) -> dict[str, Any]:
    """Remove one dish line from the food cart (bridge ``food.remove_item``)."""
    before = len(food.cart.items)
    food.cart.items[:] = [i for i in food.cart.items if i.dish_id != dish_id]
    if len(food.cart.items) == before:
        return {"ok": False, "error": "dish not in cart"}
    if not food.cart.items:
        food.cart.restaurant_id = None
    return {"ok": True, "dish_id": dish_id, "cart_count": food.cart.count()}


def set_dish_qty(food: FoodState, *, dish_id: str, quantity: int) -> dict[str, Any]:
    """Set quantity for a cart line; quantity < 1 removes it (bridge ``food.set_qty``)."""
    if quantity < 1:
        return remove_dish(food, dish_id=dish_id)
    line = next((i for i in food.cart.items if i.dish_id == dish_id), None)
    if line is None:
        return {"ok": False, "error": "dish not in cart"}
    line.quantity = quantity
    return {"ok": True, "dish_id": dish_id, "quantity": quantity, "cart_count": food.cart.count()}


def set_delivery_note(food: FoodState, note: str) -> dict[str, Any]:
    """Persist a courier/restaurant delivery instruction on the cart (M362)."""
    food.cart.delivery_note = (note or "").strip()
    return {"ok": True, "delivery_note": food.cart.delivery_note}


def _parse_eta_minutes(label: str | None) -> int | None:
    """Parse ``3:20 PM``-style labels to minutes-from-midnight for max()."""
    import re

    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*$", (label or "").strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    h = h % 12
    if ap == "PM":
        h += 12
    return h * 60 + mi


def _order_eta_label(food: FoodState, restaurant: Restaurant) -> str:
    """Prefer the latest dish-level ``eta_label`` in the cart; else restaurant."""
    best_label = restaurant.eta_label
    best_mins: int | None = _parse_eta_minutes(best_label)
    for it in food.cart.items:
        d = restaurant.dish(it.dish_id)
        label = getattr(d, "eta_label", None) if d is not None else None
        mins = _parse_eta_minutes(label)
        if label and mins is not None and (best_mins is None or mins > best_mins):
            best_label, best_mins = label, mins
        elif label and best_mins is None:
            best_label = label
    return best_label or restaurant.eta_label


def place_food_order(world: "WorldState",
                     delivery_note: str | None = None,
                     delivery_mode: str | None = None,
                     scheduled_delivery: str | None = None) -> dict[str, Any]:
    """Place the current food cart as an order, then emit FoodOrderPlaced.

    Takes the WHOLE world (not just FoodState) because emitting a cross-app
    event needs the shared event log. It still only WRITES FoodState; the
    Mail write happens in the subscriber.

    ``delivery_note`` (optional) overrides any cart.delivery_note at commit
    time — used by the checkout form when delivery notes are enabled (M362).
    ``scheduled_delivery`` (optional YYYY-MM-DD) overrides cart.scheduled_delivery
    when schedule-ahead is enabled for the task.
    """
    food = world.food
    if not food.cart.items:
        return {"ok": False, "error": "food cart is empty"}
    r = food.restaurants.get(food.cart.restaurant_id or "")
    if r is None:
        return {"ok": False, "error": "restaurant unavailable"}

    note = (delivery_note if delivery_note is not None
            else food.cart.delivery_note) or ""
    note = note.strip()
    mode = (delivery_mode or "delivery").strip().lower()
    if mode not in ("delivery", "pickup"):
        mode = "delivery"
    sched = scheduled_delivery if scheduled_delivery is not None else food.cart.scheduled_delivery
    if not getattr(food, "enable_schedule_ahead", False):
        sched = None
    else:
        sched = (sched or "").strip() or None
    subtotal = food.cart.subtotal()
    fee = 0.0 if mode == "pickup" else r.delivery_fee
    total = round(subtotal + fee, 2)
    eta = _order_eta_label(food, r)
    oid = food.new_order_id()
    order = FoodOrder(
        id=oid, restaurant_id=r.id, restaurant_name=r.name,
        items=list(food.cart.items),
        subtotal=subtotal, delivery_fee=fee, total=total,
        placed_at=f"{SEED_DATE}T18:30:00", eta_label=eta,
        status="preparing",
        delivery_note=note,
        delivery_mode=mode,
        scheduled_delivery=sched,
    )
    food.orders[oid] = order
    clear_cart(food)

    # Cross-app effect: receipt email (+ Phase-2 calendar delivery slot).
    bus.emit(
        world, type="FoodOrderPlaced", source_app="food", target_app="mail",
        payload={
            "order_id": oid,
            "restaurant": r.name,
            "subtotal": subtotal,
            "delivery_fee": fee,
            "total": total,
            "eta": eta,
            "items": [{"name": i.name, "qty": i.quantity} for i in order.items],
            "delivery_note": note,
            "scheduled_delivery": sched,
        },
    )
    return {"ok": True, "order_id": oid, "total": total, "eta": eta,
            "scheduled_delivery": sched}


def track_food_order(food: FoodState, order_id: str) -> dict[str, Any]:
    o = food.orders.get(order_id)
    if o is None:
        return {"ok": False, "error": "no such order"}
    return {"ok": True, "order_id": order_id, "status": o.status,
            "eta": o.eta_label, "total": o.total}


def cancel_food_order(food: FoodState, order_id: str) -> dict[str, Any]:
    """Cancel an active food order (preparing / on_the_way). Delivered orders
    are refused. Bridge maps this to POST /food/order/{order_id}/cancel."""
    o = food.orders.get(order_id)
    if o is None:
        return {"ok": False, "error": "no such order"}
    status = (o.status or "").lower()
    if status in ("delivered", "cancelled", "canceled"):
        return {"ok": False, "error": "order_not_cancellable", "status": o.status}
    o.status = "cancelled"
    return {"ok": True, "order_id": order_id, "status": o.status}
