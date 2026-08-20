"""Xbay — a SECOND e-commerce app (the discount-retailer foil to the main
Xmazon store), route-prefixed at /market.

Why a second store: cross-retailer comparison is one of the strongest multi-tab
clusters — same item, two stores, different sticker prices, different delivery
fees, and a coupon that applies to only ONE site. The agent must compute the
FINAL cart total per store (price - coupon + delivery), not just read stickers,
and order from the genuinely cheaper one. Xbay is intentionally cheaper on
some SKUs and pricier on others, with a delivery fee and a store-only coupon, so
neither store wins by sticker alone.
"""
