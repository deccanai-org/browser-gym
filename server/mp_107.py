"""mp_107 / vacation_hold_mail_and_recurring_delivery_pause — Cal×Shop subscriptions.

User labeled mp_101 originally; use mp_107.

Xoogle trip July 20–Aug 3. Two active S&S: one next delivery inside trip (pause),
one after return (leave alone). Third already cancelled (don't touch). Requires
durable pause affordance (shop.pause_subscription).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_107/vacation_hold_mail_and_recurring_delivery_pause"
BRIEF_KEY = "mp_107"
BRIEF = (
    "I'm going to be out of town starting the 20th for two weeks, can you pause "
    "anything on Xmazon that would normally ship during that window and let me "
    "know what got paused. Email me the details."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-07-15T11:00:00"
TRIP_START = "2026-07-20"
TRIP_END = "2026-08-03"
TRIP_EVENT = "ev_mp107_vacation"

SUB_CONFLICT = "SUB-MP107-COFFEE"   # next delivery July 25 — PAUSE
SUB_SAFE = "SUB-MP107-SOAP"        # next delivery Aug 10 — leave active
SUB_CANCELLED = "SUB-MP107-TEA"    # already cancelled — don't touch

SKU_COFFEE = "p_mp107_coffee"
SKU_SOAP = "p_mp107_soap"
SKU_TEA = "p_mp107_tea"


def task_mp_107_vacation_hold_mail_and_recurring_delivery_pause(
    seed: int,
) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.state import Product, Subscription
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[TRIP_EVENT] = CalendarEvent(
        id=TRIP_EVENT,
        title="Out of town — vacation",
        day=TRIP_START,
        day_label="Mon Jul 20",
        start="00:00",
        end="23:59",
        source="seed",
        description=(
            f"Away {TRIP_START} through {TRIP_END} (two weeks). "
            "Pause Subscribe & Save deliveries that would ship in this window."
        ),
        location="Travel",
    )
    # Multi-day visibility: also pin return day note.
    cal.events["ev_mp107_return"] = CalendarEvent(
        id="ev_mp107_return",
        title="Back from vacation",
        day=TRIP_END,
        day_label="Sun Aug 3",
        start="18:00",
        end="19:00",
        source="seed",
        description="Return evening Aug 3 — deliveries after this date are fine.",
    )

    shop = world.shop
    alice = shop.users["u_alice"]
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.subscriptions.clear()

    shop.products[SKU_COFFEE] = Product(
        id=SKU_COFFEE, name="Morning Roast Coffee Pods (24ct)", brand="BrewHaus",
        category="grocery", base_price=22.00, rating=4.6, review_count=2100,
        stock=80, image_emoji="☕", is_subscribable=True,
        short_description="S&S coffee — next delivery falls during vacation.",
        tags=["coffee", "subscription"],
    )
    shop.products[SKU_SOAP] = Product(
        id=SKU_SOAP, name="Castile Hand Soap Refill", brand="CleanCo",
        category="home", base_price=12.00, rating=4.4, review_count=600,
        stock=90, image_emoji="🧼", is_subscribable=True,
        short_description="S&S soap — next delivery AFTER return.",
        tags=["soap", "subscription"],
    )
    shop.products[SKU_TEA] = Product(
        id=SKU_TEA, name="Green Tea Bags (40ct)", brand="LeafWell",
        category="grocery", base_price=9.50, rating=4.3, review_count=400,
        stock=70, image_emoji="🍵", is_subscribable=True,
        short_description="Already-cancelled subscription decoy.",
        tags=["tea", "subscription", "cancelled"],
    )

    addr = "addr_home"
    pay = "pay_visa"
    shop.subscriptions[SUB_CONFLICT] = Subscription(
        id=SUB_CONFLICT, user_id="u_alice", product_id=SKU_COFFEE,
        variant_id=None, quantity=1, cadence="monthly",
        deliveries_remaining=5, next_delivery_date="2026-07-25",
        address_id=addr, payment_id=pay, status="active",
    )
    shop.subscriptions[SUB_SAFE] = Subscription(
        id=SUB_SAFE, user_id="u_alice", product_id=SKU_SOAP,
        variant_id=None, quantity=1, cadence="monthly",
        deliveries_remaining=4, next_delivery_date="2026-08-10",
        address_id=addr, payment_id=pay, status="active",
    )
    shop.subscriptions[SUB_CANCELLED] = Subscription(
        id=SUB_CANCELLED, user_id="u_alice", product_id=SKU_TEA,
        variant_id=None, quantity=1, cadence="monthly",
        deliveries_remaining=0, next_delivery_date="2026-07-22",
        address_id=addr, payment_id=pay, status="cancelled",
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_107_vacation_hold_mail_and_recurring_delivery_pause,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _blob(msg) -> str:
        return f"{getattr(msg, 'subject', '') or ''}\n{getattr(msg, 'body', '') or ''}"

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _subs(p: Probe) -> dict:
        shop = getattr(p.world, "shop", None) if p.world else None
        return dict(shop.subscriptions or {}) if shop else {}

    def _checked_trip(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar") or _log_has(p, "viewed_event_edit"):
            return True
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if ("july 20" in text or "jul 20" in text or "20th" in text) and (
                "aug" in text or "august" in text or "two weeks" in text or "vacation" in text
            ):
                return True
        return False

    def _checked_each_next(p: Probe) -> bool:
        if _log_has(p, "view_subscriptions"):
            return True
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if "july 25" in text or "jul 25" in text:
                if "aug" in text or "august 10" in text or "aug 10" in text:
                    return True
        # Durable: paused conflict implies inspected next dates.
        s = _subs(p).get(SUB_CONFLICT)
        return bool(s and getattr(s, "status", "") == "paused")

    def _paused_only_conflict(p: Probe) -> bool:
        subs = _subs(p)
        conflict = subs.get(SUB_CONFLICT)
        safe = subs.get(SUB_SAFE)
        if not conflict or getattr(conflict, "status", "") != "paused":
            return False
        if not safe or getattr(safe, "status", "") != "active":
            return False
        return True

    def _did_not_touch_cancelled(p: Probe) -> bool:
        s = _subs(p).get(SUB_CANCELLED)
        if not s:
            return False
        # Still cancelled; no pause/reactivate. Gate on having paused the conflict
        # so FOI does not credit this milestone.
        conflict = _subs(p).get(SUB_CONFLICT)
        if not conflict or getattr(conflict, "status", "") != "paused":
            return False
        return getattr(s, "status", "") == "cancelled"

    def _emailed_summary(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if "pause" in text and ("coffee" in text or "sub-mp107-coffee" in text or "pod" in text):
                return True
            if "paused" in text and ("subscription" in text or "subscribe" in text):
                return True
        return False

    def _paused_safe(p: Probe) -> bool:
        s = _subs(p).get(SUB_SAFE)
        return bool(s and getattr(s, "status", "") == "paused")

    def _modified_cancelled(p: Probe) -> bool:
        s = _subs(p).get(SUB_CANCELLED)
        if not s:
            return False
        return getattr(s, "status", "") != "cancelled"

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_trip_dates_from_calendar",
                    weight=0.2, check=_checked_trip, required_for_success=True,
                ),
                Milestone(
                    "checked_each_subscriptions_next_delivery_date",
                    weight=0.3, check=_checked_each_next, required_for_success=True,
                ),
                Milestone(
                    "paused_only_the_conflicting_subscription",
                    weight=0.3, check=_paused_only_conflict, required_for_success=True,
                ),
                Milestone(
                    "did_not_touch_already_cancelled_subscription",
                    weight=0.1, check=_did_not_touch_cancelled, required_for_success=True,
                ),
                Milestone(
                    "emailed_summary_of_what_was_paused",
                    weight=0.1, check=_emailed_summary, required_for_success=True,
                ),
                Milestone(
                    "paused_subscription_delivering_after_return",
                    weight=0.0, check=_paused_safe, forbidden=True,
                ),
                Milestone(
                    "modified_already_cancelled_subscription",
                    weight=0.0, check=_modified_cancelled, forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
