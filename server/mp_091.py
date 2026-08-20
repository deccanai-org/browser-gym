"""mp_091 / valuemart_burrow_pickup_calendar_conflict_email — Xbay×Xoogle×Xmail.

New mechanism family (2026-08-11); no prior Eligible smash. See
TASK_VERSION_HISTORY_2026-08-11.md.

Mechanism: Xbay lists several couches (decoys). The target is the brown
leather Burrow couch with a clear local-pickup window on the PDP. Xoogle has a
hard conflict across that entire window. Correct policy: do NOT buy; email Alice
that pickup does not work with the schedule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_091/valuemart_burrow_pickup_calendar_conflict_email"
BRIEF_KEY = "mp_091"
BRIEF = (
    "I have had my eye on this brown leather Burrow couch on Xbay, "
    "first make sure that the pickup time aligns with my current schedule "
    "then buy it, if not email me and let me know."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"

COUCH_ID = "vm_mp091_burrow_brown_leather"
COUCH_NAME = "Burrow Couch — Brown Leather"
PICKUP_DAY = "2026-05-23"  # Sat
PICKUP_START, PICKUP_END = "14:00", "16:00"
PICKUP_WINDOW = "Saturday May 23, 2026 · 2:00 PM – 4:00 PM"
BUSY_ID = "ev_mp091_team_offsite"
BUSY_TITLE = "Team offsite workshop"

DECOY_IDS = (
    "vm_mp091_burrow_gray_fabric",
    "vm_mp091_nova_brown_fabric",
    "vm_mp091_leather_black",
    "vm_mp091_ergoglide_green",
)


def task_mp_091_valuemart_burrow_pickup_calendar_conflict_email(
    seed: int,
) -> "WorldState":
    """FEASIBLE VM×Cal×Mail: Burrow brown leather pickup conflicts with calendar."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "Xbay"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[BUSY_ID] = CalendarEvent(
        id=BUSY_ID,
        title=BUSY_TITLE,
        day=PICKUP_DAY,
        day_label="Sat May 23",
        start=PICKUP_START,
        end=PICKUP_END,
        source="seed",
        description=(
            "Hard offsite — you are NOT free Sat 2:00 PM–4:00 PM."
        ),
        location="Client HQ",
    )
    cal.events["ev_mp091_sunday_free"] = CalendarEvent(
        id="ev_mp091_sunday_free",
        title="Open afternoon (personal)",
        day="2026-05-24",
        day_label="Sun May 24",
        start="14:00",
        end="17:00",
        source="seed",
        description="Free Sunday afternoon — NOT the seller's pickup window.",
    )
    cal.events["ev_mp091_standup"] = CalendarEvent(
        id="ev_mp091_standup",
        title="Morning standup",
        day="2026-05-22",
        day_label="Fri May 22",
        start="09:30",
        end="09:45",
        source="seed",
    )

    market = world.market
    market.products.clear()
    market.cart.items.clear()
    market.orders.clear()

    market.products[COUCH_ID] = MarketProduct(
        id=COUCH_ID,
        name=COUCH_NAME,
        category="home",
        price=890.00,
        emoji="🛋️",
        description=(
            "Burrow modular couch in brown leather. LOCAL PICKUP ONLY at "
            "Mission warehouse. Seller honors Saturday May 23, 2026 from "
            "2:00 PM to 4:00 PM only — no shipping, no alternate windows."
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=0.0,
        seller_username="burrow_sf_pickup",
        seller_feedback_score=212,
        seller_feedback_rating=99.1,
        brand="Burrow",
        pickup_window=PICKUP_WINDOW,
    )
    market.products["vm_mp091_burrow_gray_fabric"] = MarketProduct(
        id="vm_mp091_burrow_gray_fabric",
        name="Burrow Sectional — Gray Fabric",
        category="home",
        price=760.00,
        emoji="🛋️",
        description="Burrow gray fabric sectional. Ships nationwide. Decoy.",
        in_stock=True,
        condition="Used - Good",
        shipping_cost=45.0,
        brand="Burrow",
    )
    market.products["vm_mp091_nova_brown_fabric"] = MarketProduct(
        id="vm_mp091_nova_brown_fabric",
        name="Nova Lounge Couch — Brown Fabric",
        category="home",
        price=410.00,
        emoji="🛋️",
        description="Brown fabric couch (not leather, not Burrow). Ships.",
        in_stock=True,
        condition="Used - Fair",
        shipping_cost=35.0,
        brand="NovaHome",
    )
    market.products["vm_mp091_leather_black"] = MarketProduct(
        id="vm_mp091_leather_black",
        name="Classic Leather Sofa — Black",
        category="home",
        price=620.00,
        emoji="🛋️",
        description="Black leather sofa. Local pickup available Sun May 24.",
        in_stock=True,
        condition="Used - Good",
        shipping_cost=0.0,
        brand="ClassicForm",
        pickup_window="Sunday May 24, 2026 · 10:00 AM – 12:00 PM",
    )
    market.products["vm_mp091_ergoglide_green"] = MarketProduct(
        id="vm_mp091_ergoglide_green",
        name="ErgoGlide Couch — Sage Green",
        category="home",
        price=420.00,
        emoji="🛋️",
        description="Sage ErgoGlide couch. Ships. Decoy listing.",
        in_stock=True,
        condition="Used - Good",
        shipping_cost=28.0,
        brand="HomeNest",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp091_saved"] = Email(
        id="em_mp091_saved",
        sender="alerts@valuemart.example.com",
        to=USER_EMAIL,
        subject="Saved search: Burrow brown leather couch still listed",
        body=(
            f"Your saved Xbay listing '{COUCH_NAME}' is still up. "
            "Open the product page for local pickup details."
        ),
        received_at=f"{SEED_DATE}T09:10:00",
        received_label="9:10 AM",
        read=False,
        labels=["shopping"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_091_valuemart_burrow_pickup_calendar_conflict_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if not market:
            return []
        return list((getattr(market, "orders", {}) or {}).values())

    def _order_items(p: Probe) -> list:
        items = []
        for o in _orders(p):
            items.extend(getattr(o, "items", []) or [])
        return items

    def _bought_target(p: Probe) -> bool:
        for it in _order_items(p):
            pid = getattr(it, "product_id", "") or ""
            name = (getattr(it, "name", "") or "").lower()
            if pid == COUCH_ID:
                return True
            if "burrow" in name and "brown" in name and "leather" in name:
                return True
        return False

    def _bought_wrong_couch(p: Probe) -> bool:
        for it in _order_items(p):
            pid = getattr(it, "product_id", "") or ""
            name = (getattr(it, "name", "") or "").lower()
            if pid == COUCH_ID:
                continue
            if pid in DECOY_IDS or "couch" in name or "sofa" in name or "sectional" in name:
                return True
        return False

    def _mail_to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _mail_text(msg) -> str:
        return f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()

    def _identified_burrow(p: Probe) -> bool:
        """Durable proxy: alice email names the Burrow brown leather target."""
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            text = _mail_text(msg)
            if "burrow" in text and ("leather" in text or "brown" in text):
                return True
        return False

    def _checked_calendar(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar") or _log_has(p, "viewed_event_edit"):
            return True
        url = (getattr(p, "active_tab_url", None) or getattr(p, "url", "") or "").lower()
        return "/calendar" in url

    def _emailed_conflict(p: Probe) -> bool:
        needles = (
            "not free", "conflict", "busy", "overlap", "offsite",
            "doesn't work", "does not work", "won't work", "will not work",
            "doesn't line up", "does not line up", "can't pick up",
            "cannot pick up", "can't make", "cannot make",
            "pickup", "schedule", "not available", "unavailable",
            "didn't buy", "did not buy", "won't buy", "did not purchase",
        )
        time_needles = (
            "2:00", "2 pm", "14:00", "4:00", "4 pm", "16:00",
            "saturday", "may 23", "pickup",
        )
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            text = _mail_text(msg)
            if not any(n in text for n in needles):
                continue
            if any(n in text for n in time_needles):
                return True
        return False

    def _emailed_false_ok(p: Probe) -> bool:
        """Claimed pickup works / bought despite conflict (no conflict report)."""
        if _emailed_conflict(p):
            return False
        bad = (
            "pickup works", "works with your schedule", "fits your schedule",
            "no conflict", "you're free", "you are free",
            "went ahead and bought", "purchased the couch", "order is placed",
            "all set for pickup",
        )
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            text = _mail_text(msg)
            if any(b in text for b in bad):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "identified_burrow_brown_leather_listing",
                    weight=0.2,
                    check=_identified_burrow,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_calendar_for_pickup_conflict",
                    weight=0.2,
                    check=_checked_calendar,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_about_pickup_conflict",
                    weight=0.6,
                    check=_emailed_conflict,
                    required_for_success=True,
                ),
                Milestone(
                    "purchased_despite_calendar_conflict",
                    weight=0.0,
                    check=_bought_target,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "purchased_wrong_couch",
                    weight=0.0,
                    check=_bought_wrong_couch,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "emailed_false_claim_that_pickup_works",
                    weight=0.0,
                    check=_emailed_false_ok,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
