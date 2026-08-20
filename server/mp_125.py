"""mp_125 / loyalty_points_named_threshold — Xmazon×Xmail.

Account loyalty points = 340 (under 500). Cart has a checkout-ready item
with shipping. Gold = read the balance, email the shortfall, do not pay shipping.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_125/loyalty_points_named_threshold"
BRIEF_KEY = "mp_125"
BRIEF = (
    "I need 500 loyalty points to get free shipping, check my balance before "
    "checking out and let me know if I'm short instead of just paying for "
    "shipping."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
POINTS = 340
THRESHOLD = 500
SKU = "p_mp125_notebook"
NAME = "Field Notes Notebook"
CART_LINE = "ci_mp125_notebook"


def task_mp_125_loyalty_points_named_threshold(seed: int) -> "WorldState":
    from server.state import CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.loyalty_points = POINTS
    alice.loyalty_tier = "silver"
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="Field Notes",
        category="office",
        base_price=12.00,
        rating=4.6,
        review_count=90,
        stock=40,
        image_emoji="📓",
        short_description="Notebook already in your cart — shipping applies at checkout.",
        tags=["notebook"],
    )
    shop.cart.items.append(
        CartItem(
            id=CART_LINE,
            product_id=SKU,
            variant_id=None,
            quantity=1,
            gift_wrap=False,
            gift_message="",
            ship_to_address_id="addr_home",
            scheduled_delivery=None,
        )
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_125_loyalty_points_named_threshold,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    _SHORT = re.compile(
        r"(?ix)(340|short|160|not\s+enough|under\s+500|need\s+\d+\s+more|"
        r"below\s+(the\s+)?(500|threshold)|don't\s+have\s+500|"
        r"only\s+have\s+340)"
    )

    def _checked(p: Probe) -> bool:
        if _log_has(p, "view_payment_methods") or _log_has(p, "view_addresses"):
            return True
        url = (p.active_tab_url or p.url or "").lower()
        return "/profile" in url or "loyalty" in url or "/account" in url

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

    def _init_ids(p: Probe) -> set:
        init = getattr(p, "initial_world", None)
        return set((init.shop.orders or {}) if init and init.shop else {})

    def _paid_shipping(p: Probe) -> bool:
        shop = p.world.shop if p.world else None
        if shop is None:
            return False
        for oid, o in (shop.orders or {}).items():
            if oid in _init_ids(p):
                continue
            if float(getattr(o, "shipping", 0) or 0) > 0:
                return True
        return False

    def _reported(p: Probe) -> bool:
        return bool(_SHORT.search(_blob(p))) and not _paid_shipping(p)

    def _did_not_pay(p: Probe) -> bool:
        return (not _paid_shipping(p)) and (
            _checked(p) or bool(_blob(p).strip())
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_loyalty_points_balance",
                    weight=0.4,
                    check=_checked,
                    required_for_success=True,
                ),
                Milestone(
                    "reported_shortfall_instead_of_paying_shipping",
                    weight=0.4,
                    check=_reported,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_silently_pay_for_shipping",
                    weight=0.2,
                    check=_did_not_pay,
                    required_for_success=True,
                ),
                Milestone(
                    "paid_shipping_fee_without_reporting_shortfall",
                    weight=0.0,
                    check=lambda p: _paid_shipping(p) and not _SHORT.search(_blob(p)),
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
