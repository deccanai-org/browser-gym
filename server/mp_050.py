"""mp_050 / spoon_refund_amount_mismatch — Xbay×Xmail refund check.

Mechanism: Xbay wooden-spoon return was refunded $5.00, but the paid order
total was $18.50. Brief asks to check the order and email support if the refund
is off. Correct = mail support@valuemart naming the shortfall. Trap = treat the
$5 refund as fine, or email support about wrong item/damage instead of amount.

mp_033-adjacent (spoon/Xbay/support mail) but amount-mismatch only — no
Xmazon deals leg, so oracle can score a clean 1.0 on the support mail alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_050/spoon_refund_amount_mismatch"
BRIEF_KEY = "mp_050"
BRIEF = (
    "I think I got refunded the wrong amount for that spoon I returned on "
    "Xbay, check the order and email support if it's off."
)

USER_EMAIL = "alice@shopmail.com"
VM_SUPPORT = "support@valuemart.example.com"

VM_ORDER = "VM-4502"
SPOON_SKU = "vm_mp050_wooden_spoon"
SPOON_NAME = "Wooden Spoon"
ORDER_TOTAL = 18.50
REFUND_POSTED = 5.00

MAIL_ORDER = "em_mp050_order_confirm"
MAIL_REFUND = "em_mp050_refund_notice"


def task_mp_050_spoon_refund_amount_mismatch(seed: int) -> "WorldState":
    """FEASIBLE VM×Mail: partial spoon refund underpays; email support."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketCartItem, MarketOrder, MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    market = world.market
    market.products[SPOON_SKU] = MarketProduct(
        id=SPOON_SKU,
        name=SPOON_NAME,
        category="home",
        price=ORDER_TOTAL,
        emoji="🥄",
        description="Beechwood cooking spoon.",
        in_stock=True,
        condition="New",
        shipping_cost=0.0,
        brand="HomeChef",
    )
    market.orders[VM_ORDER] = MarketOrder(
        id=VM_ORDER,
        items=[
            MarketCartItem(
                product_id=SPOON_SKU,
                name=SPOON_NAME,
                unit_price=ORDER_TOTAL,
                quantity=1,
            )
        ],
        subtotal=ORDER_TOTAL,
        discount=0.0,
        delivery_fee=0.0,
        total=ORDER_TOTAL,
        placed_at="2026-05-10T14:00:00",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MAIL_ORDER] = Email(
        id=MAIL_ORDER,
        sender="orders@valuemart.example.com",
        to=USER_EMAIL,
        subject=f"Your Xbay order {VM_ORDER}",
        body=(
            f"Thanks for your order {VM_ORDER}.\n\n"
            f"Item: {SPOON_NAME}\n"
            f"Total charged: ${ORDER_TOTAL:.2f}\n"
        ),
        received_at=f"{SEED_DATE}T09:00:00",
        received_label="9:00 AM",
        read=True,
        labels=["purchases"],
        order_id=VM_ORDER,
    )
    mail.inbox[MAIL_REFUND] = Email(
        id=MAIL_REFUND,
        sender="billing@valuemart.example.com",
        to=USER_EMAIL,
        subject=f"Refund processed for {VM_ORDER}",
        body=(
            f"We processed your return for order {VM_ORDER} ({SPOON_NAME}).\n\n"
            f"Refund amount: ${REFUND_POSTED:.2f}\n"
            "It should appear on your statement in 3–5 business days."
        ),
        received_at=f"{SEED_DATE}T10:10:00",
        received_label="10:10 AM",
        read=False,
        labels=["purchases", "unread"],
        order_id=VM_ORDER,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_050_spoon_refund_amount_mismatch,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _amount_support(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            dest = f"{se.to or ''} {getattr(se, 'cc', '') or ''}".lower()
            if "valuemart" not in dest and VM_SUPPORT not in dest:
                continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            has_spoon = "spoon" in body
            has_order = VM_ORDER.lower() in body or "18.50" in body or "18.5" in body
            has_short = any(
                t in body
                for t in (
                    "5.00",
                    "$5",
                    "wrong amount",
                    "incorrect amount",
                    "short",
                    "underpaid",
                    "only refunded",
                    "partial",
                )
            )
            if has_spoon and has_order and has_short:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "emailed_support_refund_shortfall",
                    weight=1.0,
                    check=_amount_support,
                    required_for_success=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
