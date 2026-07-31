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
from server.apps.food.state import FoodCartItem, FoodOrder, FoodState, SEED_DATE

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


def set_dish_quantity(food: FoodState, *, dish_id: str, quantity: int) -> dict[str, Any]:
    """Change one cart line's quantity; quantity 0 removes the line.

    Without this the food cart was add-or-clear-everything: a realistic app lets
    you back one item down, and a task that says "make it two, not three" had no
    way to be performed.
    """
    line = next((i for i in food.cart.items if i.dish_id == dish_id), None)
    if line is None:
        return {"ok": False, "error": "no such line"}
    if quantity < 0:
        return {"ok": False, "error": "quantity must be at least 0"}
    if quantity == 0:
        food.cart.items.remove(line)
        if not food.cart.items:          # an empty cart is restaurant-less again
            food.cart.restaurant_id = None
    else:
        line.quantity = quantity
    return {"ok": True, "dish_id": dish_id, "cart_count": food.cart.count()}


def remove_dish(food: FoodState, *, dish_id: str) -> dict[str, Any]:
    return set_dish_quantity(food, dish_id=dish_id, quantity=0)


def clear_cart(food: FoodState) -> dict[str, Any]:
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.cart.delivery_note = ""
    return {"ok": True}


def set_delivery_note(food: FoodState, note: str) -> dict[str, Any]:
    """Persist a courier/restaurant delivery instruction on the cart (M362)."""
    food.cart.delivery_note = (note or "").strip()
    return {"ok": True, "delivery_note": food.cart.delivery_note}


def place_food_order(world: "WorldState",
                     delivery_note: str | None = None) -> dict[str, Any]:
    """Place the current food cart as an order, then emit FoodOrderPlaced.

    Takes the WHOLE world (not just FoodState) because emitting a cross-app
    event needs the shared event log. It still only WRITES FoodState; the
    Mail write happens in the subscriber.

    ``delivery_note`` (optional) overrides any cart.delivery_note at commit
    time — used by the checkout form when delivery notes are enabled (M362).
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
    subtotal = food.cart.subtotal()
    total = round(subtotal + r.delivery_fee, 2)
    oid = food.new_order_id()
    order = FoodOrder(
        id=oid, restaurant_id=r.id, restaurant_name=r.name,
        items=list(food.cart.items),
        subtotal=subtotal, delivery_fee=r.delivery_fee, total=total,
        placed_at=f"{SEED_DATE}T18:30:00", eta_label=r.eta_label,
        status="preparing",
        delivery_note=note,
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
            "delivery_fee": r.delivery_fee,
            "total": total,
            "eta": r.eta_label,
            "items": [{"name": i.name, "qty": i.quantity} for i in order.items],
            "delivery_note": note,
        },
    )
    return {"ok": True, "order_id": oid, "total": total, "eta": r.eta_label}


def track_food_order(food: FoodState, order_id: str) -> dict[str, Any]:
    o = food.orders.get(order_id)
    if o is None:
        return {"ok": False, "error": "no such order"}
    return {"ok": True, "order_id": order_id, "status": o.status,
            "eta": o.eta_label, "total": o.total}
