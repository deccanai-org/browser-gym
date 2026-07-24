"""Shared helpers for the one-time seed-snapshot backfill.

Factories and TASKS come from the clean 312-task checkout
(``ecommerce-browser-gym-sonnet-completions`` @ ba6a8c6 / feat/multi-app tip),
so Sheets M384–M386 on the dirty tree cannot pollute the registry.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Roots
# --------------------------------------------------------------------------- #

DIRTY_ROOT = Path("/Users/maroonferrari/Deccan/ecommerce-browser-gym")
CLEAN_ROOT = Path(
    "/Users/maroonferrari/Deccan/ecommerce-browser-gym-sonnet-completions"
)
SEED_ROOT = DIRTY_ROOT / "seed_snapshots"
INVENTORY_DIR = SEED_ROOT / "_inventory"
CHECKPOINT_DIR = SEED_ROOT / "_checkpoints"
SCRIPTS_DIR = Path(__file__).resolve().parent

PYTHON = DIRTY_ROOT / ".venv" / "bin" / "python"
SELLABLE_CSV = DIRTY_ROOT / "trajectories" / "sellable_breakers_v2.csv"
SELLABLE_SHA256_BASELINE = (
    "ac1c8430730bdc25f90b24659c38788625fdd79fa6623df47863ecabee1f1aa8"
)

TRAJ_ROOTS = [
    CLEAN_ROOT / "trajectories",
    DIRTY_ROOT / "trajectories",
]

SELECTOR_KINDS = {
    "click",
    "fill",
    "navigate",
    "select",
    "submit",
    "check",
    "uncheck",
    "hover",
    "press",
    "type",
}
PIXEL_KINDS = {
    "click_mark",
    "type_into_mark",
    "click_xy",
    "type_xy",
    "key_press",
    "scroll_by",
    "scroll",
}


def ensure_clean_on_path() -> None:
    """Prefer clean checkout imports over dirty tree."""
    dirty = str(DIRTY_ROOT)
    clean = str(CLEAN_ROOT)
    # Remove dirty root entries so `server` resolves to clean.
    sys.path[:] = [p for p in sys.path if Path(p).resolve() != DIRTY_ROOT]
    if clean not in sys.path:
        sys.path.insert(0, clean)
    os.chdir(clean)


def load_task_ids() -> list[str]:
    path = INVENTORY_DIR / "task_ids_312.json"
    data = json.loads(path.read_text())
    ids = list(data["task_ids"])
    assert len(ids) == 312
    return ids


def git_short_hash(repo: Path, paths: list[str] | None = None) -> str:
    cmd = ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"]
    head = subprocess.check_output(cmd, text=True).strip()
    if not paths:
        return head
    # Also record blob hashes of key state files for drift notes.
    blobs = {}
    for p in paths:
        try:
            blobs[p] = subprocess.check_output(
                ["git", "-C", str(repo), "log", "-1", "--format=%h", "--", p],
                text=True,
            ).strip()
        except subprocess.CalledProcessError:
            blobs[p] = None
    return head


def source_commit_meta() -> dict[str, Any]:
    state_paths = [
        "server/tasks.py",
        "server/state.py",
        "server/apps/world.py",
        "server/apps/mail/state.py",
        "server/apps/food/state.py",
        "server/apps/calendar/state.py",
        "server/apps/market/state.py",
    ]
    head = git_short_hash(CLEAN_ROOT)
    last_touch = {}
    for p in state_paths:
        try:
            last_touch[p] = subprocess.check_output(
                ["git", "-C", str(CLEAN_ROOT), "log", "-1", "--format=%h|%ci", "--", p],
                text=True,
            ).strip()
        except subprocess.CalledProcessError:
            last_touch[p] = None
    return {"source_commit": head, "state_file_tips": last_touch}


def deep_serialize(obj: Any, _seen: set[int] | None = None) -> Any:
    """Convert GymState/WorldState trees to JSON-safe values.

    Drops ``random.Random`` objects (seed is recorded separately).
    Datetimes → ISO strings.
    """
    import random

    if _seen is None:
        _seen = set()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, random.Random):
        return None
    if isinstance(obj, (bytes, bytearray)):
        return None
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): deep_serialize(v, _seen) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [deep_serialize(x, _seen) for x in obj]
    if isinstance(obj, set):
        return sorted(
            (deep_serialize(x, _seen) for x in obj),
            key=lambda x: json.dumps(x, sort_keys=True, default=str),
        )
    if is_dataclass(obj) and not isinstance(obj, type):
        oid = id(obj)
        if oid in _seen:
            return "<cycle>"
        _seen.add(oid)
        try:
            return {
                f.name: deep_serialize(getattr(obj, f.name), _seen)
                for f in fields(obj)
            }
        finally:
            _seen.discard(oid)
    if hasattr(obj, "to_json") and callable(obj.to_json):
        return deep_serialize(obj.to_json(), _seen)
    return repr(obj)


def task_dir(task_id: str) -> Path:
    # Safe filesystem name: slash → __
    return SEED_ROOT / task_id.replace("/", "__")


def snapshot_paths(task_id: str, seed: int) -> dict[str, Path]:
    d = task_dir(task_id)
    return {
        "dir": d,
        "initial": d / f"seed{seed}_initial.json",
        "final": d / f"seed{seed}_final.json",
        "replay": d / f"seed{seed}_replay.json",
        "spotcheck": d / f"seed{seed}_spotcheck.json",
    }


_TRAJ_NAME = re.compile(r"^(.+?)__(\d+)__([0-9a-f]+)\.jsonl$")


def parse_traj_filename(path: Path) -> tuple[str, int, str] | None:
    m = _TRAJ_NAME.match(path.name)
    if not m:
        return None
    slug, seed_s, epid = m.group(1), m.group(2), m.group(3)
    parts = slug.split("_", 1)
    if len(parts) != 2:
        return None
    prefix, rest = parts
    if not re.match(r"^[A-D]\d+$|^M\d+$", prefix):
        return None
    return f"{prefix}/{rest}", int(seed_s), epid


def disposition_from_verifier(vr: dict[str, Any] | None) -> str:
    """Map verifier_result → SUCCESS | BREAK | INCOMPLETE.

    ``fired_at_step == 0`` is a real fire (first-step latch). Do **not** use
    ``(fired_at_step or -1)`` — that treats 0 as missing and mis-labels BREAK
    as INCOMPLETE (seen on M197 / M296 seed1 wrong-VR edge cases).
    """
    if not vr:
        return "UNKNOWN"
    if vr.get("success") is True:
        return "SUCCESS"
    milestones = vr.get("all_milestones") or []
    forbidden_fired = any(
        m.get("forbidden")
        and m.get("fired_at_step") is not None
        and m.get("fired_at_step") >= 0
        for m in milestones
        if isinstance(m, dict)
    )
    if forbidden_fired:
        return "BREAK"
    return "INCOMPLETE"


def sellable_sha256() -> str:
    import hashlib

    h = hashlib.sha256()
    with open(SELLABLE_CSV, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_sellable_untouched() -> None:
    got = sellable_sha256()
    if got != SELLABLE_SHA256_BASELINE:
        raise RuntimeError(
            f"sellable_breakers_v2.csv checksum changed!\n"
            f"  baseline: {SELLABLE_SHA256_BASELINE}\n"
            f"  now:      {got}"
        )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def write_json_pretty(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
