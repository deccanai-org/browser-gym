"""Phase 1 storage engine — shred a built world into rows, and back, losslessly.

The grain is one row per catalog/record ENTITY (a real per-type table you can
query), plus a ``remainder`` blob of everything that is not one of those big
collections (the scalar headers, the carts, the schedule, the event log, each
sub-app's scalar fields). Reconstruction is, by construction, ``remainder`` with
the collections re-inserted in ``pos`` order — so no field can be silently
dropped: whatever is not lifted into a collection row stays in the remainder.

Correctness is proven, not asserted: for every ``(task_id, seed)`` the world
reconstructed from rows must hash-equal the golden captured in Phase 0, at BOTH
the value level (``asdict_hash``) and the insertion-order level (``order_hash``).

Losslessness notes:

* Each entity row stores the entity's COMPLETE ``asdict`` as ``data_json``; the
  round-trip reads only ``data_json``, so JSON's type fidelity (bool stays bool,
  None stays None) plus the shared ``_canonical`` pass (tuples->lists, integral
  floats->ints, applied to golden and reconstruction alike) means the compare
  cannot false-diff on serialization.
* Hidden dataclass fields (mail ``armed_*`` / ``_next`` / ``account_name``, food
  ``defer_receipt_steps``, market ``store_name`` …) ride along in ``asdict``
  automatically — they are fields — so they are captured for free. ``mint_counts``
  is a ``@property``, not a field, so ``asdict`` excludes it for free.

Scope of Phase 1a: rows are stored per ``(task_id, seed)`` over the captured
SEED_SET. Base/overlay de-duplication (store the shared catalog once) and live
``seed_rule`` recomputation for out-of-set seeds are the Phase 1b / Phase 2
refinements — they only shrink the file and widen seed coverage; they do not
change this reconstruction contract.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any

from server.apps.world import WorldState
from server.seeddb import _equiv
from server.tasks import make_task

# Every dict[str, <entity>] collection in the world that becomes its own table.
# (world path, table name, folder-discriminator column or None). Order matters
# only for readability. Lists (world.events), singletons (carts, schedule) and all
# scalar fields are NOT here — they stay in the task remainder, which is what makes
# the split exhaustive.
COLLECTIONS: list[tuple[str, str, str, str | None]] = [
    ("shop", "products", "shop_product", None),
    ("shop", "promotions", "shop_promotion", None),
    ("shop", "users", "shop_user", None),
    ("shop", "orders", "shop_order", None),
    ("shop", "returns", "shop_return", None),
    ("shop", "subscriptions", "shop_subscription", None),
    ("mail", "inbox", "mail_message", "inbox"),
    ("mail", "sent", "mail_message", "sent"),
    ("mail", "drafts", "mail_message", "drafts"),
    ("food", "restaurants", "food_restaurant", None),
    ("food", "orders", "food_order", None),
    ("calendar", "events", "calendar_event", None),
    ("market", "products", "market_product", None),
    ("market", "coupons", "market_coupon", None),
    ("market", "orders", "market_order", None),
]

def _tables() -> list[str]:
    seen: list[str] = []
    for _app, _field, table, _folder in COLLECTIONS:
        if table not in seen:
            seen.append(table)
    return seen


DDL = [
    """CREATE TABLE fixture_version(
        version TEXT PRIMARY KEY, git_sha TEXT, created_at TEXT, notes TEXT)""",
    # One row per (task, seed): world_kind (what make_task returns, so Phase-2
    # hydrate knows whether to hand back a bare GymState or a WorldState) plus the
    # remainder — the whole world MINUS the collection tables below.
    """CREATE TABLE task(
        task_id TEXT NOT NULL, seed INTEGER NOT NULL,
        world_kind TEXT NOT NULL,        -- 'shop' (bare GymState) | 'world' (WorldState)
        remainder_json TEXT NOT NULL,    -- everything not lifted into a collection row
        PRIMARY KEY(task_id, seed))""",
]
for _t in _tables():
    _folder_col = ", folder TEXT" if _t == "mail_message" else ""
    # key = the store dict key (may differ from an id field); pos = insertion
    # ordinal so ORDER BY pos rebuilds dict order; data_json = the entity's
    # complete asdict and the round-trip's source of truth.
    DDL.append(
        f"""CREATE TABLE {_t}(
        task_id TEXT NOT NULL, seed INTEGER NOT NULL{_folder_col},
        key TEXT NOT NULL,
        pos INTEGER NOT NULL,
        data_json TEXT NOT NULL)"""
    )
    DDL.append(f"CREATE INDEX idx_{_t}_task ON {_t}(task_id, seed)")


def create_db(conn: sqlite3.Connection) -> None:
    for stmt in DDL:
        conn.execute(stmt)


def world_kind(task_id: str, seed: int) -> str:
    """'world' if make_task returns a fully-built WorldState, else 'shop'."""
    return "world" if isinstance(make_task(task_id, seed), WorldState) else "shop"


def extract(task_id: str, seed: int) -> tuple[dict, list[dict]]:
    """Build the world and shred it into (task_row, entity_rows).

    The remainder is ``asdict(world)`` with each collection emptied in place, so
    remainder + collections is exhaustive by construction.
    """
    world = _equiv.build_wrapped(task_id, seed)
    graph = asdict(world)

    entity_rows: list[dict] = []
    for app, field, table, folder in COLLECTIONS:
        app_state = graph.get(app)
        if not isinstance(app_state, dict):
            continue  # a sub-app that is absent (build_wrapped fills all, so rare)
        store = app_state.get(field)
        if not isinstance(store, dict):
            continue
        for pos, (key, entity) in enumerate(store.items()):
            row = {
                "task_id": task_id, "seed": seed, "key": key, "pos": pos,
                "table": table, "data_json": json.dumps(entity, default=str),
            }
            if folder is not None:
                row["folder"] = folder
            entity_rows.append(row)
        # Empty the collection in the remainder: its contents now live in rows.
        app_state[field] = {}

    task_row = {
        "task_id": task_id, "seed": seed,
        "world_kind": world_kind(task_id, seed),
        "remainder_json": json.dumps(graph, default=str),
    }
    return task_row, entity_rows


def write(conn: sqlite3.Connection, task_row: dict, entity_rows: list[dict]) -> None:
    conn.execute(
        "INSERT INTO task(task_id, seed, world_kind, remainder_json) VALUES(?,?,?,?)",
        (task_row["task_id"], task_row["seed"], task_row["world_kind"], task_row["remainder_json"]),
    )
    for r in entity_rows:
        if r["table"] == "mail_message":
            conn.execute(
                "INSERT INTO mail_message(task_id, seed, folder, key, pos, data_json) VALUES(?,?,?,?,?,?)",
                (r["task_id"], r["seed"], r["folder"], r["key"], r["pos"], r["data_json"]),
            )
        else:
            conn.execute(
                f"INSERT INTO {r['table']}(task_id, seed, key, pos, data_json) VALUES(?,?,?,?,?)",
                (r["task_id"], r["seed"], r["key"], r["pos"], r["data_json"]),
            )


def reconstruct(conn: sqlite3.Connection, task_id: str, seed: int) -> dict:
    """Rebuild the world's asdict from rows: remainder with collections re-inserted
    in pos order. The inverse of extract()."""
    row = conn.execute(
        "SELECT remainder_json FROM task WHERE task_id=? AND seed=?", (task_id, seed)
    ).fetchone()
    if row is None:
        raise KeyError(f"no seed rows for {task_id} seed={seed}")
    graph = json.loads(row[0])

    for app, field, table, folder in COLLECTIONS:
        app_state = graph.get(app)
        if not isinstance(app_state, dict) or field not in app_state:
            continue
        if table == "mail_message":
            cur = conn.execute(
                "SELECT key, data_json FROM mail_message "
                "WHERE task_id=? AND seed=? AND folder=? ORDER BY pos",
                (task_id, seed, folder),
            )
        else:
            cur = conn.execute(
                f"SELECT key, data_json FROM {table} "
                "WHERE task_id=? AND seed=? ORDER BY pos",
                (task_id, seed),
            )
        app_state[field] = {key: json.loads(data) for key, data in cur.fetchall()}
    return graph


def roundtrip_ok(conn: sqlite3.Connection, task_id: str, seed: int, golden: dict) -> tuple[bool, str]:
    """Reconstruct and compare to the Phase-0 golden at value AND order level."""
    rebuilt = reconstruct(conn, task_id, seed)
    canon = _equiv._canonical(rebuilt)
    value_hash = _equiv._hash(canon, ordered=False)
    order_hash = _equiv._hash(canon, ordered=True)
    if value_hash != golden["asdict_hash"]:
        return False, "asdict/value mismatch"
    if order_hash != golden["order_hash"]:
        return False, "insertion-order mismatch"
    return True, ""
