"""Exploratory S1–S3 task hooks — NOT registered in server/tasks.py TASKS/BRIEFS.

Enables oracle runner wiring (reset + verifier suite) without sellable
cascade registration. Documented as temporary exploratory scaffolding.

Task ids:
  ``exploratory/S1_active_tab_sum_gate``
  ``exploratory/S2_cross_sheet_qty_authority``
  ``exploratory/S3_writeback_if_complete``
Start path: ``/sheets`` for all three.
"""

from __future__ import annotations

from typing import Any

from server import catalog
from server.apps.mail.state import make_mailstate
from server.apps.sheets.exploratory import checks as C
from server.apps.sheets.exploratory import seeds as S
from server.apps.world import WorldState
from server.state import (
    Address,
    GymState,
    PaymentMethod,
    User,
)
from server.verifiers import Milestone, Probe, TaskSuite

EXPLORATORY_S1_ID = "exploratory/S1_active_tab_sum_gate"
EXPLORATORY_S2_ID = "exploratory/S2_cross_sheet_qty_authority"
EXPLORATORY_S3_ID = "exploratory/S3_writeback_if_complete"
EXPLORATORY_S1_START_PATH = "/sheets"
EXPLORATORY_S2_START_PATH = "/sheets"
EXPLORATORY_S3_START_PATH = "/sheets"

# Explicit allowlist — do not auto-register sellables.
EXPLORATORY_TASK_IDS = frozenset({
    EXPLORATORY_S1_ID,
    EXPLORATORY_S2_ID,
    EXPLORATORY_S3_ID,
})

_S3_EVENT_ID = "cal_vendor_review"


def _alice() -> User:
    u = User(
        id="u_alice", email="alice@example.com",
        password="password123", full_name="Alice Anderson",
        loyalty_tier="gold",
    )
    u.addresses["addr_home"] = Address(
        id="addr_home", label="Home", full_name="Alice Anderson",
        line1="100 Park Avenue", line2="Apt 4B",
        city="Brooklyn", state="NY", zip="11201", is_default=True,
    )
    u.payment_methods["pay_visa"] = PaymentMethod(
        id="pay_visa", label="Visa ****4242",
        kind="credit_card", expires="08/27", is_default=True,
    )
    return u


def _base_shop(task_id: str, seed: int, prompt: str) -> GymState:
    shop = GymState(
        task_id=task_id,
        seed=seed,
        task_brief=prompt,
        task_difficulty="medium",  # type: ignore[arg-type]
        task_category="M",  # type: ignore[arg-type]
    )
    shop.products = catalog._build_catalog()
    shop.users = {"u_alice": _alice()}
    shop.current_user_id = "u_alice"
    return shop


def make_exploratory_s1_world(seed: int = 0) -> WorldState:
    """World factory for exploratory S1 — sheets + market + mail seeds."""
    parts = S.seed_s1_world_parts(seed)
    return WorldState(
        shop=_base_shop(EXPLORATORY_S1_ID, seed, parts["prompt"]),
        sheets=parts["sheets"],
        market=parts["market"],
        mail=parts["mail"] if parts.get("mail") is not None else make_mailstate(seed),
    )


def make_exploratory_s2_world(seed: int = 0) -> WorldState:
    """World factory for exploratory S2 — cross-sheet Approval qty + market."""
    parts = S.seed_s2_world_parts(seed)
    return WorldState(
        shop=_base_shop(EXPLORATORY_S2_ID, seed, parts["prompt"]),
        sheets=parts["sheets"],
        market=parts["market"],
        mail=parts["mail"] if parts.get("mail") is not None else make_mailstate(seed),
    )


def make_exploratory_s3_world(seed: int = 0) -> WorldState:
    """World factory for exploratory S3 — IF writeback + calendar + mail."""
    parts = S.seed_s3_world_parts(seed)
    return WorldState(
        shop=_base_shop(EXPLORATORY_S3_ID, seed, parts["prompt"]),
        sheets=parts["sheets"],
        mail=parts["mail"] if parts.get("mail") is not None else make_mailstate(seed),
        calendar=parts.get("calendar"),
    )


def _suite_exploratory_s1() -> TaskSuite:
    """Single success milestone mirrors exploratory ``s1_success`` (+ require mail)."""

    def success(probe: Probe) -> bool:
        w = probe.world
        if w is None or w.sheets is None or w.market is None:
            return False
        # Require confirmation email for oracle/eval gate (prompt asks for it).
        if w.mail is None or not w.mail.sent:
            return False
        return C.s1_success(w.sheets, w.market, w.mail)

    def harm(probe: Probe) -> bool:
        w = probe.world
        if w is None or w.sheets is None or w.market is None:
            return False
        return C.s1_harm(w.sheets, w.market)

    return TaskSuite(
        task_id=EXPLORATORY_S1_ID,
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


def _suite_exploratory_s2() -> TaskSuite:
    """Success: West×4 from live Approval!B4; harm: East / wrong qty / formula overwrite."""

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
        task_id=EXPLORATORY_S2_ID,
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


def _suite_exploratory_s3() -> TaskSuite:
    """Success: Final!F21 writeback → G21 Complete → mail C21 time."""

    def success(probe: Probe) -> bool:
        w = probe.world
        if w is None or w.sheets is None or w.mail is None:
            return False
        return C.s3_success(w.sheets, w.mail, event_id=_S3_EVENT_ID)

    def harm(probe: Probe) -> bool:
        w = probe.world
        if w is None or w.sheets is None or w.mail is None:
            return False
        return C.s3_harm(w.sheets, w.mail)

    return TaskSuite(
        task_id=EXPLORATORY_S3_ID,
        milestones=[
            Milestone(
                "s3_writeback_if_then_mail",
                weight=1.0,
                check=success,
                required_for_success=True,
            ),
            Milestone(
                "s3_harm_draft_adjacent_or_early_mail",
                weight=0.0,
                check=harm,
                forbidden=True,
            ),
        ],
    )


def is_exploratory_task(task_id: str) -> bool:
    return task_id in EXPLORATORY_TASK_IDS


def make_exploratory_task(task_id: str, seed: int) -> WorldState:
    if task_id == EXPLORATORY_S1_ID:
        return make_exploratory_s1_world(seed)
    if task_id == EXPLORATORY_S2_ID:
        return make_exploratory_s2_world(seed)
    if task_id == EXPLORATORY_S3_ID:
        return make_exploratory_s3_world(seed)
    raise KeyError(f"unknown exploratory task: {task_id}")


def build_exploratory_suite(task_id: str) -> TaskSuite:
    if task_id == EXPLORATORY_S1_ID:
        return _suite_exploratory_s1()
    if task_id == EXPLORATORY_S2_ID:
        return _suite_exploratory_s2()
    if task_id == EXPLORATORY_S3_ID:
        return _suite_exploratory_s3()
    raise KeyError(f"unknown exploratory task: {task_id}")


def exploratory_start_path(task_id: str) -> str:
    if task_id == EXPLORATORY_S1_ID:
        return EXPLORATORY_S1_START_PATH
    if task_id == EXPLORATORY_S2_ID:
        return EXPLORATORY_S2_START_PATH
    if task_id == EXPLORATORY_S3_ID:
        return EXPLORATORY_S3_START_PATH
    return "/"


def exploratory_reset_meta(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "start_path": exploratory_start_path(task_id),
        "exploratory": True,
    }
