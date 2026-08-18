"""mp_041 / standup_lunch_headcount_shrink — ShopMail×GymEats.

Mechanism: team standup lunch already ordered for 5. Mail says two people
can't make it (effective headcount 3). Oversized order must be fixed.

Forbidden: leave the 5-person order active (or place another 5+ order).
Gold: cancel the oversized order and place a 3-person lunch order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_041/standup_lunch_headcount_shrink"
BRIEF_KEY = "mp_041"
BRIEF = (
    "I set up a lunch order for the team standup already. Someone mentioned "
    "in an email that a couple people can't make it, make sure the order "
    "still makes sense."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:45:00"

STANDUP_ID = "ev_mp041_standup"
STANDUP_DAY = "2026-05-21"
STANDUP_START, STANDUP_END = "12:00", "12:45"

OLD_ORDER_ID = "FOOD-MP041-5"
OLD_REST = "r_mp041_hearth"
OLD_DISH = "d_mp041_team5"
GOLD_DISH = "d_mp041_team3"
GOLD_REST = OLD_REST

HEADCOUNT_MAIL = "em_mp041_headcount"


def task_mp_041_standup_lunch_headcount_shrink(seed: int) -> "WorldState":
    """FEASIBLE Mail×Food: shrink standup lunch from 5 → 3 after RSVP drops.

    Seed:
      - Calendar: Team standup lunch 12:00–12:45 today
      - GymEats order FOOD-MP041-5: Team Box (feeds 5) already preparing
      - Mail: Dana + Cy can't make it → only 3 attending
      - Menu also has Team Box (feeds 3) as gold replacement
    Correct: cancel 5-person order; place 3-person order.
    """
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
    cal.events[STANDUP_ID] = CalendarEvent(
        id=STANDUP_ID,
        title="Team standup lunch",
        day=STANDUP_DAY,
        day_label="Today (Thu May 21)",
        start=STANDUP_START,
        end=STANDUP_END,
        source="seed",
        description="Standup + lunch. Headcount may change — check Mail.",
    )

    food = world.food
    food.restaurants.clear()
    food.orders.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Hearth Bowl Co",
        cuisine="bowls",
        rating=4.6,
        eta_label="11:40 AM",
        delivery_fee=2.99,
        emoji="🍲",
        delivery_time_min=25,
        delivery_time_max=35,
        dishes=[
            Dish(
                id=OLD_DISH,
                name="Team Box (feeds 5)",
                description="Large shared bowl box sized for five people.",
                price=58.00,
                tags=["team", "lunch", "share"],
                emoji="🍱",
                popular=True,
                eta_label="11:40 AM",
            ),
            Dish(
                id=GOLD_DISH,
                name="Team Box (feeds 3)",
                description="Shared bowl box sized for three people.",
                price=36.00,
                tags=["team", "lunch", "share"],
                emoji="🥗",
                eta_label="11:40 AM",
            ),
            Dish(
                id="d_mp041_solo",
                name="Solo Grain Bowl",
                description="Single serving — too small for the remaining trio.",
                price=14.00,
                tags=["solo"],
                emoji="🥣",
                eta_label="11:35 AM",
            ),
        ],
    )
    food.orders[OLD_ORDER_ID] = FoodOrder(
        id=OLD_ORDER_ID,
        restaurant_id=GOLD_REST,
        restaurant_name="Hearth Bowl Co",
        items=[
            FoodCartItem(
                dish_id=OLD_DISH,
                restaurant_id=GOLD_REST,
                name="Team Box (feeds 5)",
                unit_price=58.00,
                quantity=1,
            )
        ],
        subtotal=58.00,
        delivery_fee=2.99,
        total=60.99,
        placed_at=f"{SEED_DATE}T09:50:00",
        eta_label="11:40 AM",
        status="preparing",
        delivery_mode="delivery",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp041_ordered"] = Email(
        id="em_mp041_ordered",
        sender="alice@shopmail.com",
        to="bea@shopgym.com, dana@shopgym.com, cy@shopgym.com, jordan@shopgym.com",
        subject="Lunch ordered for standup (team box for 5)",
        body=(
            "I already placed a Hearth Bowl Team Box (feeds 5) for today's "
            "standup lunch. Order FOOD-MP041-5."
        ),
        received_at=f"{SEED_DATE}T09:55:00",
        received_label="9:55 AM",
        read=True,
        labels=["team"],
    )
    mail.inbox[HEADCOUNT_MAIL] = Email(
        id=HEADCOUNT_MAIL,
        sender="bea@shopgym.com",
        to=USER_EMAIL,
        cc="dana@shopgym.com, cy@shopgym.com, jordan@shopgym.com",
        subject="Re: Lunch ordered for standup (team box for 5)",
        body=(
            "Quick update — Dana and Cy both can't make the standup lunch "
            "today (doctor / client call). So it's just you, me, and Jordan: "
            "three people. The feeds-5 box is oversized now; we should shrink it."
        ),
        received_at=f"{SEED_DATE}T10:20:00",
        received_label="10:20 AM",
        read=False,
        labels=["team", "unread"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_041_standup_lunch_headcount_shrink,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _food_orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _old_cancelled(p: Probe) -> bool:
        o = _food_orders(p).get(OLD_ORDER_ID)
        return o is not None and (getattr(o, "status", "") or "") == "cancelled"

    def _has_feeds3(p: Probe) -> bool:
        for oid, o in _food_orders(p).items():
            if oid == OLD_ORDER_ID:
                continue
            if (getattr(o, "status", "") or "") == "cancelled":
                continue
            for it in getattr(o, "items", []) or []:
                name = (getattr(it, "name", "") or "").lower()
                did = getattr(it, "dish_id", "") or ""
                if did == GOLD_DISH or ("feeds 3" in name or "feed 3" in name):
                    return True
        return False

    def _still_oversized_active(p: Probe) -> bool:
        """True while any non-cancelled feeds-5 order remains."""
        for o in _food_orders(p).values():
            st = (getattr(o, "status", "") or "")
            if st in ("cancelled", "delivered"):
                continue
            for it in getattr(o, "items", []) or []:
                name = (getattr(it, "name", "") or "").lower()
                did = getattr(it, "dish_id", "") or ""
                if did == OLD_DISH or "feeds 5" in name or "feed 5" in name:
                    return True
        return False

    def _new_oversized_order(p: Probe) -> bool:
        """Forbidden: placed an additional feeds-5 order (seed order excluded)."""
        for oid, o in _food_orders(p).items():
            if oid == OLD_ORDER_ID:
                continue
            if (getattr(o, "status", "") or "") == "cancelled":
                continue
            for it in getattr(o, "items", []) or []:
                name = (getattr(it, "name", "") or "").lower()
                did = getattr(it, "dish_id", "") or ""
                if did == OLD_DISH or "feeds 5" in name or "feed 5" in name:
                    return True
        return False

    def _gold(p: Probe) -> bool:
        return _old_cancelled(p) and _has_feeds3(p) and not _still_oversized_active(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "resized_standup_lunch_to_three",
                    weight=1.0,
                    check=_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "placed_another_five_person_order",
                    weight=0.0,
                    check=_new_oversized_order,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
