"""Coupons app routes — the ``/coupons`` route family.

Same injected-deps pattern as Mail/Calendar. Does not mutate Shop/Market/Food
checkout state; merchant on offers is verifier metadata only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from server.apps.coupons import mutations as C

router = APIRouter(prefix="/coupons", tags=["coupons"])

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(
        templates=templates, get_world=get_world,
        build_ctx=build_ctx, flash=flash,
    )


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="coupons", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def browse(request: Request):
    coupons = _deps["get_world"]().coupons
    return _render(
        request, "coupons/browse.html",
        coupons=coupons, offers=coupons.ordered_offers(),
    )


@router.get("/wallet", response_class=HTMLResponse)
async def wallet(request: Request):
    coupons = _deps["get_world"]().coupons
    return _render(
        request, "coupons/wallet.html",
        coupons=coupons, items=coupons.ordered_wallet(),
    )


@router.get("/{offer_id}", response_class=HTMLResponse)
async def detail(request: Request, offer_id: str):
    world = _deps["get_world"]()
    coupons = world.coupons
    offer = coupons.get_offer(offer_id)
    if offer is None:
        _deps["flash"](world.shop, "error", "That coupon could not be found.")
        return RedirectResponse("/coupons", 303)
    clipped = coupons.wallet.get(offer_id)
    return _render(
        request, "coupons/detail.html",
        coupons=coupons, offer=offer, clipped=clipped,
    )


@router.post("/{offer_id}/clip")
async def clip(request: Request, offer_id: str):
    world = _deps["get_world"]()
    r = C.clip_offer(world.coupons, offer_id)
    if r.get("ok"):
        if r.get("already"):
            _deps["flash"](world.shop, "success", "Already in your wallet.")
        else:
            _deps["flash"](world.shop, "success", f"Clipped code {r['code']}.")
        return RedirectResponse("/coupons/wallet", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not clip."))
    return RedirectResponse("/coupons", 303)


@router.post("/{offer_id}/unclip")
async def unclip(request: Request, offer_id: str):
    world = _deps["get_world"]()
    r = C.unclip_offer(world.coupons, offer_id)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Removed from wallet.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not unclip."))
    return RedirectResponse("/coupons/wallet", 303)


@router.post("/{offer_id}/mark-used")
async def mark_used(request: Request, offer_id: str):
    world = _deps["get_world"]()
    r = C.mark_used(world.coupons, offer_id, used=True)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Marked as used.")
        return RedirectResponse("/coupons/wallet", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not mark used."))
    return RedirectResponse(f"/coupons/{offer_id}", 303)
