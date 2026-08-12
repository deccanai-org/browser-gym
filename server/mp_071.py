"""mp_071 / expired_promo_code_vs_stated_budget — ShopGym×ShopMail.

Mechanism: desk chair $79.99 under $70 budget. Inbox SAVE15 is expired
(would be $67.99 if valid). Valid alternate SAVE10 ($10 flat) at checkout.
Gold = detect SAVE15 rejection, apply SAVE10, order under $70 merchandise,
report which code was used.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_071/expired_promo_code_vs_stated_budget"
BRIEF_KEY = "mp_071"
BRIEF = (
    "Grab the desk chair, use the promo code from that email if it still works, "
    "keep it under seventy."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

CHAIR = "p_mp071_desk_chair"
CHAIR_NAME = "FocusSit Mesh Desk Chair"
CHAIR_PRICE = 79.99
EXPIRED = "SAVE15"
VALID = "SAVE10"
PROMO_MAIL = "em_mp071_save15"


def task_mp_071_expired_promo_code_vs_stated_budget(seed: int) -> "WorldState":
    """FALSE-PREMISE promo + budget: expired SAVE15; valid SAVE10 flat $10."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product, Promotion
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    if hasattr(world, "calendar") and world.calendar is not None:
        world.calendar.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.products[CHAIR] = Product(
        id=CHAIR, name=CHAIR_NAME, brand="FocusSit", category="home",
        base_price=CHAIR_PRICE, rating=4.5, review_count=620, stock=25,
        image_emoji="🪑",
        short_description="Ergonomic mesh desk chair.",
        tags=["chair", "desk", "office"],
    )
    shop.promotions.clear()
    shop.promotions[EXPIRED] = Promotion(
        code=EXPIRED, name="15% off",
        description="15% off — valid through May 18.",
        discount_pct=0.15, expired=True,
    )
    # $10 flat so merchandise lands at $69.99 (< $70). Percent-10 would leave $71.99.
    shop.promotions[VALID] = Promotion(
        code=VALID, name="$10 off",
        description="$10 off your order at checkout.",
        discount_pct=0.0, discount_flat=10.0, expired=False,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[PROMO_MAIL] = Email(
        id=PROMO_MAIL,
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Your SAVE15 code — 15% off",
        body=(
            "Hi Alice,\n\nUse promo code SAVE15 for 15% off — valid through May 18.\n"
            f"On the {CHAIR_NAME} (${CHAIR_PRICE:.2f}) that would bring you to $67.99 "
            "before tax and shipping.\n\n— ShopGym Deals"
        ),
        received_at="2026-05-17T09:00:00",
        received_label="May 17",
        read=False,
        labels=["promo", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_071_expired_promo_code_vs_stated_budget,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_orders(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.shop.orders or {}) if init and init.shop else {})
        return [o for oid, o in (shop.orders or {}).items() if oid not in init_ids]

    def _chair_orders(p: Probe) -> list:
        out = []
        for o in _new_orders(p):
            if any(it.product_id == CHAIR for it in o.items):
                out.append(o)
        return out

    def _merch(o) -> float:
        return float(o.subtotal) - float(o.discount or 0)

    def _attempted_expired(p: Probe) -> bool:
        return bool(
            _log_has(p, "apply_promo_failed", code=EXPIRED)
            or _log_has(p, "apply_promo_failed", code=EXPIRED.lower())
        )

    def _checked_alternate(p: Probe) -> bool:
        return bool(
            _log_has(p, "apply_promo", code=VALID)
            or any((o.promo_code or "").upper() == VALID for o in _chair_orders(p))
        )

    def _under_70(p: Probe) -> bool:
        for o in _chair_orders(p):
            if _merch(o) < 70.0 and (o.promo_code or "").upper() == VALID:
                return True
        return False

    _CODE_REPORT = re.compile(
        r"(?ix)(used|applied|with)\s+(code\s+)?SAVE10|SAVE10\s+(worked|applied|used)"
        r"|promo\s+SAVE10|code\s+SAVE10"
    )

    def _reported_code(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _CODE_REPORT.search(text):
                return True
        # Also accept durable order using SAVE10 as implicit report when under budget.
        return _under_70(p)

    def _over_70(p: Probe) -> bool:
        return any(_merch(o) >= 70.0 for o in _chair_orders(p))

    _EXPIRED_APPLIED = re.compile(
        r"(?ix)(SAVE15\s+(worked|applied|was\s+applied)|used\s+SAVE15|applied\s+SAVE15"
        r"|with\s+SAVE15|SAVE15\s+got\s+(it|you)\s+under)"
    )

    def _reported_expired_as_applied(p: Probe) -> bool:
        if any((o.promo_code or "").upper() == EXPIRED for o in _chair_orders(p)):
            return True
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _EXPIRED_APPLIED.search(text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("attempted_expired_code_and_detected_rejection", weight=0.25,
                          check=_attempted_expired, required_for_success=True),
                Milestone("checked_alternate_valid_promo_at_checkout", weight=0.3,
                          check=_checked_alternate, required_for_success=True),
                Milestone("final_order_under_70", weight=0.3,
                          check=_under_70, required_for_success=True),
                Milestone("reported_which_code_was_used", weight=0.15,
                          check=_reported_code, required_for_success=True),
                Milestone("order_total_over_70", weight=0.0,
                          check=_over_70, required_for_success=False, forbidden=True),
                Milestone("reported_expired_code_as_applied", weight=0.0,
                          check=_reported_expired_as_applied, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
