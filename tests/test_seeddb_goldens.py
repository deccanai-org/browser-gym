"""Phase 0 gate: the goldens are stationary and the oracle can't silently drift.

These are the "ruler" tests. Until the SQL hydrator exists (Phase 2) the goldens
are graded only against the factories, but three things must already hold or the
whole migration is built on sand:

1. The committed goldens re-capture byte-identically (make_task is stationary).
2. ``build_wrapped`` still equals what a real reset produces (the reference the
   goldens are built through hasn't drifted from ``_reset_inline``).
3. ``hash_world`` still produces its pinned outputs (the algorithm copied verbatim
   from the annotator hasn't been "improved" on this side).

All three are fast (no browser) and CI-blocking.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from server.seeddb import _equiv

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from tools import gen_goldens  # noqa: E402


def test_goldens_are_stationary():
    """Re-capturing the goldens must match the committed file byte-for-byte.

    A legitimate factory change (new product, new task) will fail this — that is
    the point: golden updates must be conscious. Regenerate with
    ``python tools/gen_goldens.py`` and review the diff."""
    committed = gen_goldens.GOLDEN_PATH.read_text(encoding="utf-8")
    fresh = gen_goldens._serialize(gen_goldens.capture())
    assert fresh == committed, (
        "seed_hashes.json drifted from the factories — make_task is not stationary, "
        "or a factory changed. Re-run tools/gen_goldens.py and review the diff."
    )


# A spread across single-app (A/B/C/D) and cross-app (M) tasks, so both the
# WorldState-returning and the GymState-wrapped paths of _reset_inline are covered.
_SAMPLE = [
    "A1/buy_wireless_mouse",
    "A2/filter_laptop",
    "M301/stale_tracking_forward_sycophancy",
    "M310/cancel_sub_false_no_transit_claim",
]


@pytest.mark.parametrize("task_id", _SAMPLE)
@pytest.mark.parametrize("seed", [0, 1])
def test_build_wrapped_matches_a_real_reset(task_id, seed):
    """build_wrapped must equal SESSION.world after a real _reset_inline.

    build_wrapped re-implements _reset_inline's wrap-and-default logic to avoid
    touching the SESSION global; if _reset_inline gains a line and this doesn't,
    the goldens would silently lie. This catches that drift at both surfaces."""
    import server.main as m

    m._reset_inline(task_id, seed)
    live = m.SESSION.world
    ref = _equiv.build_wrapped(task_id, seed)
    assert _equiv.asdict_hash(live) == _equiv.asdict_hash(ref), "asdict drift vs real reset"
    assert _equiv.hash_world(live.to_json()) == _equiv.hash_world(ref.to_json()), "to_json drift vs real reset"


# Anti-drift for the verbatim-copied hash. The annotator repo
# (backend/app/checkpoints.py) MUST carry the identical fixtures + expected values;
# if either side "improves" _normalize/hash_world, its pinned test breaks and the
# two are forced back into sync. Do not update these literals without updating the
# annotator's mirror.
_PINNED = [
    (
        {"b": 1, "a": 2.0, "action_log": ["x"], "flash_messages": [1],
         "nested": {"y": 2, "x": 1.0}, "lst": [3.0, {"m": 1.0}]},
        "a5e8e7169c9b51d8d072515ec06e6756c86a09dbb6243c56ccf145caa25524ee",
    ),
    (
        {"step": 5, "cart": {"items": [{"qty": 2.0}], "applied_promo": None}},
        "9d7c90ef37388d9938eab2e759b1995393504863e3bb8af3a5395c252f11c55d",
    ),
]


@pytest.mark.parametrize("world,expected", _PINNED)
def test_hash_world_output_is_pinned(world, expected):
    """hash_world must produce its committed output — the annotator compares these
    exact bytes, so a change here silently breaks cross-repo checkpoint/replay."""
    assert _equiv.hash_world(world) == expected


def test_hash_world_strips_volatile_and_collapses_integral_floats():
    """The two load-bearing rules, asserted directly so a refactor can't quietly
    drop them while the pinned literals happen to still match."""
    base = {"b": 1, "a": 2.0, "nested": {"x": 1.0}}
    with_volatile = {**base, "action_log": ["x"], "flash_messages": [1]}
    all_int = {"b": 1, "a": 2, "nested": {"x": 1}}
    assert _equiv.hash_world(with_volatile) == _equiv.hash_world(base)   # volatile stripped
    assert _equiv.hash_world(base) == _equiv.hash_world(all_int)         # 2.0 hashes as 2
