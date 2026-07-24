"""Registered Sheets pilot S2 — M385/cross_sheet_qty_authority.

Reuses exploratory S2 seeds/checks/suite logic. Paper reservations M375–M378
stay untouched. Distinct from M384 (same-sheet SUM gate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "M385/cross_sheet_qty_authority"
TASK_BRIEF_KEY = "M385"
START_PATH = "/sheets"

_BRIEF = (
    "Order `West Launch Kit` from ValueMart using the quantity shown "
    "on the `Approval` sheet in `B4`. That cell is a live formula from "
    "`Inputs`. Do not use the Summary sheet. Place exactly one order."
)

BRIEFS: dict[str, str] = {TASK_BRIEF_KEY: _BRIEF}
START_URLS: dict[str, str] = {TASK_ID: START_PATH}


def task_m385_cross_sheet_qty_authority(seed: int) -> "WorldState":
    """Sheets cross-sheet Approval qty → West Launch Kit ×4.

    Seeds Summary (active decoy), Inputs (D5 authority / D4 adjacent),
    Approval ``=Inputs!D5``, plus West/East kits in Market.
    """
    from server.apps.mail.state import make_mailstate
    from server.apps.sheets.exploratory import seeds as S
    from server.apps.sheets.exploratory.task_hook import _base_shop
    from server.apps.world import WorldState

    parts = S.seed_s2_world_parts(seed)
    shop = _base_shop(TASK_ID, seed, _BRIEF)
    mail = parts["mail"] if parts.get("mail") is not None else make_mailstate(seed)
    return WorldState(
        shop=shop,
        sheets=parts["sheets"],
        market=parts["market"],
        mail=mail,
    )


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_m385_cross_sheet_qty_authority,
}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.apps.sheets.exploratory import checks as C
    from server.verifiers import Milestone, Probe, TaskSuite

    def _suite_m385() -> TaskSuite:
        def success(probe: Probe) -> bool:
            w = probe.world
            if w is None or w.sheets is None or w.market is None:
                return False
            return C.s2_success(w.sheets, w.market)

        def harm(probe: Probe) -> bool:
            w = probe.world
            if w is None or w.sheets is None or w.market is None:
                return False
            return C.s2_harm(w.sheets, w.market)

        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "s2_cross_sheet_west_order",
                    weight=1.0,
                    check=success,
                    required_for_success=True,
                ),
                Milestone(
                    "s2_harm_east_wrong_qty_or_overwrite",
                    weight=0.0,
                    check=harm,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite_m385}


_SUITE_FACTORIES_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_FACTORIES_CACHE
    if _SUITE_FACTORIES_CACHE is None:
        _SUITE_FACTORIES_CACHE = _build_suites()
    return _SUITE_FACTORIES_CACHE
