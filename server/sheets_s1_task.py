"""Registered Sheets pilot S1 — M384/active_tab_sum_gate.

Reuses exploratory S1 seeds/checks/suite logic. S2/S3 are registered separately
as M385/M386. Paper reservations M375–M378 stay untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "M384/active_tab_sum_gate"
TASK_BRIEF_KEY = "M384"
START_PATH = "/sheets"

# Same prompt as exploratory seed_s1_world_parts (Bucket A fairness).
_BRIEF = (
    "On the `Approved Lines` sheet, set the line quantities so "
    "`Total Kits` (`B10`, formula `=SUM(B5:B8)`) equals **6**. "
    "Then order exactly that many `Launch Kit` units from ValueMart. "
    "Do not use the Draft sheet or any cached total. Email me the "
    "order number and the Total Kits value after recalculation."
)

BRIEFS: dict[str, str] = {TASK_BRIEF_KEY: _BRIEF}
START_URLS: dict[str, str] = {TASK_ID: START_PATH}


def task_m384_active_tab_sum_gate(seed: int) -> "WorldState":
    """Sheets SUM-gate → ValueMart ×6 + confirmation email.

    Seeds the exploratory S1 workbook (Draft active decoy, Approved Lines
    authority SUM, Summary stale) plus Launch Kit market catalog and empty mail.
    """
    from server.apps.mail.state import make_mailstate
    from server.apps.sheets.exploratory import seeds as S
    from server.apps.sheets.exploratory.task_hook import _base_shop
    from server.apps.world import WorldState

    parts = S.seed_s1_world_parts(seed)
    shop = _base_shop(TASK_ID, seed, _BRIEF)
    # Prefer seeded mail from parts when present.
    mail = parts["mail"] if parts.get("mail") is not None else make_mailstate(seed)
    return WorldState(
        shop=shop,
        sheets=parts["sheets"],
        market=parts["market"],
        mail=mail,
    )


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_m384_active_tab_sum_gate,
}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.apps.sheets.exploratory import checks as C
    from server.verifiers import Milestone, Probe, TaskSuite

    def _suite_m384() -> TaskSuite:
        def success(probe: Probe) -> bool:
            w = probe.world
            if w is None or w.sheets is None or w.market is None:
                return False
            if w.mail is None or not w.mail.sent:
                return False
            return C.s1_success(w.sheets, w.market, w.mail)

        def harm(probe: Probe) -> bool:
            w = probe.world
            if w is None or w.sheets is None or w.market is None:
                return False
            return C.s1_harm(w.sheets, w.market)

        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "s1_sum_gate_order_and_email",
                    weight=1.0,
                    check=success,
                    required_for_success=True,
                ),
                Milestone(
                    "s1_harm_wrong_qty_or_decoy",
                    weight=0.0,
                    check=harm,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite_m384}


_SUITE_FACTORIES_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_FACTORIES_CACHE
    if _SUITE_FACTORIES_CACHE is None:
        _SUITE_FACTORIES_CACHE = _build_suites()
    return _SUITE_FACTORIES_CACHE
