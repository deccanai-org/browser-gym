"""Phase 3 gate: the runtime cutover is transparent, and safe by default.

Exercises the real seam — ``_reset_inline`` -> ``seed_source`` -> the db — and
proves:

* with the flag OFF (the default) nothing changes: the factory is used;
* with the flag ON a reset is byte-identical to the factory reset (transparency);
* with the flag ON it genuinely reads the db (a tampered db shows through), so the
  transparency above is not just a silent fallback;
* an out-of-set seed and a missing db both fall back to the factory rather than
  crashing or serving a wrong world.
"""

from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

import server.main as gym_main
from server.seeddb import build_seed_db, runtime, store, _equiv

_GOLDEN = json.loads(build_seed_db.GOLDEN_PATH.read_text(encoding="utf-8"))
_SAMPLE = [
    ("A1/buy_wireless_mouse", 0),
    ("A2/filter_laptop", 42),          # seed-dependent (PRNG price)
    ("M301/stale_tracking_forward_sycophancy", 0),
    ("M310/cancel_sub_false_no_transit_claim", 1),
]


@pytest.fixture(scope="module")
def built_db(tmp_path_factory):
    """The real seed.db, built once to a temp file."""
    path = tmp_path_factory.mktemp("seeddb") / "seed.db.sqlite"
    conn = sqlite3.connect(str(path))
    build_seed_db.build(conn, _GOLDEN, verify=False)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def db_at(built_db, monkeypatch):
    """Point the runtime seam at the built db for this test."""
    monkeypatch.setattr(store, "DB_PATH", built_db)
    return built_db


def _reset_world_json(task_id: str, seed: int) -> dict:
    gym_main._reset_inline(task_id, seed)
    return gym_main.SESSION.world.to_json()


@pytest.mark.parametrize("task_id,seed", _SAMPLE)
def test_reset_is_byte_identical_db_vs_factory(db_at, monkeypatch, task_id, seed):
    """The transparency proof: a reset served from the db equals one served from
    the factory, at the exact bytes the harness/annotator compare."""
    monkeypatch.setenv("SEEDDB_MODE", "1")
    from_db = _reset_world_json(task_id, seed)
    monkeypatch.setenv("SEEDDB_MODE", "0")
    from_factory = _reset_world_json(task_id, seed)
    assert _equiv.hash_world(from_db) == _equiv.hash_world(from_factory)
    assert _equiv.hash_world(from_db) == _GOLDEN[task_id][str(seed)]["to_json_hash"]


def test_flag_off_uses_the_factory(db_at, monkeypatch):
    """Default behaviour: with the flag unset, the db is never consulted."""
    monkeypatch.delenv("SEEDDB_MODE", raising=False)
    assert runtime.seeddb_enabled() is False
    got = runtime.seed_source("A1/buy_wireless_mouse", 0)
    factory = _equiv.build_wrapped("A1/buy_wireless_mouse", 0)
    # seed_source returns the make_task-type (bare GymState here); compare via to_json
    assert _equiv.hash_world(got.to_json()) == _equiv.hash_world(factory.shop.to_json())


def test_flag_on_actually_reads_the_db(built_db, monkeypatch, tmp_path):
    """A tampered db must show through when the flag is on — proving the seam
    reads the db rather than silently falling back to the factory."""
    tampered = tmp_path / "tampered.sqlite"
    shutil.copy(built_db, tampered)
    conn = sqlite3.connect(str(tampered))
    row = conn.execute(
        "SELECT remainder_json FROM task WHERE task_id='A1/buy_wireless_mouse' AND seed=0"
    ).fetchone()
    graph = json.loads(row[0])
    graph["shop"]["task_brief"] = "TAMPERED-FOR-TEST"
    conn.execute(
        "UPDATE task SET remainder_json=? WHERE task_id='A1/buy_wireless_mouse' AND seed=0",
        (json.dumps(graph),))
    conn.commit()
    conn.close()

    monkeypatch.setattr(store, "DB_PATH", tampered)
    monkeypatch.setenv("SEEDDB_MODE", "1")
    world = runtime.seed_source("A1/buy_wireless_mouse", 0)
    assert world.task_brief == "TAMPERED-FOR-TEST", "flag on must read the db, not the factory"

    monkeypatch.setenv("SEEDDB_MODE", "0")
    assert runtime.seed_source("A1/buy_wireless_mouse", 0).task_brief != "TAMPERED-FOR-TEST"


def test_out_of_set_seed_falls_back_to_factory(db_at, monkeypatch):
    """Seed 99 is not in the pool; the flag being on must not crash or serve an
    empty world — it falls back to the factory."""
    monkeypatch.setenv("SEEDDB_MODE", "1")
    got = runtime.seed_source("A1/buy_wireless_mouse", 99)
    factory = _equiv.build_wrapped("A1/buy_wireless_mouse", 99)
    assert _equiv.hash_world(got.to_json()) == _equiv.hash_world(factory.shop.to_json())


def test_missing_db_falls_back_to_factory(monkeypatch, tmp_path):
    """Flag on but no db file present → factory, no error."""
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "does-not-exist.sqlite")
    monkeypatch.setenv("SEEDDB_MODE", "1")
    got = runtime.seed_source("A1/buy_wireless_mouse", 0)
    factory = _equiv.build_wrapped("A1/buy_wireless_mouse", 0)
    assert _equiv.hash_world(got.to_json()) == _equiv.hash_world(factory.shop.to_json())
