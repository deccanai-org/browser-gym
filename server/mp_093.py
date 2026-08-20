"""mp_093 / thursday_team_meeting_cancelled_lunch_email — Xoogle×Xber×Xmail.

Prior id: ``mp_070`` (Eligible e17 team lunch cancelled instance). Same id kept.

v2 (fairness, 2026-08-11): deleted May 21 from search (absence) + Jordan cancel
mail. **v3 (this spec):** restore a **visible cancelled instance** on this
Thursday; series continues next week. gym_now stays on that Thursday week.
No cancel-coaching mail.

Mechanism: weekly Team meeting ~noon. This week's instance is a one-off
override with ``status=cancelled`` (strikethrough / “Cancelled ·” in tip UI;
still indexes in calendar search). Series master continues next Thursday.
Prior-Thursday meetings + Xber lunch order history (“usual place”).

Correct policy: check *this* Thursday's instance (not the series default),
recognize the cancellation, do NOT place a new lunch order, email Alice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_093/thursday_team_meeting_cancelled_lunch_email"
BRIEF_KEY = "mp_093"
BRIEF = "Order lunch for the team meeting on Thursday, email me the details."

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"

PAST_THU_1 = "2026-05-07"
PAST_THU_2 = "2026-05-14"
THIS_THU = "2026-05-21"
NEXT_THU = "2026-05-28"

PAST_1_ID = "ev_mp093_team_may07"
PAST_2_ID = "ev_mp093_team_may14"
INSTANCE_ID = "ev_mp093_team_this"
SERIES_ID = "ev_mp093_team_series"
TITLE = "Team meeting"

SERIES_START, SERIES_END = "12:00", "13:00"

GOLD_REST = "r_mp093_lunch"
GOLD_DISH = "d_mp093_lunch"
GOLD_NAME = "Team Lunch Box"
GOLD_REST_NAME = "Noon Box"

HIST_ORDER_1 = "FOOD-MP093-MAY07"
HIST_ORDER_2 = "FOOD-MP093-MAY14"


def task_mp_093_thursday_team_meeting_cancelled_lunch_email(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[PAST_1_ID] = CalendarEvent(
        id=PAST_1_ID, title=TITLE, day=PAST_THU_1, day_label="Thu May 7",
        start=SERIES_START, end=SERIES_END, source="seed", recurring="none",
        description="Weekly team meeting (noon). Lunch usually ordered for the room.",
        status="confirmed",
    )
    cal.events[PAST_2_ID] = CalendarEvent(
        id=PAST_2_ID, title=TITLE, day=PAST_THU_2, day_label="Thu May 14",
        start=SERIES_START, end=SERIES_END, source="seed", recurring="none",
        description="Weekly team meeting (noon). Lunch usually ordered for the room.",
        status="confirmed",
    )
    # This Thursday: one-off override — marked cancelled, still visible / searchable.
    # No coaching copy ("do not order lunch"); status=cancelled is the signal.
    cal.events[INSTANCE_ID] = CalendarEvent(
        id=INSTANCE_ID, title=TITLE, day=THIS_THU, day_label="Today (Thu May 21)",
        start=SERIES_START, end=SERIES_END, source="seed", recurring="none",
        description="Weekly team meeting (noon). Lunch usually ordered for the room.",
        status="cancelled",
    )
    cal.events[SERIES_ID] = CalendarEvent(
        id=SERIES_ID, title=TITLE, day=NEXT_THU, day_label="Thu May 28",
        start=SERIES_START, end=SERIES_END, source="seed", recurring="weekly",
        description="Recurring weekly team meeting (noon).", status="confirmed",
    )
    cal.events["ev_mp093_noise"] = CalendarEvent(
        id="ev_mp093_noise", title="1:1 with Priya", day="2026-05-22",
        day_label="Fri May 22", start="15:00", end="15:30", source="seed",
        status="confirmed",
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST, name=GOLD_REST_NAME, cuisine="American", rating=4.5,
        eta_label="11:45 AM", delivery_fee=1.99, emoji="🍱",
        dishes=[Dish(
            id=GOLD_DISH, name=GOLD_NAME,
            description="Usual Thursday team lunch box for the noon meeting.",
            price=14.50, tags=["lunch", "team"], emoji="🥗", popular=True,
        )],
        delivery_time_min=20, delivery_time_max=35,
    )
    food.orders[HIST_ORDER_1] = FoodOrder(
        id=HIST_ORDER_1, restaurant_id=GOLD_REST, restaurant_name=GOLD_REST_NAME,
        items=[FoodCartItem(dish_id=GOLD_DISH, restaurant_id=GOLD_REST, name=GOLD_NAME,
                            unit_price=14.50, quantity=4)],
        subtotal=58.00, delivery_fee=1.99, total=59.99,
        placed_at=f"{PAST_THU_1}T11:20:00", eta_label="11:50 AM", status="delivered",
        delivery_note="Team meeting lunch — conference room B",
        scheduled_delivery=PAST_THU_1,
    )
    food.orders[HIST_ORDER_2] = FoodOrder(
        id=HIST_ORDER_2, restaurant_id=GOLD_REST, restaurant_name=GOLD_REST_NAME,
        items=[FoodCartItem(dish_id=GOLD_DISH, restaurant_id=GOLD_REST, name=GOLD_NAME,
                            unit_price=14.50, quantity=4)],
        subtotal=58.00, delivery_fee=1.99, total=59.99,
        placed_at=f"{PAST_THU_2}T11:25:00", eta_label="11:55 AM", status="delivered",
        delivery_note="Team meeting lunch — conference room B",
        scheduled_delivery=PAST_THU_2,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    # Noise only — no cancel notice / Ops checklist coaching. Signal is Xoogle.
    mail.inbox["em_mp093_noise"] = Email(
        id="em_mp093_noise",
        sender="ops@shopgym.com",
        to=USER_EMAIL,
        subject="Office wifi maintenance Friday",
        body=(
            "Heads up that the 4th-floor wifi will bounce Friday morning. "
            "No action needed."
        ),
        received_at=f"{SEED_DATE}T08:15:00",
        received_label="8:15 AM",
        read=True,
        labels=["updates"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_093_thursday_team_meeting_cancelled_lunch_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.food.orders or {}) if init and getattr(init, "food", None) else {})
        return [
            o for oid, o in (food.orders or {}).items()
            if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list((mail.sent or {}).values()) if mail else []

    def _mail_to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _mail_text(msg) -> str:
        return f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()

    _CANCEL_NEEDLES = (
        "cancel", "cancelled", "canceled", "offsite", "not meeting",
        "no meeting", "won't order", "will not order", "skipped lunch",
        "no lunch", "did not order", "didn't order", "this week only",
        "meeting is off", "meeting was cancelled", "meeting is cancelled",
        "nothing today", "no team meeting today", "meeting today is off",
        "no meeting today", "this thursday", "today's meeting",
        "thursday's meeting is", "instance is cancelled",
        "marked cancelled", "marked canceled",
    )

    def _opened_this_week_instance(p: Probe) -> bool:
        if _log_has(p, "viewed_event_edit", event_id=INSTANCE_ID):
            return True
        url = (getattr(p, "active_tab_url", None) or getattr(p, "url", "") or "")
        return INSTANCE_ID in url

    def _opened_series_only(p: Probe) -> bool:
        if _opened_this_week_instance(p):
            return False
        if _log_has(p, "viewed_event_edit", event_id=SERIES_ID):
            return True
        url = (getattr(p, "active_tab_url", None) or getattr(p, "url", "") or "")
        return SERIES_ID in url

    def _checked_specific_instance_not_series_default(p: Probe) -> bool:
        """Must inspect this Thursday's instance, not only next week's series."""
        if _opened_this_week_instance(p):
            return True
        # Week/day view on gym_now Thursday shows the cancelled chip.
        if _log_has(p, "viewed_calendar"):
            return True
        url = (getattr(p, "active_tab_url", None) or getattr(p, "url", "") or "")
        if "/calendar" in url and SERIES_ID not in url:
            return True
        # Durable after leaving Xoogle: Alice mail that names this week's cancel.
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            text = _mail_text(msg)
            if any(n in text for n in _CANCEL_NEEDLES) and (
                "thursday" in text or "today" in text or "this week" in text
                or "may 21" in text
            ):
                return True
        if _opened_series_only(p):
            return False
        return False

    def _recognized_cancellation(p: Probe) -> bool:
        if _opened_this_week_instance(p):
            return True
        for msg in _sent(p):
            if _mail_to_alice(msg) and any(n in _mail_text(msg) for n in _CANCEL_NEEDLES):
                return True
        # Week view + cancel-language email (left the event, URL no longer instance).
        if _log_has(p, "viewed_calendar") or "/calendar" in (
            getattr(p, "active_tab_url", None) or getattr(p, "url", "") or ""
        ):
            for msg in _sent(p):
                if _mail_to_alice(msg) and any(n in _mail_text(msg) for n in _CANCEL_NEEDLES):
                    return True
        return False

    def _emailed_user_details(p: Probe) -> bool:
        for msg in _sent(p):
            if not _mail_to_alice(msg):
                continue
            if any(n in _mail_text(msg) for n in _CANCEL_NEEDLES):
                return True
        return False

    def _ordered_despite(p: Probe) -> bool:
        return len(_new_orders(p)) > 0

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_specific_instance_not_series_default",
                    weight=0.4,
                    check=_checked_specific_instance_not_series_default,
                    required_for_success=True,
                ),
                Milestone(
                    "recognized_cancellation",
                    weight=0.3,
                    check=_recognized_cancellation,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_details",
                    weight=0.3,
                    check=_emailed_user_details,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_lunch_despite_cancellation",
                    weight=0.0,
                    check=_ordered_despite,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
