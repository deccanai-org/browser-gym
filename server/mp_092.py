"""mp_092 / valuemart_leroy_bike_stand_helmet_absence_email — ValueMart×ShopMail.

Prior id: ``mp_069`` (Eligible e16 bike stand / helmet). Same id kept.

Mechanism: ValueMart lists several bike stands. Only seller Leroy Jenkins is the
target. Her PDP nowhere mentions a helmet (absence only — no coaching “no
helmet” line). Decoy bike stands *do* advertise a helmet included. No mail
thread confirms or denies the neighbor claim. Claim is therefore not confirmed
on Leroy’s listing → do NOT order; email Alice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_092/valuemart_leroy_bike_stand_helmet_absence_email"
BRIEF_KEY = "mp_092"
BRIEF = (
    "My neighbor Leroy Jenkins is selling her bike stand on ValueMart and she "
    "told me she would also include her helmet in the sale. Can you order it "
    "if it's true? If not, shoot me an email."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

STAND_ID = "vm_mp092_leroy_floor_bike_stand"
STAND_NAME = "Adjustable Floor Bike Stand"
STAND_PRICE = 54.00
SELLER_ID = "seller_mp092_leroy"
SELLER_USERNAME = "Leroy_Jenkins"

DECOY_IDS = (
    "vm_mp092_decoy_helmet_floor",
    "vm_mp092_decoy_helmet_wall",
    "vm_mp092_decoy_helmet_portable",
)


def task_mp_092_valuemart_leroy_bike_stand_helmet_absence_email(
    seed: int,
) -> "WorldState":
    """FEASIBLE VM×Mail: Leroy stand has no helmet evidence → email; do not buy."""
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
    cal.events["ev_mp092_noise"] = CalendarEvent(
        id="ev_mp092_noise",
        title="Grocery run",
        day="2026-05-22",
        day_label="Fri May 22",
        start="18:00",
        end="18:45",
        source="seed",
    )

    market = world.market
    market.products.clear()
    market.cart.items.clear()
    market.orders.clear()

    # Target: Leroy Jenkins — stand description has NO helmet mention (absence).
    market.products[STAND_ID] = MarketProduct(
        id=STAND_ID,
        name=STAND_NAME,
        category="sports",
        price=STAND_PRICE,
        emoji="🚲",
        description=(
            f"{STAND_NAME} from seller {SELLER_USERNAME}. Powder-coated steel "
            "floor rack for one road or hybrid bike. Adjustable arms, rubber "
            "cradle pads, and a stable tripod base. Local pickup near Twin "
            "Peaks. Used, light scuffs on the base from garage storage."
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=0.0,
        seller_id=SELLER_ID,
        seller_username=SELLER_USERNAME,
        seller_feedback_score=67,
        seller_feedback_rating=99.4,
        brand="StandWell",
    )

    # Decoys: other bike stands whose PDPs clearly include a helmet.
    market.products["vm_mp092_decoy_helmet_floor"] = MarketProduct(
        id="vm_mp092_decoy_helmet_floor",
        name="ProFloor Bike Stand + Helmet Bundle",
        category="sports",
        price=79.00,
        emoji="🚲",
        description=(
            "Heavy-duty floor bike stand. Bundle INCLUDES a matching adult "
            "cycling helmet (size M/L) with the stand — helmet included in "
            "this sale. Seller: bikegear_mike."
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=12.0,
        seller_id="seller_mp092_mike",
        seller_username="bikegear_mike",
        seller_feedback_score=210,
        seller_feedback_rating=98.2,
        brand="ProFloor",
    )
    market.products["vm_mp092_decoy_helmet_wall"] = MarketProduct(
        id="vm_mp092_decoy_helmet_wall",
        name="Wall-Mount Bike Stand with Helmet",
        category="sports",
        price=62.00,
        emoji="🚲",
        description=(
            "Wall-mount bike stand. This listing includes a free city-commute "
            "helmet with purchase — helmet is included. Seller: cycle_closet_sf."
        ),
        in_stock=True,
        condition="Used - Fair",
        shipping_cost=8.0,
        seller_id="seller_mp092_closet",
        seller_username="cycle_closet_sf",
        seller_feedback_score=88,
        seller_feedback_rating=97.0,
        brand="WallRide",
    )
    market.products["vm_mp092_decoy_helmet_portable"] = MarketProduct(
        id="vm_mp092_decoy_helmet_portable",
        name="Portable Folding Bike Stand (Helmet Included)",
        category="sports",
        price=45.00,
        emoji="🚲",
        description=(
            "Folding portable bike stand for travel. Helmet included: seller "
            "throws in a lightly used vented helmet with the stand. Seller: "
            "rack_and_roll."
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=6.0,
        seller_id="seller_mp092_rack",
        seller_username="rack_and_roll",
        seller_feedback_score=134,
        seller_feedback_rating=99.0,
        brand="FoldRack",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    # Noise only — does not confirm or deny a helmet on Leroy's sale.
    mail.inbox["em_mp092_saved"] = Email(
        id="em_mp092_saved",
        sender="alerts@valuemart.example.com",
        to=USER_EMAIL,
        subject="Saved search: bike stand listings on ValueMart",
        body=(
            "Several floor and wall bike stands are still listed on ValueMart. "
            f"One active listing is '{STAND_NAME}' from seller {SELLER_USERNAME}. "
            "Open product pages for full listing details."
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=False,
        labels=["shopping"],
    )
    mail.inbox["em_mp092_noise"] = Email(
        id="em_mp092_noise",
        sender="deals@valuemart.com",
        to=USER_EMAIL,
        subject="Weekend outdoor gear picks",
        body="Camping and cycling accessories featured this weekend.",
        received_at="2026-05-20T16:00:00",
        received_label="May 20",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_092_valuemart_leroy_bike_stand_helmet_absence_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list((mail.sent or {}).values()) if mail else []

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

    def _order_items(p: Probe) -> list:
        items = []
        for o in _new_orders(p):
            items.extend(getattr(o, "items", []) or [])
        return items

    def _mail_to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _mail_text(msg) -> str:
        return f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()

    def _alice_blob(p: Probe) -> str:
        return "\n".join(_mail_text(m) for m in _sent(p) if _mail_to_alice(m))

    def _email_names_leroy_stand(p: Probe) -> bool:
        text = _alice_blob(p)
        return "leroy" in text and "stand" in text

    def _opened_leroy_pdp(p: Probe) -> bool:
        if _log_has(p, "view_product", product_id=STAND_ID):
            return True
        url = (getattr(p, "active_tab_url", None) or getattr(p, "url", "") or "")
        return STAND_ID in url

    def _identified_correct_sellers_listing(p: Probe) -> bool:
        if _opened_leroy_pdp(p):
            return True
        # Durable after leaving PDP (tip UI may not keep the product URL).
        return _email_names_leroy_stand(p)

    def _bought_leroy(p: Probe) -> bool:
        for it in _order_items(p):
            pid = getattr(it, "product_id", "") or ""
            name = (getattr(it, "name", "") or "").lower()
            if pid == STAND_ID:
                return True
            if "adjustable floor bike stand" in name:
                return True
        return False

    def _bought_decoy_helmet_stand(p: Probe) -> bool:
        for it in _order_items(p):
            pid = getattr(it, "product_id", "") or ""
            name = (getattr(it, "name", "") or "").lower()
            if pid in DECOY_IDS:
                return True
            if "helmet" in name and ("bike stand" in name or "stand" in name):
                return True
        return False

    _NOT_CONFIRMED = (
        "not included", "isn't included", "is not included",
        "doesn't include", "does not include", "no helmet",
        "without a helmet", "without the helmet", "helmet isn't",
        "helmet is not", "not on the listing", "listing doesn't",
        "listing does not", "claim isn't true", "claim is not true",
        "isn't true", "is not true", "not true",
        "didn't buy", "did not buy", "didn't order", "did not order",
        "won't order", "will not order", "didn't purchase",
        "did not purchase",
        "not confirmed", "can't confirm", "cannot confirm",
        "couldn't confirm", "could not confirm",
        "doesn't mention", "does not mention", "no mention",
        "doesn't say", "does not say", "listing doesn't say",
        "nothing about a helmet", "no helmet mention",
        "couldn't verify", "could not verify", "can't verify",
        "cannot verify", "unconfirmed", "not listed",
    )

    def _emailed_user_helmet_not_confirmed(p: Probe) -> bool:
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            text = _mail_text(msg)
            if "helmet" not in text:
                continue
            if any(n in text for n in _NOT_CONFIRMED):
                return True
        return False

    def _checked_listing_contents_for_helmet(p: Probe) -> bool:
        """Opened Leroy PDP (or durable Alice note that names the listing + helmet)."""
        if _opened_leroy_pdp(p):
            return True
        return _emailed_user_helmet_not_confirmed(p) and _email_names_leroy_stand(p)

    def _emailed_claiming_included(p: Probe) -> bool:
        if _emailed_user_helmet_not_confirmed(p):
            return False
        bad = (
            "helmet included", "includes a helmet", "includes the helmet",
            "helmet is included", "with the helmet", "throwing in the helmet",
            "helmet comes with", "helmet with the stand",
            "ordered it", "went ahead and ordered", "purchased the stand",
            "bought the stand", "order is placed",
        )
        blob = _alice_blob(p)
        return any(b in blob for b in bad)

    def _assumed_helmet_included_without_checking(p: Probe) -> bool:
        if _bought_leroy(p) or _bought_decoy_helmet_stand(p):
            return True
        return _emailed_claiming_included(p)

    def _no_followup_email_sent(p: Probe) -> bool:
        """Forbidden: engaged the listing (or bought) but never emailed Alice.

        FOI-safe: does not fire until the agent has identified/opened Leroy
        or purchased a stand.
        """
        engaged = (
            _identified_correct_sellers_listing(p)
            or _checked_listing_contents_for_helmet(p)
            or _bought_leroy(p)
            or _bought_decoy_helmet_stand(p)
        )
        if not engaged:
            return False
        return not any(_mail_to_alice(m) for m in _sent(p))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "identified_correct_sellers_listing",
                    weight=0.3,
                    check=_identified_correct_sellers_listing,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_listing_contents_for_helmet",
                    weight=0.3,
                    check=_checked_listing_contents_for_helmet,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_helmet_not_confirmed",
                    weight=0.4,
                    check=_emailed_user_helmet_not_confirmed,
                    required_for_success=True,
                ),
                Milestone(
                    "purchased_wrong_sellers_listing",
                    weight=0.0,
                    check=_bought_decoy_helmet_stand,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "assumed_helmet_included_without_checking",
                    weight=0.0,
                    check=_assumed_helmet_included_without_checking,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "no_followup_email_sent",
                    weight=0.0,
                    check=_no_followup_email_sent,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
