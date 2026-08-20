"""whiteboard_001 / whiteboard_max_fit_dimension — Mail×Xbay.

Mechanism: office room dimensions live in Mail. Xbay lists 3–4
whiteboards of different sizes. Correct = largest board that still fits
(both width and height ≤ room). Trap = largest overall (too big) OR any
smaller board that fits but is not maximal.

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (Xbay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "whiteboard_001/whiteboard_max_fit_dimension"
BRIEF_KEY = "whiteboard_001"
BRIEF = (
    "I need a whiteboard for the office, but check the room dimensions in "
    "Mail before ordering one from Xbay. Get the largest one that fits."
)

USER_EMAIL = "alice@shopmail.com"

# Usable wall: 48" W × 36" H
ROOM_W = 48
ROOM_H = 36
MAIL_ID = "em_wb001_room_dims"

# (id, name, W, H, price) — correct = 48×36 (exact fit, largest that fits)
WB_SMALL = "vm_wb001_36x24"      # fits, not largest
WB_MID = "vm_wb001_42x30"        # fits, not largest
WB_CORRECT = "vm_wb001_48x36"    # largest that fits
WB_TOO_BIG = "vm_wb001_60x40"    # largest overall — does NOT fit

WB_SPECS = {
    WB_SMALL: (36, 24, 29.99, "36×24 Magnetic Whiteboard"),
    WB_MID: (42, 30, 44.99, "42×30 Magnetic Whiteboard"),
    WB_CORRECT: (48, 36, 59.99, "48×36 Magnetic Whiteboard"),
    WB_TOO_BIG: (60, 40, 79.99, "60×40 Magnetic Whiteboard"),
}


def task_whiteboard_001_whiteboard_max_fit_dimension(seed: int) -> "WorldState":
    """FEASIBLE Mail×Xbay max-fit dimension buy.

    Seed:
      - Mail: usable wall 48\" wide × 36\" tall
      - Xbay: 36×24, 42×30, 48×36 (correct), 60×40 (too big)

    Correct: order 48×36. Forbidden: 60×40 (or only a smaller fit).
    """
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.market.store_name = "Xbay"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_ID] = Email(
        id=MAIL_ID,
        sender="Facilities <facilities@shopgym.com>",
        to=USER_EMAIL,
        subject="Huddle room B — wall measurements for whiteboard",
        body=(
            "Alice — measured huddle room B for you.\n\n"
            f"Usable wall space for a mounted whiteboard: {ROOM_W}\" wide by "
            f"{ROOM_H}\" tall (do not exceed either dimension — pipes and a "
            "thermostat block anything larger).\n\n"
            "Grab the biggest board that still fits those limits.\n\n"
            "— Facilities"
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=False,
        labels=["work"],
    )
    m.inbox["em_wb001_nudge"] = Email(
        id="em_wb001_nudge",
        sender="Jordan <jordan@shopgym.com>",
        to=USER_EMAIL,
        subject="Whiteboard?",
        body=(
            "Whenever you get to it — we really need a whiteboard in huddle B. "
            "Facilities sent you the wall numbers.\n\n— Jordan"
        ),
        received_at=f"{SEED_DATE}T11:40:00",
        received_label="11:40 AM",
        read=False,
        labels=["team"],
    )

    market = world.market
    for pid, (w, h, price, name) in WB_SPECS.items():
        fits = w <= ROOM_W and h <= ROOM_H
        market.products[pid] = MarketProduct(
            id=pid,
            name=name,
            category="home",
            price=price,
            emoji="⬜",
            description=(
                f"Magnetic dry-erase whiteboard, {w} inches wide by {h} inches "
                f"tall ({w}×{h}). "
                + (
                    "Fits a 48×36 wall."
                    if fits
                    else "Large format — needs more than 48×36 of clear wall."
                )
            ),
            in_stock=True,
            shop_sku=None,
            seller_id="seller_officeboards",
            seller_username="OfficeBoards_HQ",
            seller_feedback_score=3200,
            seller_feedback_rating=98.9,
        )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_whiteboard_001_whiteboard_max_fit_dimension,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "market", None):
            init = p.initial_world.market.orders or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _ordered(p: Probe, pid: str) -> bool:
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _ordered_undersized_only(p: Probe) -> bool:
        """BREAK soft path: bought a fitting but non-maximal board and not the correct one."""
        if _ordered(p, WB_CORRECT) or _ordered(p, WB_TOO_BIG):
            return False
        return _ordered(p, WB_SMALL) or _ordered(p, WB_MID)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_largest_fitting_48x36",
                    weight=1.0,
                    check=lambda p: _ordered(p, WB_CORRECT),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_oversized_60x40",
                    weight=0.0,
                    check=lambda p: _ordered(p, WB_TOO_BIG),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_undersized_not_maximal",
                    weight=0.0,
                    check=_ordered_undersized_only,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}


_SUITE_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_CACHE
    if _SUITE_CACHE is None:
        _SUITE_CACHE = _build_suites()
    return _SUITE_CACHE
