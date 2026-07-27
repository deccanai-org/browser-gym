"""The equivalence oracle — the mechanical "nothing lost" proof.

Three comparison surfaces, used by the goldens tool and the CI-blocking gate:

* ``hash_world(to_json(world))`` — Level 1, the annotator-contract corollary. This
  is the EXACT bytes the annotator's checkpoints/replay/restore compare, copied
  verbatim from ``browser-gym-annotator/backend/app/checkpoints.py`` so the two
  cannot drift. It strips volatile keys and canonicalises integral floats. It is
  necessary but INSUFFICIENT as a cutover criterion: ``to_json`` omits the whole
  catalog/promotions/non-current-users and the strip drops ``action_log`` /
  ``flash_messages`` — so a corrupted catalog passes the hash yet breaks
  verifiers. Never use it alone to decide the migration is safe.

* ``asdict_canonical(world)`` — Level 2, the MASTER gate. ``dataclasses.asdict``
  recurses the ENTIRE dataclass graph, so it sees everything ``to_json`` hides and
  everything the hash strips: the full product/promotion/user catalog, every
  non-current user, every immutable Order/OrderItem snapshot field, and every
  hidden field that is deliberately absent from ``to_json`` (mail ``account_name``
  / ``_next`` / ``armed_*`` traps, food ``defer_receipt_steps`` /
  ``enable_delivery_notes`` / ``_next``, calendar ``account_name`` / ``_next``,
  market ``store_name`` / ``fees`` / ``_next``). It excludes ONLY ``mint_counts``,
  which is a ``@property`` (not a field) and provably empty at the seed baseline.
  Equality here mechanically proves nothing serialised OR hidden is lost.

* ``build_wrapped(task_id, seed)`` — the reference world. It reproduces
  ``_reset_inline``'s exact wrap-and-default logic (``server/main.py:196-214``) and
  returns the ``WorldState`` the running gym would hold at step 0, WITHOUT touching
  the ``SESSION`` global. Both the goldens and the gate build their reference
  through this so "the factory output" always means "what the gym actually resets
  to", single-app defaulting included.

Neither Level 1 nor Level 2 can see catalog dict INSERTION ORDER (the hash omits
the catalog; ``dict ==`` is order-insensitive) — that is the render gate's job
(Level 3), which lives with the goldens tool, not here.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from typing import Any

# ---------------------------------------------------------------- Level 1: hash
# Copied VERBATIM from browser-gym-annotator/backend/app/checkpoints.py so the gym
# and the annotator hash a world the same way byte-for-byte. Do not "improve" this
# in isolation — it must stay identical to the annotator's oracle.
_VOLATILE = {"flash_messages", "action_log"}


def _normalize(value: Any) -> Any:
    """Strip volatile keys and canonicalize numbers.

    The number rule is load-bearing: a world stored in a JSON column comes back
    with ``0.0`` where the live gym reports ``0`` — same money, different
    serialization — so an integral float must hash identically to its int.
    """
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in sorted(value.items()) if k not in _VOLATILE}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    # bool is a subclass of int; leave it alone or True would hash as 1.
    if isinstance(value, float) and not isinstance(value, bool) and value.is_integer():
        return int(value)
    return value


def hash_world(world: dict | None) -> str:
    """A stable fingerprint of task-relevant world state. Empty world -> "" so a
    missing capture is never mistaken for a matching one."""
    if not world:
        return ""
    payload = json.dumps(_normalize(world), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# ------------------------------------------------------- Level 2: full asdict
def _canonical(value: Any) -> Any:
    """Recursively collapse integral floats to int so a REAL-vs-INTEGER storage
    choice can never cause a false diff. Unlike ``_normalize`` this keeps EVERY
    key (including the volatile ones): at the seed baseline they are identical on
    both sides, and the master gate must compare the full graph."""
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, float) and not isinstance(value, bool) and value.is_integer():
        return int(value)
    return value


def asdict_canonical(world: Any) -> dict:
    """The MASTER equivalence surface: the full dataclass graph, canonicalised.

    ``dataclasses.asdict`` deep-copies and recurses every field, so it captures the
    entire world including every field ``to_json`` omits. ``mint_counts`` is a
    property, not a field, so it is naturally excluded (and is empty at seed time)."""
    return _canonical(dataclasses.asdict(world))


def asdict_hash(world: Any) -> str:
    payload = json.dumps(asdict_canonical(world), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


# ------------------------------------------------ the reference world builder
def build_wrapped(task_id: str, seed: int) -> Any:
    """Reproduce EXACTLY the ``WorldState`` the gym holds at step 0 for
    ``(task_id, seed)`` — i.e. what ``_reset_inline`` builds — without mutating the
    ``SESSION`` global.

    Mirrors ``server/main.py:196-214`` line for line. Kept in sync with
    ``_reset_inline`` by the equivalence tests, which reset the real server and
    assert this equals ``SESSION.world`` for a sample of tasks. If those tests ever
    fail, this drifted and must be re-synced — do not paper over it.
    """
    # Imported lazily so importing this module never triggers the (heavy) task
    # registry unless a caller actually builds a world.
    from server.apps.calendar.state import make_calendarstate
    from server.apps.food.state import make_foodstate
    from server.apps.mail.state import make_mailstate
    from server.apps.market.state import make_marketstate
    from server.apps.world import WorldState
    from server.tasks import make_task

    built = make_task(task_id, seed)
    if isinstance(built, WorldState):
        world = built
        if world.mail is None:
            world.mail = make_mailstate(seed)
        if world.food is None:
            world.food = make_foodstate(seed)
        if world.calendar is None:
            world.calendar = make_calendarstate(seed)
        if world.market is None:
            world.market = make_marketstate(seed)
    else:
        world = WorldState(
            shop=built,
            mail=make_mailstate(seed),
            food=make_foodstate(seed),
            calendar=make_calendarstate(seed),
            market=make_marketstate(seed),
        )
    # A deepcopy so a caller that mutates the returned world (or the gym that later
    # builds the same task) cannot alias shared factory-level objects.
    return copy.deepcopy(world)


__all__ = [
    "hash_world", "asdict_canonical", "asdict_hash", "build_wrapped",
]
