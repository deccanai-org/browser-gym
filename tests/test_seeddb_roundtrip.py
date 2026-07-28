"""Phase 1 gate: the seed.db reconstructs byte-equivalent worlds.

Builds the seed database in-memory from the factories (the seed.db file is a
reproducible build artifact, not committed) and reconstructs every (task_id, seed)
from its rows, comparing to the Phase-0 goldens at BOTH the value level
(asdict_hash) and the insertion-order level (order_hash).

This is the mechanical "nothing lost" proof for storage: whatever the factories
produce is reconstructable from SQL, exactly. It is fast (~5s: ~3s build + ~2s
verify), so it runs per-PR with no tiering. To materialise the file itself:
``python -m server.seeddb.build_seed_db``.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from server.seeddb import store, build_seed_db, _equiv

_GOLDEN = json.loads(build_seed_db.GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db():
    """A freshly built in-memory seed db, shared across this module's tests."""
    conn = sqlite3.connect(":memory:")
    cells, failures = build_seed_db.build(conn, _GOLDEN, verify=False)
    assert not failures  # build() with verify=False never populates failures; guard anyway
    yield conn
    conn.close()


def test_covers_every_task_and_seed(db):
    """Every (task, seed) in the goldens has a task row — no silent gaps."""
    have = {(t, int(s)) for t, s in db.execute("SELECT task_id, seed FROM task")}
    want = {(t, int(s)) for t, seeds in _GOLDEN.items() for s in seeds}
    assert have == want, f"coverage gap: {sorted(want - have)[:5]} missing, {sorted(have - want)[:5]} extra"


def test_every_cell_reconstructs_byte_equivalent(db):
    """The whole set: reconstruct all 1560 worlds from rows and hash-match the
    goldens at value AND insertion-order level. This is the losslessness proof."""
    bad: list[str] = []
    n = 0
    for task_id, seeds in _GOLDEN.items():
        for seed_s, golden in seeds.items():
            ok, why = store.roundtrip_ok(db, task_id, int(seed_s), golden)
            n += 1
            if not ok:
                bad.append(f"{task_id} seed={seed_s}: {why}")
    assert not bad, f"{len(bad)}/{n} cells did not reconstruct, e.g. {bad[:10]}"


def test_fixture_version_row_present(db):
    row = db.execute("SELECT version FROM fixture_version").fetchone()
    assert row and row[0] == build_seed_db.FIXTURE_VERSION


def test_a_queryable_relational_shape(db):
    """It is a real SQL db, not an opaque blob: per-entity tables you can query."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"shop_product", "shop_order", "mail_message", "market_product", "task"} <= tables
    # json_extract works over the entity payload
    names = [r[0] for r in db.execute(
        "SELECT json_extract(data_json,'$.name') FROM shop_product "
        "WHERE task_id='A1/buy_wireless_mouse' AND seed=0 ORDER BY pos LIMIT 3")]
    assert names and all(names)


def test_order_hash_actually_guards_insertion_order(db):
    """A guard on the guard: reversing a reconstructed catalog's key order must
    change the order_hash but not the value hash — proving order_hash is what
    catches a reordered catalog that asdict-equality is blind to."""
    rebuilt = store.reconstruct(db, "A1/buy_wireless_mouse", 0)
    products = rebuilt["shop"]["products"]
    assert len(products) > 2
    rebuilt["shop"]["products"] = dict(reversed(list(products.items())))
    canon = _equiv._canonical(rebuilt)
    golden = _GOLDEN["A1/buy_wireless_mouse"]["0"]
    assert _equiv._hash(canon, ordered=False) == golden["asdict_hash"], "value hash is order-insensitive"
    assert _equiv._hash(canon, ordered=True) != golden["order_hash"], "order hash MUST catch the reorder"
