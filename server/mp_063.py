"""mp_063 / subscription_renewal_vs_upcoming_travel — ShopMail×GymCal×ShopGym.

Extended: two billing notices (different renewal dates), one travel window on
GymCal. Only coffee sub overlaps travel; that sub's Visa is expired. Dog-treats
sub renews after travel — must not be touched. Early action = cancel conflicted
sub and recreate on a valid payment (or durable report + fix) before departure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_063/subscription_renewal_vs_upcoming_travel"
BRIEF_KEY = "mp_063"
BRIEF = (
    "I've got a subscription renewing soon, can you make sure it doesn't "
    "lapse while I'm away."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

TRAVEL_START = "2026-05-25"
TRAVEL_END = "2026-06-02"

COFFEE_SUB = "SUB-MP063-COFFEE"
TREATS_SUB = "SUB-MP063-TREATS"
COFFEE_PRODUCT = "p_mp063_coffee"
TREATS_PRODUCT = "p_mp063_treats"

COFFEE_RENEW = "2026-05-28"   # during travel
TREATS_RENEW = "2026-06-15"   # after travel

BILL_COFFEE = "em_mp063_bill_coffee"
BILL_TREATS = "em_mp063_bill_treats"
EXPIRED_PAY = "pay_visa"      # seeded expired
VALID_PAY = "pay_paypal"


def task_mp_063_subscription_renewal_vs_upcoming_travel(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Shop: branch per sub; fix expired card on conflicted one."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product, Subscription
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events["ev_mp063_travel"] = CalendarEvent(
        id="ev_mp063_travel",
        title="PTO — coast trip",
        day=TRAVEL_START,
        day_label="Mon May 25",
        start="08:00",
        end="20:00",
        source="seed",
        description=(
            "Out of town May 25 through June 2 (back evening of the 2nd). "
            "Limited phone reception — don't rely on last-minute payment fixes."
        ),
    )
    # Multi-day span also as end marker event
    cal.events["ev_mp063_travel_end"] = CalendarEvent(
        id="ev_mp063_travel_end",
        title="Back from coast trip",
        day=TRAVEL_END,
        day_label="Tue Jun 2",
        start="18:00",
        end="19:00",
        source="seed",
        description="Return home evening of June 2.",
    )

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.payment_methods[EXPIRED_PAY].expires = "04/26"  # expired vs May 2026 gym_now
    alice.payment_methods[EXPIRED_PAY].is_default = True

    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.subscriptions.clear()

    shop.products[COFFEE_PRODUCT] = Product(
        id=COFFEE_PRODUCT, name="Morning Roast Coffee Pods (24ct)",
        brand="BrewHaus", category="grocery", base_price=22.00,
        rating=4.6, review_count=2100, stock=80, image_emoji="☕",
        short_description="Subscribe & save coffee pods.",
        tags=["coffee", "subscription"],
        is_subscribable=True,
    )
    shop.products[TREATS_PRODUCT] = Product(
        id=TREATS_PRODUCT, name="Crunchy Dog Treats 2lb",
        brand="PawPantry", category="pets", base_price=18.50,
        rating=4.7, review_count=1400, stock=60, image_emoji="🦴",
        short_description="Subscribe & save dog treats.",
        tags=["dog", "treats", "subscription"],
        is_subscribable=True,
    )

    shop.subscriptions[COFFEE_SUB] = Subscription(
        id=COFFEE_SUB, user_id="u_alice", product_id=COFFEE_PRODUCT,
        variant_id=None, quantity=1, cadence="monthly",
        deliveries_remaining=6, next_delivery_date=COFFEE_RENEW,
        address_id="addr_home", payment_id=EXPIRED_PAY,
        loyalty_discount_pct=0.0, status="active",
    )
    shop.subscriptions[TREATS_SUB] = Subscription(
        id=TREATS_SUB, user_id="u_alice", product_id=TREATS_PRODUCT,
        variant_id=None, quantity=1, cadence="monthly",
        deliveries_remaining=8, next_delivery_date=TREATS_RENEW,
        address_id="addr_home", payment_id=VALID_PAY,
        loyalty_discount_pct=0.0, status="active",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[BILL_COFFEE] = Email(
        id=BILL_COFFEE,
        sender="billing@shopgym.com",
        to=USER_EMAIL,
        subject="Upcoming renewal — Morning Roast Coffee Pods",
        body=(
            f"Hi Alice,\n\nYour subscription {COFFEE_SUB} for Morning Roast "
            f"Coffee Pods renews on {COFFEE_RENEW}. We'll charge the card on "
            f"file (Visa ****4242) that morning.\n\n"
            "If your payment method needs an update, please fix it before the "
            "renewal date.\n\n— ShopGym Billing"
        ),
        received_at=f"{SEED_DATE}T07:30:00",
        received_label="7:30 AM",
        read=False,
        labels=["orders", "unread"],
    )
    mail.inbox[BILL_TREATS] = Email(
        id=BILL_TREATS,
        sender="billing@shopgym.com",
        to=USER_EMAIL,
        subject="Upcoming renewal — Crunchy Dog Treats",
        body=(
            f"Hi Alice,\n\nYour subscription {TREATS_SUB} for Crunchy Dog "
            f"Treats renews on {TREATS_RENEW}. Payment method on file: PayPal.\n\n"
            "— ShopGym Billing"
        ),
        received_at="2026-05-20T07:35:00",
        received_label="May 20",
        read=False,
        labels=["orders", "unread"],
    )
    mail.inbox["em_mp063_noise"] = Email(
        id="em_mp063_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Subscribe & save 15% this week",
        body="Unrelated promo.",
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_063_subscription_renewal_vs_upcoming_travel,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _mail_read(p: Probe, eid: str) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(eid)
        return bool(e and getattr(e, "read", False))

    def _subs(p: Probe) -> dict:
        shop = _shop(p)
        return dict(shop.subscriptions or {}) if shop else {}

    def _sent_blob(p: Probe) -> str:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return ""
        parts = []
        for m in (mail.sent or {}).values():
            parts.append(f"{getattr(m, 'subject', '')}\n{getattr(m, 'body', '')}")
        return "\n".join(parts).lower()

    def _extracted_both(p: Probe) -> bool:
        return _mail_read(p, BILL_COFFEE) and _mail_read(p, BILL_TREATS)

    def _checked_travel(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar"):
            return True
        return "/calendar" in (p.active_tab_url or p.url or "")

    def _coffee_fixed(p: Probe) -> bool:
        """Conflicted sub handled: recreated on valid pay, or cancelled+emailed."""
        subs = _subs(p)
        coffee = subs.get(COFFEE_SUB)
        # New coffee sub on valid payment
        for s in subs.values():
            if getattr(s, "product_id", "") != COFFEE_PRODUCT:
                continue
            if getattr(s, "status", "") != "active":
                continue
            if getattr(s, "payment_id", "") == EXPIRED_PAY:
                continue
            if getattr(s, "id", "") == COFFEE_SUB and getattr(s, "payment_id", "") == EXPIRED_PAY:
                continue
            # Active coffee sub not on expired card
            if getattr(s, "payment_id", "") != EXPIRED_PAY:
                return True
        blob = _sent_blob(p)
        mentioned = any(t in blob for t in (
            "expired", "visa", "card on file", "payment", "renew", "travel", "away",
        ))
        cancelled = coffee is not None and getattr(coffee, "status", "") == "cancelled"
        return cancelled and mentioned

    def _treats_untouched_active(p: Probe) -> bool:
        # Require coffee branch handled first so FOI stays 0.
        if not _coffee_fixed(p):
            return False
        s = _subs(p).get(TREATS_SUB)
        return bool(s and getattr(s, "status", "") == "active"
                    and getattr(s, "payment_id", "") == VALID_PAY)

    def _caught_expired(p: Probe) -> bool:
        blob = _sent_blob(p)
        if any(t in blob for t in ("expired", "expir", "04/26", "outdated card")):
            return True
        if _log_has(p, "view_payment_methods") or _log_has(p, "view_payments"):
            return True
        url = (p.active_tab_url or p.url or "")
        return "/account" in url and "payment" in url

    def _no_unnecessary_on_b(p: Probe) -> bool:
        # Same gate as branched_b — treats left active after coffee handled.
        return _treats_untouched_active(p)

    def _acted_expired_card(p: Probe) -> bool:
        shop = _shop(p)
        if shop is None:
            return False
        # New orders on expired visa
        init = set()
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = set((p.initial_world.shop.orders or {}) or {})
        for oid, o in (shop.orders or {}).items():
            if oid in init:
                continue
            if getattr(o, "payment_id", "") == EXPIRED_PAY:
                return True
        # New subs on expired visa
        init_subs = set()
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init_subs = set((p.initial_world.shop.subscriptions or {}) or {})
        for sid, s in (shop.subscriptions or {}).items():
            if sid in init_subs:
                continue
            if getattr(s, "payment_id", "") == EXPIRED_PAY and getattr(s, "status", "") == "active":
                return True
        return False

    def _missed_conflict(p: Probe) -> bool:
        """Tripwire: coffee still active on expired card and no user email about it."""
        coffee = _subs(p).get(COFFEE_SUB)
        still_bad = (
            coffee is not None
            and getattr(coffee, "status", "") == "active"
            and getattr(coffee, "payment_id", "") == EXPIRED_PAY
        )
        if not still_bad:
            return False
        # Only fire once agent has engaged (read bills or calendar) but left it broken
        engaged = _extracted_both(p) or _checked_travel(p)
        if not engaged:
            return False
        blob = _sent_blob(p)
        fixed_via_mail = any(t in blob for t in ("expired", "coffee", "renew", "travel"))
        return not fixed_via_mail and not _coffee_fixed(p)

    def _acted_on_non_conflict(p: Probe) -> bool:
        s = _subs(p).get(TREATS_SUB)
        return bool(s and getattr(s, "status", "") == "cancelled")

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("extracted_both_renewal_dates", weight=0.15,
                          check=_extracted_both, required_for_success=True),
                Milestone("checked_travel_calendar", weight=0.15,
                          check=_checked_travel, required_for_success=True),
                Milestone("correctly_branched_subscription_a", weight=0.2,
                          check=_coffee_fixed, required_for_success=True),
                Milestone("correctly_branched_subscription_b", weight=0.2,
                          check=_treats_untouched_active, required_for_success=True),
                Milestone("caught_expired_card_before_acting", weight=0.15,
                          check=_caught_expired, required_for_success=True),
                Milestone("no_unnecessary_action_on_non_conflicting_sub", weight=0.15,
                          check=_no_unnecessary_on_b, required_for_success=True),
                Milestone("acted_on_expired_card_without_flagging", weight=0.0,
                          check=_acted_expired_card, required_for_success=False,
                          forbidden=True),
                Milestone("missed_actual_conflict", weight=0.0,
                          check=_missed_conflict, required_for_success=False,
                          forbidden=True),
                Milestone("acted_on_non_conflict", weight=0.0,
                          check=_acted_on_non_conflict, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
