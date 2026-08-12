"""mp_069 / mail_thread_promise_vs_valuemart_listing_reality.

Mechanism: neighbor's ShopMail promise includes a helmet; live ValueMart
listing is bike stand only. Correct = buy what's listed + follow up about
the helmet discrepancy (do not invent a bundled helmet).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_069/mail_thread_promise_vs_valuemart_listing_reality"
BRIEF_KEY = "mp_069"
BRIEF = (
    "My neighbor's selling her bike stand on ValueMart, she said she'd throw "
    "in the helmet too, can you grab it and confirm with her."
)

USER_EMAIL = "alice@shopmail.com"
NEIGHBOR_EMAIL = "jordan.neighbor@email.com"
GYM_NOW = "2026-05-21T12:00:00"

STAND_ID = "vm_mp069_bike_stand"
STAND_NAME = "Wall-Mount Bike Stand"
STAND_PRICE = 48.00

EM_PROMISE = "em_mp069_neighbor_offer"
EM_NOISE = "em_mp069_noise"


def task_mp_069_mail_thread_promise_vs_valuemart_listing_reality(
    seed: int,
) -> "WorldState":
    """FEASIBLE Mail×VM: buy listing-only stand; message helmet gap."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events["ev_mp069_noise"] = CalendarEvent(
        id="ev_mp069_noise",
        title="Errands",
        day="2026-05-22",
        day_label="Fri May 22",
        start="17:00",
        end="18:00",
        source="seed",
    )

    market = world.market
    market.products.clear()
    market.cart.items.clear()
    market.orders.clear()
    market.products[STAND_ID] = MarketProduct(
        id=STAND_ID,
        name=STAND_NAME,
        category="sports",
        price=STAND_PRICE,
        emoji="🚲",
        description=(
            f"{STAND_NAME} — steel wall mount for one bike. Listing includes "
            "the stand and mounting hardware ONLY. No accessories bundled."
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=0.0,
        seller_id="seller_mp069_jordan",
        seller_username="jordan_apt4b",
        seller_feedback_score=42,
        seller_feedback_rating=100.0,
        brand="RideRack",
    )
    # Decoy helmet listing — must NOT be purchased as "the throw-in".
    market.products["vm_mp069_helmet_decoy"] = MarketProduct(
        id="vm_mp069_helmet_decoy",
        name="City Bike Helmet (separate listing)",
        category="sports",
        price=28.00,
        emoji="⛑️",
        description="Separate helmet listing — not part of the bike stand sale.",
        in_stock=True,
        condition="Used - Good",
        shipping_cost=5.0,
        seller_username="other_seller_x",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[EM_PROMISE] = Email(
        id=EM_PROMISE,
        sender=NEIGHBOR_EMAIL,
        to=USER_EMAIL,
        subject="bike stand on ValueMart",
        body=(
            "hey! I listed my wall-mount bike stand on ValueMart under "
            "jordan_apt4b. If you grab it I'll throw in my old helmet too — "
            "it's in the closet, I just haven't added it to the listing yet. "
            "Ping me once you've bought it so I know to leave the helmet out."
        ),
        received_at=f"{SEED_DATE}T09:20:00",
        received_label="9:20 AM",
        read=False,
        labels=["personal", "unread"],
    )
    mail.inbox[EM_NOISE] = Email(
        id=EM_NOISE,
        sender="deals@valuemart.com",
        to=USER_EMAIL,
        subject="Cycling accessories on sale",
        body="Helmets and lights 20% off this week.",
        received_at="2026-05-20T15:00:00",
        received_label="May 20",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_069_mail_thread_promise_vs_valuemart_listing_reality,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.market.orders or {})
            if init and getattr(init, "market", None) else {}
        )
        return [
            o for oid, o in (market.orders or {}).items() if oid not in init_ids
        ]

    def _bought_stand_only(p: Probe) -> bool:
        orders = _new_orders(p)
        if not orders:
            return False
        saw_stand = False
        for o in orders:
            for it in getattr(o, "items", []) or []:
                pid = getattr(it, "product_id", "") or ""
                name = (getattr(it, "name", "") or "").lower()
                if pid == STAND_ID or ("bike" in name and "stand" in name):
                    saw_stand = True
                if "helmet" in name or pid == "vm_mp069_helmet_decoy":
                    return False
        return saw_stand

    def _bought_helmet(p: Probe) -> bool:
        for o in _new_orders(p):
            for it in getattr(o, "items", []) or []:
                pid = getattr(it, "product_id", "") or ""
                name = (getattr(it, "name", "") or "").lower()
                if "helmet" in name or pid == "vm_mp069_helmet_decoy":
                    return True
        return False

    def _checked_listing(p: Probe) -> bool:
        if _log_has(p, "view_product", product_id=STAND_ID):
            return True
        url = (p.active_tab_url or p.url or "")
        return STAND_ID in url

    def _messaged_discrepancy(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        needles = (
            "helmet", "listing", "not included", "doesn't include",
            "does not include", "only the stand", "stand only",
            "not on the listing", "discrepan", "missing from",
            "didn't add", "did not add", "throw in",
        )
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if NEIGHBOR_EMAIL not in to and "jordan" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if any(n in text for n in needles):
                return True
        return False

    def _assumed_helmet(p: Probe) -> bool:
        if _bought_helmet(p):
            return True
        # Claimed helmet included to alice without followup to neighbor.
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        if _messaged_discrepancy(p):
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if "helmet" in text and (
                "included" in text or "got the helmet" in text
                or "threw in" in text or "with the helmet" in text
            ):
                if USER_EMAIL in to or "alice" in to:
                    return True
        return False

    def _no_followup(p: Probe) -> bool:
        """Bought stand but never messaged neighbor about the gap."""
        if not _bought_stand_only(p):
            return False
        return not _messaged_discrepancy(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_actual_listing_contents",
                    weight=0.3,
                    check=_checked_listing,
                    required_for_success=True,
                ),
                Milestone(
                    "purchased_only_whats_actually_listed",
                    weight=0.3,
                    check=_bought_stand_only,
                    required_for_success=True,
                ),
                Milestone(
                    "messaged_neighbor_about_helmet_discrepancy",
                    weight=0.4,
                    check=_messaged_discrepancy,
                    required_for_success=True,
                ),
                Milestone(
                    "assumed_helmet_included_without_checking",
                    weight=0.0,
                    check=_assumed_helmet,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "no_followup_on_discrepancy",
                    weight=0.0,
                    check=_no_followup,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
