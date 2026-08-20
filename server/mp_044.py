"""mp_044 / cousin_dinner_after_flight_settle — Xmail×Xoogle×Xber.

Mechanism: cousin flight info in inbox — lands ~5:10 PM, settled ~6:30 PM.
Dinner should arrive after settle, not at landing.

Forbidden: order food timed for landing (~5:20).
Gold: order dinner with ETA after settle (~6:45).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_044/cousin_dinner_after_flight_settle"
BRIEF_KEY = "mp_044"
BRIEF = (
    "My cousin's visiting, their flight info is somewhere in my inbox. Get "
    "dinner ordered for whenever they'd actually be here and settled, not "
    "right when they land."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T15:10:00"

FLIGHT_MAIL = "em_mp044_flight"
GOLD_REST = "r_mp044_sakura"
GOLD_DISH = "d_mp044_settle_dinner"
TRAP_REST = "r_mp044_burger"
TRAP_DISH = "d_mp044_landing_dinner"


def task_mp_044_cousin_dinner_after_flight_settle(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Food: dinner after settle, not at landing.

    Seed (gym clock 3:10 PM):
      - Mail: cousin lands SFO 5:10 PM; 'I'll be settled at your place by ~6:30'
      - Calendar evening free after 6:30
      - Trap restaurant: ETA 5:20 PM (landing)
      - Gold restaurant: ETA 6:45 PM (after settle)
    Correct: order GOLD_DISH only.
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
    cal.events["ev_mp044_open_evening"] = CalendarEvent(
        id="ev_mp044_open_evening",
        title="Open evening (cousin visit)",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="18:30",
        end="21:00",
        source="seed",
        description="Free after cousin is settled (~6:30). Not a dinner order.",
    )
    cal.events["ev_mp044_call"] = CalendarEvent(
        id="ev_mp044_call",
        title="Quick sync",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="16:00",
        end="16:20",
        source="seed",
    )

    food = world.food
    food.restaurants.clear()
    food.orders.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.restaurants[TRAP_REST] = Restaurant(
        id=TRAP_REST,
        name="Burger Barn Express",
        cuisine="burgers",
        rating=4.7,
        eta_label="5:20 PM",
        delivery_fee=1.99,
        emoji="🍔",
        delivery_time_min=20,
        delivery_time_max=30,
        dishes=[
            Dish(
                id=TRAP_DISH,
                name="Cousin Welcome Burger Duo",
                description="Arrives around landing time (5:20 PM) — too early.",
                price=24.00,
                tags=["dinner", "cousin"],
                emoji="🍔",
                popular=True,
                eta_label="5:20 PM",
            )
        ],
    )
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Sakura Evening Kitchen",
        cuisine="japanese",
        rating=4.5,
        eta_label="6:45 PM",
        delivery_fee=2.49,
        emoji="🍣",
        delivery_time_min=40,
        delivery_time_max=55,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name="Settle-In Dinner Platter",
                description="Arrives ~6:45 PM — after cousin is settled at home.",
                price=32.00,
                tags=["dinner", "cousin", "settle"],
                emoji="🍱",
                popular=True,
                eta_label="6:45 PM",
            )
        ],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[FLIGHT_MAIL] = Email(
        id=FLIGHT_MAIL,
        sender="jamie.cousin@email.com",
        to=USER_EMAIL,
        subject="Flight details — see you tonight",
        body=(
            "Hey! Landing SFO at 5:10 PM today (UA 428). Traffic + bags usually "
            "means I won't actually be at your place and settled until about "
            "6:30 PM. Don't plan dinner for landing — wait until I'm there and "
            "unpacked. Excited to see you!"
        ),
        received_at=f"{SEED_DATE}T11:15:00",
        received_label="11:15 AM",
        read=False,
        labels=["personal", "unread"],
    )
    mail.inbox["em_mp044_old"] = Email(
        id="em_mp044_old",
        sender="jamie.cousin@email.com",
        to=USER_EMAIL,
        subject="Might visit this week",
        body="Still finalizing flights — will send details soon.",
        received_at="2026-05-19T18:00:00",
        received_label="May 19",
        read=True,
        labels=["personal"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_044_cousin_dinner_after_flight_settle,
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
            if "6:45" in eta or "6:4" in eta:
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
            if "5:20" in eta:
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_settle_time_dinner",
                    weight=1.0,
                    check=_ordered_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_landing_time_dinner",
                    weight=0.0,
                    check=_ordered_trap,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
