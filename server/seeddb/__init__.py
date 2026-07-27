"""SQL seed-database layer for the gym.

The gym's seed data lives in a read-only SQLite file and is hydrated into the
SAME in-memory dataclass graph the Python factories produce. This package is a
SEED SOURCE ONLY: the live episode still runs entirely on in-memory dataclasses
mutated by ``server/mutations.py`` and serialised by the unchanged ``to_json``.

Nothing here is wired into the runtime until the equivalence gate is green and
``SEEDDB_MODE`` is turned on. See ``docs/SQL_SEED_DB_MIGRATION.md``.
"""
