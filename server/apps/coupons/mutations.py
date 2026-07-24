"""Coupons mutations — touch ONLY CouponsState.

Clip / unclip / mark-used only. This module never applies discounts to Shop,
Market, or Food carts, and never rejects a code based on ``CouponOffer.merchant``.
Merchant is verifier metadata; redeem stays on existing checkout paths.
"""

from __future__ import annotations

from typing import Any

from server.apps.coupons.state import SEED_DATE, ClippedCoupon, CouponsState


def clip_offer(coupons: CouponsState, offer_id: str) -> dict[str, Any]:
    offer = coupons.offers.get(offer_id)
    if offer is None:
        return {"ok": False, "error": "no such offer"}
    if offer_id in coupons.wallet:
        return {"ok": True, "offer_id": offer_id, "already": True}
    coupons.wallet[offer_id] = ClippedCoupon(
        offer_id=offer_id,
        clipped_at=f"{SEED_DATE}T12:00:00",
        used=False,
    )
    return {"ok": True, "offer_id": offer_id, "code": offer.code}


def unclip_offer(coupons: CouponsState, offer_id: str) -> dict[str, Any]:
    if offer_id not in coupons.wallet:
        return {"ok": False, "error": "offer is not in wallet"}
    coupons.wallet.pop(offer_id)
    return {"ok": True, "offer_id": offer_id}


def mark_used(coupons: CouponsState, offer_id: str, *, used: bool = True) -> dict[str, Any]:
    """Optional wallet bookkeeping. Does not apply or revoke a store discount."""
    clipped = coupons.wallet.get(offer_id)
    if clipped is None:
        return {"ok": False, "error": "offer is not in wallet"}
    clipped.used = bool(used)
    return {"ok": True, "offer_id": offer_id, "used": clipped.used}
