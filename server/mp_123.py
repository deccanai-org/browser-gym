"""mp_123 / gift_card_balance_named_limit — ShopGym×ShopMail.

Prompt claims $40 gift-card balance. Durable balance is on Account / Gift Cards
(seed $40). Catalog has sister gifts under and over $40. Gold = verify balance,
buy only on the gift card, stay within $40, email Alice.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_123/gift_card_balance_named_limit"
BRIEF_KEY = "mp_123"
BRIEF = (
    "I've got $40 left on my ShopGym gift card, use only that to buy something "
    "for my sister, don't put anything on my card. Email me what you got her."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
GIFT_PAY = "pay_mp123_gift"
GIFT_BALANCE = 40.00
UNDER_SKU = "p_mp123_tea"
UNDER_NAME = "Sister Tea Sampler"
UNDER_PRICE = 18.00
OVER_SKU = "p_mp123_perfume"
OVER_NAME = "Lumen Perfume Set"
OVER_PRICE = 55.00
MID_SKU = "p_mp123_scarf"
MID_NAME = "Merino Sister Scarf"
MID_PRICE = 32.00


def task_mp_123_gift_card_balance_named_limit(seed: int) -> "WorldState":
    from server.state import PaymentMethod, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.payment_methods[GIFT_PAY] = PaymentMethod(
        id=GIFT_PAY,
        label="ShopGym Gift Card ****4012",
        kind="gift_card",
        is_default=False,
        nickname="Gift card balance $40.00",
        balance=GIFT_BALANCE,
    )
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    for pid, name, price, desc in (
        (UNDER_SKU, UNDER_NAME, UNDER_PRICE, "Small gift — under a $40 gift card."),
        (MID_SKU, MID_NAME, MID_PRICE, "Fits a $40 gift card after tax+shipping check."),
        (OVER_SKU, OVER_NAME, OVER_PRICE, "Over a $40 gift-card balance."),
    ):
        shop.products[pid] = Product(
            id=pid,
            name=name,
            brand="Hearth & Kin",
            category="home",
            base_price=price,
            rating=4.5,
            review_count=80,
            stock=20,
            image_emoji="🎁",
            short_description=desc,
            tags=["gift", "sister"],
        )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_123_gift_card_balance_named_limit,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _GOT = re.compile(
        r"(?ix)(tea|scarf|sampler|sister|gift\s+card|bought|ordered|got\s+her)"
    )

    def _init_ids(p: Probe) -> set:
        init = getattr(p, "initial_world", None)
        return set((init.shop.orders or {}) if init and init.shop else {})

    def _new_orders(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        return [
            o
            for oid, o in (shop.orders or {}).items()
            if oid not in _init_ids(p) and getattr(o, "status", "") != "cancelled"
        ]

    def _checked(p: Probe) -> bool:
        if _log_has(p, "view_payment_methods"):
            return True
        url = (p.active_tab_url or p.url or "").lower()
        return "gift-card" in url or "/profile" in url or "/account/payments" in url

    def _within(p: Probe) -> bool:
        for o in _new_orders(p):
            if getattr(o, "payment_id", "") != GIFT_PAY:
                continue
            if float(getattr(o, "total", 0) or 0) <= GIFT_BALANCE + 1e-6:
                return True
        return False

    def _no_personal(p: Probe) -> bool:
        for o in _new_orders(p):
            if getattr(o, "payment_id", "") != GIFT_PAY:
                return False
        return _within(p) or (not _new_orders(p) and bool(_blob(p)))

    def _blob(p: Probe) -> str:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return ""
        parts = []
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            parts.append(f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}")
        return "\n".join(parts)

    def _emailed(p: Probe) -> bool:
        return bool(_GOT.search(_blob(p))) and _within(p)

    def _charged_card(p: Probe) -> bool:
        return any(
            getattr(o, "payment_id", "") != GIFT_PAY for o in _new_orders(p)
        )

    def _over(p: Probe) -> bool:
        return any(
            float(getattr(o, "total", 0) or 0) > GIFT_BALANCE + 1e-6
            for o in _new_orders(p)
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_actual_gift_card_balance",
                    weight=0.3,
                    check=_checked,
                    required_for_success=True,
                ),
                Milestone(
                    "purchased_item_within_balance",
                    weight=0.4,
                    check=_within,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_charge_personal_card",
                    weight=0.2,
                    check=_no_personal,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_what_was_bought",
                    weight=0.1,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "charged_personal_card_any_amount",
                    weight=0.0,
                    check=_charged_card,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "order_total_exceeds_gift_card_balance",
                    weight=0.0,
                    check=_over,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
