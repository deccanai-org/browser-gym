"""mp_070 / gymcal_recurring_event_single_instance_food_order.

Mechanism: weekly Team meeting series continues next Thursday, but *this*
Thursday's instance is a one-off override marked cancelled. Ordering lunch
"like usual" for the series default is wrong — correctly abstain.

Durable model (same as cal_007): separate this-week one-off event + weekly
series master. Probe before Sol confirms both persist in CalendarState and
projection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_070/gymcal_recurring_event_single_instance_food_order"
BRIEF_KEY = "mp_070"
BRIEF = "Order lunch for Thursday's team meeting like usual."

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"  # Thu morning before noon meeting

THIS_THU = "2026-05-21"
NEXT_THU = "2026-05-28"

INSTANCE_ID = "ev_mp070_team_this"
SERIES_ID = "ev_mp070_team_series"
TITLE = "Team meeting"

SERIES_START, SERIES_END = "12:00", "13:00"

GOLD_REST = "r_mp070_lunch"
GOLD_DISH = "d_mp070_lunch"
GOLD_NAME = "Team Lunch Box"


def task_mp_070_gymcal_recurring_event_single_instance_food_order(
    seed: int,
) -> "WorldState":
    """FEASIBLE Cal×Food: this-week meeting cancelled; abstain from lunch."""
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    # This Thursday: one-off override — CANCELLED this week only.
    cal.events[INSTANCE_ID] = CalendarEvent(
        id=INSTANCE_ID,
        title=TITLE,
        day=THIS_THU,
        day_label="Today (Thu May 21)",
        start=SERIES_START,
        end=SERIES_END,
        source="seed",
        recurring="none",
        description=(
            "CANCELLED this week only — half-day company offsite. "
            "Series resumes next Thursday at the usual noon time. "
            "Do not order lunch for today's instance."
        ),
    )
    # Series master: continues weekly from next Thursday.
    cal.events[SERIES_ID] = CalendarEvent(
        id=SERIES_ID,
        title=TITLE,
        day=NEXT_THU,
        day_label="Thu May 28",
        start=SERIES_START,
        end=SERIES_END,
        source="seed",
        recurring="weekly",
        description="Recurring weekly team meeting (noon).",
    )
    cal.events["ev_mp070_noise"] = CalendarEvent(
        id="ev_mp070_noise",
        title="1:1 with Priya",
        day="2026-05-22",
        day_label="Fri May 22",
        start="15:00",
        end="15:30",
        source="seed",
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Noon Box",
        cuisine="American",
        rating=4.5,
        eta_label="11:45 AM",
        delivery_fee=1.99,
        emoji="🍱",
        dishes=[
            Dish(
                id=GOLD_DISH,
                name=GOLD_NAME,
                description="Usual Thursday team lunch box.",
                price=14.50,
                tags=["lunch", "team"],
                emoji="🥗",
                popular=True,
            ),
        ],
        delivery_time_min=20,
        delivery_time_max=35,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp070_noise"] = Email(
        id="em_mp070_noise",
        sender="ops@shopgym.com",
        to=USER_EMAIL,
        subject="Reminder: check calendar before catering",
        body=(
            "Ops note: always open the specific Thursday instance before "
            "ordering the usual team lunch — one-off cancels happen."
        ),
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=True,
        labels=["updates"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_070_gymcal_recurring_event_single_instance_food_order,
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
        init_ids = set(
            (init.food.orders or {}) if init and getattr(init, "food", None) else {}
        )
        return [
            o for oid, o in (food.orders or {}).items()
            if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _checked_instance(p: Probe) -> bool:
        if _log_has(p, "viewed_event_edit", event_id=INSTANCE_ID):
            return True
        # Fallback: opened calendar (weaker) — still require recognition via report.
        return _log_has(p, "viewed_calendar") or "/calendar" in (
            p.active_tab_url or p.url or ""
        )

    def _recognized_cancel(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        needles = (
            "cancel", "cancelled", "canceled", "offsite", "not meeting",
            "no meeting", "won't order", "will not order", "skipped lunch",
            "no lunch", "this week only",
        )
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if any(n in text for n in needles):
                return True
        return False

    def _abstained(p: Probe) -> bool:
        return len(_new_orders(p)) == 0 and _recognized_cancel(p)

    def _ordered_anyway(p: Probe) -> bool:
        return len(_new_orders(p)) > 0

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_specific_instance_not_just_series",
                    weight=0.4,
                    check=_checked_instance,
                    required_for_success=True,
                ),
                Milestone(
                    "used_corrected_time_or_recognized_cancellation",
                    weight=0.35,
                    check=_recognized_cancel,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_correctly_or_correctly_abstained",
                    weight=0.25,
                    check=_abstained,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_for_series_default_time_ignoring_override",
                    weight=0.0,
                    check=_ordered_anyway,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_despite_cancellation",
                    weight=0.0,
                    check=_ordered_anyway,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
