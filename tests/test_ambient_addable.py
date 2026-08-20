"""The browse-only catalog is addable, and still invisible to verifiers.

Four fifths of what a Xmazon annotator can see is ambient filler, and
nineteen twentieths of Xbay. The mocks render all of it with an
Add-to-cart button on every item, but the engine only knew the task's own
products — so clicking any of the rest was rejected as "unknown product" and the
cart silently stayed empty. Measured across seven tasks: 188 of 231 Xmazon
products and 158 of 167 Xbay listings were dead buttons.

The fix has to hold two things at once, and this file exists to keep them from
drifting apart:

  ADDABLE   — the affordance the storefront shows must actually work.
  INVISIBLE — `/_harness/world_full` is `asdict(world)`, and that IS the world
              the annotator hashes; verifiers read `state.products` directly.
              Ambient content in either would change every task's hash (breaking
              every recorded trajectory) and would land in stock checks, search
              assertions and catalog queries. The M239 lesson is that changing
              what the world affords can delete a breaker outright.
"""

from __future__ import annotations

import dataclasses

import pytest

from server import ambient, mutations
from server.apps.market import mutations as M
from server.main import SESSION, _reset_inline

TASK = "M105/false_double_charge"


@pytest.fixture()
def world():
    _reset_inline(TASK, 0)
    return SESSION.world


def _amb_shop_id() -> str:
    ambient.load()
    return next(iter(ambient._shop))


def _amb_market_id() -> str:
    ambient.load()
    return next(iter(ambient._market))


def test_the_registry_covers_what_the_storefront_shows(world):
    """If these fall to zero the fix is silently gone and every filler product
    is a dead button again."""
    shop_n, market_n = ambient.counts()
    assert shop_n > 150, f"only {shop_n} ambient shop products registered"
    assert market_n > 100, f"only {market_n} ambient listings registered"


def test_an_ambient_product_can_be_added_to_the_cart(world):
    pid = _amb_shop_id()
    assert world.shop.products.get(pid) is None, "this test is meaningless if the task owns it"

    r = mutations.add_to_cart(world.shop, product_id=pid, quantity=2)

    assert r["ok"] is True, r
    assert [l.product_id for l in world.shop.cart.items] == [pid]


def test_an_ambient_line_prices_correctly(world):
    """It is not enough to accept the add: everything downstream prices a line by
    looking the product up again, and a line the catalog cannot price would
    crash at checkout instead of at the click."""
    pid = _amb_shop_id()
    mutations.add_to_cart(world.shop, product_id=pid, quantity=2)
    line = world.shop.cart.items[0]

    unit = mutations._resolve_unit_price(world.shop, line.product_id, line.variant_id)

    assert unit == pytest.approx(ambient.shop(pid).base_price)
    assert unit > 0


def test_valuemart_ambient_listings_are_addable_too(world):
    """Xbay is the worse case — 158 of 167 listings are ambient."""
    lid = _amb_market_id()
    assert world.market.products.get(lid) is None

    r = M.add_to_cart(world.market, product_id=lid, quantity=1)

    assert r["ok"] is True, r
    assert world.market.cart.count() == 1


def test_a_product_that_is_in_NEITHER_catalog_is_still_refused(world):
    """The refusal path has to survive: it is what tells an annotator their click
    did nothing, and it was invisible until very recently."""
    r = mutations.add_to_cart(world.shop, product_id="p_no_such_thing_anywhere", quantity=1)
    assert r["ok"] is False
    assert r["error"] == "unknown product"

    rm = M.add_to_cart(world.market, product_id="vm_no_such_thing", quantity=1)
    assert rm["ok"] is False


# --------------------------------------------------------------- invisibility

def test_no_ambient_row_reaches_the_hashed_world(world):
    """`/_harness/world_full` is `asdict(world)` and that is what the annotator
    hashes. One ambient id in here changes the hash of every task and invalidates
    every checkpoint and recorded trajectory."""
    dumped = dataclasses.asdict(world)

    leaked = [k for k in (dumped.get("shop") or {}).get("products", {}) if k.startswith("amb_")]
    leaked += [k for k in (dumped.get("market") or {}).get("products", {}) if k.startswith("amb_")]

    assert not leaked, f"ambient content reached the hashed world: {leaked[:5]}"


def test_a_verifier_reading_the_catalog_cannot_see_ambient_content(world):
    """Verifiers read `probe.state.products`. Invisibility here is structural —
    ambient lives in a different object — rather than a convention someone has to
    remember."""
    assert not [k for k in world.shop.products if k.startswith("amb_")]
    assert not [k for k in world.market.products if k.startswith("amb_")]
    # ...and the registry is genuinely populated, so the assertion above is not
    # passing because nothing was loaded.
    assert ambient.counts()[0] > 0


def test_an_ambient_line_IS_visible_once_it_is_in_the_cart(world):
    """The deliberate half. Adding a distractor is a real mistake a task should
    be able to catch, so a verifier asserting "the cart holds exactly the
    diffuser" must still fail when it holds a diffuser and a novelty tablet."""
    pid = _amb_shop_id()
    mutations.add_to_cart(world.shop, product_id=pid, quantity=1)

    dumped = dataclasses.asdict(world)
    lines = (dumped.get("shop") or {}).get("cart", {}).get("items") or []

    assert [l["product_id"] for l in lines] == [pid], "the cart must not hide what is in it"


def test_the_registry_is_rebuilt_per_episode(world):
    """Rebuilt on reset so one task's filler cannot leak into the next — the
    registry is process-global, and the pool now keeps a gym process alive across
    many sessions."""
    before = ambient.counts()
    _reset_inline("M111/false_premise_masks_expired_card", 0)
    assert ambient.counts() == before
    assert ambient.shop(_amb_shop_id()) is not None
