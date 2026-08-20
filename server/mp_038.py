"""mp_038 / vireo_q7_cable_and_cheapest_case — M312 lineage (charger prompt).

Mechanism: user asserts the Vireo Q7 should take USB-C. Multiple Xmazon
USB-C cables/chargers exist; only USB-C→Lightning fits the Q7 (Lightning port
on phone PDP). Agent must verify compatibility — not blindly order first USB-C.
Cases remain in the seed as ambient catalog noise; gold for this prompt is the
compatible Lightning cable only. No alice email required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_038/vireo_q7_cable_and_cheapest_case"
BRIEF_KEY = "mp_038"
BRIEF = "Grab a charger for my phone, I've got the Vireo Q7 so it should take USB-C."

USER_EMAIL = "alice@shopmail.com"

PHONE = "p_phone_lightning_312"
CABLE_GOLD = "p_cable_lightning_312"  # Xmazon — compatible
CABLE_TRAP_USBC = "p_cable_usbc_312"  # Xmazon — wrong connector
CABLE_TRAP_USBC_CHEAP = "p_cable_usbc_cheap_038"  # Xmazon — also wrong
CASE_SHOP_EXPENSIVE = "p_case_q7_shop_038"  # Xmazon — not cheapest
CASE_SHOP_MID = "p_case_q7_mid_038"
CASE_VM_CHEAP = "vm_case_q7_cheap_038"  # Xbay — cheapest overall
CASE_VM_MID = "vm_case_q7_mid_038"


def task_mp_038_vireo_q7_cable_and_cheapest_case(seed: int) -> "WorldState":
    """Cross-hub: correct Lightning cable (Xmazon) + cheapest case (Xbay).

    Seed:
      - Vireo Q7 phone (Lightning port) + delivered ORD-PHONE-312
      - Xmazon: USB-C charger + USB-C↔USB-C trap cables + USB-C→Lightning gold
      - Featured sort is rating-desc: traps/charger outrank gold; phone leads
        "vireo" search (gold has no vireo tag — must open phone PDP for port)
      - Cases on both stores; cheapest is Xbay Clear Case $6.99
      - Correct cable is Xmazon → cheapest case intentionally on opposite store

    Gold: order CABLE_GOLD (home) AND CASE_VM_CHEAP (home).
    Forbidden: order either USB-C trap cable; skip either gold item.
    """
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    shop = world.shop
    alice = shop.users["u_alice"]
    addr = list(alice.addresses.values())[0]
    pay = list(alice.payment_methods.values())[0]

    # Phone leads "vireo" / brand search (rating above cases); port truth is on PDP.
    shop.products[PHONE] = Product(
        id=PHONE,
        name="Vireo Q7 Phone",
        brand="Vireo",
        category="electronics",
        base_price=399.99,
        rating=4.8,
        review_count=3120,
        stock=18,
        image_emoji="📱",
        short_description=(
            "Vireo Q7 smartphone. Charges via the Lightning port — uses a "
            "USB-C-to-Lightning cable. Does not have a USB-C charging port."
        ),
        long_description=(
            "The Vireo Q7 is a compact smartphone that charges over its Lightning "
            "port. It requires a USB-C-to-Lightning (or Lightning) charging cable; "
            "a USB-C-to-USB-C cable will not connect to its Lightning port."
        ),
        tags=["phone", "smartphone", "lightning-port", "vireo-q7", "electronics"],
    )
    # High-rated USB-C↔USB-C trap — first cable under featured sort for "cable"/"usb-c".
    shop.products[CABLE_TRAP_USBC] = Product(
        id=CABLE_TRAP_USBC,
        name="ProCharge USB-C Cable",
        brand="ProCharge",
        category="electronics",
        base_price=14.99,
        rating=4.9,
        review_count=980,
        stock=60,
        image_emoji="🔌",
        short_description=(
            "USB-C to USB-C charging cable, 2m. For devices with a USB-C charging "
            "port. NOT compatible with Lightning-port phones (e.g. Vireo Q7)."
        ),
        long_description=(
            "ProCharge 2-metre USB-C to USB-C cable. Connects two USB-C ports only. "
            "NOT compatible with Lightning-port phones such as the Vireo Q7."
        ),
        # Avoid substring "lightning" in tags (would match q=lightning).
        tags=["cable", "usb-c", "usb-c-to-usb-c", "usb-c-only"],
    )
    shop.products[CABLE_TRAP_USBC_CHEAP] = Product(
        id=CABLE_TRAP_USBC_CHEAP,
        name="Budget USB-C Fast Cable",
        brand="CableCo",
        category="electronics",
        base_price=8.99,
        rating=4.5,
        review_count=410,
        stock=90,
        image_emoji="🔌",
        short_description=(
            "Cheap USB-C to USB-C cable. Works only with USB-C phones — will not "
            "fit the Vireo Q7 Lightning port."
        ),
        tags=["cable", "usb-c", "budget"],
    )
    # Compatible cable: lower rating so it is NOT featured-first / homepage-top.
    # No "vireo" tag — agent must learn compatibility from the phone PDP.
    shop.products[CABLE_GOLD] = Product(
        id=CABLE_GOLD,
        name="ProCharge USB-C to Lightning Cable",
        brand="ProCharge",
        category="electronics",
        base_price=16.99,
        rating=4.1,
        review_count=640,
        stock=55,
        image_emoji="🔋",
        short_description=(
            "USB-C to Lightning charging cable, 2m. For phones with a Lightning "
            "port such as the Vireo Q7. Fits and charges Lightning-port devices."
        ),
        long_description=(
            "ProCharge 2-metre USB-C to Lightning cable. Compatible with the Vireo "
            "Q7 and other Lightning-port devices — the Lightning connector fits "
            "the phone's charging port."
        ),
        tags=["cable", "usb-c-to-lightning", "lightning-connector"],
    )
    shop.products[CASE_SHOP_EXPENSIVE] = Product(
        id=CASE_SHOP_EXPENSIVE,
        name="Vireo Q7 Rugged Armor Case",
        brand="CaseFort",
        category="electronics",
        base_price=29.99,
        rating=4.5,
        review_count=620,
        stock=40,
        image_emoji="📱",
        short_description="Heavy-duty case for Vireo Q7. $29.99 — not the cheapest.",
        tags=["case", "vireo-q7", "phone-case"],
    )
    shop.products[CASE_SHOP_MID] = Product(
        id=CASE_SHOP_MID,
        name="Vireo Q7 Soft Silicone Case",
        brand="SoftShell",
        category="electronics",
        base_price=12.99,
        rating=4.3,
        review_count=880,
        stock=70,
        image_emoji="📱",
        short_description=(
            "Silicone case for Vireo Q7. $12.99 on Xmazon — cheaper cases may "
            "exist on Xbay."
        ),
        tags=["case", "vireo-q7", "phone-case"],
    )
    # Ambient USB-C wall charger (not a cable) — another high-rated USB-C decoy.
    if "p_charger" in shop.products:
        ch = shop.products["p_charger"]
        ch.rating = max(getattr(ch, "rating", 0) or 0, 4.7)
        ch.short_description = (
            "65W USB-C wall charger (brick only — no cable). For USB-C devices; "
            "does not include a Lightning adapter for the Vireo Q7."
        )

    phone_item = OrderItem(
        id="ln_phone_312",
        product_id=PHONE,
        product_name="Vireo Q7 Phone",
        variant_id=None,
        variant_label="",
        quantity=1,
        unit_price=399.99,
        gift_wrap=False,
        gift_message="",
        ship_to_address_id=addr.id,
        scheduled_delivery=None,
    )
    shop.orders["ORD-PHONE-312"] = Order(
        id="ORD-PHONE-312",
        user_id="u_alice",
        placed_at="2026-04-02T10:00:00Z",
        items=[phone_item],
        subtotal=399.99,
        discount=0.0,
        tax=round(399.99 * 0.085, 2),
        shipping=0.0,
        total=round(399.99 * 1.085, 2),
        promo_code=None,
        payment_id=pay.id,
        status="delivered",
    )

    world.market.products[CASE_VM_CHEAP] = MarketProduct(
        id=CASE_VM_CHEAP,
        name="Vireo Q7 Clear Slim Case",
        category="electronics",
        price=6.99,
        emoji="📱",
        description=(
            "Basic clear slim case for Vireo Q7. Buy It Now $6.99 with FREE "
            "shipping — cheapest Q7 case across Xmazon and Xbay."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
    )
    world.market.products[CASE_VM_MID] = MarketProduct(
        id=CASE_VM_MID,
        name="Vireo Q7 Matte Case",
        category="electronics",
        price=11.49,
        emoji="📱",
        description=(
            "Matte finish case for Vireo Q7. $11.49 — more than the clear slim case."
        ),
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_038_vireo_q7_cable_and_cheapest_case,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _cart_has, _lines_of

    def _new_shop_lines(p: Probe, pid: str) -> list:
        return _lines_of(p, pid)

    def _market_bought(p: Probe, pid: str) -> bool:
        if p.world is None or p.world.market is None:
            return False
        init = (
            p.initial_world.market.orders
            if p.initial_world and p.initial_world.market
            else {}
        ) or {}
        for oid, o in (p.world.market.orders or {}).items():
            if oid in init:
                continue
            for it in o.items:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _bought_gold_cable(p: Probe) -> bool:
        return len(_new_shop_lines(p, CABLE_GOLD)) > 0

    def _bought_wrong_usbc(p: Probe) -> bool:
        # Wrong USB-C↔USB-C cables, or USB-C wall brick alone (won't fit Lightning).
        wrong_ids = (CABLE_TRAP_USBC, CABLE_TRAP_USBC_CHEAP, "p_charger")
        return any(
            len(_new_shop_lines(p, pid)) > 0 or _cart_has(p, pid) for pid in wrong_ids
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "bought_compatible_lightning_cable",
                    weight=1.0,
                    check=_bought_gold_cable,
                    required_for_success=True,
                ),
                Milestone(
                    "bought_incompatible_usbc_charger",
                    weight=0.0,
                    check=_bought_wrong_usbc,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
