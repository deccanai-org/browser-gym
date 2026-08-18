"""mp_113 / kettle_reason_unlock_address_change_email — ShopGym×ShopMail.

Solvable twin of mp_112 (Eligible e22 mp_074b redesign). Same brief/target
address; kettle order is still processing so reason-for-change dropdown unlocks
address edit. Gold = select reason, update to work address, email Alice.
Forbidden: claim change is impossible. mp_074b left untouched.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_113/kettle_reason_unlock_address_change_email"
BRIEF_KEY = "mp_113"
BRIEF = (
    "I totally forgot to change my delivery address before placing an order "
    "for my QuickBoil Electric Kettle — can you change it to 500 Madison "
    "Avenue, New York NY 10022? Email me once you are done."
)

USER_EMAIL = "alice@shopmail.com"
ORDER_ID = "ORD-MP113-KETTLE"
LINE_ID = "ln_mp113_kettle"
SKU = "p_mp113_kettle"
NAME = "QuickBoil Electric Kettle"
FROM_ADDR = "addr_home"
TO_ADDR = "addr_work"

_CANT = re.compile(
    r"(?ix)(can\s*n[o']t\s+change|cannot\s+change|unable\s+to\s+change|"
    r"too\s+late|out\s+for\s+delivery|no\s+longer\s+(possible|available))"
)
_OK_MAIL = re.compile(
    r"(?ix)("
    r"(address|ship-?to).{0,40}(changed|updated|switched)|"
    r"updated\s+the\s+(delivery\s+)?address|"
    r"500\s+madison|"
    r"work\s+address|"
    r"ord-mp113"
    r")"
)


def task_mp_113_kettle_reason_unlock_address_change_email(seed: int) -> "WorldState":
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    shop = world.shop

    # Decoy OFD blender — wrong order / wrong status.
    shop.products["p_mp113_decoy_blender"] = Product(
        id="p_mp113_decoy_blender",
        name="PulseBlend Mini",
        brand="PulseBlend",
        category="home",
        base_price=39.00,
        rating=4.0,
        review_count=120,
        stock=10,
        image_emoji="🥤",
        short_description="Out for delivery distractor.",
        tags=["blender"],
    )
    from server.state import Shipment, ShipmentEvent

    shop.orders["ORD-MP113-BLEND"] = Order(
        id="ORD-MP113-BLEND",
        user_id="u_alice",
        placed_at="2026-05-18T10:00:00Z",
        items=[
            OrderItem(
                id="ln_mp113_blend",
                product_id="p_mp113_decoy_blender",
                product_name="PulseBlend Mini",
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=39.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id=FROM_ADDR,
                scheduled_delivery=None,
            )
        ],
        subtotal=39.00,
        discount=0.0,
        tax=3.32,
        shipping=5.99,
        total=48.31,
        promo_code=None,
        payment_id="pay_visa",
        status="out_for_delivery",
        shipments=[
            Shipment(
                id="sh_mp113_blend",
                carrier="UPS",
                tracking_number="1ZMP113BLND",
                item_ids=["ln_mp113_blend"],
                status="out_for_delivery",
                estimated_delivery="Arriving today",
                events=[
                    ShipmentEvent(
                        timestamp="2026-05-21T07:00:00Z",
                        status="out_for_delivery",
                        detail="Out for delivery.",
                    )
                ],
            )
        ],
    )

    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="QuickBoil",
        category="home",
        base_price=42.00,
        rating=4.4,
        review_count=510,
        stock=20,
        image_emoji="🫖",
        short_description="Electric kettle. Still processing — address editable.",
        tags=["kettle"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-05-20T14:00:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=SKU,
                product_name=NAME,
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=42.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id=FROM_ADDR,
                scheduled_delivery=None,
            )
        ],
        subtotal=42.00,
        discount=0.0,
        tax=3.57,
        shipping=5.99,
        total=51.56,
        promo_code=None,
        payment_id="pay_visa",
        status="confirmed",
        shipments=[],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_113_kettle_reason_unlock_address_change_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/account/orders"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _changed(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        o = shop.orders.get(ORDER_ID) if shop else None
        if not o or not o.items:
            return False
        return o.items[0].ship_to_address_id == TO_ADDR

    def _selected_reason(p: Probe) -> bool:
        return bool(
            _log_has(p, "change_order_address", order_id=ORDER_ID) or _changed(p)
        )

    def _emailed_ok(p: Probe) -> bool:
        if not _changed(p):
            return False
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _OK_MAIL.search(text) and not _CANT.search(text):
                return True
        return False

    def _stated_impossible(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _CANT.search(text) and not _changed(p):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "selected_reason_dropdown",
                    weight=0.3,
                    check=_selected_reason,
                    required_for_success=True,
                ),
                Milestone(
                    "address_updated_successfully",
                    weight=0.4,
                    check=_changed,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_address_updated",
                    weight=0.3,
                    check=_emailed_ok,
                    required_for_success=True,
                ),
                Milestone(
                    "stated_change_not_possible",
                    weight=0.0,
                    check=_stated_impossible,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
