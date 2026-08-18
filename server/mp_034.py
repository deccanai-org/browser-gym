"""mp_034 / desk_chair_cross_hub_cheaper_or_faster — ShopGym×ValueMart.

Mechanism: compare ErgoDesk office chair landed cost (price + shipping) on
both hubs; totals within $5 → pick faster ship (ValueMart). Gaming decoy is
cheaper but wrong style.

UI-discoverability:
  - ShopGym PDP: ErgoDesk Pro Office Chair $180 + FREE delivery (5-day note)
  - ValueMart PDP: same model $175 + $18 ship (2-day ETA in description)
  - ValueMart RaceSeat Pro gaming chair cheaper total but gaming-style
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_034/desk_chair_cross_hub_cheaper_or_faster"
BRIEF_KEY = "mp_034"
BRIEF = (
    "I need a new desk chair, office-appropriate not gaming-style. Check both "
    "ValueMart and ShopGym for the same or equivalent model, compare total "
    "cost including shipping, and get it from whichever is actually cheaper. "
    "If they're within $5 of each other, go with whichever ships faster."
)

USER_EMAIL = "alice@shopmail.com"

SG_CHAIR = "p_mp034_ergodesk"
VM_CHAIR = "vm_mp034_ergodesk"
VM_GAMING = "vm_mp034_raceseat"

# ShopGym: $180 + $0 ship = $180, ships in ~5 days
# ValueMart: $175 + $18 = $193… wait CAND had VM cheaper total within $5.
# CAND: SG 180+15=195, VM 175+18=193 → within $5, VM faster (2 vs 5 days).
# Use that: ShopGym shipping shown as $15 "standard" via non-prime? But ShopGym
# projects all as FREE Prime delivery. Encode ShopGym landed as base_price that
# already reflects sticker, and put shipping fee in short_description as
# "Standard shipping $15 (5 business days)" while still charging 180 at checkout
# — that breaks compare honesty.
#
# Better: ShopGym price 195 with free ship (5 days); ValueMart 175+18=193 (2 days).
# Or stick to CAND numbers with shop base 180 and a $15 shipping product note
# that agents must add mentally — fragile.
#
# Practical bridge-honest design:
#   ShopGym: base_price=195.00, Prime free ship, description "Ships in 5 business days"
#   ValueMart: price=175, shipping_cost=18 → 193, description "Ships in 2 business days"
#   Within $5 → ValueMart wins on speed.
#   Gaming: 160+0=160 cheaper but forbidden style.


def task_mp_034_desk_chair_cross_hub_cheaper_or_faster(seed: int) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.products[SG_CHAIR] = Product(
        id=SG_CHAIR,
        name="ErgoDesk Pro Office Chair",
        brand="ErgoDesk",
        category="home",
        base_price=195.00,
        rating=4.6,
        review_count=980,
        stock=25,
        image_emoji="🪑",
        short_description=(
            "Office mesh desk chair (not gaming). FREE delivery. "
            "Estimated delivery: 5 business days."
        ),
        tags=["office", "desk-chair"],
    )

    market = world.market
    market.products[VM_CHAIR] = MarketProduct(
        id=VM_CHAIR,
        name="ErgoDesk Pro Office Chair",
        category="home",
        price=175.00,
        emoji="🪑",
        description=(
            "Same ErgoDesk Pro office chair. Shipping $18.00 "
            "(landed total $193.00). Estimated delivery: 2 business days — "
            "faster than ShopGym's 5-day free delivery on the $195 listing."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=18.00,
        brand="ErgoDesk",
        shop_sku=SG_CHAIR,
        seller_username="OfficeSupply_HQ",
        seller_feedback_score=4200,
        seller_feedback_rating=99.1,
    )
    market.products[VM_GAMING] = MarketProduct(
        id=VM_GAMING,
        name="RaceSeat Pro Gaming Chair",
        category="home",
        price=160.00,
        emoji="🎮",
        description=(
            "Racing-style gaming chair with RGB. Free shipping. Ships in 1 day. "
            "Cheaper total than ErgoDesk — but gaming-style, not office-appropriate."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
        brand="RaceSeat",
        seller_username="GameGear_Mart",
        seller_feedback_score=2100,
        seller_feedback_rating=97.5,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_034_desk_chair_cross_hub_cheaper_or_faster,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_shop(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return []
        init = (p.initial_world.shop.orders if p.initial_world and p.initial_world.shop else {}) or {}
        return [o for oid, o in (shop.orders or {}).items() if oid not in init]

    def _new_market(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if not market:
            return []
        init = (
            p.initial_world.market.orders
            if p.initial_world and p.initial_world.market
            else {}
        ) or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _bought_shop_chair(p: Probe) -> bool:
        for o in _new_shop(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == SG_CHAIR:
                    return True
        return False

    def _bought_vm_chair(p: Probe) -> bool:
        for o in _new_market(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == VM_CHAIR:
                    return True
        return False

    def _bought_gaming(p: Probe) -> bool:
        for o in _new_market(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == VM_GAMING:
                    return True
        return False

    def _ordered_correct(p: Probe) -> bool:
        # Within-$5 + faster → ValueMart ErgoDesk.
        return _bought_vm_chair(p) and not _bought_shop_chair(p) and not _bought_gaming(p)

    def _office_not_gaming(p: Probe) -> bool:
        if _bought_gaming(p):
            return False
        return _bought_vm_chair(p) or _bought_shop_chair(p)

    def _compare_evidence(p: Probe) -> bool:
        """Require agent-sent note OR both hubs inspected via action log.

        Durable compare signal: alice email mentioning both stores' totals, OR
        simply that the correct ValueMart order was placed (oracle path emails
        the compare). Prefer mail evidence when present; else accept correct buy
        only if shop chair was NOT also bought (implies a choice was made).
        """
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail:
            for se in (mail.sent or {}).values():
                body = f"{se.subject or ''}\n{se.body or ''}".lower()
                if ("shopgym" in body or "shop gym" in body or "amazon" in body) and (
                    "valuemart" in body or "value mart" in body or "ebay" in body
                ):
                    if any(x in body for x in ("193", "195", "shipping", "total", "faster", "within")):
                        return True
        # Fallback: correct exclusive VM purchase counts as compare outcome.
        return _ordered_correct(p)

    def _without_compare(p: Probe) -> bool:
        # Shortcut: buy gaming (cheapest look) or buy ShopGym without VM win.
        if _bought_gaming(p):
            return True
        if _bought_shop_chair(p) and not _bought_vm_chair(p):
            return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "compared_landed_cost_both_stores",
                    weight=0.3,
                    check=_compare_evidence,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_cheaper_or_tiebreak_faster",
                    weight=0.5,
                    check=_ordered_correct,
                    required_for_success=True,
                ),
                Milestone(
                    "office_not_gaming_style",
                    weight=0.2,
                    check=_office_not_gaming,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_without_cross_shop_compare",
                    weight=0.0,
                    check=_without_compare,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_gaming_style",
                    weight=0.0,
                    check=_bought_gaming,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
