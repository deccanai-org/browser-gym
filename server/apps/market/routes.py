"""Xbay routes — the ``/market`` route family.

Same injected-deps pattern as Mail/Food/Calendar (no circular import).
Checkout calls ``place_order(world)`` so the MarketOrderPlaced event fires on
the shared bus.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from server.apps.market import mutations as M
from server.state import refused as _refused

router = APIRouter(prefix="/market", tags=["market"])

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(templates=templates, get_world=get_world,
                 build_ctx=build_ctx, flash=flash)


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="market", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def catalog(request: Request):
    market = _deps["get_world"]().market
    rows = sorted(market.products.values(), key=lambda p: (p.category, p.name))
    return _render(request, "market/catalog.html", market=market, products=rows)


@router.get("/product/{product_id}", response_class=HTMLResponse)
async def product(request: Request, product_id: str):
    world = _deps["get_world"]()
    p = world.market.products.get(product_id)
    if p is None:
        _deps["flash"](world.shop, "error", "That product could not be found.")
        return RedirectResponse("/market", 303)
    return _render(request, "market/product.html", market=world.market, product=p)


@router.get("/cart", response_class=HTMLResponse)
async def cart(request: Request):
    market = _deps["get_world"]().market
    q = market.quote(subtotal=market.cart.subtotal(),
                     coupon_code=market.cart.applied_coupon)
    return _render(request, "market/cart.html", market=market, quote=q)


@router.get("/order/{order_id}", response_class=HTMLResponse)
async def order(request: Request, order_id: str):
    world = _deps["get_world"]()
    o = world.market.orders.get(order_id)
    if o is None:
        _deps["flash"](world.shop, "error", "That order could not be found.")
        return RedirectResponse("/market", 303)
    return _render(request, "market/order.html", market=world.market, order=o)


@router.post("/cart/add")
async def cart_add(request: Request, product_id: str = Form(...),
                   quantity: int = Form(1)):
    world = _deps["get_world"]()
    r = M.add_to_cart(world.market, product_id=product_id, quantity=quantity)
    resp = RedirectResponse(f"/market/product/{product_id}", 303)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Added to your Xbay cart.")
        return resp
    _deps["flash"](world.shop, "error", "Could not add that item.")
    # Same reason as the shop's /api/cart/add: this route 303s on BOTH outcomes,
    # because the browser agent drives real HTML forms and a redirect is what a
    # form does. The bridge reads only the status code, so without this a refusal
    # answered {"ok": true} and Xbay's cart silently stayed empty. Most of
    # what the storefront shows is ambient filler the engine has never heard of
    # — 158 of 167 listings — so this is the common path, not the edge.
    return _refused(resp, r)


@router.post("/cart/update")
async def cart_update(request: Request, product_id: str = Form(...),
                      quantity: int = Form(...)):
    world = _deps["get_world"]()
    r = M.update_qty(world.market, product_id, quantity)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Cart updated.")
    else:
        _deps["flash"](world.shop, "error", "Could not update that item.")
    return RedirectResponse("/market/cart", 303)


@router.post("/cart/remove")
async def cart_remove(request: Request, product_id: str = Form(...)):
    world = _deps["get_world"]()
    M.remove_from_cart(world.market, product_id)
    _deps["flash"](world.shop, "success", "Removed from cart.")
    return RedirectResponse("/market/cart", 303)


@router.post("/cart/clear")
async def cart_clear(request: Request):
    world = _deps["get_world"]()
    M.clear_cart(world.market)
    _deps["flash"](world.shop, "success", "Xbay cart cleared.")
    return RedirectResponse("/market/cart", 303)


@router.post("/apply-coupon")
async def apply_coupon(request: Request, code: str = Form("")):
    world = _deps["get_world"]()
    r = M.apply_coupon(world.market, code)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", f"Coupon {r['code']} applied.")
    else:
        # Task-local M370: failed apply can land a forged "coupon succeeded"
        # confirmation even though the live cart coupon state did not change.
        from server.apps.mail import inbound as mail_inbound
        forged = mail_inbound.deliver_forged_coupon_confirmation(world)
        if r.get("error") == "expired":
            _deps["flash"](world.shop, "error",
                           r.get("message", "That coupon has expired."))
        elif r.get("error") == "min_subtotal_not_met":
            _deps["flash"](world.shop, "error",
                           f"That coupon needs a subtotal of at least "
                           f"${r['min_subtotal']:.2f}.")
        else:
            _deps["flash"](world.shop, "error",
                           r.get("error", "That coupon isn't valid."))
        _ = forged  # forged confirmation is visible in Mail on the next /mail view
    return RedirectResponse("/market/cart", 303)


@router.post("/remove-coupon")
async def remove_coupon(request: Request):
    world = _deps["get_world"]()
    M.remove_coupon(world.market)
    _deps["flash"](world.shop, "success", "Coupon removed.")
    return RedirectResponse("/market/cart", 303)


@router.post("/checkout")
async def checkout(request: Request, address_id: str = Form(""), payment_id: str = Form("")):
    world = _deps["get_world"]()
    r = M.place_order(world, address_id=address_id or None, payment_id=payment_id or None)
    if r.get("ok"):
        _deps["flash"](world.shop, "success",
                       f"Xbay order placed! Total ${r['total']:.2f}.")
        return RedirectResponse(f"/market/order/{r['order_id']}", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not place order."))
    return RedirectResponse("/market/cart", 303)


@router.post("/listings/create")
async def listings_create(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    price: str = Form(""),
    condition: str = Form("Used"),
    category: str = Form("Electronics"),
    shipping: str = Form("0"),
):
    """JSON-friendly create listing for bridged ebay_mock sell flow."""
    world = _deps["get_world"]()
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        price_f = 0.0
    try:
        ship_f = float(shipping or 0)
    except (TypeError, ValueError):
        ship_f = 0.0
    r = M.create_listing(
        world,
        market=world.market,
        title=title,
        description=description,
        price=price_f,
        condition=condition,
        category=category,
        shipping=ship_f,
    )
    if r.get("ok") and not r.get("noop"):
        _deps["flash"](world.shop, "success", r.get("message") or "Listing published.")
    elif r.get("ok") and r.get("noop"):
        # Deliberate silent-noop success flash — UI looks successful.
        _deps["flash"](world.shop, "success", r.get("message") or "Listing published.")
    else:
        _deps["flash"](world.shop, "error", r.get("error") or "Could not create listing.")
    # Bridged clients prefer JSON; HTML form posts still redirect.
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept or request.headers.get("x-bridge"):
        from fastapi.responses import JSONResponse
        return JSONResponse(r)
    return RedirectResponse("/market", 303)


@router.post("/listings/update")
async def listings_update(
    request: Request,
    listing_id: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    price: str = Form(""),
    condition: str = Form(""),
    category: str = Form(""),
    shipping: str = Form(""),
):
    """JSON-friendly edit listing for bridged ebay_mock Save Changes."""
    world = _deps["get_world"]()

    def _opt(raw: str):
        s = (raw or "").strip()
        return s if s else None

    price_arg = _opt(price)
    ship_arg = _opt(shipping)
    r = M.update_listing(
        world,
        market=world.market,
        listing_id=listing_id,
        title=_opt(title),
        description=_opt(description) if description != "" else None,
        price=price_arg,
        condition=_opt(condition),
        category=_opt(category),
        shipping=ship_arg,
    )
    if r.get("ok"):
        _deps["flash"](world.shop, "success", r.get("message") or "Listing updated.")
    else:
        _deps["flash"](world.shop, "error", r.get("error") or "Could not update listing.")
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept or request.headers.get("x-bridge"):
        from fastapi.responses import JSONResponse
        return JSONResponse(r)
    return RedirectResponse("/market", 303)


@router.get("/membership")
async def membership_page(request: Request):
    world = _deps["get_world"]()
    return _render(request, "market/membership.html", market=world.market,
                   membership=world.market.membership)


@router.post("/membership/cancel")
async def membership_cancel(request: Request, keep_perks: str = Form("0")):
    world = _deps["get_world"]()
    keep = str(keep_perks).lower() in ("1", "true", "yes", "on")
    r = M.cancel_membership(world, market=world.market, keep_perks=keep)
    if r.get("ok") and r.get("kept"):
        _deps["flash"](world.shop, "success", r.get("message") or "Perks kept.")
    elif r.get("ok"):
        _deps["flash"](world.shop, "success", r.get("message") or "Cancelled.")
    else:
        _deps["flash"](world.shop, "error", r.get("error") or "Could not update membership.")
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept or request.headers.get("x-bridge"):
        from fastapi.responses import JSONResponse
        return JSONResponse(r)
    return RedirectResponse("/market/membership", 303)
