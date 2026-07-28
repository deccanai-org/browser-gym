"""Phase 3 runtime seam — serve seeds from the DB behind ``SEEDDB_MODE``.

``_reset_inline`` builds its baseline through ``seed_source`` instead of calling
``make_task`` directly. When ``SEEDDB_MODE`` is on AND the pool covers
``(task, seed)``, ``seed_source`` returns the hydrated world; otherwise it returns
the factory's — which remains the generator and the fallback for an out-of-set
seed, a missing db, or the flag being off.

The branch lives HERE, not inside ``make_task``: the seed db is *built from*
``make_task`` (via ``build_wrapped``/``extract``/the goldens), so hydrating inside
``make_task`` would be circular. Keeping ``make_task`` a pure factory keeps it the
immutable source of truth and the fallback.

Default OFF, so this is a no-op until the flag is flipped — the gym runs entirely
on the factories, byte-for-byte as before. Turn it on with ``SEEDDB_MODE=1`` once
the transparency check (Phase 3 exit) is green.
"""

from __future__ import annotations

import os
import sqlite3

from server.seeddb import hydrate, store
from server.tasks import make_task


def seeddb_enabled() -> bool:
    return os.getenv("SEEDDB_MODE", "").strip().lower() in ("1", "true", "on", "yes")


def seed_source(task_id: str, seed: int):
    """The make_task-equivalent baseline for ``(task, seed)``.

    From ``seed.db`` when the flag is on and the pool covers it; from the factory
    otherwise. A fresh read-only connection per call — a reset is not a hot path,
    and a per-call connection sidesteps SQLite's cross-thread rules under the
    gym's server.
    """
    if seeddb_enabled() and store.DB_PATH.exists():
        conn = sqlite3.connect(f"file:{store.DB_PATH}?mode=ro", uri=True)
        try:
            if hydrate.has(conn, task_id, seed):
                return hydrate.hydrate_world(conn, task_id, seed)
        finally:
            conn.close()
    return make_task(task_id, seed)
