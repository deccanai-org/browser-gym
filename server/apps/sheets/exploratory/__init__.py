"""Exploratory Sheets task fixtures (S1–S3) — not registered in server/tasks.py.

Seed builders + success/harm predicates for proving mechanisms before any
BRIEFS / make_task wiring. Temporary exploratory task hooks (``task_hook``)
let UI-only oracles reset/verify without sellable registration — see
``task_hook.py`` and the design note.
"""

from __future__ import annotations

from server.apps.sheets.exploratory import checks, seeds, task_hook

__all__ = ["checks", "seeds", "task_hook"]
