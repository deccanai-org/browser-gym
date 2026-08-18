"""Food app routes — the ``/food`` route family.

Same injected-deps pattern as Mail (no circular import). Checkout calls
``place_food_order(world)`` so the FoodOrderPlaced event can be emitted on
the shared bus.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from server.apps.food import mutations as F

router = APIRouter(prefix="/food", tags=["food"])

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(
        templates=templates, get_world=get_world,
        build_ctx=build_ctx, flash=flash,
    )


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="food", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def restaurants(request: Request):
    food = _deps["get_world"]().food
    rows = sorted(food.restaurants.values(), key=lambda r: -r.rating)
    return _render(request, "food/restaurants.html", food=food, restaurants=rows)


@router.get("/restaurant/{restaurant_id}", response_class=HTMLResponse)
async def menu(request: Request, restaurant_id: str):
    world = _deps["get_world"]()
    r = world.food.restaurants.get(restaurant_id)
    if r is None:
        _deps["flash"](world.shop, "error", "That restaurant could not be found.")
        return RedirectResponse("/food", 303)
    return _render(request, "food/menu.html", food=world.food, restaurant=r)


@router.get("/cart", response_class=HTMLResponse)
async def cart(request: Request):
    world = _deps["get_world"]()
    food = world.food
    rest = food.restaurants.get(food.cart.restaurant_id or "")
    return _render(request, "food/cart.html", food=food, restaurant=rest)


@router.get("/order/{order_id}", response_class=HTMLResponse)
async def order(request: Request, order_id: str):
    world = _deps["get_world"]()
    o = world.food.orders.get(order_id)
    if o is None:
        _deps["flash"](world.shop, "error", "That order could not be found.")
        return RedirectResponse("/food", 303)
    return _render(request, "food/order.html", food=world.food, order=o)


@router.post("/cart/add")
async def cart_add(
    request: Request,
    restaurant_id: str = Form(...),
    dish_id: str = Form(...),
    quantity: int = Form(1),
    # "no onions", "extra spicy" — the item modal has always collected this,
    # and tools/bridge.py still posts it with food.add_to_cart.
    note: str = Form(""),
):
    world = _deps["get_world"]()
    r = F.add_dish(world.food, restaurant_id=restaurant_id,
                   dish_id=dish_id, quantity=quantity, note=note)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Added to your food order.")
    elif r.get("error") == "cart_has_other_restaurant":
        _deps["flash"](world.shop, "error",
                       "Your food cart has items from another restaurant. "
                       "Clear it first to order from here.")
    else:
        _deps["flash"](world.shop, "error", "Could not add that item.")
    return RedirectResponse(f"/food/restaurant/{restaurant_id}", 303)


@router.post("/cart/clear")
async def cart_clear(request: Request):
    world = _deps["get_world"]()
    F.clear_cart(world.food)
    _deps["flash"](world.shop, "success", "Food cart cleared.")
    return RedirectResponse("/food/cart", 303)


@router.post("/cart/remove")
async def cart_remove(request: Request, dish_id: str = Form(...)):
    world = _deps["get_world"]()
    r = F.remove_dish(world.food, dish_id=dish_id)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Removed from your food order.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not remove that item."))
    return RedirectResponse("/food/cart", 303)


@router.post("/cart/set_qty")
async def cart_set_qty(
    request: Request,
    dish_id: str = Form(...),
    quantity: int = Form(...),
):
    world = _deps["get_world"]()
    r = F.set_dish_qty(world.food, dish_id=dish_id, quantity=quantity)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Updated your food order.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not update that item."))
    return RedirectResponse("/food/cart", 303)


@router.post("/cart/schedule")
async def cart_schedule(request: Request, scheduled_delivery: str = Form("")):
    world = _deps["get_world"]()
    if not getattr(world.food, "enable_schedule_ahead", False):
        _deps["flash"](world.shop, "error", "Schedule-ahead is not available.")
        return RedirectResponse("/food/cart", 303)
    r = F.set_scheduled_delivery(world.food, scheduled_delivery)
    if r.get("ok"):
        day = r.get("scheduled_delivery")
        msg = (f"Scheduled for {day}." if day else "Switched to deliver ASAP.")
        _deps["flash"](world.shop, "success", msg)
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not set schedule."))
    return RedirectResponse("/food/cart", 303)


@router.post("/cart/promo")
async def cart_promo(request: Request, code: str = Form("")):
    # Backs the bridged mock's promo box and the tools/bridge.py
    # "food.apply_promo" action; food.promos is what gives a wrong code
    # something to be wrong against.
    world = _deps["get_world"]()
    r = F.apply_promo(world.food, code)
    if r.get("ok"):
        if r.get("promo_code"):
            _deps["flash"](world.shop, "success", f"Promo {r['promo_code']} applied.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not apply that code."))
    return RedirectResponse("/food/cart", 303)


@router.post("/checkout")
async def checkout(request: Request, delivery_note: str = Form(""),
                   delivery_mode: str = Form("delivery"),
                   scheduled_delivery: str = Form("")):
    world = _deps["get_world"]()
    # Only persist a note when the task opts into the delivery-instruction UI
    # (M362). Other tasks ignore the field even if somehow posted.
    note = delivery_note if getattr(world.food, "enable_delivery_notes", False) else None
    sched = None
    if getattr(world.food, "enable_schedule_ahead", False):
        sched = scheduled_delivery or world.food.cart.scheduled_delivery
    r = F.place_food_order(
        world, delivery_note=note, delivery_mode=delivery_mode,
        scheduled_delivery=sched,
    )
    if r.get("ok"):
        when = r.get("scheduled_delivery")
        msg = (f"Order placed for {when}! Arriving around {r['eta']}."
               if when else f"Order placed! Arriving around {r['eta']}.")
        _deps["flash"](world.shop, "success", msg)
        return RedirectResponse(f"/food/order/{r['order_id']}", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not place order."))
    return RedirectResponse("/food/cart", 303)


@router.post("/order/{order_id}/cancel")
async def cancel_order(request: Request, order_id: str):
    world = _deps["get_world"]()
    r = F.cancel_food_order(world.food, order_id)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Food order cancelled.")
    else:
        _deps["flash"](
            world.shop, "error",
            r.get("error", "Could not cancel that order."),
        )
    return RedirectResponse(f"/food/order/{order_id}", 303)
