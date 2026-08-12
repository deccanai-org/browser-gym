"""mp_037 / farewell_gift_moved_last_day — GymCal×ShopMail×ShopGym.

Mechanism: Calendar still shows Jordan's last day on May 28. A recent Mail
thread moves the last day earlier to May 25. Delivery deadline = reconciled
Mail date. Gold gift listing arrives before May 25; trap listing arrives by
the stale calendar date (May 27–28) but after the real last day.

Forbidden: buy using only the stale calendar date (late gift); wrong gift SKU.
Gold: order on-time farewell gift (arrive-by before updated last day).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_037/farewell_gift_moved_last_day"
BRIEF_KEY = "mp_037"
BRIEF = (
    "Grab a gift for whoever's leaving the team this month and make sure it "
    "gets there before their last day. Check if that date's still accurate — "
    "I think there was some back and forth about it recently. A nice notebook "
    "is fine; email me once it's ordered."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"

# Stale calendar authority
LAST_DAY_EVENT_ID = "ev_mp037_jordan_last"
LAST_DAY_TITLE = "Jordan's last day"
STALE_LAST_DAY = "2026-05-28"          # still on calendar
STALE_LABEL = "Thu May 28"
# Reconciled from Mail
REAL_LAST_DAY = "2026-05-25"           # updated last day
REAL_LABEL = "May 25"

OLD_MAIL_ID = "em_mp037_last_day_may28"
UPDATE_MAIL_ID = "em_mp037_last_day_may25"
WHO_MAIL_ID = "em_mp037_jordan_leaving"

# ShopGym gifts
GOLD = "p_mp037_notebook_ontime"       # arrives by May 24
TRAP_LATE = "p_mp037_notebook_late"    # arrives May 27 — OK for calendar, misses Mail
TRAP_WRONG = "p_mp037_mug_generic"     # not a notebook / wrong gift type

CONFIRM_TOKS = ("ordered", "order", "placed", "notebook", "jordan", "gift")
DATE_TOKS = (
    "may 25",
    "may 25th",
    "5/25",
    "25th",
    "not the 28th",
    "not may 28",
    "earlier",
    "moved up",
    "last day is",
)


def task_mp_037_farewell_gift_moved_last_day(seed: int) -> "WorldState":
    """FEASIBLE Cal×Mail×Shop: gift arrives before Mail-updated last day.

    Seed (today Thu May 21):
      - Calendar: Jordan's last day Thu May 28 (STALE)
      - Mail older: last day still May 28
      - Mail latest: last day moved up to Monday May 25
      - ShopGym: Lined Farewell Notebook — arrives May 24 (GOLD)
      - ShopGym: same notebook — arrives May 27 (late for real last day)
      - ShopGym: generic mug (wrong gift; brief asks notebook)

    Correct: buy GOLD; confirm email citing May 25 (not 28).
    """
    from server.apps.calendar.state import CalendarEvent
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[LAST_DAY_EVENT_ID] = CalendarEvent(
        id=LAST_DAY_EVENT_ID,
        title=LAST_DAY_TITLE,
        day=STALE_LAST_DAY,
        day_label=STALE_LABEL,
        start="17:00",
        end="18:00",
        source="seed",
        description=(
            "Jordan's last day on the team (calendar hold). Confirm against "
            "recent Mail before shipping farewell gifts."
        ),
    )
    cal.events["ev_mp037_standup"] = CalendarEvent(
        id="ev_mp037_standup",
        title="Morning standup",
        day="2026-05-22",
        day_label="Fri May 22",
        start="09:30",
        end="09:45",
        source="seed",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[WHO_MAIL_ID] = Email(
        id=WHO_MAIL_ID,
        sender="hr@shopgym.com",
        to=USER_EMAIL,
        subject="Jordan Park is leaving the team this month",
        body=(
            "Heads-up: Jordan Park's last day is coming up. A small farewell "
            "gift from the pod would be kind — notebook is a safe pick."
        ),
        received_at="2026-05-18T10:00:00",
        received_label="May 18",
        read=True,
        labels=["work"],
    )
    mail.inbox[OLD_MAIL_ID] = Email(
        id=OLD_MAIL_ID,
        sender="hr@shopgym.com",
        to=USER_EMAIL,
        cc="jordan.park@shopgym.com",
        subject="Jordan's last day — May 28",
        body=(
            "Confirming Jordan Park's last day is Thursday, May 28, 2026. "
            "Please plan farewells around that date."
        ),
        received_at="2026-05-19T09:15:00",
        received_label="May 19",
        read=True,
        labels=["work"],
    )
    mail.inbox[UPDATE_MAIL_ID] = Email(
        id=UPDATE_MAIL_ID,
        sender="hr@shopgym.com",
        to=USER_EMAIL,
        cc="jordan.park@shopgym.com",
        subject="Update: Jordan's last day moved to May 25",
        body=(
            "Correction — Jordan's last day moved up to Monday, May 25, 2026 "
            "(not May 28). Please ignore the older May 28 note and the calendar "
            "hold if it still shows the 28th.\n\n"
            "Gifts need to arrive on or before May 25 so Jordan gets them "
            "before leaving."
        ),
        received_at=f"{SEED_DATE}T09:50:00",
        received_label="9:50 AM",
        read=False,
        labels=["work", "unread"],
    )

    shop = world.shop
    # Keep only the farewell-gift choices so ShopGym search/home thrash cannot
    # bury the notebook listings under ambient Yankee Candle / unrelated SKUs.
    shop.products.clear()
    shop.products[GOLD] = Product(
        id=GOLD,
        name="Lined Farewell Notebook — Express",
        brand="NoteWell",
        category="office",
        base_price=18.00,
        rating=4.7,
        review_count=640,
        stock=40,
        image_emoji="📓",
        short_description=(
            "Cloth-bound lined notebook — classic farewell gift. FREE delivery. "
            f"Estimated delivery: arrives by May 24, 2026 — before Jordan's "
            f"updated last day ({REAL_LABEL})."
        ),
        tags=["notebook", "gift", "farewell", "express"],
    )
    shop.products[TRAP_LATE] = Product(
        id=TRAP_LATE,
        name="Lined Farewell Notebook — Standard",
        brand="NoteWell",
        category="office",
        base_price=16.00,
        rating=4.6,
        review_count=710,
        stock=55,
        image_emoji="📓",
        short_description=(
            "Same cloth-bound farewell notebook. FREE delivery. Estimated "
            "delivery: arrives May 27, 2026 — before the calendar's May 28 "
            f"last-day hold, but AFTER the Mail-updated last day ({REAL_LABEL})."
        ),
        tags=["notebook", "gift", "farewell", "standard"],
    )
    shop.products[TRAP_WRONG] = Product(
        id=TRAP_WRONG,
        name="Team Spirit Ceramic Mug",
        brand="CupCo",
        category="home",
        base_price=12.00,
        rating=4.4,
        review_count=220,
        stock=80,
        image_emoji="☕",
        short_description=(
            "Generic mug. FREE delivery by May 23. Not the notebook farewell "
            "gift HR suggested."
        ),
        tags=["mug", "gift"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_037_farewell_gift_moved_last_day,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for oid, o in (shop.orders or {}).items() if oid not in init]

    def _ordered(p: Probe, pid: str) -> bool:
        for o in _new_orders(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _confirm_email(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if not mail:
            return False
        for se in (mail.sent or {}).values():
            blob = f"{se.subject or ''}\n{se.body or ''}".lower()
            if not any(t in blob for t in CONFIRM_TOKS):
                continue
            if any(t in blob for t in DATE_TOKS):
                return True
        return False

    def _gold_order(p: Probe) -> bool:
        return _ordered(p, GOLD)

    def _success(p: Probe) -> bool:
        return _gold_order(p) and _confirm_email(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_notebook_before_updated_last_day",
                    weight=0.7,
                    check=_gold_order,
                    required_for_success=True,
                ),
                Milestone(
                    "confirm_email_cites_updated_date",
                    weight=0.3,
                    check=_confirm_email,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_late_for_mail_last_day",
                    weight=0.0,
                    check=lambda p: _ordered(p, TRAP_LATE),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_wrong_gift_type",
                    weight=0.0,
                    check=lambda p: _ordered(p, TRAP_WRONG),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "full_gold",
                    weight=0.0,
                    check=_success,
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
