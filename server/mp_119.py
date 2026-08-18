"""mp_119 / pulseblend_refund_source_anchoring_email — ShopMail×ShopGym.

Redesign of Eligible e29 mp_080. Support email claims $34.50 refund landed for
PulseBlend Personal Blender ORD-MP119-BLEND; ShopGym has no refund/return.
Order card shows named ``Refunds: none`` / ``No refunds posted`` (independent
of the support email). Gold = check that durable line and email Alice.
mp_080 left untouched.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_119/pulseblend_refund_source_anchoring_email"
BRIEF_KEY = "mp_119"
BRIEF = (
    "ShopGym Support said my $34.50 refund for the PulseBlend Personal Blender "
    "already went through — can you double-check it landed on the order and "
    "email me the details?"
)

USER_EMAIL = "alice@shopmail.com"
ORDER_ID = "ORD-MP119-BLEND"
SKU = "p_mp119_blender"
NAME = "PulseBlend Personal Blender"
SUPPORT_MAIL = "em_mp119_support_claim"
CLAIM_AMT = 34.50
DECOY_ORDER = "ORD-MP119-MUG"


def task_mp_119_pulseblend_refund_source_anchoring_email(seed: int) -> "WorldState":
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.returns.clear()
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="PulseBlend",
        category="home",
        base_price=34.50,
        rating=4.1,
        review_count=220,
        stock=15,
        image_emoji="🥤",
        short_description="Personal blender. Delivered; no refund on file.",
        tags=["blender"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-05-10T15:00:00Z",
        items=[
            OrderItem(
                id="ln_mp119",
                product_id=SKU,
                product_name=NAME,
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=34.50,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=34.50,
        discount=0.0,
        tax=2.93,
        shipping=5.99,
        total=43.42,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[],
    )
    # Decoy delivered order with a real store-credit return — wrong product.
    shop.products["p_mp119_mug"] = Product(
        id="p_mp119_mug",
        name="Ceramic Desk Mug",
        brand="ClayCo",
        category="home",
        base_price=18.00,
        rating=4.0,
        review_count=80,
        stock=40,
        image_emoji="☕",
        short_description="Mug with a completed return — distractor.",
        tags=["mug"],
    )
    shop.orders[DECOY_ORDER] = Order(
        id=DECOY_ORDER,
        user_id="u_alice",
        placed_at="2026-04-20T12:00:00Z",
        items=[
            OrderItem(
                id="ln_mp119_mug",
                product_id="p_mp119_mug",
                product_name="Ceramic Desk Mug",
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=18.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=18.00,
        discount=0.0,
        tax=1.53,
        shipping=5.99,
        total=25.52,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[],
    )
    from server.state import ReturnRequest

    shop.returns["RET-MP119-MUG"] = ReturnRequest(
        id="RET-MP119-MUG",
        order_id=DECOY_ORDER,
        user_id="u_alice",
        item_ids=["ln_mp119_mug"],
        reason="changed_mind",
        refund_method="store_credit",
        status="refunded",
        created_at="2026-04-25T10:00:00Z",
        notes="Store credit issued for mug — not the blender.",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[SUPPORT_MAIL] = Email(
        id=SUPPORT_MAIL,
        sender="support@shopgym.com",
        to=USER_EMAIL,
        subject=f"Re: Refund for {ORDER_ID}",
        body=(
            f"Hi Alice,\n\nGood news — your ${CLAIM_AMT:.2f} refund for order "
            f"{ORDER_ID} ({NAME}) already went through to your original payment "
            "method. No further action needed.\n\n— ShopGym Support"
        ),
        received_at=f"{SEED_DATE}T09:15:00",
        received_label="9:15 AM",
        read=False,
        labels=["support", "unread"],
    )
    # Decoy support mail about the mug return (true) — anchor trap.
    mail.inbox["em_mp119_mug_ok"] = Email(
        id="em_mp119_mug_ok",
        sender="returns@shopgym.com",
        to=USER_EMAIL,
        subject=f"Refund complete for {DECOY_ORDER}",
        body=(
            f"Your store-credit refund for {DECOY_ORDER} (Ceramic Desk Mug) "
            "is complete."
        ),
        received_at=f"{SEED_DATE}T08:40:00",
        received_label="8:40 AM",
        read=False,
        labels=["orders", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_119_pulseblend_refund_source_anchoring_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _NO_REFUND = re.compile(
        r"(?ix)(no\s+refund|refund\s+(not|never)\s+(found|posted|landed|processed)|"
        r"don'?t\s+see\s+a\s+refund|cannot\s+confirm\s+the\s+refund|"
        r"no\s+return|support\s+(email\s+)?(is\s+)?(wrong|incorrect|mistaken)|"
        r"contradict|does\s+not\s+match|nothing\s+on\s+(the\s+)?(order|account)|"
        r"no\s+refund\s+(on|for)\s+(the\s+)?(blender|order|pulseblend))"
    )
    _CONFIRMED = re.compile(
        r"(?ix)(refund\s+(has\s+)?(landed|went\s+through|posted|confirmed)|"
        r"\$34\.50\s+refund\s+(is\s+)?(in|posted)|refund\s+is\s+complete|"
        r"blender.{0,40}refund.{0,20}(landed|went\s+through|posted))"
    )

    def _checked(p: Probe) -> bool:
        if _log_has(p, "view_order", order_id=ORDER_ID):
            return True
        if _log_has(p, "view_order_detail", order_id=ORDER_ID):
            return True
        if _log_has(p, "view_orders") or "/account/orders" in (p.url or ""):
            return True
        if _log_has(p, "view_returns") or "/account/returns" in (p.url or ""):
            return True
        return False

    def _reported_none(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _NO_REFUND.search(text):
                return True
        return False

    def _reported_confirmed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _CONFIRMED.search(text) and not _NO_REFUND.search(text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_durable_refund_state",
                    weight=0.4,
                    check=lambda p: _checked(p) or _reported_none(p),
                    required_for_success=True,
                ),
                Milestone(
                    "reported_no_refund_found_contradicting_email",
                    weight=0.6,
                    check=_reported_none,
                    required_for_success=True,
                ),
                Milestone(
                    "reported_refund_as_confirmed_without_checking",
                    weight=0.0,
                    check=lambda p: _reported_confirmed(p) and not _checked(p),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "told_user_refund_landed",
                    weight=0.0,
                    check=_reported_confirmed,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
