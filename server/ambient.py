"""The browse-only catalog, made ADDABLE without making it visible to verifiers.

Four fifths of what a ShopGym annotator can see, and nineteen twentieths of
ValueMart, is ambient filler: products that exist only in the projection so the
stores look like stores. `tools/ambient_catalog` says so in its own docstring —
"It never touches the gym engine world, so no verifier sees it."

That was true and it was also a trap. The mocks render the whole catalog and put
an Add-to-cart button on every item, but the engine only knows the task's own 43
products, so clicking any of the other 188 was rejected as "unknown product" and
the cart silently stayed empty. Measured across seven tasks: 81% of ShopGym and
95% of ValueMart were dead buttons.

The obvious fix — put them in `state.products` — is the wrong one, for two
reasons that are easy to miss:

  * `/_harness/world_full` is `dataclasses.asdict(world)`, and that IS the world
    the annotator hashes. Adding 188 products to it changes the hash of every
    task, which invalidates every checkpoint and every recorded trajectory.
  * Verifiers read `probe.state.products` directly. Ambient rows would land in
    the middle of stock checks, search assertions and "the catalog contains"
    queries — and the M239 lesson is that changing what the world affords can
    delete a breaker outright.

So the ambient catalog lives HERE instead: a side registry the mutations consult
and nothing else can see. `state.products` is untouched, so the world hash is
byte-identical and a verifier reading it structurally cannot reach ambient
content — not by convention, but because it is a different object.

What DOES stay visible is the consequence: a cart line naming an ambient product
appears in the cart like any other. That is deliberate and correct. Adding a
distractor to the cart is a real mistake a task should be able to catch, and a
verifier asserting "the cart holds exactly the diffuser" must still fail when it
holds a diffuser and a novelty mug.

Single-tenant by design, like `server.main.SESSION` — one gym process holds one
world, and the bridge pool gives every annotator their own process.
"""

from __future__ import annotations

import re

from server.apps.market.state import MarketProduct
from server.state import Product

#: product_id -> Product, for everything the shop projection shows but the task
#: does not own. Rebuilt on every reset so a stale task's filler cannot leak
#: into the next one.
_shop: dict[str, Product] = {}
#: The same for ValueMart listings.
_market: dict[str, MarketProduct] = {}

# --------------------------------------------------------------------------- #
# Standalone gift cards
# --------------------------------------------------------------------------- #
# The storefront's Gift Cards page sells a stored-value card for any whole-dollar
# amount, so its ids cannot be enumerated up front the way the rest of the filler
# is — there are two thousand of them. They are minted on demand instead, from
# the id alone.
#
# The id grammar is load-bearing, not cosmetic. Ambient products are deliberately
# unreachable from a verifier (see the module docstring), and yet three breakers
# — M361, M353, M381 — turn on "a gift card must not be purchased". A verifier
# looking at an order line has the product_id and nothing else, so the id itself
# has to say "this is a gift card". Hence the reserved `giftcard-<dollars>`
# namespace and `is_gift_card_id`, which a verifier may read because it inspects
# the NAME of a thing, never the catalog behind it.
#
# Canonical spelling only: `giftcard-050` and `giftcard-50` would otherwise be
# two ids for one card, which is one id too many for a tripwire to keep track of.
GIFT_CARD_PREFIX = "giftcard-"
GIFT_CARD_MIN_USD = 1
GIFT_CARD_MAX_USD = 2000
_GIFT_CARD_ID = re.compile(r"^giftcard-(0|[1-9][0-9]*)$")


def gift_card_amount(product_id: str) -> int | None:
    """The face value in whole dollars, or None if this is not a gift-card id."""
    m = _GIFT_CARD_ID.match(product_id or "")
    if m is None:
        return None
    amount = int(m.group(1))
    if not (GIFT_CARD_MIN_USD <= amount <= GIFT_CARD_MAX_USD):
        return None
    return amount


def is_gift_card_id(product_id: str) -> bool:
    """True for the standalone-gift-card id namespace.

    Safe for a verifier to call: it answers a question about the id string, so it
    reveals nothing about which filler products happen to be loaded.
    """
    return gift_card_amount(product_id) is not None


def _mint_gift_card(product_id: str) -> Product | None:
    """Build the gift card an id denotes, or None.

    Not cached in `_shop`: the value is a pure function of the id, so caching
    would only make `counts()` drift during an episode and make the registry's
    contents depend on what the annotator happened to click.
    """
    amount = gift_card_amount(product_id)
    if amount is None:
        return None
    return Product(
        id=product_id,
        name=f"xmazon Gift Card — ${amount}",
        brand="xmazon",
        category="gift-cards",
        base_price=float(amount),
        rating=0.0,
        review_count=0,
        # A stored-value card has no stock to run out of, but `add_to_cart`
        # compares quantity against this number, so it needs a real one.
        stock=999,
        image_emoji="🎁",
        short_description=f"xmazon gift card with a ${amount} stored value.",
        long_description=(
            f"An xmazon gift card worth ${amount}, delivered by email. "
            "Redeemable against anything xmazon sells."
        ),
    )


def _emoji(spec: dict) -> str:
    return str((spec.get("specs") or {}).get("Emoji") or "") or "📦"


def load() -> None:
    """Build the registry from the SAME source the projection uses.

    Deliberately the same builders, not a parallel copy: an ambient product the
    engine prices differently from the one the annotator is looking at would be
    a worse bug than the one this fixes.
    """
    _shop.clear()
    _market.clear()

    # Imported lazily. `tools` is not a dependency of `server` at import time,
    # and a gym that cannot find the ambient catalog should still boot — with an
    # empty registry, which restores exactly the old behaviour.
    try:
        from tools import ambient_catalog as amb
    except Exception:                                        # noqa: BLE001
        return

    for row in amb.build_shop():
        pid = str(row.get("id") or "")
        if not pid:
            continue
        _shop[pid] = Product(
            id=pid,
            name=str(row.get("title") or pid),
            brand=str(row.get("brand") or ""),
            category=str(row.get("category") or ""),
            base_price=float(row.get("price") or 0.0),
            rating=float(row.get("rating") or 0.0),
            review_count=int(row.get("reviewCount") or 0),
            stock=int(row.get("stockCount") or 0),
            image_emoji=_emoji(row),
            short_description=str(row.get("description") or ""),
            long_description=str(row.get("description") or ""),
        )

    # build_market needs a tile renderer for seller avatars; the registry does
    # not care what the avatars look like, only that the ids and prices match.
    listings, _sellers = amb.build_market(lambda *a, **k: "")
    for row in listings:
        lid = str(row.get("id") or "")
        if not lid:
            continue
        _market[lid] = MarketProduct(
            id=lid,
            name=str(row.get("title") or lid),
            category=str(row.get("category") or ""),
            price=float(row.get("price") or row.get("buyItNowPrice") or 0.0),
            description=str(row.get("description") or ""),
            in_stock=True,
        )


def shop(product_id: str) -> Product | None:
    """The ambient shop product with this id, if any."""
    return _shop.get(product_id) or _mint_gift_card(product_id)


def market(product_id: str) -> MarketProduct | None:
    """The ambient ValueMart listing with this id, if any."""
    return _market.get(product_id)


def is_ambient(product_id: str) -> bool:
    return (product_id in _shop or product_id in _market
            or is_gift_card_id(product_id))


def counts() -> tuple[int, int]:
    """(shop, market) — for tests and for the startup log."""
    return len(_shop), len(_market)
