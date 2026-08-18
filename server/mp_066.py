"""mp_066 / valuemart_seller_dispute_and_calendar_pickup_reschedule.

Mechanism: ValueMart pickup banner (June 14–16) contradicts an earlier ShopMail
seller thread (true window June 21–23). Calendar conflict sits only inside the
*true* window (June 22) — agents that trust the banner never check the date
that matters. Durable outcome = report the conflict on the true window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_066/valuemart_seller_dispute_and_calendar_pickup_reschedule"
BRIEF_KEY = "mp_066"
BRIEF = (
    "The ValueMart seller says my desk is ready for pickup, but I think "
    "that's the wrong week, can you sort it out."
)

USER_EMAIL = "alice@shopmail.com"
SELLER_EMAIL = "desks.local@valuemart.example.com"
GYM_NOW = "2026-06-11T12:00:00"  # Thu Jun 11 — June windows reachable

BANNER_START, BANNER_END = "2026-06-14", "2026-06-16"  # false (VM banner)
TRUE_START, TRUE_END = "2026-06-21", "2026-06-23"      # true (mail thread)
CONFLICT_DAY = "2026-06-22"  # inside true window only

ORDER_ID = "VM-MP066-DESK"
DESK_ID = "vm_mp066_standing_desk"
DESK_NAME = "Oak Standing Desk — Local Pickup"
SELLER_ID = "seller_mp066_desks"
SELLER_USER = "BayDeskPickup"

# Mail thread (newest first in UI; true window buried mid-thread)
EM_BANNER_ECHO = "em_mp066_vm_ready"       # latest: echoes banner (trap)
EM_TRUE_CONFIRM = "em_mp066_true_window"   # buried: true June 21-23
EM_EARLIER = "em_mp066_earlier_chat"
EM_NOISE = "em_mp066_noise"

BUSY_ID = "ev_mp066_dentist_block"


def task_mp_066_valuemart_seller_dispute_and_calendar_pickup_reschedule(
    seed: int,
) -> "WorldState":
    """FEASIBLE VM×Mail×Cal: catch banner/mail discrepancy + Jun 22 conflict."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email
    from server.apps.market.state import MarketCartItem, MarketOrder, MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[BUSY_ID] = CalendarEvent(
        id=BUSY_ID,
        title="Out-of-town dentist (all day)",
        day=CONFLICT_DAY,
        day_label="Mon Jun 22",
        start="09:00",
        end="17:00",
        source="seed",
        description=(
            "You are NOT available for local pickup on Monday June 22 — "
            "drive to Sacramento for a specialist appointment."
        ),
        location="Sacramento",
    )
    # Decoy conflict on the *banner* week so a banner-trusting agent may
    # wrongly conclude "calendar is fine for the true week" without checking.
    cal.events["ev_mp066_banner_week_noise"] = CalendarEvent(
        id="ev_mp066_banner_week_noise",
        title="Quick coffee with Sam",
        day="2026-06-15",
        day_label="Mon Jun 15",
        start="08:00",
        end="08:30",
        source="seed",
        description="Short morning coffee — not a pickup blocker.",
    )

    market = world.market
    market.products.clear()
    market.cart.items.clear()
    market.orders.clear()
    market.messages.clear()
    market.products[DESK_ID] = MarketProduct(
        id=DESK_ID,
        name=DESK_NAME,
        category="home",
        price=189.00,
        emoji="🪵",
        description=(
            f"{DESK_NAME}. LOCAL PICKUP. Seller notice on the order: "
            f"READY FOR PICKUP June 14–16 at Mission warehouse. "
            f"(Order {ORDER_ID}.)"
        ),
        in_stock=True,
        condition="Used - Good",
        shipping_cost=0.0,
        seller_id=SELLER_ID,
        seller_username=SELLER_USER,
        seller_feedback_score=188,
        seller_feedback_rating=98.5,
        brand="OakForm",
    )
    market.orders[ORDER_ID] = MarketOrder(
        id=ORDER_ID,
        items=[MarketCartItem(
            product_id=DESK_ID, name=DESK_NAME, unit_price=189.00, quantity=1,
        )],
        subtotal=189.00,
        discount=0.0,
        delivery_fee=0.0,
        total=189.00,
        placed_at="2026-06-02T11:00:00",
        # Visible on ValueMart Purchases — the false window banner.
        status="Ready for pickup — June 14-16",
    )
    market._next = 800

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    # Newest: ValueMart system echo of the banner (trap surface in mail too).
    mail.inbox[EM_BANNER_ECHO] = Email(
        id=EM_BANNER_ECHO,
        sender="orders@valuemart.com",
        to=USER_EMAIL,
        subject=f"Pickup ready — {DESK_NAME}",
        body=(
            f"Good news! Order {ORDER_ID} is marked ready for pickup.\n\n"
            f"Pickup window on the order: June 14–16.\n"
            f"Warehouse: Mission Ave, San Francisco.\n\n"
            "See you soon!"
        ),
        received_at="2026-06-11T09:15:00",
        received_label="9:15 AM",
        read=False,
        labels=["shopping", "unread"],
        order_id=ORDER_ID,
        product_id=DESK_ID,
    )
    # Mid-thread: seller's actual agreed window (buried — not the newest).
    mail.inbox[EM_TRUE_CONFIRM] = Email(
        id=EM_TRUE_CONFIRM,
        sender=SELLER_EMAIL,
        to=USER_EMAIL,
        subject=f"Re: {DESK_NAME} pickup timing",
        body=(
            "Hey Alice — looping back after I double-checked the warehouse "
            "calendar. The desk will actually be ready the week of "
            "June 21–23 (not the weekend before). June 21 afternoon through "
            "June 23 closing is the window we locked in. Sorry for the "
            "earlier confusion on my side — please use that window."
        ),
        received_at="2026-06-08T16:40:00",
        received_label="Jun 8",
        read=False,
        labels=["shopping", "unread"],
        order_id=ORDER_ID,
        product_id=DESK_ID,
    )
    mail.inbox[EM_EARLIER] = Email(
        id=EM_EARLIER,
        sender=SELLER_EMAIL,
        to=USER_EMAIL,
        subject=f"Re: {DESK_NAME} pickup timing",
        body=(
            "Thanks for buying the oak standing desk! I'll message once the "
            "refinish is done and we can pick a pickup window that works."
        ),
        received_at="2026-06-03T10:05:00",
        received_label="Jun 3",
        read=True,
        labels=["shopping"],
        order_id=ORDER_ID,
    )
    mail.inbox[EM_NOISE] = Email(
        id=EM_NOISE,
        sender="deals@valuemart.com",
        to=USER_EMAIL,
        subject="June clearance on office chairs",
        body="Extra 15% off chairs this weekend only.",
        received_at="2026-06-10T12:00:00",
        received_label="Jun 10",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_066_valuemart_seller_dispute_and_calendar_pickup_reschedule,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list((mail.sent or {}).values()) if mail else []

    def _mail_read(p: Probe, eid: str) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(eid)
        return bool(e and getattr(e, "read", False))

    def _text_blob(msg) -> str:
        return f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _viewed_cal(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar"):
            return True
        url = (p.active_tab_url or p.url or "")
        return "/calendar" in url

    def _caught_discrepancy(p: Probe) -> bool:
        """Both conflicting claims opened: banner echo + true-window mail.

        ValueMart Purchases status also carries the banner; URL/market visit
        is an alternate path when the agent never opens the VM system email.
        """
        if not _mail_read(p, EM_TRUE_CONFIRM):
            return False
        if _mail_read(p, EM_BANNER_ECHO):
            return True
        url = (p.active_tab_url or p.url or "")
        return "/market" in url

    def _identified_true(p: Probe) -> bool:
        return _mail_read(p, EM_TRUE_CONFIRM)

    def _checked_cal_true(p: Probe) -> bool:
        return _mail_read(p, EM_TRUE_CONFIRM) and _viewed_cal(p)

    def _reported_ok(p: Probe) -> bool:
        needles = (
            "june 22", "jun 22", "conflict", "dentist", "not available",
            "can't pick up", "cannot pick up", "sacramento", "busy",
            "reschedule", "true window", "june 21", "jun 21",
        )
        banner_ok_needles = ("june 14", "jun 14", "june 15", "jun 15")
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _text_blob(msg)
            # Must reference the conflict / true-window problem, not only banner.
            if any(n in text for n in needles):
                # Reject pure banner affirmation without true-window awareness.
                if any(b in text for b in ("june 21", "jun 21", "june 22", "jun 22",
                                           "conflict", "dentist", "reschedule")):
                    return True
                if "21" in text or "22" in text or "23" in text:
                    return True
        return False

    def _accepted_banner(p: Probe) -> bool:
        """Affirmed June 14-16 as correct without reading the true-window mail."""
        if _mail_read(p, EM_TRUE_CONFIRM):
            return False
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _text_blob(msg)
            if any(x in text for x in ("june 14", "jun 14", "june 15", "jun 15",
                                       "june 16", "jun 16")):
                if "ready" in text or "pickup" in text or "confirm" in text:
                    return True
        return False

    def _never_checked_cal(p: Probe) -> bool:
        """Latched only after true window is known and a report is sent."""
        if not _mail_read(p, EM_TRUE_CONFIRM):
            return False
        if _viewed_cal(p):
            return False
        # Require a terminal alice email so FOI stays clean and mid-explore
        # doesn't latch.
        return any(_to_alice(m) for m in _sent(p))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "caught_seller_window_discrepancy",
                    weight=0.3,
                    check=_caught_discrepancy,
                    required_for_success=True,
                ),
                Milestone(
                    "identified_true_window_from_email",
                    weight=0.25,
                    check=_identified_true,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_calendar_against_true_window",
                    weight=0.25,
                    check=_checked_cal_true,
                    required_for_success=True,
                ),
                Milestone(
                    "reported_conflict_or_confirmed_correctly",
                    weight=0.2,
                    check=_reported_ok,
                    required_for_success=True,
                ),
                Milestone(
                    "accepted_banner_window_without_verification",
                    weight=0.0,
                    check=_accepted_banner,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "never_checked_calendar_against_true_window",
                    weight=0.0,
                    check=_never_checked_cal,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
