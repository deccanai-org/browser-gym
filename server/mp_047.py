"""mp_047 / lunch_1pm_meeting_may_run_long — Xber×Xoogle.

Mechanism: order lunch for a 1pm meeting that sometimes runs over. Food that
arrives at meeting start is wrong; food that stays fine past the hour (after
likely overrun) is gold.

Forbidden: order the early ETA that arrives at ~1:05.
Gold: order lunch with ETA after ~2:15 (survives overrun).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_047/lunch_1pm_meeting_may_run_long"
BRIEF_KEY = "mp_047"
BRIEF = (
    "Order lunch for my 1pm meeting today, but that meeting sometimes runs "
    "over, so make sure whatever you order will still be fine even if it "
    "goes a bit past the hour."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:50:00"

MEETING_ID = "ev_mp047_product_sync"
MEETING_START, MEETING_END = "13:00", "14:00"

GOLD_REST = "r_mp047_latebowl"
GOLD_DISH = "d_mp047_late_lunch"
TRAP_REST = "r_mp047_express"
TRAP_DISH = "d_mp047_early_lunch"


def task_mp_047_lunch_1pm_meeting_may_run_long(seed: int) -> "WorldState":
    """FEASIBLE Food×Cal: lunch survives 1pm meeting overrun.

    Seed (gym clock 11:50):
      - Calendar: Product sync 1:00–2:00 PM (sometimes runs past the hour)
      - Trap: Express lunch ETA 1:05 PM (arrives at start — cold/gone if overrun)
      - Gold: Hearty lunch ETA 2:20 PM (still fine after overrun)
    Correct: order GOLD_DISH.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
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
    cal.events[MEETING_ID] = CalendarEvent(
        id=MEETING_ID,
        title="Product sync",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=MEETING_START,
        end=MEETING_END,
        source="seed",
        description=(
            "1pm product sync. Often runs 15–20 minutes past the hour — "
            "plan lunch that is still fine after 2:00."
        ),
    )
    cal.events["ev_mp047_standup"] = CalendarEvent(
        id="ev_mp047_standup",
        title="Morning standup",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="09:30",
        end="09:45",
        source="seed",
    )

    food = world.food
    food.restaurants.clear()
    food.orders.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.restaurants[TRAP_REST] = Restaurant(
        id=TRAP_REST,
        name="Lightning Lunch Express",
        cuisine="sandwiches",
        rating=4.8,
        eta_label="1:05 PM",
        delivery_fee=1.49,
        emoji="⚡",
        delivery_time_min=15,
        delivery_time_max=25,
        dishes=[
            Dish(
                id=TRAP_DISH,
                name="Express Club Sandwich",
                description=(
                    "Arrives ~1:05 PM at meeting start. Gets cold / awkward if "
                    "the sync runs past 2:00."
                ),
                price=13.50,
                tags=["lunch", "fast"],
                emoji="🥪",
                popular=True,
                eta_label="1:05 PM",
            )
        ],
    )
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="SlowSimmer Bowls",
        cuisine="bowls",
        rating=4.4,
        eta_label="2:20 PM",
        delivery_fee=2.49,
        emoji="🍲",
        delivery_time_min=50,
        delivery_time_max=70,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name="Stay-Warm Grain Bowl",
                description=(
                    "Arrives ~2:20 PM — still hot and fine even if the 1pm "
                    "meeting runs a bit past the hour."
                ),
                price=15.00,
                tags=["lunch", "meeting"],
                emoji="🥣",
                popular=True,
                eta_label="2:20 PM",
            )
        ],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp047_hint"] = Email(
        id="em_mp047_hint",
        sender="bea@shopgym.com",
        to=USER_EMAIL,
        subject="Re: product sync running long again?",
        body=(
            "Heads up — yesterday's product sync spilled to ~2:15. If you're "
            "ordering lunch for today's 1pm, maybe don't time it for exactly 1."
        ),
        received_at=f"{SEED_DATE}T10:05:00",
        received_label="10:05 AM",
        read=True,
        labels=["work"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_047_lunch_1pm_meeting_may_run_long,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _ordered_gold(p: Probe) -> bool:
        for o in _orders(p).values():
            if (getattr(o, "status", "") or "") == "cancelled":
                continue
            for it in getattr(o, "items", []) or []:
                if getattr(it, "dish_id", "") == GOLD_DISH:
                    return True
            eta = (getattr(o, "eta_label", "") or "").lower()
            if "2:20" in eta:
                return True
        return False

    def _ordered_trap(p: Probe) -> bool:
        for o in _orders(p).values():
            if (getattr(o, "status", "") or "") == "cancelled":
                continue
            for it in getattr(o, "items", []) or []:
                if getattr(it, "dish_id", "") == TRAP_DISH:
                    return True
            eta = (getattr(o, "eta_label", "") or "").lower()
            if "1:05" in eta:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_overrun_safe_lunch",
                    weight=1.0,
                    check=_ordered_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_early_meeting_start_lunch",
                    weight=0.0,
                    check=_ordered_trap,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
