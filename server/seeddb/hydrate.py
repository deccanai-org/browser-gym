"""Phase 2 — rebuild LIVE dataclass objects from the seed pool.

Phase 1 proved the DB reconstructs the world's ``asdict`` byte-for-byte. This
turns that dict back into the real dataclass graph the gym runs on, so
``make_task`` can one day serve from SQL (Phase 3) with nothing downstream
noticing.

The reconstruction reuses ``server.apps.statecodec.from_dict`` — the same
reflection-based rebuilder the resume codec uses — so hydration and resume cannot
diverge in how they turn a snapshot back into objects. ``from_dict`` reads each
field's type hint and rebuilds nested dataclasses / lists / dicts, ignoring any
non-field key, and never touches ``mint_counts`` (a property) or the per-app
``_next`` counters are restored as the plain int fields they are.

``hydrate_world`` returns the SAME type ``make_task`` returns — a bare
``GymState`` for a single-app task, a ``WorldState`` for a cross-app one — so it
flows through the unchanged ``_reset_inline`` (which re-defaults the sub-apps for
a single-app task exactly as it does for the factory). Nothing here is wired into
the runtime; ``make_task`` still builds from the factories until Phase 3 flips
``SEEDDB_MODE``.
"""

from __future__ import annotations

import sqlite3

from server.apps.bus import WorldEvent
from server.apps.calendar.state import CalendarState
from server.apps.food.state import FoodState
from server.apps.mail.state import MailState
from server.apps.market.state import MarketState
from server.apps.scheduler import ScheduleState
from server.apps.statecodec import from_dict
from server.apps.world import WorldState
from server.seeddb import store
from server.state import GymState


def _world_from_dict(g: dict) -> WorldState:
    """Rebuild WorldState from its asdict form.

    WorldState is assembled field by field rather than via ``from_dict`` because
    its sub-app annotations are forward references (``Optional["MailState"]``) that
    ``typing.get_type_hints`` cannot resolve in world.py's namespace — the same
    reason statecodec decomposes WorldState by hand. Every sub-store DOES resolve,
    so ``from_dict`` rebuilds each one (and their nested entity graphs)."""
    def sub(cls: type, key: str):
        return from_dict(cls, g[key]) if g.get(key) is not None else None

    return WorldState(
        shop=from_dict(GymState, g["shop"]),
        mail=sub(MailState, "mail"),
        food=sub(FoodState, "food"),
        calendar=sub(CalendarState, "calendar"),
        market=sub(MarketState, "market"),
        events=[from_dict(WorldEvent, e) for e in g.get("events", [])],
        schedule=from_dict(ScheduleState, g["schedule"]) if g.get("schedule") is not None else ScheduleState(),
    )


def hydrate_full(conn: sqlite3.Connection, task_id: str, seed: int) -> WorldState:
    """The complete WorldState rebuilt from rows — every catalog/record entity as
    a real dataclass instance. This is what the Phase-2 gate grades against the
    golden: it must asdict-equal the factory's wrapped world."""
    return _world_from_dict(store.reconstruct(conn, task_id, seed))


def hydrate_world(conn: sqlite3.Connection, task_id: str, seed: int):
    """The ``make_task``-equivalent: a bare GymState for a single-app task, a
    WorldState for a cross-app one. Raises KeyError if this (task, seed) is not in
    the pool (an out-of-set seed) — the caller falls back to the factory."""
    row = conn.execute(
        "SELECT world_kind FROM task WHERE task_id=? AND seed=?", (task_id, seed)
    ).fetchone()
    if row is None:
        raise KeyError(f"{task_id} seed={seed} is not in the seed db")
    world = hydrate_full(conn, task_id, seed)
    return world.shop if row[0] == "shop" else world


def has(conn: sqlite3.Connection, task_id: str, seed: int) -> bool:
    """Whether the pool covers this (task, seed) — the fast path exists."""
    return conn.execute(
        "SELECT 1 FROM task WHERE task_id=? AND seed=?", (task_id, seed)
    ).fetchone() is not None
