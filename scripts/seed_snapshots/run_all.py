#!/usr/bin/env python3
"""Run the full seed-snapshot backfill pipeline (checkpointed)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from common import PYTHON, SCRIPTS_DIR, assert_sellable_untouched


STEPS = [
    "inventory.py",
    "generate_initial.py",
    "extract_finals.py",
    "replay_verify.py",
    "spotcheck.py",
    "seed_branching.py",
    "build_manifest.py",
]


def main() -> None:
    assert_sellable_untouched()
    for step in STEPS:
        print(f"\n======== {step} ========", flush=True)
        rc = subprocess.call([str(PYTHON), str(SCRIPTS_DIR / step)])
        if rc != 0:
            raise SystemExit(f"{step} failed with {rc}")
    assert_sellable_untouched()
    print("\n[done] sellable CSV untouched; pipeline complete.", flush=True)


if __name__ == "__main__":
    main()
