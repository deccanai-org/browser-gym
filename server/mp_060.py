"""mp_060 / cousin_dinner_email_calendar_schedule — ShopMail×GymCal×GymEats.

Same id (Eligible e9). 2026-08-11 **Friday rewrite** (v2): uniqueness is
Friday-only dinner (Thu dentist distract; Sat pottery overlap; Sun departure)
with vegetarian + for-two + under-$30. Prior v1 used Thursday-gold / Fri Team-sync.
See MP060_FRIDAY_REWRITE_2026-08-11.md + TASK_VERSION_HISTORY_2026-08-11.md.

Mechanism: cousin fluff email buries Saturday pottery 1–8pm (dinner-hours
overlap by arithmetic) + Sunday morning departure; user's calendar has an
unrelated Thursday dentist so Friday clear is not a free pass. Sole valid
dinner night is Friday. Order must be vegetarian, for two, durable total < $30,
and schedule-ahead (not ASAP).

Requires food.enable_schedule_ahead = True so FoodOrder.scheduled_delivery
persists from the hub Now/Schedule picker (btn-schedule-*).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_060/cousin_dinner_email_calendar_schedule"
BRIEF_KEY = "mp_060"
BRIEF = (
    "My cousin Jamie is visiting for a long weekend and I want to plan something nice. "
    "Check the email she sent, see what days work around my calendar, and get a "
    "vegetarian dinner for two under 30 dollars for whichever night makes sense."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

# Long-weekend window (May 2026 gym calendar convention)
THU = "2026-05-21"  # dentist distractor; Jamie not yet arrived
FRI = "2026-05-22"  # sole valid dinner night (Jamie arrives midday; evening open)
SAT = "2026-05-23"  # cousin pottery 1–8pm blocks dinner hours
SUN = "2026-05-24"  # cousin heading back Sunday morning

COUSIN_EMAIL_ID = "em_mp060_cousin_visit"
DENTIST_EVENT = "ev_mp060_dentist"

GOLD_REST = "r_mp060_dinner"
GOLD_DISH = "d_mp060_veg_for_two"          # named for-two + vegetarian + under $30 w/ fee
TRAP_MEAT = "d_mp060_steak_for_two"        # non-vegetarian trap
TRAP_PRICE = "d_mp060_veg_tasting"         # vegetarian but over budget
VEG_SINGLE = "d_mp060_veggie_bowl"         # vegetarian; qty≥2 also satisfies for-two

BUDGET = 30.0

COUSIN_EMAIL_BODY = (
    "hii!! ok so I am SO excited to finally come visit, it's been way too long. "
    "also I finally got that new car (the little blue one I sent you pics of, "
    "remember) so the drive up won't be as bad as last time lol. I'll get in "
    "Friday sometime midday. anyway I looked up the weather and it's supposed to "
    "be nice the whole time which is great because I really want to just walk "
    "around and not be stuck inside. oh also I signed up for that pottery class "
    "thing on Saturday, it runs like 1 to 8pm which is annoyingly long, so that "
    "whole day's kind of shot, but otherwise I'm free the whole time honestly. "
    "heading back Sunday morning so we'll have to squeeze it in before then. "
    "can't wait to catch up properly, see you soon!"
)


def task_mp_060_cousin_dinner_email_calendar_schedule(seed: int) -> "WorldState":
    """FEASIBLE Mail×Cal×Food: schedule vegetarian dinner for Friday only.

    Seed (gym clock Thu May 21 noon):
      - Mail: Jamie Anderson fluff; Fri midday arrival; Sat pottery 1–8pm;
        Sunday morning departure
      - Cal: Thu dentist (distract); Fri/Sat/Sun free on user side (no Team sync)
      - Food: enable_schedule_ahead=True; veg for-two under $30 + traps
    Correct: FoodOrder.scheduled_delivery == 2026-05-22 (Friday), vegetarian,
    for-two durable, total < $30.
    """
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
    # Unrelated Thursday dentist — forces calendar open; Friday has no conflict.
    cal.events[DENTIST_EVENT] = CalendarEvent(
        id=DENTIST_EVENT,
        title="Dentist cleaning",
        day=THU,
        day_label="Thu May 21",
        start="15:00",
        end="16:00",
        source="seed",
        description="Routine cleaning — unrelated to the cousin visit.",
    )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.cart.scheduled_delivery = None
    food.orders.clear()
    # delivery_fee 2.49 → gold dish 26.50 yields total 28.99 < 30
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Harbor Table",
        cuisine="American",
        rating=4.7,
        eta_label="7:00 PM",
        delivery_fee=2.49,
        emoji="🍽️",
        dishes=[
            Dish(
                id=GOLD_DISH,
                name="Vegetarian Dinner for Two",
                description=(
                    "Shared garden plate for two — roasted veg, grains, and "
                    "seasonal salad. Vegetarian."
                ),
                price=26.50,
                tags=["vegetarian", "dinner", "for-two"],
                emoji="🥗",
                popular=True,
                eta_label="7:00 PM",
            ),
            Dish(
                id=VEG_SINGLE,
                name="Harvest Veggie Bowl",
                description="Single vegetarian bowl — order two for a pair.",
                price=12.00,
                tags=["vegetarian", "bowl"],
                emoji="🥬",
                popular=False,
                eta_label="7:00 PM",
            ),
            Dish(
                id=TRAP_MEAT,
                name="Steak Dinner for Two",
                description="Ribeye shared plate for two — not vegetarian.",
                price=28.00,
                tags=["dinner", "meat", "for-two"],
                emoji="🥩",
                popular=True,
                eta_label="7:00 PM",
            ),
            Dish(
                id=TRAP_PRICE,
                name="Chef Vegetarian Tasting for Two",
                description="Six-course vegetarian tasting — exceeds a $30 budget.",
                price=42.00,
                tags=["vegetarian", "dinner", "for-two"],
                emoji="🍽️",
                popular=False,
                eta_label="7:30 PM",
            ),
        ],
        delivery_time_min=30,
        delivery_time_max=45,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[COUSIN_EMAIL_ID] = Email(
        id=COUSIN_EMAIL_ID,
        sender="Jamie Anderson <jamie.anderson@email.com>",
        to=USER_EMAIL,
        subject="omg can't wait!!",
        body=COUSIN_EMAIL_BODY,
        received_at=f"{SEED_DATE}T09:40:00",
        received_label="9:40 AM",
        read=False,
        labels=["personal", "unread"],
    )
    mail.inbox["em_mp060_noise"] = Email(
        id="em_mp060_noise",
        sender="deals@shopmail.com",
        to=USER_EMAIL,
        subject="Weekend brunch specials near you",
        body="Half-off brunch this Saturday — book a table!",
        received_at="2026-05-20T16:00:00",
        received_label="May 20",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_060_cousin_dinner_email_calendar_schedule,
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

    def _sd(o) -> str | None:
        sd = getattr(o, "scheduled_delivery", None)
        if sd is None:
            return None
        sd = str(sd).strip()
        return sd or None

    def _dish_lookup(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        out: dict = {}
        if food is None:
            return out
        for r in (food.restaurants or {}).values():
            for d in getattr(r, "dishes", None) or []:
                out[d.id] = d
        return out

    def _order_lines(o) -> list:
        return list(getattr(o, "items", None) or [])

    def _is_vegetarian_line(p: Probe, it) -> bool:
        """Item-level: dish tags include 'vegetarian' (real scorable field)."""
        dishes = _dish_lookup(p)
        did = getattr(it, "dish_id", None)
        d = dishes.get(did) if did else None
        if d is None:
            # Fall back to name hint only if dish vanished from menu
            name = (getattr(it, "name", "") or "").lower()
            return "vegetarian" in name or "veggie" in name
        tags = [t.lower() for t in (getattr(d, "tags", None) or [])]
        if "vegetarian" in tags or "vegan" in tags:
            return True
        if "meat" in tags or "seafood" in tags:
            return False
        name = (getattr(d, "name", "") or "").lower()
        return "vegetarian" in name or "veggie" in name

    def _is_for_two_line(it) -> bool:
        """Durable for-two: qty≥2 OR named for-two / serves-2 portion."""
        qty = int(getattr(it, "quantity", 1) or 1)
        if qty >= 2:
            return True
        name = (getattr(it, "name", "") or "").lower()
        return any(
            tok in name
            for tok in ("for two", "for 2", "serves 2", "serves-2", "feeds 2")
        )

    def _read_full_cousin_email(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(COUSIN_EMAIL_ID)
        return bool(e and getattr(e, "read", False))

    def _identified_saturday_unavailable(p: Probe) -> bool:
        """Proxy: read fluff with 1–8pm pottery range, then do not schedule Saturday.

        Dinner-hours overlap is arithmetic on the seeded time range (1–8pm ∩ ~6–9pm).
        """
        if not _read_full_cousin_email(p):
            return False
        orders = _new_orders(p)
        if not orders:
            return False
        return all(_sd(o) != SAT for o in orders)

    def _checked_own_calendar_friday_clear(p: Probe) -> bool:
        """Must open calendar (Thu dentist distractor); Friday has no blocking event."""
        if _log_has(p, "viewed_calendar"):
            return True
        url = (p.active_tab_url or p.url or "")
        return "/calendar" in url

    def _selected_friday(p: Probe) -> bool:
        return any(_sd(o) == FRI for o in _new_orders(p))

    def _ordered_vegetarian_for_two(p: Probe) -> bool:
        """Item-level durable: every line vegetarian-tagged AND for-two satisfied."""
        for o in _new_orders(p):
            lines = _order_lines(o)
            if not lines:
                continue
            if not all(_is_vegetarian_line(p, it) for it in lines):
                continue
            # For-two: any line qty≥2 / named for-two, OR total veg qty ≥ 2
            if any(_is_for_two_line(it) for it in lines):
                return True
            total_qty = sum(int(getattr(it, "quantity", 1) or 1) for it in lines)
            if total_qty >= 2:
                return True
        return False

    def _order_total_under_30(p: Probe) -> bool:
        return any(
            float(getattr(o, "total", 0) or 0) < BUDGET
            for o in _new_orders(p)
        )

    def _ordered_saturday(p: Probe) -> bool:
        return any(_sd(o) == SAT for o in _new_orders(p))

    def _ordered_non_vegetarian(p: Probe) -> bool:
        for o in _new_orders(p):
            for it in _order_lines(o):
                if not _is_vegetarian_line(p, it):
                    return True
        return False

    def _order_total_over_30(p: Probe) -> bool:
        return any(
            float(getattr(o, "total", 0) or 0) > BUDGET
            for o in _new_orders(p)
        )

    def _asap_despite_future_pick(p: Probe) -> bool:
        """Tripwire: a placed order has null/ASAP scheduled_delivery.

        Catches Deliver-now shortcuts and the enable_schedule_ahead=False
        flag-gate failure (UI slot selected, durable state still ASAP).
        """
        return any(_sd(o) is None for o in _new_orders(p))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "read_full_cousin_email",
                    weight=0.2,
                    check=_read_full_cousin_email,
                    required_for_success=True,
                ),
                Milestone(
                    "identified_saturday_unavailable_from_time_range",
                    weight=0.2,
                    check=_identified_saturday_unavailable,
                    required_for_success=True,
                ),
                Milestone(
                    "checked_own_calendar_confirmed_friday_clear",
                    weight=0.15,
                    check=_checked_own_calendar_friday_clear,
                    required_for_success=True,
                ),
                Milestone(
                    "selected_friday_as_correct_night",
                    weight=0.15,
                    check=_selected_friday,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_vegetarian_dinner_for_two",
                    weight=0.15,
                    check=_ordered_vegetarian_for_two,
                    required_for_success=True,
                ),
                Milestone(
                    "order_total_under_30",
                    weight=0.15,
                    check=_order_total_under_30,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_on_saturday_conflict_night",
                    weight=0.0,
                    check=_ordered_saturday,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_non_vegetarian_item",
                    weight=0.0,
                    check=_ordered_non_vegetarian,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "order_total_over_30",
                    weight=0.0,
                    check=_order_total_over_30,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "order_defaulted_to_asap_despite_future_pick",
                    weight=0.0,
                    check=_asap_despite_future_pick,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
