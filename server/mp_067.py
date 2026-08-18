"""mp_067 / gymeats_group_order_dietary_conflict_reschedule.

Mechanism: ShopMail RSVP thread revises headcount, diet, and date mid-thread.
GymCal still shows the *old* game-night date (stale). Mail is fresher — order
must use final Sunday date + dairy-free + cancelled guest removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_067/gymeats_group_order_dietary_conflict_reschedule"
BRIEF_KEY = "mp_067"
BRIEF = (
    "Can you sort dinner for game night, check who's coming and what they "
    "can eat."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

OLD_DAY = "2026-05-23"  # Sat — stale calendar + early mail
NEW_DAY = "2026-05-24"  # Sun — final reschedule in mail

CAL_EVENT = "ev_mp067_game_night"
THREAD = [
    "em_mp067_m1_invite",
    "em_mp067_m2_bob",
    "em_mp067_m3_carol_ok",
    "em_mp067_m4_dan_cancel",
    "em_mp067_m5_reschedule",
    "em_mp067_m6_carol_dairy",
]

GOLD_REST = "r_mp067_game"
GOLD_DISH = "d_mp067_dairyfree_pack"
GOLD_NAME = "Dairy-Free Game Night Pack (serves 3)"

TRAP_DAIRY = "d_mp067_cheese_pizza"
TRAP_REST = "r_mp067_dairytrap"


def task_mp_067_gymeats_group_order_dietary_conflict_reschedule(
    seed: int,
) -> "WorldState":
    """FEASIBLE Mail×Cal×Food: final RSVP state over stale calendar."""
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
    # Stale: still Saturday. Mail later moves game night to Sunday.
    cal.events[CAL_EVENT] = CalendarEvent(
        id=CAL_EVENT,
        title="Game night",
        day=OLD_DAY,
        day_label="Sat May 23",
        start="18:00",
        end="22:00",
        source="seed",
        description=(
            "Board-game night at Alice's — date may change; check the email "
            "thread for the latest."
        ),
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    # Chronological seed; UI sorts newest-first so dietary + reschedule aren't
    # the absolute top without opening older messages in the same subject.
    rows = [
        (
            THREAD[0], "alice@shopmail.com", f"{SEED_DATE}T09:00:00", "9:00 AM", True,
            "Game night this Saturday? Thinking pizza for four — Bob, Carol, "
            "Dan, and me. Reply if you're in.",
        ),
        (
            THREAD[1], "bob@shopmail.com", f"{SEED_DATE}T09:40:00", "9:40 AM", True,
            "I'm in! Saturday works. Pepperoni is fine for me.",
        ),
        (
            THREAD[2], "carol@shopmail.com", f"{SEED_DATE}T10:15:00", "10:15 AM", True,
            "Count me in for Saturday. Pizza sounds great — no restrictions "
            "on my side.",
        ),
        (
            THREAD[3], "dan@shopmail.com", f"{SEED_DATE}T11:05:00", "11:05 AM", True,
            "Ugh — I have to bail. Something came up Saturday. Don't order "
            "for me.",
        ),
        (
            THREAD[4], "alice@shopmail.com", f"{SEED_DATE}T14:20:00", "2:20 PM", False,
            "Quick change: building has an open house Saturday afternoon so "
            "we're moving game night to SUNDAY May 24 same time (6pm). Bob "
            "and Carol still good? Dan already out.",
        ),
        (
            THREAD[5], "carol@shopmail.com", f"{SEED_DATE}T16:50:00", "4:50 PM", False,
            "Sunday works! Also — actually nvm I can't do dairy. Sorry for "
            "the flip-flop earlier. Please make whatever we order dairy-free.",
        ),
    ]
    for eid, sender, when, label, read, body in rows:
        mail.inbox[eid] = Email(
            id=eid,
            sender=sender,
            to=USER_EMAIL,
            cc="bob@shopmail.com, carol@shopmail.com, dan@shopmail.com",
            subject="Re: game night dinner",
            body=body,
            received_at=when,
            received_label=label,
            read=read,
            labels=["personal"] + (["unread"] if not read else []),
        )

    food = world.food
    food.enable_schedule_ahead = True
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.cart.scheduled_delivery = None
    food.orders.clear()
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Tabletop Kitchen",
        cuisine="American",
        rating=4.6,
        eta_label="6:00 PM",
        delivery_fee=2.49,
        emoji="🎲",
        dishes=[
            Dish(
                id=GOLD_DISH,
                name=GOLD_NAME,
                description=(
                    "Three dairy-free dinner portions — hummus bowls, "
                    "marinara (no cheese), and herb salad. Serves 3."
                ),
                price=42.00,
                tags=["dairy-free", "game-night", "serves-3"],
                emoji="🥗",
                popular=True,
                eta_label="6:00 PM",
            ),
        ],
        delivery_time_min=35,
        delivery_time_max=50,
    )
    food.restaurants[TRAP_REST] = Restaurant(
        id=TRAP_REST,
        name="Cheese Board Co",
        cuisine="Pizza",
        rating=4.8,
        eta_label="5:50 PM",
        delivery_fee=1.99,
        emoji="🍕",
        dishes=[
            Dish(
                id=TRAP_DAIRY,
                name="Four-Cheese Party Pizza (serves 4)",
                description=(
                    "Crowd favorite with mozzarella and gouda — CONTAINS "
                    "DAIRY. Sized for four people."
                ),
                price=38.00,
                tags=["contains-dairy", "pizza", "serves-4"],
                emoji="🧀",
                popular=True,
            ),
        ],
        delivery_time_min=30,
        delivery_time_max=45,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_067_gymeats_group_order_dietary_conflict_reschedule,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _mail_read(p: Probe, eid: str) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(eid)
        return bool(e and getattr(e, "read", False))

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

    def _dish_ids(o) -> set[str]:
        out = set()
        for it in getattr(o, "items", []) or []:
            did = getattr(it, "dish_id", None) or getattr(it, "product_id", None)
            if did:
                out.add(did)
            name = (getattr(it, "name", "") or "").lower()
            if "cheese" in name or "dairy" in name and "free" not in name:
                out.add("__dairyish__")
        return out

    def _read_full_thread(p: Probe) -> bool:
        # Must open the late dietary correction AND the reschedule (not just latest).
        return _mail_read(p, THREAD[5]) and _mail_read(p, THREAD[4])

    def _used_headcount(p: Probe) -> bool:
        """Proxy: ordered gold 3-serve pack, not the serves-4 dairy trap."""
        orders = _new_orders(p)
        if not orders:
            return False
        return any(GOLD_DISH in _dish_ids(o) for o in orders)

    def _used_dietary(p: Probe) -> bool:
        orders = _new_orders(p)
        if not orders:
            return False
        if any(TRAP_DAIRY in _dish_ids(o) for o in orders):
            return False
        return any(GOLD_DISH in _dish_ids(o) for o in orders)

    def _used_date(p: Probe) -> bool:
        return any(_sd(o) == NEW_DAY for o in _new_orders(p))

    def _ordered_final(p: Probe) -> bool:
        for o in _new_orders(p):
            if GOLD_DISH in _dish_ids(o) and _sd(o) == NEW_DAY:
                return True
        return False

    def _ordered_stale(p: Probe) -> bool:
        return any(_sd(o) == OLD_DAY for o in _new_orders(p))

    def _ignored_diet(p: Probe) -> bool:
        return any(TRAP_DAIRY in _dish_ids(o) for o in _new_orders(p))

    def _ordered_cancelled_person(p: Probe) -> bool:
        """Trap pizza serves 4 (includes cancelled Dan)."""
        for o in _new_orders(p):
            if TRAP_DAIRY in _dish_ids(o):
                return True
            for it in getattr(o, "items", []) or []:
                name = (getattr(it, "name", "") or "").lower()
                qty = int(getattr(it, "quantity", 1) or 1)
                if "serves 4" in name or qty >= 4:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "read_full_thread_not_just_latest",
                    weight=0.2,
                    check=_read_full_thread,
                    required_for_success=True,
                ),
                Milestone(
                    "used_corrected_headcount",
                    weight=0.2,
                    check=_used_headcount,
                    required_for_success=True,
                ),
                Milestone(
                    "used_corrected_dietary_restriction",
                    weight=0.2,
                    check=_used_dietary,
                    required_for_success=True,
                ),
                Milestone(
                    "used_correct_rescheduled_date_not_stale_calendar",
                    weight=0.25,
                    check=_used_date,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_matching_final_state",
                    weight=0.15,
                    check=_ordered_final,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_for_stale_calendar_date",
                    weight=0.0,
                    check=_ordered_stale,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ignored_dietary_correction",
                    weight=0.0,
                    check=_ignored_diet,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_for_cancelled_person",
                    weight=0.0,
                    check=_ordered_cancelled_person,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
