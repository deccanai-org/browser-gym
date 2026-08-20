"""mp_068 / valuemart_price_watch_vs_gymcal_deadline.

Mechanism: Xbay couch mid-range with "may drop further end of month"
speculation. Xoogle move-in is 5 days out — hard buy-by. Correct = buy now
at $380 before the deadline, not wait for a hypothetical further drop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_068/valuemart_price_watch_vs_gymcal_deadline"
BRIEF_KEY = "mp_068"
BRIEF = (
    "I've had my eye on a couch on Xbay, grab it whenever it's actually "
    "the best time to buy."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
MOVE_IN = "2026-05-26"  # 5 days out — before end of month

COUCH_ID = "vm_mp068_couch"
COUCH_NAME = "Harbor Slipcover Couch"
COUCH_PRICE = 380.00
WAS_PRICE = 450.00

MOVE_EVENT = "ev_mp068_move_in"
WATCH_MAIL = "em_mp068_watch"


def task_mp_068_valuemart_price_watch_vs_gymcal_deadline(seed: int) -> "WorldState":
    """FEASIBLE VM×Cal: deadline bounds 'best time' — buy now at $380."""
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
    cal.events[MOVE_EVENT] = CalendarEvent(
        id=MOVE_EVENT,
        title="Move-in day",
        day=MOVE_IN,
        day_label="Tue May 26",
        start="09:00",
        end="17:00",
        source="seed",
        description=(
            "Keys at 9am — furniture must already be purchased and scheduled "
            "before this day. End-of-month sales don't help if you move in "
            "on the 26th."
        ),
        location="New apartment",
    )
    cal.events["ev_mp068_noise"] = CalendarEvent(
        id="ev_mp068_noise",
        title="Team standup",
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
        price=COUCH_PRICE,
        emoji="🛋️",
        description=(
            f"{COUCH_NAME}. Price history note: was ${WAS_PRICE:.0f}, now "
            f"${COUCH_PRICE:.0f}. Seller note: price may drop further closer "
            f"to end of month — watch for another cut after the 28th."
        ),
        in_stock=True,
        condition="Used - Excellent",
        shipping_cost=0.0,
        seller_username="harbor_home_sf",
        seller_feedback_score=240,
        seller_feedback_rating=99.1,
        brand="HarborHome",
    )
    market.products["vm_mp068_lamp_decoy"] = MarketProduct(
        id="vm_mp068_lamp_decoy",
        name="Floor Lamp",
        category="home",
        price=45.00,
        emoji="💡",
        description="Not the couch.",
        in_stock=True,
        condition="New",
        shipping_cost=8.0,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[WATCH_MAIL] = Email(
        id=WATCH_MAIL,
        sender="alerts@valuemart.com",
        to=USER_EMAIL,
        subject=f"Still watching: {COUCH_NAME}",
        body=(
            f"Your watched listing '{COUCH_NAME}' is ${COUCH_PRICE:.0f} "
            f"(was ${WAS_PRICE:.0f}). Some shoppers wait for end-of-month "
            "cuts — open the listing for the seller's price note."
        ),
        received_at=f"{SEED_DATE}T08:30:00",
        received_label="8:30 AM",
        read=False,
        labels=["shopping", "unread"],
        product_id=COUCH_ID,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_068_valuemart_price_watch_vs_gymcal_deadline,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _bought_couch(p: Probe) -> bool:
        market = getattr(p.world, "market", None) if p.world else None
        if market is None:
            return False
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.market.orders or {})
            if init and getattr(init, "market", None) else {}
        )
        for oid, o in (market.orders or {}).items():
            if oid in init_ids:
                continue
            for it in getattr(o, "items", []) or []:
                pid = getattr(it, "product_id", "") or ""
                name = (getattr(it, "name", "") or "").lower()
                price = float(getattr(it, "unit_price", 0) or 0)
                if pid == COUCH_ID or "couch" in name:
                    if abs(price - COUCH_PRICE) < 0.01 or price == 0:
                        return True
                    return True
        return False

    def _viewed_cal(p: Probe) -> bool:
        if _log_has(p, "viewed_calendar"):
            return True
        return "/calendar" in (p.active_tab_url or p.url or "")

    def _engaged_listing(p: Probe) -> bool:
        if _log_has(p, "view_product", product_id=COUCH_ID):
            return True
        url = (p.active_tab_url or p.url or "")
        return COUCH_ID in url or "/market" in url

    def _checked_cal(p: Probe) -> bool:
        return _viewed_cal(p)

    def _recognized_deadline(p: Probe) -> bool:
        """Proxy: checked calendar AND purchased (didn't wait)."""
        return _viewed_cal(p) and _bought_couch(p)

    def _purchased_before(p: Probe) -> bool:
        return _bought_couch(p)

    def _did_not_purchase(p: Probe) -> bool:
        """Latch only after engagement so FOI stays 0.0."""
        if _bought_couch(p):
            return False
        return _viewed_cal(p) or _engaged_listing(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_calendar_for_deadline",
                    weight=0.3,
                    check=_checked_cal,
                    required_for_success=True,
                ),
                Milestone(
                    "recognized_deadline_overrides_price_speculation",
                    weight=0.3,
                    check=_recognized_deadline,
                    required_for_success=True,
                ),
                Milestone(
                    "purchased_before_deadline",
                    weight=0.4,
                    check=_purchased_before,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_purchase_within_deadline_window",
                    weight=0.0,
                    check=_did_not_purchase,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
