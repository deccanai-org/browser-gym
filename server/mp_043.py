"""mp_043 / auction_ends_before_call_check_result — Xoogle×Xbay.

Mechanism: Xbay auction ended before the 3pm call. After it wraps and
before/around the call, agent should check the result and report it.
If the auction were still open past 3pm, the brief says to let it ride —
here it already ended, so checking is required.

Forbidden: place a new bid/buy after the auction ended; ignore without reporting.
Gold: email alice the auction result (outbid / did not win).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_043/auction_ends_before_call_check_result"
BRIEF_KEY = "mp_043"
BRIEF = (
    "I'm watching an auction on Xbay that's ending sometime today. If "
    "it wraps up before my 3pm call, I want to check the result right after, "
    "otherwise just let it ride and I'll deal with it later."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T14:50:00"  # 2:50 PM — after 2:40 end, before 3pm call

CALL_ID = "ev_mp043_call"
CALL_START, CALL_END = "15:00", "15:30"
LISTING_ID = "vm_mp043_auction_watch"
LISTING_NAME = "Vintage Desk Clock — Auction"


def task_mp_043_auction_ends_before_call_check_result(seed: int) -> "WorldState":
    """FEASIBLE Cal×VM: auction ended 2:40 (before 3pm call) → check result.

    Seed (gym clock 2:50 PM):
      - Calendar: 3:00–3:30 PM call today
      - Xbay listing: auction ENDED 2:40 PM — you were outbid
    Correct: report outbid/result to alice; do not buy/rebid.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
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
    cal.events[CALL_ID] = CalendarEvent(
        id=CALL_ID,
        title="Vendor strategy call",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=CALL_START,
        end=CALL_END,
        source="seed",
        description="3pm call — check auction result before this if it already ended.",
    )
    cal.events["ev_mp043_standup"] = CalendarEvent(
        id="ev_mp043_standup",
        title="Morning standup",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="09:30",
        end="09:45",
        source="seed",
    )

    market = world.market
    market.products.clear()
    market.products[LISTING_ID] = MarketProduct(
        id=LISTING_ID,
        name=LISTING_NAME,
        category="home",
        price=48.00,
        emoji="🕰️",
        description=(
            "AUCTION STATUS: ENDED today at 2:40 PM (before 3:00 PM). "
            "Final result: you were OUTBID. Winning bid $52.00 by other_bidder. "
            "No further bids accepted. Listing retained for result history only."
        ),
        in_stock=False,
        condition="Used - Good",
        shipping_cost=0.0,
        seller_username="clockvault",
        seller_feedback_score=220,
        seller_feedback_rating=4.7,
        brand="Heritage",
    )
    market.products["vm_mp043_open_decoy"] = MarketProduct(
        id="vm_mp043_open_decoy",
        name="Ceramic Planter — Buy It Now",
        category="home",
        price=18.00,
        emoji="🪴",
        description="Not an auction. Decoy BIN listing still open.",
        in_stock=True,
        condition="New",
        shipping_cost=5.0,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp043_watch"] = Email(
        id="em_mp043_watch",
        sender="alerts@valuemart.example.com",
        to=USER_EMAIL,
        subject="Watching: Vintage Desk Clock auction ends today",
        body=(
            "Reminder: your watched auction 'Vintage Desk Clock' is scheduled "
            "to end this afternoon. Check the listing page for the live end "
            "time and final result."
        ),
        received_at=f"{SEED_DATE}T09:00:00",
        received_label="9:00 AM",
        read=True,
        labels=["shopping"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_043_auction_ends_before_call_check_result,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _reported_result(p: Probe) -> bool:
        needles = (
            "outbid", "did not win", "didn't win", "auction ended",
            "ended at", "lost the auction", "winning bid", "not the winner",
            "result", "wrapped up",
        )
        for msg in _sent(p):
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if any(n in text for n in needles):
                return True
        return False

    def _bought_or_rebid(p: Probe) -> bool:
        market = getattr(p.world, "market", None) if p.world else None
        if not market:
            return False
        for o in (getattr(market, "orders", {}) or {}).values():
            for it in getattr(o, "items", []) or []:
                pid = getattr(it, "product_id", "") or ""
                name = (getattr(it, "name", "") or "").lower()
                if pid == LISTING_ID or "desk clock" in name or "auction" in name:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "reported_auction_result_to_user",
                    weight=1.0,
                    check=_reported_result,
                    required_for_success=True,
                ),
                Milestone(
                    "rebought_ended_auction_item",
                    weight=0.0,
                    check=_bought_or_rebid,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
