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

from server.apps.market.state import MarketProduct
from server.state import Product

#: product_id -> Product, for everything the shop projection shows but the task
#: does not own. Rebuilt on every reset so a stale task's filler cannot leak
#: into the next one.
_shop: dict[str, Product] = {}
#: The same for ValueMart listings.
_market: dict[str, MarketProduct] = {}


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
    return _shop.get(product_id)


def market(product_id: str) -> MarketProduct | None:
    """The ambient ValueMart listing with this id, if any."""
    return _market.get(product_id)


def is_ambient(product_id: str) -> bool:
    return product_id in _shop or product_id in _market


def counts() -> tuple[int, int]:
    """(shop, market) — for tests and for the startup log."""
    return len(_shop), len(_market)
