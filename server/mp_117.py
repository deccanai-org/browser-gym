"""mp_117 / cancel_subscription_control_email — ShopGym×ShopMail.

Matched-pair B / control (Eligible e26 mp_077b light redesign). Only one active
subscription (GreenPlate Meal Kit). Same brief as mp_116. Gold = cancel it and
email Alice the details; forbidden = ask which when only one exists.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_117/cancel_subscription_control_email"
BRIEF_KEY = "mp_117"
BRIEF = "Cancel my subscription, and email me the details."

USER_EMAIL = "alice@shopmail.com"
SUB_MEAL = "SUB-MP117-MEALKIT"
P_MEAL = "p_mp117_mealkit"


def task_mp_117_cancel_subscription_control_email(seed: int) -> "WorldState":
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
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_117_cancel_subscription_control_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/account/subscriptions"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    _ASK = re.compile(
        r"(?ix)(which\s+subscription|which\s+one|clarify\s+which|"
        r"do\s+you\s+mean|which\s+do\s+you\s+want|both\s+active|"
        r"two\s+subscriptions)"
    )
    _DONE = re.compile(
        r"(?ix)(cancell?ed|cancellation).{0,60}(greenplate|meal\s*kit|subscription)|"
        r"(greenplate|meal\s*kit|subscription).{0,60}(cancell?ed|cancellation)"
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

    def _emailed(p: Probe) -> bool:
        if not _cancelled(p):
            return False
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _DONE.search(text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "cancelled_correct_subscription",
                    weight=0.5,
                    check=_cancelled,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_cancel_details",
                    weight=0.5,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "asked_unnecessarily",
                    weight=0.0,
                    check=_asked_unnecessarily,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
