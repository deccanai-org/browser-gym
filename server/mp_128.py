"""mp_128 / two_emails_named_conflicting_instruction — ShopMail×ShopGym.

Two Alice emails about a standing-desk order: first cancel, later keep and
change color to walnut. Timestamps unambiguous. Gold = follow the later email.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_128/two_emails_named_conflicting_instruction"
BRIEF_KEY = "mp_128"
BRIEF = (
    "I sent two emails about the standing desk order, the second one has the "
    "actual final answer, follow that one and email me confirming what you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
ORDER_ID = "ORD-MP128-DESK"
LINE_ID = "ln_mp128_desk"
SKU = "p_mp128_desk"
NAME = "AeroLift Standing Desk"
VAR_OAK = "v_mp128_oak"
VAR_WALNUT = "v_mp128_walnut"
MAIL_OLD = "em_mp128_cancel"
MAIL_NEW = "em_mp128_walnut"


def task_mp_128_two_emails_named_conflicting_instruction(seed: int) -> "WorldState":
    from server.apps.mail.state import Email
    from server.state import Order, OrderItem, Product, ProductVariant
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.returns.clear()
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="AeroLift",
        category="home",
        base_price=249.00,
        rating=4.5,
        review_count=160,
        stock=6,
        image_emoji="🖥️",
        short_description="Electric standing desk. Color is a saved option.",
        tags=["desk"],
        variants=[
            ProductVariant(
                id=VAR_OAK, label="Oak", attributes={"color": "oak"}, stock=3
            ),
            ProductVariant(
                id=VAR_WALNUT, label="Walnut", attributes={"color": "walnut"}, stock=3
            ),
        ],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-05-20T16:00:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=SKU,
                product_name=NAME,
                variant_id=VAR_OAK,
                variant_label="Oak",
                quantity=1,
                unit_price=249.00,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=249.00,
        discount=0.0,
        tax=21.16,
        shipping=5.99,
        total=276.15,
        promo_code=None,
        payment_id="pay_visa",
        status="confirmed",
        shipments=[],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MAIL_OLD] = Email(
        id=MAIL_OLD,
        sender=USER_EMAIL,
        to="assistant@shopmail.com",
        subject="standing desk — cancel it",
        body="Can you cancel the standing desk order? I changed my mind.",
        received_at="2026-05-20T18:00:00",
        received_label="Tue 6:00 PM",
        read=False,
        labels=["unread"],
    )
    mail.inbox[MAIL_NEW] = Email(
        id=MAIL_NEW,
        sender=USER_EMAIL,
        to="assistant@shopmail.com",
        subject="standing desk — actually keep it",
        body=(
            "Ignore the cancel note — actually keep it, just change the color "
            "to walnut."
        ),
        received_at="2026-05-20T19:40:00",
        received_label="Tue 7:40 PM",
        read=False,
        labels=["unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_128_two_emails_named_conflicting_instruction,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _OK = re.compile(r"(?ix)(walnut|kept|keep|color|desk)")

    def _both_emails(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        old = mail.inbox.get(MAIL_OLD)
        new = mail.inbox.get(MAIL_NEW)
        opened = bool(old and old.read) and bool(new and new.read)
        if opened:
            return True
        return _log_has(p, "view_email", email_id=MAIL_OLD) and _log_has(
            p, "view_email", email_id=MAIL_NEW
        )

    def _order(p: Probe):
        shop = p.world.shop if p.world else None
        return (shop.orders or {}).get(ORDER_ID) if shop else None

    def _kept(p: Probe) -> bool:
        o = _order(p)
        return o is not None and getattr(o, "status", "") != "cancelled"

    def _walnut(p: Probe) -> bool:
        o = _order(p)
        if o is None or getattr(o, "status", "") == "cancelled":
            return False
        for it in o.items:
            vid = (getattr(it, "variant_id", "") or "").lower()
            lab = (getattr(it, "variant_label", "") or "").lower()
            if VAR_WALNUT in vid or "walnut" in lab:
                return True
        return False

    def _emailed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _OK.search(text) and _walnut(p):
                return True
        return False

    def _cancelled(p: Probe) -> bool:
        o = _order(p)
        return o is not None and getattr(o, "status", "") == "cancelled"

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "identified_both_emails",
                    weight=0.2,
                    check=lambda p: _both_emails(p) or _walnut(p),
                    required_for_success=True,
                ),
                Milestone(
                    "followed_most_recent_instruction",
                    weight=0.5,
                    check=lambda p: _kept(p) and _walnut(p),
                    required_for_success=True,
                ),
                Milestone(
                    "changed_color_to_walnut",
                    weight=0.2,
                    check=_walnut,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_confirmation",
                    weight=0.1,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "cancelled_order_following_stale_email",
                    weight=0.0,
                    check=_cancelled,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
