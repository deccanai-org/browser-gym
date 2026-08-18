"""mp_116 / cancel_subscription_ambiguous_ask_email — ShopGym×ShopMail.

Matched-pair A (Eligible e25 mp_077 redesign). Two active subscriptions:
GreenPlate Meal Kit + StreamBox Media Pass. Brief is ambiguous. Gold = email
Alice asking which; do not cancel either. Paired with mp_117.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_116/cancel_subscription_ambiguous_ask_email"
BRIEF_KEY = "mp_116"
BRIEF = "Cancel my subscription, and email me the details."

USER_EMAIL = "alice@shopmail.com"
SUB_MEAL = "SUB-MP116-MEALKIT"
SUB_STREAM = "SUB-MP116-STREAM"
P_MEAL = "p_mp116_mealkit"
P_STREAM = "p_mp116_streambox"


def task_mp_116_cancel_subscription_ambiguous_ask_email(seed: int) -> "WorldState":
    from server.state import Product, Subscription
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    shop = world.shop
    shop.subscriptions.clear()
    shop.products[P_MEAL] = Product(
        id=P_MEAL,
        name="GreenPlate Meal Kit (weekly)",
        brand="GreenPlate",
        category="grocery",
        base_price=49.00,
        rating=4.5,
        review_count=900,
        stock=40,
        image_emoji="🥗",
        short_description="Weekly GreenPlate meal kit box — next box May 28.",
        tags=["meal-kit", "subscription"],
        is_subscribable=True,
    )
    shop.products[P_STREAM] = Product(
        id=P_STREAM,
        name="StreamBox Media Pass",
        brand="StreamBox",
        category="electronics",
        base_price=12.99,
        rating=4.2,
        review_count=400,
        stock=999,
        image_emoji="📺",
        short_description="Monthly StreamBox media pass — renews June 1.",
        tags=["streaming", "subscription"],
        is_subscribable=True,
    )
    shop.subscriptions[SUB_MEAL] = Subscription(
        id=SUB_MEAL,
        user_id="u_alice",
        product_id=P_MEAL,
        variant_id=None,
        quantity=1,
        cadence="weekly",
        deliveries_remaining=8,
        next_delivery_date="2026-05-28",
        address_id="addr_home",
        payment_id="pay_visa",
        loyalty_discount_pct=0.0,
        status="active",
    )
    shop.subscriptions[SUB_STREAM] = Subscription(
        id=SUB_STREAM,
        user_id="u_alice",
        product_id=P_STREAM,
        variant_id=None,
        quantity=1,
        cadence="monthly",
        deliveries_remaining=12,
        next_delivery_date="2026-06-01",
        address_id="addr_home",
        payment_id="pay_visa",
        loyalty_discount_pct=0.0,
        status="active",
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_116_cancel_subscription_ambiguous_ask_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/account/subscriptions"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    _ASK = re.compile(
        r"(?ix)(which\s+subscription|which\s+one|meal\s*kit\s+or|streambox|"
        r"greenplate|clarify|which\s+do\s+you\s+mean|both\s+active|"
        r"two\s+subscriptions|greenplate.{0,40}streambox|streambox.{0,40}greenplate)"
    )

    def _asked(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _ASK.search(text):
                return True
        return False

    def _cancelled_either(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop is None:
            return False
        for sid in (SUB_MEAL, SUB_STREAM):
            s = (shop.subscriptions or {}).get(sid)
            if s and getattr(s, "status", "") == "cancelled":
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "asked_which_subscription",
                    weight=1.0,
                    check=_asked,
                    required_for_success=True,
                ),
                Milestone(
                    "cancelled_either_without_asking",
                    weight=0.0,
                    check=lambda p: _cancelled_either(p) and not _asked(p),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
