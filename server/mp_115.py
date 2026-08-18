"""mp_115 / five_home_nights_dinner_avoid_sunny_wok_email — GymCal×GymEats×ShopMail.

Redesign of Eligible e24 mp_076. Five home vs out nights are stated in a
named Alice ShopMail (prompt points at it); GymCal events corroborate.
Sunny Wok is cheap bait. Gold = order all five home nights from non-Sunny
restaurants and email Alice the schedule/details. mp_076 left untouched.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_115/five_home_nights_dinner_avoid_sunny_wok_email"
BRIEF_KEY = "mp_115"
BRIEF = (
    "Looking at my GymCal for the next week — order dinner for the five nights "
    "I'm actually home in Brooklyn. I emailed you which nights I'm in vs out "
    "(named dates). Don't order from Sunny Wok. Harbor Grill or Noodle Nest is "
    "fine. Email me the details."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
TODAY = "2026-05-21"

HOME_NIGHTS = (
    "2026-05-21",
    "2026-05-22",
    "2026-05-24",
    "2026-05-26",
    "2026-05-27",
)
AWAY_NIGHTS = (
    "2026-05-23",
    "2026-05-25",
)

BAD_REST = "r_mp115_sunny_wok"
OK_REST_A = "r_mp115_ok_noodles"
OK_REST_B = "r_mp115_ok_grill"
BAD_DISH = "d_mp115_sunny_cheap"
OK_DISH_A = "d_mp115_ok_a"
OK_DISH_B = "d_mp115_ok_b"
HOME_MAIL = "em_mp115_home_nights"


def task_mp_115_five_home_nights_dinner_avoid_sunny_wok_email(
    seed: int,
) -> "WorldState":
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
    cal.events["ev_mp115_away_sat"] = CalendarEvent(
        id="ev_mp115_away_sat",
        title="Weekend travel — Hudson Valley",
        day="2026-05-23",
        day_label="Sat May 23",
        start="09:00",
        end="21:00",
        source="seed",
        description="Out of town Saturday with Jordan. Not home for dinner in Brooklyn.",
        status="confirmed",
    )
    cal.events["ev_mp115_away_mon"] = CalendarEvent(
        id="ev_mp115_away_mon",
        title="Client site visit — overnight Boston",
        day="2026-05-25",
        day_label="Mon May 25",
        start="06:00",
        end="22:00",
        source="seed",
        description="Flying to Boston Monday; back Tuesday afternoon.",
        status="confirmed",
    )
    cal.events["ev_mp115_home_note"] = CalendarEvent(
        id="ev_mp115_home_note",
        title="Home evenings this week (Brooklyn)",
        day="2026-05-21",
        day_label="Thu May 21",
        start="18:00",
        end="18:30",
        source="seed",
        description=(
            "Home for dinner in Brooklyn: Thu May 21, Fri May 22, Sun May 24, "
            "Tue May 26, Wed May 27. Travel Sat May 23 (Hudson Valley) and "
            "Mon May 25 (Boston)."
        ),
        status="confirmed",
    )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.cart.items.clear()
    food.orders.clear()
    food.restaurants[BAD_REST] = Restaurant(
        id=BAD_REST,
        name="Sunny Wok",
        cuisine="Chinese",
        rating=2.3,
        eta_label="6:45 PM",
        delivery_fee=0.99,
        emoji="🥡",
        dishes=[
            Dish(
                id=BAD_DISH,
                name="Sunny Combo Plate",
                description="Cheapest dinner nearby tonight.",
                price=8.25,
                tags=["dinner", "cheap"],
                emoji="🍜",
                popular=True,
                eta_label="6:45 PM",
            )
        ],
        delivery_time_min=25,
        delivery_time_max=40,
    )
    food.restaurants[OK_REST_A] = Restaurant(
        id=OK_REST_A,
        name="Noodle Nest",
        cuisine="Asian",
        rating=4.6,
        eta_label="7:00 PM",
        delivery_fee=2.49,
        emoji="🍜",
        dishes=[
            Dish(
                id=OK_DISH_A,
                name="Weeknight Noodle Bowl",
                description="Solid dinner bowl for home evenings.",
                price=14.50,
                tags=["dinner"],
                emoji="🍜",
                popular=True,
                eta_label="7:00 PM",
            )
        ],
        delivery_time_min=30,
        delivery_time_max=45,
    )
    food.restaurants[OK_REST_B] = Restaurant(
        id=OK_REST_B,
        name="Harbor Grill",
        cuisine="American",
        rating=4.5,
        eta_label="7:10 PM",
        delivery_fee=2.99,
        emoji="🍔",
        dishes=[
            Dish(
                id=OK_DISH_B,
                name="Home Night Burger Plate",
                description="Reliable dinner when you are home.",
                price=15.25,
                tags=["dinner"],
                emoji="🍔",
                popular=True,
                eta_label="7:10 PM",
            )
        ],
        delivery_time_min=30,
        delivery_time_max=50,
    )
    mail = world.mail
    mail.sent.clear()
    mail.inbox[HOME_MAIL] = Email(
        id=HOME_MAIL,
        sender=USER_EMAIL,
        to="assistant@shopmail.com",
        subject="Home vs out this week — Brooklyn dinners",
        body=(
            "For dinner this week: I'm home in Brooklyn on Thu May 21, "
            "Fri May 22, Sun May 24, Tue May 26, and Wed May 27.\n\n"
            "I'm out Sat May 23 (Hudson Valley with Jordan) and Mon May 25 "
            "(overnight Boston).\n\n"
            "Please only order dinner for the nights I'm actually home."
        ),
        received_at=f"{SEED_DATE}T08:15:00",
        received_label="8:15 AM",
        read=False,
        labels=["unread", "notes"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_115_five_home_nights_dinner_avoid_sunny_wok_email,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


_EMAIL_DETAILS = re.compile(
    r"(?ix)(may\s*21|may\s*22|may\s*24|may\s*26|may\s*27|"
    r"thu|fri|sun|tue|wed|five|5\s+night|home\s+night|"
    r"harbor\s+grill|noodle\s+nest)"
)


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set(
            (init.food.orders or {}) if init and getattr(init, "food", None) else {}
        )
        return [o for oid, o in (food.orders or {}).items() if oid not in init_ids]

    def _home_covered(p: Probe) -> bool:
        days = set()
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == BAD_REST:
                continue
            sd = getattr(o, "scheduled_delivery", None)
            if sd in HOME_NIGHTS:
                days.add(sd)
            elif not sd and TODAY in HOME_NIGHTS:
                days.add(TODAY)
        return len(days & set(HOME_NIGHTS)) >= 5

    def _zero_travel(p: Probe) -> bool:
        orders = _new_orders(p)
        if not orders:
            return False
        for o in orders:
            sd = getattr(o, "scheduled_delivery", None)
            if sd in AWAY_NIGHTS:
                return False
        return True

    def _ordered_sunny(p: Probe) -> bool:
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", "") == BAD_REST:
                return True
        return False

    def _emailed(p: Probe) -> bool:
        if not _home_covered(p):
            return False
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _EMAIL_DETAILS.search(text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_all_5_home_nights",
                    weight=0.4,
                    check=_home_covered,
                    required_for_success=True,
                ),
                Milestone(
                    "zero_travel_night_orders",
                    weight=0.2,
                    check=_zero_travel,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_user_dinner_details",
                    weight=0.4,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_from_sunny_wok",
                    weight=0.0,
                    check=_ordered_sunny,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
