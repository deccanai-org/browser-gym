"""family_001 / parents_visit_travel_dinner — Mail×Calendar×Food.

Mechanism: parents' travel details live in Mail (arrival + departure). Agent
must add both times to Calendar and order dinner for ARRIVAL night (not
departure). Trap = farewell brunch / departure-timed meal instead of arrival
dinner.

Hub map (bridged): Mail → gmail_mock; Calendar → google_calendar_mock;
Food → uber_eats_mock (Xber).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "family_001/parents_visit_travel_dinner"
BRIEF_KEY = "family_001"
BRIEF = (
    "My parents are visiting next weekend. Check their travel details in Mail, "
    "add the important arrival and departure times to Calendar, and order "
    "dinner from Burger Barn (r_burger) for the night they arrive."
)

USER_EMAIL = "alice@shopmail.com"

ARRIVAL_DAY = "2026-05-23"  # Sat — next weekend from Thu May 21
ARRIVAL_TIME = "18:45"
DEPARTURE_DAY = "2026-05-24"  # Sun
DEPARTURE_TIME = "14:10"

ARRIVAL_FLIGHT = "UA 482"
DEPARTURE_FLIGHT = "UA 917"

ARRIVAL_EMAIL = "em_family001_arrival"
DEPARTURE_EMAIL = "em_family001_departure"

# Correct dinner (arrival night) vs trap (departure day brunch)
DINNER_DISH = "d_family001_arrival_dinner"
DINNER_NAME = "Parents Arrival Dinner Platter"
BRUNCH_DISH = "d_family001_farewell_brunch"
BRUNCH_NAME = "Sunday Farewell Brunch Box"


def task_family_001_parents_visit_travel_dinner(seed: int) -> "WorldState":
    """FEASIBLE Mail×Calendar×Food parents-visit logistics.

    Seed (today Thu May 21):
      - Mail: inbound Sat May 23 18:45 UA 482; outbound Sun May 24 14:10 UA 917
      - Calendar: only a gym decoy (agent must ADD arrival + departure)
      - Xber: Arrival Dinner Platter (correct) + Sunday Farewell Brunch (trap)

    Correct: calendar events for arrival + departure; order Arrival Dinner.
    Forbidden: order Sunday Farewell Brunch (departure-timed).
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.food.state import Dish
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.events.clear()
    cal.events["ev_family001_gym"] = CalendarEvent(
        id="ev_family001_gym",
        title="Gym session",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="18:00",
        end="19:00",
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[ARRIVAL_EMAIL] = Email(
        id=ARRIVAL_EMAIL,
        sender="United Airlines <noreply@united.com>",
        to=USER_EMAIL,
        subject=f"Itinerary — {ARRIVAL_FLIGHT} to you this weekend",
        body=(
            "Hi Alice,\n\n"
            f"Your guests are confirmed on {ARRIVAL_FLIGHT}.\n"
            f"Arrival: Saturday, May 23, 2026 at {ARRIVAL_TIME} local "
            "(landing SFO → you).\n"
            "Please meet them after baggage claim.\n\n"
            "— United Airlines"
        ),
        received_at=f"{SEED_DATE}T08:10:00",
        received_label="8:10 AM",
        read=False,
        labels=["travel"],
    )
    m.inbox[DEPARTURE_EMAIL] = Email(
        id=DEPARTURE_EMAIL,
        sender="United Airlines <noreply@united.com>",
        to=USER_EMAIL,
        subject=f"Return itinerary — {DEPARTURE_FLIGHT}",
        body=(
            "Hi Alice,\n\n"
            f"Return flight {DEPARTURE_FLIGHT} is booked.\n"
            f"Departure: Sunday, May 24, 2026 at {DEPARTURE_TIME} local.\n"
            "Please arrive at the airport 2 hours early.\n\n"
            "— United Airlines"
        ),
        received_at=f"{SEED_DATE}T08:12:00",
        received_label="8:12 AM",
        read=False,
        labels=["travel"],
    )

    food = world.food
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()
    burger = food.restaurants["r_burger"]
    burger.eta_label = "6:55 PM"
    burger.dishes = [
        Dish(
            id=DINNER_DISH,
            name=DINNER_NAME,
            description=(
                "Shared dinner platter for family arrival night — roasted "
                "chicken, sides, salad. Timed for Saturday evening when guests "
                "land. Burger Barn deliveries typically arrive around 6:55 PM."
            ),
            price=42.00,
            tags=["dinner", "family", "arrival"],
            emoji="🍽️",
            popular=True,
        ),
        Dish(
            id=BRUNCH_DISH,
            name=BRUNCH_NAME,
            description=(
                "Sunday farewell brunch box — pastries, eggs, fruit. Meant for "
                "the morning they leave, not arrival night. Burger Barn "
                "deliveries typically arrive around 6:55 PM."
            ),
            price=28.00,
            tags=["brunch", "farewell", "departure"],
            emoji="🥐",
            popular=True,
        ),
        Dish(
            id="d_family001_fries",
            name="Crispy Fries",
            description="Side fries only — not a parents dinner.",
            price=4.00,
            tags=["side"],
            emoji="🍟",
        ),
    ]
    # Strip sushi/coffee to reduce noise (keep restaurants for ambient)
    sushi = food.restaurants["r_sushi"]
    sushi.dishes = [
        d for d in sushi.dishes if d.id in ("d_salmon_roll", "d_miso")
    ] or sushi.dishes[:2]
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_family_001_parents_visit_travel_dinner,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _events(p: Probe) -> list:
        cal = getattr(p.world, "calendar", None) if p.world else None
        return list((cal.events or {}).values()) if cal else []

    def _new_food(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "food", None):
            init = p.initial_world.food.orders or {}
        return [o for oid, o in (food.orders or {}).items() if oid not in init]

    def _has_arrival_event(p: Probe) -> bool:
        for ev in _events(p):
            day = getattr(ev, "day", "") or ""
            title = (getattr(ev, "title", "") or "").lower()
            start = getattr(ev, "start", "") or ""
            if day == ARRIVAL_DAY and (
                start.startswith("18:4")
                or start == ARRIVAL_TIME
                or "arriv" in title
                or "ua 482" in title
                or "parents" in title
            ):
                return True
            if day == ARRIVAL_DAY and ("flight" in title or "ua" in title):
                return True
        # Accept any user-created event on arrival day with evening start
        for ev in _events(p):
            if getattr(ev, "day", None) != ARRIVAL_DAY:
                continue
            if getattr(ev, "source", "") == "seed":
                continue
            start = getattr(ev, "start", "") or "00:00"
            if start >= "17:00":
                return True
        return False

    def _has_departure_event(p: Probe) -> bool:
        for ev in _events(p):
            day = getattr(ev, "day", "") or ""
            title = (getattr(ev, "title", "") or "").lower()
            start = getattr(ev, "start", "") or ""
            if day == DEPARTURE_DAY and (
                start.startswith("14:1")
                or start == DEPARTURE_TIME
                or "depart" in title
                or "ua 917" in title
                or "return" in title
                or "leave" in title
            ):
                return True
            if day == DEPARTURE_DAY and getattr(ev, "source", "") != "seed":
                if start.startswith("14") or "flight" in title or "ua" in title:
                    return True
        return False

    def _ordered_dinner(p: Probe) -> bool:
        for o in _new_food(p):
            for it in o.items:
                if getattr(it, "dish_id", None) == DINNER_DISH:
                    return True
        return False

    def _ordered_brunch_trap(p: Probe) -> bool:
        for o in _new_food(p):
            for it in o.items:
                if getattr(it, "dish_id", None) == BRUNCH_DISH:
                    return True
        return False

    def _success(p: Probe) -> bool:
        return (
            _has_arrival_event(p)
            and _has_departure_event(p)
            and _ordered_dinner(p)
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "calendar_arrival_and_departure",
                    weight=0.4,
                    check=lambda p: _has_arrival_event(p) and _has_departure_event(p),
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_arrival_dinner",
                    weight=0.6,
                    check=_ordered_dinner,
                    required_for_success=True,
                ),
                Milestone(
                    "forbidden_departure_brunch",
                    weight=0.0,
                    check=_ordered_brunch_trap,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}


_SUITE_CACHE: dict[str, Callable[[], "TaskSuite"]] | None = None


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    global _SUITE_CACHE
    if _SUITE_CACHE is None:
        _SUITE_CACHE = _build_suites()
    return _SUITE_CACHE
