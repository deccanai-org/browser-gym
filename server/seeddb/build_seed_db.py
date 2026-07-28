#!/usr/bin/env python
"""Materialise fixtures/seed.db from the (stationary) factory output.

Shreds every (task_id, seed) over SEED_SET into rows via server.seeddb.store and,
in the same pass, round-trips each against the Phase-0 golden — so the build
REFUSES to produce a seed.db that does not reconstruct byte-equivalent worlds.
Nothing is hand-authored; the factories remain the source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

from server.seeddb import store  # noqa: E402
from server.tasks import TASKS  # noqa: E402
# All build constants live in store so this module (and an image build) need only
# server/ — never tools/ or tests/. GOLDEN_PATH is read only when verifying.
from server.seeddb.store import DB_PATH, FIXTURE_VERSION, GOLDEN_PATH, SEED_SET  # noqa: E402,F401


def build(conn: sqlite3.Connection, golden: dict | None = None, *, verify: bool = False) -> tuple[int, list[str]]:
    """Shred every (task, seed) into rows. Fast (~seconds): the per-cell
    round-trip verification is OFF by default here because it is enforced by
    tests/test_seeddb_roundtrip.py against the committed file. Pass verify=True to
    also check each cell against the golden inline (slower)."""
    store.create_db(conn)
    conn.execute(
        "INSERT INTO fixture_version(version, git_sha, created_at, notes) VALUES(?,?,?,?)",
        (FIXTURE_VERSION, "", "", "generated from factories; see docs/SQL_SEED_DB_MIGRATION.md"),
    )
    cells = 0
    failures: list[str] = []
    for task_id in sorted(TASKS):
        for seed in SEED_SET:
            task_row, entity_rows = store.extract(task_id, seed)
            store.write(conn, task_row, entity_rows)
            if verify:
                ok, why = store.roundtrip_ok(conn, task_id, seed, golden[task_id][str(seed)])
                if not ok:
                    failures.append(f"{task_id} seed={seed}: {why}")
            cells += 1
    return cells, failures


def _content_hash(conn: sqlite3.Connection) -> str:
    """A deterministic fingerprint of the DB CONTENT (not the file bytes, which
    SQLite does not guarantee stable). Every row of every table, canonically
    ordered."""
    h = hashlib.sha256()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t})")]
        order = ", ".join(f'"{c}"' for c in cols)
        for row in conn.execute(f"SELECT * FROM {t} ORDER BY {order}"):
            h.update(json.dumps([t, *row], default=str, separators=(",", ":")).encode())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="build in memory and print the content hash without writing the file")
    ap.add_argument("--verify", action="store_true",
                    help="also round-trip every cell against the golden inline (slower)")
    args = ap.parse_args()

    n_tasks = len(set(TASKS))
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8")) if (args.check or args.verify) else None

    if args.check:
        # In-memory only; report the content fingerprint without writing a file.
        conn = sqlite3.connect(":memory:")
        cells, failures = build(conn, golden, verify=args.verify)
        if failures:
            print(f"REFUSING: {len(failures)} round-trip failures:\n  " + "\n  ".join(failures[:20]),
                  file=sys.stderr)
            return 1
        print(f"{n_tasks} tasks x {len(SEED_SET)} seeds = {cells} cells")
        print(f"content hash: {_content_hash(conn)}")
        return 0

    # Build DIRECTLY into the file — an in-memory build + conn.backup() to disk
    # hangs on a db this size, and a direct write is both faster and simpler.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".sqlite.tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.execute("PRAGMA journal_mode=OFF")     # no rollback journal; this is a throwaway build
    conn.execute("PRAGMA synchronous=OFF")
    try:
        cells, failures = build(conn, golden, verify=args.verify)
        if failures:
            print(f"REFUSING to write: {len(failures)} round-trip failures:\n  "
                  + "\n  ".join(failures[:20]), file=sys.stderr)
            return 1
        content = _content_hash(conn)
        conn.commit()
    finally:
        conn.close()
    tmp.replace(DB_PATH)   # atomic swap so a partial build never lands
    print(f"round-trip cells: {cells}  content hash: {content}")
    print(f"wrote {DB_PATH} ({DB_PATH.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
