"""Storage engine — a content-addressed seed pool + per-task composition.

This is Shravan's "store the shared seed data once, assemble it per task", made
lossless and safe:

* ``seed_entity`` is the DEDUPLICATED pool — every DISTINCT seed entity (a
  product, an email, an order) stored exactly once, keyed by the hash of its
  content. The catalog that Phase 1a duplicated ~300x across tasks collapses to
  one row per distinct value (measured: 43 MB -> ~2.7 MB).
* ``seed_member`` is the per-(task, seed) COMPOSITION: for each collection, an
  ordered list of (key -> pool entity). This is the "task overlay" — which
  entities a task's world contains, in what order.
* ``task`` holds the per-task REMAINDER: everything that is not one of those
  collections (scalar headers, carts, schedule, event log, each sub-app's scalar
  fields). It does not dedup and is not meant to — it is genuinely per task.

Why content-addressing rather than a literal base+diff overlay: it gets the same
de-duplication with none of the hazards a diff has. There is no "reorder the base
rows" case (every membership carries its own ``pos``), no tombstone bookkeeping,
and no trouble with an entity that varies in two ways at once by seed (a distinct
value is simply a distinct pool row). Seed-invariant entities dedup automatically
(same content -> same hash); A2's seed-varying price becomes a handful of pool
rows; the calendar parity event is present in odd-seed compositions and absent
from even ones. All of it falls out of "store distinct content once, reference it
in order".

Reconstruction is exact by construction — remainder + each collection's members
resolved through the pool in ``pos`` order — so the round-trip gate that graded
Phase 1a grades this unchanged: every (task, seed) must hash-equal its Phase-0
golden at value AND insertion-order level.

Scope: rows cover the captured SEED_SET. An out-of-set seed is not in the pool;
the Phase-2 hydrator falls back to the factory for those (the factories remain
the source of truth and fallback), or a later step precomputes more seeds.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict

from server.apps.world import WorldState
from server.seeddb import _equiv
from server.tasks import make_task

# Every dict[str, <entity>] collection that is lifted out of the remainder into the
# content-addressed pool. (app, field, collection_id, entity_type). collection_id is
# the reconstruction path; entity_type makes the pool queryable
# (SELECT * FROM seed_entity WHERE entity_type='Product').
COLLECTIONS: list[tuple[str, str, str, str]] = [
    ("shop", "products", "shop.products", "Product"),
    ("shop", "promotions", "shop.promotions", "Promotion"),
    ("shop", "users", "shop.users", "User"),
    ("shop", "orders", "shop.orders", "Order"),
    ("shop", "returns", "shop.returns", "Return"),
    ("shop", "subscriptions", "shop.subscriptions", "Subscription"),
    ("mail", "inbox", "mail.inbox", "Email"),
    ("mail", "sent", "mail.sent", "Email"),
    ("mail", "drafts", "mail.drafts", "Email"),
    ("food", "restaurants", "food.restaurants", "Restaurant"),
    ("food", "orders", "food.orders", "FoodOrder"),
    ("calendar", "events", "calendar.events", "CalendarEvent"),
    ("market", "products", "market.products", "MarketProduct"),
    ("market", "coupons", "market.coupons", "MarketCoupon"),
    ("market", "orders", "market.orders", "MarketOrder"),
]

_BY_ID = {c[2]: c for c in COLLECTIONS}

DDL = [
    """CREATE TABLE fixture_version(
        version TEXT PRIMARY KEY, git_sha TEXT, created_at TEXT, notes TEXT)""",
    # The per-(task, seed) remainder: the whole world MINUS the collections below.
    """CREATE TABLE task(
        task_id TEXT NOT NULL, seed INTEGER NOT NULL,
        world_kind TEXT NOT NULL,        -- 'shop' (bare GymState) | 'world' (WorldState)
        remainder_json TEXT NOT NULL,
        PRIMARY KEY(task_id, seed))""",
    # The deduplicated pool: each distinct seed entity once, keyed by content hash.
    # data_json = the entity's complete asdict and the round-trip's source of truth.
    """CREATE TABLE seed_entity(
        content_hash TEXT PRIMARY KEY,   -- sha256(data_json)
        entity_type TEXT NOT NULL,       -- Product | Email | Order | ... (queryable)
        data_json TEXT NOT NULL)""",
    # The per-(task, seed) composition: ordered references into the pool. No
    # primary key — the source dict already guarantees unique keys, so a composite
    # PK would only add a large redundant index; the lookup index below is all
    # reconstruction needs.
    """CREATE TABLE seed_member(
        task_id TEXT NOT NULL, seed INTEGER NOT NULL,
        collection TEXT NOT NULL,        -- 'shop.products', 'mail.inbox', ...
        key TEXT NOT NULL,               -- the store dict key
        pos INTEGER NOT NULL,            -- ORDER BY pos rebuilds dict insertion order
        content_hash TEXT NOT NULL)""",
    "CREATE INDEX idx_member_lookup ON seed_member(task_id, seed, collection, pos)",
    "CREATE INDEX idx_entity_type ON seed_entity(entity_type)",
]


def create_db(conn: sqlite3.Connection) -> None:
    for stmt in DDL:
        conn.execute(stmt)


def world_kind(task_id: str, seed: int) -> str:
    """'world' if make_task returns a fully-built WorldState, else 'shop'."""
    return "world" if isinstance(make_task(task_id, seed), WorldState) else "shop"


def extract(task_id: str, seed: int) -> tuple[dict, list[dict]]:
    """Build the world and shred it into (task_row, member_rows).

    Each member row carries the entity's data_json inline; write() is what pools
    it by content hash. The remainder is asdict(world) with each collection
    emptied in place, so remainder + collections is exhaustive by construction.
    """
    world = _equiv.build_wrapped(task_id, seed)
    graph = asdict(world)

    members: list[dict] = []
    for app, field, collection_id, entity_type in COLLECTIONS:
        app_state = graph.get(app)
        if not isinstance(app_state, dict):
            continue
        store = app_state.get(field)
        if not isinstance(store, dict):
            continue
        for pos, (key, entity) in enumerate(store.items()):
            data_json = json.dumps(entity, default=str)
            members.append({
                "task_id": task_id, "seed": seed, "collection": collection_id,
                "key": key, "pos": pos, "entity_type": entity_type,
                "content_hash": hashlib.sha256(data_json.encode()).hexdigest(),
                "data_json": data_json,
            })
        app_state[field] = {}   # contents now live in members

    task_row = {
        "task_id": task_id, "seed": seed,
        "world_kind": world_kind(task_id, seed),
        "remainder_json": json.dumps(graph, default=str),
    }
    return task_row, members


def write(conn: sqlite3.Connection, task_row: dict, members: list[dict]) -> None:
    conn.execute(
        "INSERT INTO task(task_id, seed, world_kind, remainder_json) VALUES(?,?,?,?)",
        (task_row["task_id"], task_row["seed"], task_row["world_kind"], task_row["remainder_json"]),
    )
    for m in members:
        conn.execute(
            "INSERT OR IGNORE INTO seed_entity(content_hash, entity_type, data_json) VALUES(?,?,?)",
            (m["content_hash"], m["entity_type"], m["data_json"]),
        )
        conn.execute(
            "INSERT INTO seed_member(task_id, seed, collection, key, pos, content_hash) VALUES(?,?,?,?,?,?)",
            (m["task_id"], m["seed"], m["collection"], m["key"], m["pos"], m["content_hash"]),
        )


def reconstruct(conn: sqlite3.Connection, task_id: str, seed: int) -> dict:
    """Rebuild the world's asdict: remainder with each collection's members
    resolved through the pool, in pos order. The inverse of extract()."""
    row = conn.execute(
        "SELECT remainder_json FROM task WHERE task_id=? AND seed=?", (task_id, seed)
    ).fetchone()
    if row is None:
        raise KeyError(f"no seed rows for {task_id} seed={seed}")
    graph = json.loads(row[0])

    for app, field, collection_id, _type in COLLECTIONS:
        app_state = graph.get(app)
        if not isinstance(app_state, dict) or field not in app_state:
            continue
        cur = conn.execute(
            "SELECT m.key, e.data_json FROM seed_member m "
            "JOIN seed_entity e ON e.content_hash = m.content_hash "
            "WHERE m.task_id=? AND m.seed=? AND m.collection=? ORDER BY m.pos",
            (task_id, seed, collection_id),
        )
        app_state[field] = {key: json.loads(data) for key, data in cur.fetchall()}
    return graph


def roundtrip_ok(conn: sqlite3.Connection, task_id: str, seed: int, golden: dict) -> tuple[bool, str]:
    """Reconstruct and compare to the Phase-0 golden at value AND order level."""
    rebuilt = reconstruct(conn, task_id, seed)
    canon = _equiv._canonical(rebuilt)
    if _equiv._hash(canon, ordered=False) != golden["asdict_hash"]:
        return False, "asdict/value mismatch"
    if _equiv._hash(canon, ordered=True) != golden["order_hash"]:
        return False, "insertion-order mismatch"
    return True, ""
