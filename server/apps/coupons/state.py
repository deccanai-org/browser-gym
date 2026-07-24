"""Coupons app store — CouponsState + CouponOffer + ClippedCoupon.

Wholly separate from ValueMart's ``MarketCoupon`` catalog. Fixed timestamps so
a reset for a given seed reproduces an identical offer book.

Merchant field (``CouponOffer.merchant``) is informational metadata for future
task verifiers only — the Coupons app never enforces merchant matching at
checkout, and Shop/Market/Food apply-coupon paths must not gain a merchant gate
from this app. Mismatched-merchant tasks check via verifier, not env refusal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEED_DATE = "2026-05-21"


@dataclass
class CouponOffer:
    id: str
    code: str
    title: str
    description: str = ""
    # Informational only for verifiers — NOT enforced at checkout.
    # Values: shop | market | food | any
    merchant: str = "any"
    discount_label: str = ""          # display string, e.g. "10% off"
    expires_on: str = SEED_DATE
    expired: bool = False
    min_spend: float | None = None


@dataclass
class ClippedCoupon:
    offer_id: str
    clipped_at: str
    used: bool = False


@dataclass
class CouponsState:
    offers: dict[str, CouponOffer] = field(default_factory=dict)
    wallet: dict[str, ClippedCoupon] = field(default_factory=dict)
    _next: int = 1

    def new_id(self) -> str:
        cid = f"cpn_{self._next}"
        self._next += 1
        return cid

    def get_offer(self, offer_id: str) -> CouponOffer | None:
        return self.offers.get(offer_id)

    def ordered_offers(self) -> list[CouponOffer]:
        return sorted(self.offers.values(), key=lambda o: o.id)

    def ordered_wallet(self) -> list[tuple[CouponOffer, ClippedCoupon]]:
        rows: list[tuple[CouponOffer, ClippedCoupon]] = []
        for offer_id, clipped in self.wallet.items():
            offer = self.offers.get(offer_id)
            if offer is not None:
                rows.append((offer, clipped))
        return sorted(rows, key=lambda pair: pair[1].clipped_at, reverse=True)

    def to_json(self) -> dict[str, Any]:
        return {
            "offers": {k: asdict(v) for k, v in self.offers.items()},
            "wallet": {k: asdict(v) for k, v in self.wallet.items()},
        }


def make_couponsstate(seed: int = 0) -> CouponsState:
    """Seed a mixed offer book: valid, expired, and merchant-labeled decoys.

    Merchant labels are verifier metadata only — clipping and later typing a
    code into Shop/Market/Food checkout is not blocked by mismatch here.
    """
    c = CouponsState()
    # Seed flips one decoy code string so episodes stay deterministic per seed.
    decoy_code = "STALE10" if seed % 2 == 0 else "STALE15"
    rows = [
        CouponOffer(
            id="", code="SAVE10", title="10% off ShopGym",
            description="Percent-off for the main ShopGym store.",
            merchant="shop", discount_label="10% off",
            expires_on="2026-12-31", expired=False, min_spend=25.0,
        ),
        CouponOffer(
            id="", code="VALUE10", title="ValueMart 10% off",
            description="Matches the familiar ValueMart code family.",
            merchant="market", discount_label="10% off",
            expires_on="2026-12-31", expired=False, min_spend=20.0,
        ),
        CouponOffer(
            id="", code="EATS5", title="$5 off food delivery",
            description="Food-app labeled offer (verifier metadata only).",
            merchant="food", discount_label="$5 off",
            expires_on="2026-12-31", expired=False, min_spend=None,
        ),
        CouponOffer(
            id="", code=decoy_code, title="Expired weekend deal",
            description="Expired decoy — still clipable; checkout may reject.",
            merchant="any", discount_label="15% off",
            expires_on="2026-01-01", expired=True, min_spend=0.0,
        ),
        CouponOffer(
            id="", code="ANYTHING5", title="Anywhere $5 off",
            description="Labeled merchant=any — still not auto-applied.",
            merchant="any", discount_label="$5 off",
            expires_on="2026-12-31", expired=False, min_spend=None,
        ),
    ]
    for offer in rows:
        oid = c.new_id()
        offer.id = oid
        c.offers[oid] = offer
    return c
