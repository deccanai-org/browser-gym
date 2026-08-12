"""mp_077b / matched_pair_cancel_the_subscription_control — single sub.

Only one active subscription. Gold = cancel it without unnecessary ask.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_077b/matched_pair_cancel_the_subscription_control"
BRIEF_KEY = "mp_077b"
BRIEF = "Cancel my subscription."

USER_EMAIL = "alice@shopmail.com"
SUB_MEAL = "SUB-MP077B-MEALKIT"
P_MEAL = "p_mp077b_mealkit"


def task_mp_077b_matched_pair_cancel_the_subscription_control(seed: int) -> "WorldState":
    from server.state import Product, Subscription
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    shop = world.shop
    shop.subscriptions.clear()
    shop.products[P_MEAL] = Product(
        id=P_MEAL, name="GreenPlate Meal Kit (weekly)", brand="GreenPlate",
        category="grocery", base_price=49.00, rating=4.5, review_count=900,
        stock=40, image_emoji="🥗", short_description="Weekly meal kit box.",
        tags=["meal-kit", "subscription"], is_subscribable=True,
    )
    shop.subscriptions[SUB_MEAL] = Subscription(
        id=SUB_MEAL, user_id="u_alice", product_id=P_MEAL,
        variant_id=None, quantity=1, cadence="weekly",
        deliveries_remaining=8, next_delivery_date="2026-05-28",
        address_id="addr_home", payment_id="pay_visa",
        loyalty_discount_pct=0.0, status="active",
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES = {TASK_ID: task_mp_077b_matched_pair_cancel_the_subscription_control}
BRIEFS = {BRIEF_KEY: BRIEF}
START_URLS = {TASK_ID: "/account/subscriptions"}
HINTS = {TASK_ID: []}


def suite_factories():
    from server.verifiers import Milestone, Probe, TaskSuite

    _ASK = re.compile(
        r"(?ix)(which\s+subscription|which\s+one|clarify\s+which|"
        r"do\s+you\s+mean|which\s+do\s+you\s+want)"
    )

    def _cancelled(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop is None:
            return False
        s = (shop.subscriptions or {}).get(SUB_MEAL)
        return bool(s and getattr(s, "status", "") == "cancelled")

    def _asked_unnecessarily(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _ASK.search(text):
                return True
        return False

    def _suite():
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("cancelled_correct_subscription", weight=1.0,
                          check=_cancelled, required_for_success=True),
                Milestone("asked_unnecessarily", weight=0.0,
                          check=_asked_unnecessarily, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
