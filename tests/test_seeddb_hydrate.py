"""Phase 2 gate: the seed db rebuilds the LIVE dataclass graph, losslessly.

Phase 1 proved the DB reconstructs the world's asdict. This proves the next step:
turning that back into real dataclass objects (via statecodec.from_dict) yields a
world byte-equivalent to the factory's — at the value, insertion-order, AND
to_json level — for every (task, seed). Plus the return-type contract Phase 3
depends on: hydrate_world hands back exactly what make_task does.

Nothing here is wired into the runtime; make_task still builds from the factories.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from server.seeddb import build_seed_db, hydrate, _equiv
from server.apps.world import WorldState
from server.state import GymState

_GOLDEN = json.loads(build_seed_db.GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(":memory:")
    build_seed_db.build(conn, _GOLDEN, verify=False)
    yield conn
    conn.close()


def test_hydrate_rebuilds_every_world_byte_equivalent(db):
    """The whole set: hydrate_full rebuilds live objects that hash-equal the golden
    at value, insertion-order, and to_json level. This is the object-rebuild
    losslessness proof."""
    bad: list[str] = []
    for task_id, seeds in _GOLDEN.items():
        for seed_s, g in seeds.items():
            w = hydrate.hydrate_full(db, task_id, int(seed_s))
            if _equiv.asdict_hash(w) != g["asdict_hash"]:
                bad.append(f"{task_id}#{seed_s}:value")
            elif _equiv.order_hash(w) != g["order_hash"]:
                bad.append(f"{task_id}#{seed_s}:order")
            elif _equiv.hash_world(w.to_json()) != g["to_json_hash"]:
                bad.append(f"{task_id}#{seed_s}:to_json")
    assert not bad, f"{len(bad)} hydrated worlds differ from the golden, e.g. {bad[:10]}"


# A spread across single-app + cross-app tasks and both parities.
_SAMPLE = [
    ("A1/buy_wireless_mouse", 0),
    ("A2/filter_laptop", 42),
    ("M301/stale_tracking_forward_sycophancy", 0),
    ("M310/cancel_sub_false_no_transit_claim", 1),
]


@pytest.mark.parametrize("task_id,seed", _SAMPLE)
def test_hydrate_matches_the_live_factory_not_only_the_frozen_golden(db, task_id, seed):
    """Compare against the live factory too, so a golden that somehow drifted from
    the code cannot hide a hydration bug."""
    got = hydrate.hydrate_full(db, task_id, seed)
    fac = _equiv.build_wrapped(task_id, seed)
    assert _equiv.asdict_hash(got) == _equiv.asdict_hash(fac)
    assert _equiv.order_hash(got) == _equiv.order_hash(fac)
    assert _equiv.hash_world(got.to_json()) == _equiv.hash_world(fac.to_json())


def test_hydrate_world_returns_the_make_task_type(db):
    """Single-app -> bare GymState; cross-app -> WorldState. This is what lets
    hydrate drop in behind make_task without touching _reset_inline."""
    shop = hydrate.hydrate_world(db, "A1/buy_wireless_mouse", 0)
    assert isinstance(shop, GymState) and not isinstance(shop, WorldState)
    world = hydrate.hydrate_world(db, "M301/stale_tracking_forward_sycophancy", 0)
    assert isinstance(world, WorldState)


def test_hydrated_entities_are_real_dataclasses_that_serialise(db):
    """Not dicts: the rebuilt catalog is live dataclass instances, and to_json
    round-trips them the way the running gym expects."""
    world = hydrate.hydrate_full(db, "A1/buy_wireless_mouse", 0)
    product = next(iter(world.shop.products.values()))
    assert type(product).__name__ == "Product"
    assert isinstance(product.variants, list)  # nested collection rebuilt too
    assert "task_id" in world.to_json()         # serialises without error


def test_out_of_set_seed_is_a_miss_not_a_wrong_world(db):
    """A seed not in the pool must raise, so the Phase-3 caller falls back to the
    factory rather than silently serving an empty/wrong world."""
    with pytest.raises(KeyError):
        hydrate.hydrate_world(db, "A1/buy_wireless_mouse", 99)
    assert hydrate.has(db, "A1/buy_wireless_mouse", 0) is True
    assert hydrate.has(db, "A1/buy_wireless_mouse", 99) is False
