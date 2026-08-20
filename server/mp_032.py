"""mp_032 / recurring_lunch_quickadd_pickup_bcc — Xoogle×Xber×Xmail.

Mechanism: create a biweekly team lunch starting TODAY (gym clock ~12:40,
lunch 1–2pm), avoid colliding with a noon block later in the month on the
biweekly cadence, order vegetarian pickup from Xber that arrives **on time
for lunch** (ETA before lunch start vs gym_now), then BCC the team the plan
(not reply-all / To-blast).

UI-discoverable facts:
  - Xoogle red now-line / Today = task `_gym_now` (~12:40 on Thu May 21)
  - Xoogle: Budget Sync today noon; Client Demo Jun 4 noon (biweekly trap)
  - Xoogle Quick Add (+): NL create with every other week / biweekly + today
  - Xber: Vegetarian filter; Delivery/Pickup toggle; ETA labels vs lunch
  - Xmail compose: Bcc field (Ctrl+Shift+B)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_032/recurring_lunch_quickadd_pickup_bcc"
BRIEF_KEY = "mp_032"
BRIEF = (
    "Set up a recurring team lunch every other week starting today, make sure "
    "it does not collide with anything because I might be forgetting about "
    "something later in the month. I also need you to order food from "
    "somewhere with vegetarian options and make sure it gets here on time for "
    "lunch. Make it pickup and then email the team the plan (BCC everyone "
    "instead of a big reply-all thread)."
)

USER_EMAIL = "alice@shopmail.com"
TEAM = (
    "dana@shopgym.com",
    "bea@shopgym.com",
    "cy@shopgym.com",
)

# Frozen gym clock: just before the 1pm lunch window so on-time pickup fits.
GYM_NOW = "2026-05-21T12:40:00"
LUNCH_DAY = "2026-05-21"  # today
LUNCH_START, LUNCH_END = "13:00", "14:00"
LUNCH_TITLE_TOKS = ("team lunch", "lunch")

# Today noon block — traps scheduling lunch over the current hour.
TODAY_BLOCK_ID = "ev_mp032_budget_sync"
TODAY_BLOCK_START, TODAY_BLOCK_END = "12:00", "13:00"
TODAY_BLOCK_TITLE = "Budget Sync"

# Later-in-month biweekly trap: Jun 4 = exactly 2 weeks after May 21.
# Noon slot collides if agent schedules biweekly at noon instead of 1pm.
LATER_BLOCK_ID = "ev_mp032_client_demo"
LATER_BLOCK_DAY = "2026-06-04"
LATER_BLOCK_START, LATER_BLOCK_END = "12:00", "13:00"
LATER_BLOCK_TITLE = "Client Demo"

GOLD_REST = "r_mp032_greenbowl"
GOLD_DISH = "d_mp032_green_bowl"
TRAP_NO_VEG = "r_mp032_burgerlane"
TRAP_SLOW = "r_mp032_slowfeast"


def _eta_max_before_lunch(delivery_time_max: int) -> bool:
    """True if gym_now + delivery_time_max lands at or before lunch start."""
    now = datetime.fromisoformat(GYM_NOW)
    lunch = datetime.fromisoformat(f"{LUNCH_DAY}T{LUNCH_START}:00")
    return now + timedelta(minutes=int(delivery_time_max)) <= lunch


def task_mp_032_recurring_lunch_quickadd_pickup_bcc(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[TODAY_BLOCK_ID] = CalendarEvent(
        id=TODAY_BLOCK_ID,
        title=TODAY_BLOCK_TITLE,
        day=LUNCH_DAY,
        day_label="Thursday (May 21)",
        start=TODAY_BLOCK_START,
        end=TODAY_BLOCK_END,
        source="seed",
        description="Standing budget sync — blocks noon today.",
    )
    # Later-in-month decoy on the biweekly cadence (noon trap, 1pm free).
    cal.events[LATER_BLOCK_ID] = CalendarEvent(
        id=LATER_BLOCK_ID,
        title=LATER_BLOCK_TITLE,
        day=LATER_BLOCK_DAY,
        day_label="Thursday (Jun 4)",
        start=LATER_BLOCK_START,
        end=LATER_BLOCK_END,
        source="seed",
        description="Client demo two weeks out — biweekly noon lunch would collide.",
    )
    cal.events["ev_mp032_allhands"] = CalendarEvent(
        id="ev_mp032_allhands",
        title="All-Hands",
        day="2026-06-09",
        day_label="Tuesday (Jun 9)",
        start="10:00",
        end="11:00",
        source="seed",
    )
    cal.events["ev_mp032_dentist"] = CalendarEvent(
        id="ev_mp032_dentist",
        title="Dentist",
        day="2026-05-28",
        day_label="Thursday (May 28)",
        start="09:00",
        end="09:45",
        source="seed",
    )

    food = world.food
    food.restaurants.clear()
    food.orders.clear()
    food.cart.items.clear()
    # Gold: veg + pickup ETA before lunch start (12:40 + 18m = 12:58 ≤ 13:00).
    assert _eta_max_before_lunch(18)
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Green Bowl Kitchen",
        cuisine="Healthy",
        rating=4.7,
        eta_label="12:55 PM",
        delivery_fee=2.49,
        emoji="🥗",
        delivery_time_min=10,
        delivery_time_max=18,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name="Harvest Veggie Bowl",
                description="Roasted veg, quinoa, tahini — vegetarian.",
                price=14.50,
                tags=["vegetarian"],
                emoji="🥗",
                popular=True,
            ),
            Dish(
                id="d_mp032_green_chicken",
                name="Chicken Power Bowl",
                description="Same base with grilled chicken.",
                price=15.50,
                tags=[],
                emoji="🍗",
            ),
        ],
    )
    # Fast enough for lunch but no vegetarian options.
    food.restaurants[TRAP_NO_VEG] = Restaurant(
        id=TRAP_NO_VEG,
        name="Burger Lane",
        cuisine="Burgers",
        rating=4.5,
        eta_label="12:52 PM",
        delivery_fee=1.99,
        emoji="🍔",
        delivery_time_min=8,
        delivery_time_max=12,
        dishes=[
            Dish(
                id="d_mp032_burger",
                name="Classic Smash Burger",
                description="Beef patty — no vegetarian option on this menu.",
                price=11.00,
                tags=[],
                emoji="🍔",
                popular=True,
            ),
        ],
    )
    # Vegetarian but ETA after lunch start (too late).
    assert not _eta_max_before_lunch(45)
    food.restaurants[TRAP_SLOW] = Restaurant(
        id=TRAP_SLOW,
        name="Slow Feast Garden",
        cuisine="Vegetarian",
        rating=4.8,
        eta_label="1:25 PM",
        delivery_fee=3.49,
        emoji="🍲",
        delivery_time_min=40,
        delivery_time_max=55,
        dishes=[
            Dish(
                id="d_mp032_slow_veg",
                name="Garden Thali",
                description=(
                    "Vegetarian — but ETA is after lunch starts (1:25 PM), "
                    "too late for the 1:00 PM lunch window."
                ),
                price=16.00,
                tags=["vegetarian"],
                emoji="🍲",
                popular=True,
            ),
        ],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp032_team_roster"] = Email(
        id="em_mp032_team_roster",
        sender="dana@shopgym.com",
        to=USER_EMAIL,
        subject="Team lunch people",
        body=(
            "For the recurring team lunch, please loop in "
            f"{TEAM[0]}, {TEAM[1]}, and {TEAM[2]} — BCC is fine so we "
            "don't start a reply-all storm."
        ),
        received_at="2026-05-20T16:00:00",
        received_label="Yesterday",
        read=True,
        labels=["work"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_032_recurring_lunch_quickadd_pickup_bcc,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_events(p: Probe) -> list:
        cal = getattr(p.world, "calendar", None) if p.world else None
        if cal is None:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "calendar", None):
            init = p.initial_world.calendar.events or {}
        return [e for eid, e in (cal.events or {}).items() if eid not in init]

    def _is_lunch(e) -> bool:
        title = (getattr(e, "title", "") or "").lower()
        return any(t in title for t in LUNCH_TITLE_TOKS)

    def _overlaps(e, day: str, start: str, end: str) -> bool:
        if getattr(e, "day", None) != day:
            return False
        s, en = getattr(e, "start", ""), getattr(e, "end", "")
        return bool(s and en and s < end and start < en)

    def _biweekly_lunch(p: Probe) -> bool:
        for e in _new_events(p):
            if not _is_lunch(e):
                continue
            if (getattr(e, "recurring", "") or "").lower() != "biweekly":
                continue
            if getattr(e, "day", None) != LUNCH_DAY:
                continue
            # Prefer the gold 1–2pm window; accept any non-colliding today slot
            # that starts at or after 13:00 so noon traps fail this or collision.
            if getattr(e, "start", "") != LUNCH_START:
                s = getattr(e, "start", "") or ""
                if s < "13:00":
                    continue
            return True
        return False

    def _no_collision(p: Probe) -> bool:
        lunches = [e for e in _new_events(p) if _is_lunch(e)]
        if not lunches:
            return False
        for e in lunches:
            if _overlaps(e, LUNCH_DAY, TODAY_BLOCK_START, TODAY_BLOCK_END):
                return False
            if _overlaps(e, LATER_BLOCK_DAY, LATER_BLOCK_START, LATER_BLOCK_END):
                return False
            # Biweekly series: same wall-clock on LATER_BLOCK_DAY must be free.
            if (getattr(e, "recurring", "") or "").lower() == "biweekly":
                s, en = getattr(e, "start", ""), getattr(e, "end", "")
                if s and en and s < LATER_BLOCK_END and LATER_BLOCK_START < en:
                    # Series would collide with Client Demo on Jun 4.
                    return False
        return True

    def _veg_pickup_on_time_for_lunch(p: Probe) -> bool:
        """Veg dish + pickup from a restaurant whose max ETA is before lunch."""
        food = getattr(p.world, "food", None) if p.world else None
        if food is None:
            return False
        init = {}
        if p.initial_world and getattr(p.initial_world, "food", None):
            init = p.initial_world.food.orders or {}
        restaurants = food.restaurants or {}
        for oid, o in (food.orders or {}).items():
            if oid in init:
                continue
            if (getattr(o, "status", "") or "").lower() in ("cancelled", "canceled"):
                continue
            if (getattr(o, "delivery_mode", "") or "").lower() != "pickup":
                continue
            rid = getattr(o, "restaurant_id", None)
            rest = restaurants.get(rid) if rid else None
            if rest is None:
                continue
            dmax = getattr(rest, "delivery_time_max", None)
            if dmax is None or not _eta_max_before_lunch(int(dmax)):
                continue
            dish_ids = {getattr(it, "dish_id", None) for it in (o.items or [])}
            # Any vegetarian-tagged dish from an on-time restaurant counts;
            # gold path uses Harvest Veggie Bowl at Green Bowl.
            tags_ok = False
            for d in getattr(rest, "dishes", []) or []:
                if d.id in dish_ids and "vegetarian" in (d.tags or []):
                    tags_ok = True
                    break
            if tags_ok or GOLD_DISH in dish_ids:
                return True
        return False

    def _team_bcc(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            bcc = (getattr(se, "bcc", "") or "").lower()
            body = f"{se.subject or ''}\n{se.body or ''}".lower()
            if not any(t in body for t in ("lunch", "pickup", "green bowl", "plan")):
                continue
            if all(addr.lower() in bcc for addr in TEAM):
                return True
        return False

    def _reply_all_blast(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for se in (mail.sent or {}).values():
            to = (getattr(se, "to", "") or "").lower()
            bcc = (getattr(se, "bcc", "") or "").lower()
            on_to = sum(1 for addr in TEAM if addr.lower() in to)
            on_bcc = sum(1 for addr in TEAM if addr.lower() in bcc)
            if on_to >= 2 and on_bcc == 0:
                return True
        return False

    def _colliding_lunch(p: Probe) -> bool:
        for e in _new_events(p):
            if not _is_lunch(e):
                continue
            if _overlaps(e, LUNCH_DAY, TODAY_BLOCK_START, TODAY_BLOCK_END):
                return True
            if (getattr(e, "recurring", "") or "").lower() == "biweekly":
                s, en = getattr(e, "start", ""), getattr(e, "end", "")
                if s and en and s < LATER_BLOCK_END and LATER_BLOCK_START < en:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "recurring_biweekly_from_today_created",
                    weight=0.3,
                    check=_biweekly_lunch,
                    required_for_success=True,
                ),
                Milestone(
                    "no_collision_with_existing_event",
                    weight=0.2,
                    check=_no_collision,
                    required_for_success=True,
                ),
                Milestone(
                    "veg_pickup_on_time_for_lunch_ordered",
                    weight=0.3,
                    check=_veg_pickup_on_time_for_lunch,
                    required_for_success=True,
                ),
                Milestone(
                    "team_emailed_via_bcc",
                    weight=0.2,
                    check=_team_bcc,
                    required_for_success=True,
                ),
                Milestone(
                    "reply_all_or_to_line_blast",
                    weight=0.0,
                    check=_reply_all_blast,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "colliding_lunch_scheduled",
                    weight=0.0,
                    check=_colliding_lunch,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
