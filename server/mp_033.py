"""mp_033 / deals_kitchen_and_vm_wrong_item — Xmazon×Xbay×Xmail.

Mechanism: mom emailed a kitchen shopping list (knife set, spatula set, and
ceramic mixing bowl) — agent must read that mail. Cover her requested items
via Xmazon's deals surface (matching gold deals, including the bowl — not
decoys). Separately, last week's Xbay order arrived as a spoon (wrong
item vs the Ceramic Mixing Bowl that was ordered) — email support for a
refund/return naming the spoon. Notify alice once both are handled.

UI-discoverability:
  - Xmail inbox: mom's request lists knife set + spatula + ceramic bowl
  - Xmazon header /search?deals=true — gold deals match mom's list (incl bowl)
  - Xbay Dashboard purchase history (VM-4401 Ceramic Mixing Bowl)
  - Xmail: delivery note shows Wooden Spoon arrived
  - Xbay returns are decorative — durable path is mail to support
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_033/deals_kitchen_and_vm_wrong_item"
BRIEF_KEY = "mp_033"
BRIEF = (
    "I got an email from my mom asking me to buy her some items but the "
    "Xbay order from last week was completely wrong so I need you to "
    "refund that because they gave me a spoon. Then look through the new "
    "deal section of Xmazon and make sure the items she requested are "
    "covered including the bowl. Email me once its handled"
)

USER_EMAIL = "alice@shopmail.com"
MOM_EMAIL = "mom@family.example.com"
MOM_EMAIL_ID = "em_mp033_mom_list"
VM_SUPPORT = "support@valuemart.example.com"

# Mom's list (discoverable only via her email) → matching Xmazon deals
GOLD_KNIFE = "p_mp033_knife_set"
GOLD_SPATULA = "p_mp033_spatula_set"
GOLD_BOWL = "p_mp033_ceramic_bowl"
GOLD_DEALS = (GOLD_KNIFE, GOLD_SPATULA, GOLD_BOWL)

TRAP_CHEAP = "p_mp033_plastic_ladle"
TRAP_NON_KITCHEN = "p_mp033_bt_speaker"
TRAP_WRONG_KITCHEN = "p_mp033_whisk_set"  # kitchen deal, not on mom's list
TRAP_DEALS = (TRAP_CHEAP, TRAP_NON_KITCHEN, TRAP_WRONG_KITCHEN)

VM_ORDER = "VM-4401"
VM_ORDERED_SKU = "vm_mp033_mixing_bowl"
VM_ORDERED_NAME = "Ceramic Mixing Bowl"
VM_WRONG_NAME = "Wooden Spoon"

SPOON_TOKS = (
    "wooden spoon",
    "wood spoon",
    "spoon",
)
WRONG_ITEM_TOKS = (
    "wrong item",
    "wrong-item",
    "incorrect item",
    "not what i ordered",
    "not what i bought",
    "different item",
    "instead of",
    *SPOON_TOKS,
)
DAMAGED_ONLY_TOKS = (
    "damaged",
    "broken",
    "defective",
    "arrived broken",
)
NOTIFY_MOM_TOKS = (
    "mom",
    "knife",
    "spatula",
    "bowl",
    "deal",
    "covered",
    "requested",
)
NOTIFY_VM_TOKS = (
    "valuemart",
    "wrong",
    "spoon",
    "support",
    "refund",
    "sorted",
    "handled",
    "mixing bowl",
)


def task_mp_033_deals_kitchen_and_vm_wrong_item(seed: int) -> "WorldState":
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketCartItem, MarketOrder, MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.products[GOLD_KNIFE] = Product(
        id=GOLD_KNIFE,
        name="ProChef 8-Piece Knife Set",
        brand="ProChef",
        category="kitchen",
        base_price=29.99,
        rating=4.7,
        review_count=2140,
        stock=40,
        image_emoji="🔪",
        short_description="8-piece knife set on deal — matches mom's request.",
        tags=["was_price:59.99", "deal"],
    )
    shop.products[GOLD_SPATULA] = Product(
        id=GOLD_SPATULA,
        name="FlexiGrip Silicone Spatula Set",
        brand="FlexiGrip",
        category="kitchen",
        base_price=12.99,
        rating=4.6,
        review_count=980,
        stock=60,
        image_emoji="🍳",
        short_description="Silicone spatula set on deal — matches mom's request.",
        tags=["was_price:24.99", "deal"],
    )
    shop.products[GOLD_BOWL] = Product(
        id=GOLD_BOWL,
        name="HomeBake Ceramic Mixing Bowl",
        brand="HomeBake",
        category="kitchen",
        base_price=16.99,
        rating=4.8,
        review_count=1520,
        stock=45,
        image_emoji="🥣",
        short_description="Ceramic mixing bowl on deal — matches mom's request.",
        tags=["was_price:32.99", "deal"],
    )
    shop.products[TRAP_CHEAP] = Product(
        id=TRAP_CHEAP,
        name="Budget Plastic Ladle",
        brand="ValueWare",
        category="kitchen",
        base_price=3.99,
        rating=2.1,
        review_count=88,
        stock=200,
        image_emoji="🥄",
        short_description="Cheap kitchen deal — not on mom's list.",
        tags=["was_price:9.99", "deal"],
    )
    shop.products[TRAP_NON_KITCHEN] = Product(
        id=TRAP_NON_KITCHEN,
        name="Pocket Bluetooth Speaker",
        brand="SoundBit",
        category="electronics",
        base_price=19.99,
        rating=4.9,
        review_count=5200,
        stock=90,
        image_emoji="🔊",
        short_description="High-rated deal but not kitchen and not on mom's list.",
        tags=["was_price:39.99", "deal"],
    )
    shop.products[TRAP_WRONG_KITCHEN] = Product(
        id=TRAP_WRONG_KITCHEN,
        name="Balloon Whisk Duo",
        brand="BakeLite",
        category="kitchen",
        base_price=8.99,
        rating=4.5,
        review_count=640,
        stock=75,
        image_emoji="🍥",
        short_description="Kitchen deal decoy — whisks, not what mom asked for.",
        tags=["was_price:16.99", "deal"],
    )

    market = world.market
    market.products[VM_ORDERED_SKU] = MarketProduct(
        id=VM_ORDERED_SKU,
        name=VM_ORDERED_NAME,
        category="home",
        price=18.50,
        emoji="🥣",
        description=(
            f"{VM_ORDERED_NAME} (what you ordered). Delivery photo / packing "
            f"slip mismatch: customer received a {VM_WRONG_NAME} instead."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
        brand="HomeChef",
    )
    market.orders[VM_ORDER] = MarketOrder(
        id=VM_ORDER,
        items=[
            MarketCartItem(
                product_id=VM_ORDERED_SKU,
                name=VM_ORDERED_NAME,
                unit_price=18.50,
                quantity=1,
            )
        ],
        subtotal=18.50,
        discount=0.0,
        delivery_fee=0.0,
        total=18.50,
        placed_at="2026-05-14T15:20:00",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MOM_EMAIL_ID] = Email(
        id=MOM_EMAIL_ID,
        sender=MOM_EMAIL,
        to=USER_EMAIL,
        subject="Can you grab a few kitchen things for me?",
        body=(
            "Hi Sweetie, When you get the chance could you pick up an "
            "8-piece knife set, a silicone spatula set, and a ceramic "
            "mixing bowl for me. Thank you! Love, Mom"
        ),
        received_at="2026-05-20T09:15:00",
        received_label="Yesterday",
        read=False,
        labels=["personal"],
    )
    mail.inbox["em_mp033_vm_delivery"] = Email(
        id="em_mp033_vm_delivery",
        sender="orders@valuemart.example.com",
        to=USER_EMAIL,
        subject=f"Delivered: {VM_ORDER}",
        body=(
            f"Your Xbay order {VM_ORDER} was marked delivered yesterday.\n\n"
            f"Ordered: {VM_ORDERED_NAME}\n"
            f"Carrier scan / photo label: {VM_WRONG_NAME}\n\n"
            "If this isn't what you ordered, contact support@valuemart.example.com "
            "and describe the problem (wrong item vs damaged)."
        ),
        received_at="2026-05-20T11:00:00",
        received_label="Yesterday",
        read=False,
        labels=["purchases"],
        order_id=VM_ORDER,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_033_deals_kitchen_and_vm_wrong_item,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_shop_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for oid, o in (shop.orders or {}).items() if oid not in init]

    def _ordered_product(p: Probe, pid: str) -> bool:
        for o in _new_shop_orders(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _mom_items_covered(p: Probe) -> bool:
        """All deals matching mom's emailed list must be ordered (incl. bowl)."""
        return all(_ordered_product(p, pid) for pid in GOLD_DEALS)

    def _non_matching_deal(p: Probe) -> bool:
        return any(_ordered_product(p, pid) for pid in TRAP_DEALS)

    def _wrong_item_support(p: Probe) -> bool:
        """Support mail must mention spoon AND the actual ordered item."""
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            dest = f"{se.to or ''} {getattr(se, 'cc', '') or ''} {getattr(se, 'bcc', '') or ''}".lower()
            if "valuemart" not in dest and VM_SUPPORT not in dest:
                if "valuemart" not in (se.to or "").lower():
                    continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            has_spoon = any(t in body for t in SPOON_TOKS)
            has_ordered = (
                "mixing bowl" in body
                or VM_ORDERED_NAME.lower() in body
                or VM_ORDER.lower() in body
            )
            has_wrong = any(t in body for t in WRONG_ITEM_TOKS)
            if has_spoon and has_ordered and has_wrong:
                return True
        return False

    def _damaged_not_wrong(p: Probe) -> bool:
        """Forbidden: framed as damaged/defective without wrong-item language."""
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            dest = f"{se.to or ''}".lower()
            if "valuemart" not in dest and VM_SUPPORT.split("@")[0] not in dest:
                continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            has_damage = any(t in body for t in DAMAGED_ONLY_TOKS)
            has_wrong = any(t in body for t in WRONG_ITEM_TOKS)
            if has_damage and not has_wrong:
                return True
        return False

    def _user_notified(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            if USER_EMAIL not in (se.to or "").lower():
                continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            mom_hits = sum(1 for t in NOTIFY_MOM_TOKS if t in body)
            vm_hits = sum(1 for t in NOTIFY_VM_TOKS if t in body)
            if mom_hits >= 2 and vm_hits >= 2:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "mom_requested_items_covered_via_deals",
                    weight=0.4,
                    check=_mom_items_covered,
                    required_for_success=True,
                ),
                Milestone(
                    "valuemart_wrong_item_return_started",
                    weight=0.4,
                    check=_wrong_item_support,
                    required_for_success=True,
                ),
                Milestone(
                    "user_notified_both_done",
                    weight=0.2,
                    check=_user_notified,
                    required_for_success=True,
                ),
                Milestone(
                    "treated_as_damaged_not_wrong_item",
                    weight=0.0,
                    check=_damaged_not_wrong,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_non_matching_deal",
                    weight=0.0,
                    check=_non_matching_deal,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
