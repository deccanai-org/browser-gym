"""world -> load_state -> world must preserve the MUTABLE slice.

This is the gate behind "when I come back to a half-finished task I get my exact
world". `apply_snapshot` overlays a captured world onto a freshly reset one, and
anything it fails to carry across comes back at its SEED value — silently, and
differently per task, which is the worst shape a bug can have here.

Two things were being lost and are covered below:

  * per-app `_next` id counters — absent from `to_json()`, so a restore restarted
    ids at 1 and the next minted email OVERWROTE an existing one.
  * per-product stock — `mutations.py` decrements it when an order is placed, but
    statecodec treats products as rebuildable catalog, so a resumed checkout task
    silently restocked everything the annotator had bought.
"""

from __future__ import annotations

import dataclasses

import pytest

from server import main as M
from server.apps import statecodec

# One per primary app, so a regression in any sub-app's overlay shows up.
TASKS = [
    "M37/false_overcharge",                     # mail-led
    "M100/two_recipient_expired",               # shop / checkout
    "M310/cancel_sub_false_no_transit_claim",   # shop / subscriptions
]


def _snapshot(world) -> dict:
    """What suspend records: the COMPLETE world, which is what restore reads."""
    return dataclasses.asdict(world)


@pytest.mark.parametrize("task_id", TASKS)
def test_stock_survives_the_round_trip(task_id):
    """A reset restocks; the restore must put the annotator's stock back."""
    M._reset_inline(task_id, 0)
    world = M._world()
    pid = next(iter(world.shop.products))
    product = world.shop.products[pid]

    product.stock -= 3                      # what placing an order does
    variant_before = None
    if product.variants:
        product.variants[0].stock -= 2
        variant_before = product.variants[0].stock
    stock_before = product.stock

    snap = _snapshot(world)

    M._reset_inline(task_id, 0)
    fresh = M._world()
    assert fresh.shop.products[pid].stock != stock_before, (
        "the reset must restock — otherwise this test proves nothing"
    )

    statecodec.apply_snapshot(fresh, snap)
    assert fresh.shop.products[pid].stock == stock_before
    if variant_before is not None:
        assert fresh.shop.products[pid].variants[0].stock == variant_before


@pytest.mark.parametrize("task_id", TASKS)
def test_a_restored_world_does_not_mint_an_id_that_already_exists(task_id):
    """The failure this prevents is silent data loss, not an error.

    With `_next` back at 1, the next `new_id()` returns an id an existing email
    already has — and the record it names is overwritten in place.
    """
    M._reset_inline(task_id, 0)
    world = M._world()
    existing = set(world.mail.inbox) | set(world.mail.sent) | set(world.mail.drafts)
    snap = _snapshot(world)

    M._reset_inline(task_id, 0)
    fresh = M._world()
    statecodec.apply_snapshot(fresh, snap)

    minted = fresh.mail.new_id()
    assert minted not in existing, (
        f"{minted} already names an existing record — minting it overwrites that record"
    )


def test_the_counter_is_derived_from_the_records_not_the_snapshot():
    """Deriving rather than persisting keeps `to_json()`'s shape — and therefore
    every recorded world hash, the seed goldens and the db-vs-factory
    byte-equality tests — unchanged, and it self-heals worlds captured before
    this existed."""
    M._reset_inline(TASKS[0], 0)
    world = M._world()
    snap = _snapshot(world)
    assert "_next" not in snap.get("shop", {}), "shop has no id counter to carry"

    M._reset_inline(TASKS[0], 0)
    fresh = M._world()
    fresh.mail._next = 1                       # as a bare reset leaves it
    statecodec.apply_snapshot(fresh, snap)

    highest = max((int(k.removeprefix("em_")) for k in fresh.mail.inbox
                   if k.startswith("em_") and k.removeprefix("em_").isdigit()), default=0)
    assert fresh.mail._next == highest + 1
