#!/usr/bin/env python
"""Capture the golden reference the SQL migration is graded against.

For every ``(task_id, seed)`` this records the signatures the equivalence gate
will later assert the SQL-hydrated world reproduces byte-for-byte:

* ``asdict_hash``   — Level 2 MASTER: the full dataclass graph, value-canonical.
                      Order-INSENSITIVE (dict ==), so it proves nothing is lost by
                      VALUE but is blind to insertion order.
* ``to_json_hash``  — Level 1: the annotator's exact ``hash_world(to_json())``,
                      i.e. the bytes the annotator's checkpoints/replay compare.
* ``order_hash``    — Level 3 (data level): a signature of the insertion order of
                      EVERY dict and list in the world. This is what catches a
                      reordered catalog, which ``asdict_hash`` provably cannot see
                      yet the storefront renders in insertion order. Rendered-HTML
                      (``render_hash``) is captured later, at the Phase 2/3 cutover
                      cross-check, when there is a hydrator to compare against.
* ``product_order`` — the shop product ids in dict order, kept human-readable so a
                      catalog-order failure is diagnosable at a glance.

The reference is built through ``_equiv.build_wrapped`` — the same wrap-and-default
logic ``_reset_inline`` uses — so "the golden" always means "what the gym actually
resets to". The output must be byte-identical on two consecutive runs
(stationarity); run with ``--check`` to fail if it differs from what is committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

# Allow running as `python tools/gen_goldens.py` from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server.seeddb import _equiv  # noqa: E402
from server.seeddb.store import GOLDEN_PATH, SEED_SET  # noqa: E402,F401 (single source)
from server.tasks import TASKS  # noqa: E402


def _order_hash(world: object) -> str:
    """A fingerprint of the insertion order of every dict + list in the world.

    ``_canonical`` rebuilds dicts in iteration order, and ``sort_keys=False`` keeps
    it — so any reordering anywhere (products, promotions, users, cart lines,
    events) changes this hash, while a pure value change is already caught by
    ``asdict_hash``. The two together are complete: value AND order."""
    payload = json.dumps(_equiv.asdict_canonical(world), sort_keys=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _product_order(world: object) -> list[str]:
    shop = getattr(world, "shop", None)
    products = getattr(shop, "products", None)
    return list(products.keys()) if isinstance(products, dict) else []


def capture() -> dict:
    out: dict[str, dict] = {}
    failures: list[str] = []
    for task_id in sorted(TASKS):
        per_seed: dict[str, dict] = {}
        for seed in SEED_SET:
            try:
                world = _equiv.build_wrapped(task_id, seed)
            except Exception as exc:  # noqa: BLE001 — surface which task/seed cannot build
                failures.append(f"{task_id} seed={seed}: {type(exc).__name__}: {exc}")
                continue
            per_seed[str(seed)] = {
                "asdict_hash": _equiv.asdict_hash(world),
                "to_json_hash": _equiv.hash_world(world.to_json()),
                "order_hash": _order_hash(world),
                "product_order": _product_order(world),
            }
        out[task_id] = per_seed
    if failures:
        raise SystemExit(
            f"{len(failures)} (task, seed) pairs could not build — the golden is "
            f"incomplete, refusing to write:\n  " + "\n  ".join(failures[:20])
        )
    return out


def _serialize(goldens: dict) -> str:
    # Deterministic on disk: sorted keys, stable separators, trailing newline.
    return json.dumps(goldens, sort_keys=True, indent=2) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture / verify the seed golden reference.")
    ap.add_argument("--check", action="store_true",
                    help="fail if the freshly captured goldens differ from the committed file")
    args = ap.parse_args()

    goldens = capture()
    text = _serialize(goldens)
    n_tasks = len(goldens)
    n_cells = sum(len(v) for v in goldens.values())

    if args.check:
        if not GOLDEN_PATH.exists():
            print(f"no committed golden at {GOLDEN_PATH}", file=sys.stderr)
            return 1
        committed = GOLDEN_PATH.read_text(encoding="utf-8")
        if committed != text:
            print("GOLDEN DRIFT: freshly captured seed_hashes.json != committed. "
                  "make_task is not stationary, or the world changed.", file=sys.stderr)
            return 1
        print(f"goldens stationary: {n_tasks} tasks x {len(SEED_SET)} seeds = {n_cells} cells match")
        return 0

    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {GOLDEN_PATH} — {n_tasks} tasks x {len(SEED_SET)} seeds = {n_cells} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
