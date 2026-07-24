"""Coupons app — a user coupon wallet / clipping book at ``/coupons``.

Separate from ValueMart's in-store ``MarketCoupon`` / ``POST /market/apply-coupon``.
This app browses offers and clips codes into a wallet; redeem still goes through
existing Shop / Market / Food checkout apply-coupon paths.

IMPORTANT — merchant field semantics:
``CouponOffer.merchant`` is **metadata for future task verifiers only**. The
environment itself does **NOT** block mismatched-merchant codes at Shop, Market,
or Food checkout. A task that cares about wrong-merchant redemption must assert
that via its verifier (e.g. order/coupon state), not by expecting the checkout
path to refuse the code. Do not add merchant-gate enforcement to apply-coupon.
"""
