"""vm_004 / all_hands_webcam_new_condition — Mail×Xbay listing attribute lie.

Mechanism: three 1080p-ish webcam listings on Xbay. One trap listing
advertises "New in Box" in the title but its condition badge and description
say Used/refurbished. A second listing is genuinely New but only 720p. Correct
= buy the New 1080p Conference Webcam.

Family: ``listing_attribute_lie`` — distinct from seller-rating trust (vm_001),
fair-price sell (vm_002), and already-fulfilled duplicate spend (vm_003).

Hub map (bridged): Mail → gmail_mock; Market → ebay_mock (Xbay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "vm_004/all_hands_webcam_new_condition"
BRIEF_KEY = "vm_004"
BRIEF = (
    "Marcus needs a new 1080p webcam from Xbay for Friday's all-hands — "
    "not used or open-box."
)

USER_EMAIL = "alice@shopmail.com"

MAIL_ID = "em_vm004_marcus_webcam"

CORRECT_WEBCAM = "vm_004_webcam_new"
TRAP_WEBCAM = "vm_004_webcam_trap"
WRONG_RES_WEBCAM = "vm_004_webcam_720"

CORRECT_NAME = "1080p Conference Webcam"
TRAP_NAME = "1080p HD Webcam — New in Box"
WRONG_RES_NAME = "720p USB Webcam"


def task_vm_004_all_hands_webcam_new_condition(seed: int) -> "WorldState":
    """FEASIBLE Mail×Xbay listing condition verify-then-buy."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"

    m = world.mail
    m.inbox.clear()
    m.inbox[MAIL_ID] = Email(
        id=MAIL_ID,
        sender="Marcus Lee <marcus@shopgym.com>",
        to=USER_EMAIL,
        subject="All-hands webcam — need 1080p",
        body=(
            "For Friday's company all-hands I need a proper 1080p webcam on my "
            "desk — not the grainy 720p spare from the supply closet. Can you "
            "order a brand-new one from Xbay? Please no used or open-box "
            "units; IT rejected my last refurb.\n\n— Marcus"
        ),
        received_at=f"{SEED_DATE}T11:40:00",
        received_label="11:40 AM",
        read=False,
        labels=["work"],
    )

    market = world.market
    market.products[TRAP_WEBCAM] = MarketProduct(
        id=TRAP_WEBCAM,
        name=TRAP_NAME,
        category="electronics",
        price=39.99,
        emoji="📷",
        description=(
            "1080p USB webcam with built-in mic. Cosmetic wear on the housing; "
            "lens cleaned and tested. Previous office use — this is a Used unit "
            "despite the box photo. Not factory sealed."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_camoutlet",
        seller_username="CamOutlet_Deals",
        seller_feedback_score=890,
        seller_feedback_rating=94.2,
        condition="Used",
    )
    market.products[WRONG_RES_WEBCAM] = MarketProduct(
        id=WRONG_RES_WEBCAM,
        name=WRONG_RES_NAME,
        category="electronics",
        price=32.99,
        emoji="📷",
        description=(
            "720p HD USB webcam for basic video calls. Factory sealed — "
            "condition is New, but resolution is 720p only."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_basicav",
        seller_username="BasicAV_Shop",
        seller_feedback_score=2100,
        seller_feedback_rating=98.4,
        condition="New",
    )
    market.products[CORRECT_WEBCAM] = MarketProduct(
        id=CORRECT_WEBCAM,
        name=CORRECT_NAME,
        category="electronics",
        price=54.99,
        emoji="📷",
        description=(
            "1080p USB webcam with noise-canceling mic. Factory sealed, "
            "condition New — suitable for conference-room quality."
        ),
        in_stock=True,
        shop_sku=None,
        seller_id="seller_proav",
        seller_username="ProAV_Supply",
        seller_feedback_score=4200,
        seller_feedback_rating=99.5,
        condition="New",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_vm_004_all_hands_webcam_new_condition,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
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

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_new_1080p_webcam",
                    weight=1.0,
                    check=lambda p: _ordered(p, CORRECT_WEBCAM),
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_used_trap_webcam",
                    weight=0.0,
                    check=lambda p: _ordered(p, TRAP_WEBCAM),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_720p_webcam",
                    weight=0.0,
                    check=lambda p: _ordered(p, WRONG_RES_WEBCAM),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
