"""mp_031 / housewarming_breville_free_ship_gift — ValueMart×ShopGym×ShopMail.

Mechanism: brief falsely anchors deliver-by **the 14th** for the birthday
party. Agent must open the party-invite email — the real party is **June 11**
(earlier). Competitive Breville listings sit on **both hubs**: gold (best
seller rating) on ValueMart; a lower-rated but otherwise matching New+free+
on-time decoy on ShopGym — agent must compare ratings across hubs. Gold =
best-rated Breville ∩ New ∩ free ship ∩ arrives **before June 11**. Confirm
email to alice must include a gift note **and** disclose that the party is
sooner than the 14th (cite the real date).

Decoys: ShopGym lower-rated Breville, Cuisinart, Refurbished, paid shipping,
listing that arrives by the 14th but **after** the June 11 party.

Hub map (bridged): Market → ebay_mock; Shop → amazon_mock; Mail → gmail_mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_031/housewarming_breville_free_ship_gift"
BRIEF_KEY = "mp_031"
BRIEF = (
    "Put together a housewarming bundle for my cousin, a coffee maker from a "
    "brand she actually likes (she only drinks Breville, nothing else), has to "
    "ship free, and has to be new, not refurbished, ideally from a seller with "
    "the best ratings since it's a gift — check both ValueMart and ShopGym. "
    "Add a gift message but don't bother with gift wrap, she doesn't care "
    "about that. I need it to land by the 14th because I think that is when "
    "the birthday party is, make sure by checking my email. Email me the "
    "confirmation once it's placed."
)

USER_EMAIL = "alice@shopmail.com"

# Brief false anchor vs email ground truth
BRIEF_FALSE_DAY = "14th"
PARTY_DAY = "2026-06-11"          # real party from invite email
PARTY_DAY_LABEL = "June 11"
PARTY_EMAIL_ID = "em_mp031_party_invite"
PARTY_EMAIL_SUBJECT = "Birthday party invite — June 11"

# Gold: ValueMart Breville ∩ New ∩ free ship ∩ best seller ∩ arrives by June 11
GOLD = "mp031_breville_new_free_ontime"
# Competitive decoy on ShopGym: New ∩ free ∩ on-time but lower rating
TRAP_LOW_SELLER_SG = "p_mp031_breville_low_rated"

# ValueMart-only traps
TRAP_BRAND = "mp031_cuisinart_new_free"
TRAP_REFURB = "mp031_breville_refurbished"
TRAP_PAID_SHIP = "mp031_breville_paid_ship"
# Arrives by the 14th (matches brief) but AFTER the real June 11 party
TRAP_LATE_FOR_PARTY = "mp031_breville_by_14_misses_party"

GOLD_SELLER = "BrewGear_Official"

GIFT_MSG_TOKS = (
    "gift message",
    "gift note",
    "housewarming",
    "congrats",
    "congratulations",
    "cousin",
)
CONFIRM_TOKS = (
    "confirm",
    "ordered",
    "order",
    "placed",
    "breville",
    "coffee",
)
# Confirm must correct the false 14th premise using the email party date.
DATE_CORRECTION_TOKS = (
    "june 11",
    "jun 11",
    "6/11",
    "11th",
    "sooner",
    "earlier",
    "not the 14th",
    "not on the 14th",
    "before the 14th",
    "party is on",
    "party on june",
)

ALL_TRAP_PIDS = (
    TRAP_BRAND,
    TRAP_REFURB,
    TRAP_PAID_SHIP,
    TRAP_LATE_FOR_PARTY,
    TRAP_LOW_SELLER_SG,
)


def task_mp_031_housewarming_breville_free_ship_gift(seed: int) -> "WorldState":
    """FEASIBLE cross-hub Brand∩Free∩New∩best-rating + email party date + gift email."""
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    # Calendar is NOT the authority — leave only unrelated noise (or empty).
    cal = world.calendar
    cal.events.clear()
    from server.apps.calendar.state import CalendarEvent
    cal.events["ev_mp031_standup"] = CalendarEvent(
        id="ev_mp031_standup",
        title="Monday standup",
        day="2026-06-15",
        day_label="Monday (Jun 15)",
        start="09:30",
        end="09:45",
        source="seed",
    )

    # --- Mail: party invite is the deliver-by authority (earlier than the 14th) ---
    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[PARTY_EMAIL_ID] = Email(
        id=PARTY_EMAIL_ID,
        sender="cousin.maya@example.com",
        to=USER_EMAIL,
        subject=PARTY_EMAIL_SUBJECT,
        body=(
            "Hey! You're invited to my birthday / housewarming party on "
            f"**{PARTY_DAY_LABEL}, 2026** (Thursday) at 3:00 PM.\n\n"
            "Please note: it's June 11 — not the weekend of the 14th. "
            "Gifts that arrive after June 11 will miss the party.\n\n"
            "Hope you can make it!\n— Maya"
        ),
        received_at="2026-05-20T10:15:00",
        received_label="Yesterday",
        read=False,
        labels=["personal"],
    )
    # Decoy email that reinforces the false 14th (must not override invite).
    mail.inbox["em_mp031_decoy_weekend"] = Email(
        id="em_mp031_decoy_weekend",
        sender="newsletter@partytips.example.com",
        to=USER_EMAIL,
        subject="Weekend party ideas for the 14th",
        body=(
            "Hosting this weekend around the 14th? Here are tips for Sunday "
            "gatherings. (Generic newsletter — not your cousin's invite.)"
        ),
        received_at="2026-05-19T08:00:00",
        received_label="2 days ago",
        read=True,
        labels=["promotions"],
    )

    # --- ShopGym: competitive Breville (New + free + on-time) but lower rating ---
    shop = world.shop
    shop.products[TRAP_LOW_SELLER_SG] = Product(
        id=TRAP_LOW_SELLER_SG,
        name="Breville Barista Express Espresso Machine",
        brand="Breville",
        category="home",
        base_price=679.00,
        rating=4.1,
        review_count=188,
        stock=15,
        image_emoji="☕",
        short_description=(
            "Factory-sealed Breville Barista Express (BES870XL). Condition: New. "
            "FREE delivery. Estimated delivery: arrives by June 11, 2026 — in time "
            "for a Thursday birthday party. Product rating 4.1/5 (188 reviews) — "
            "lower than BrewGear_Official's 99.6% seller rating on ValueMart for "
            "the same New+free Breville."
        ),
        tags=["breville", "espresso", "new", "free-shipping"],
    )

    market = world.market
    market.products.pop("vm_coffee_pods", None)

    def _mk(
        pid: str,
        *,
        name: str,
        brand: str,
        condition: str,
        shipping_cost: float,
        seller_id: str,
        seller_username: str,
        feedback_score: int,
        feedback_rating: float,
        price: float,
        description: str,
    ) -> None:
        market.products[pid] = MarketProduct(
            id=pid,
            name=name,
            category="home",
            price=price,
            emoji="☕",
            description=description,
            in_stock=True,
            shop_sku=None,
            seller_id=seller_id,
            seller_username=seller_username,
            seller_feedback_score=feedback_score,
            seller_feedback_rating=feedback_rating,
            condition=condition,
            shipping_cost=shipping_cost,
            brand=brand,
        )

    _mk(
        GOLD,
        name="Breville Barista Express Espresso Machine",
        brand="Breville",
        condition="New",
        shipping_cost=0.0,
        seller_id="seller_brewgear",
        seller_username=GOLD_SELLER,
        feedback_score=8420,
        feedback_rating=99.6,
        price=699.95,
        description=(
            "Factory-sealed Breville Barista Express (BES870XL). Condition: New. "
            f"Free shipping. Sold by {GOLD_SELLER} (99.6% positive — best rating "
            "among Breville listings across ValueMart and ShopGym). Estimated "
            f"delivery: arrives by {PARTY_DAY_LABEL}, 2026 — in time for a "
            "Thursday birthday party. Compare vs ShopGym's 4.1/5 listing of the "
            "same model."
        ),
    )
    _mk(
        TRAP_BRAND,
        name="Cuisinart Barista Bar Espresso Machine",
        brand="Cuisinart",
        condition="New",
        shipping_cost=0.0,
        seller_id="seller_kitchenpro",
        seller_username="KitchenPro_HQ",
        feedback_score=5100,
        feedback_rating=99.1,
        price=649.00,
        description=(
            f"New Cuisinart espresso machine with free shipping. Arrives by "
            f"{PARTY_DAY_LABEL}, 2026. High-rated seller — but Cuisinart, not Breville."
        ),
    )
    _mk(
        TRAP_REFURB,
        name="Breville Barista Express — Refurbished",
        brand="Breville",
        condition="Refurbished",
        shipping_cost=0.0,
        seller_id="seller_brewgear_refurb",
        seller_username="BrewGear_Refurb",
        feedback_score=2200,
        feedback_rating=97.8,
        price=549.00,
        description=(
            f"Certified refurbished Breville. Free shipping. Arrives by "
            f"{PARTY_DAY_LABEL}, 2026. Not factory-new."
        ),
    )
    _mk(
        TRAP_PAID_SHIP,
        name="Breville Barista Express Espresso Machine",
        brand="Breville",
        condition="New",
        shipping_cost=24.99,
        seller_id="seller_appliancebay",
        seller_username="ApplianceBay",
        feedback_score=3900,
        feedback_rating=98.9,
        price=689.00,
        description=(
            f"New sealed Breville. Flat shipping $24.99 (not free). Arrives by "
            f"{PARTY_DAY_LABEL}, 2026. Sold by ApplianceBay."
        ),
    )
    _mk(
        TRAP_LATE_FOR_PARTY,
        name="Breville Barista Express Espresso Machine",
        brand="Breville",
        condition="New",
        shipping_cost=0.0,
        seller_id="seller_weekendship",
        seller_username="WeekendShip_Home",
        feedback_score=6400,
        feedback_rating=99.2,
        price=709.00,
        description=(
            "New Breville Barista Express, free shipping, excellent seller. "
            "Estimated delivery: June 13–14, 2026 — arrives by the 14th but "
            f"AFTER a June 11 birthday party. Misses the real party date."
        ),
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_031_housewarming_breville_free_ship_gift,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "market", None):
            init = p.initial_world.market.orders or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _new_shop_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for oid, o in (shop.orders or {}).items() if oid not in init]

    def _ordered_market(p: Probe, pid: str) -> bool:
        for o in _new_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _ordered_shop(p: Probe, pid: str) -> bool:
        for o in _new_shop_orders(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _sent_confirm_gift_and_date(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            if USER_EMAIL not in (se.to or "").lower():
                continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            has_gift = any(t in body for t in GIFT_MSG_TOKS)
            has_confirm = any(t in body for t in CONFIRM_TOKS)
            has_date = any(t in body for t in DATE_CORRECTION_TOKS)
            if has_gift and has_confirm and has_date:
                return True
        return False

    def _confirm_omits_date_correction(p: Probe) -> bool:
        """Forbidden: ordered something and emailed alice with confirm/gift but
        no earlier-date correction (acted on the false 14th premise)."""
        ordered_any = (
            _ordered_market(p, GOLD)
            or _ordered_shop(p, TRAP_LOW_SELLER_SG)
            or any(_ordered_market(p, pid) for pid in (
                TRAP_BRAND, TRAP_REFURB, TRAP_PAID_SHIP, TRAP_LATE_FOR_PARTY,
            ))
        )
        if not ordered_any:
            return False
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            if USER_EMAIL not in (se.to or "").lower():
                continue
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            has_confirm = any(t in body for t in CONFIRM_TOKS)
            has_date = any(t in body for t in DATE_CORRECTION_TOKS)
            if has_confirm and not has_date:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_breville_best_rated_before_party",
                    weight=0.55,
                    check=lambda p: _ordered_market(p, GOLD),
                    required_for_success=True,
                ),
                Milestone(
                    "confirm_email_gift_and_earlier_date",
                    weight=0.45,
                    check=_sent_confirm_gift_and_date,
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_wrong_brand",
                    weight=0.0,
                    check=lambda p: _ordered_market(p, TRAP_BRAND),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_refurbished",
                    weight=0.0,
                    check=lambda p: _ordered_market(p, TRAP_REFURB),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_paid_shipping",
                    weight=0.0,
                    check=lambda p: _ordered_market(p, TRAP_PAID_SHIP),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_low_rated_cross_hub",
                    weight=0.0,
                    check=lambda p: _ordered_shop(p, TRAP_LOW_SELLER_SG),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_late_for_email_party",
                    weight=0.0,
                    check=lambda p: _ordered_market(p, TRAP_LATE_FOR_PARTY),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "forbidden_confirm_omits_earlier_date",
                    weight=0.0,
                    check=_confirm_omits_date_correction,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
