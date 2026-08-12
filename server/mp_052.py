"""mp_052 / water_filter_deadline_unit_price — GymCal×ShopGym.

Mechanism (A1): pitcher filter is due; calendar shows conference leave date.
Multi-pack is cheaper per unit but arrives AFTER leave. Single pack is dearer
total but arrives before leave. Gold = calendar + reject unit-price bait.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_052/water_filter_deadline_unit_price"
BRIEF_KEY = "mp_052"
BRIEF = (
    "The water filter for my pitcher is due, grab the cheapest one that'll "
    "actually get here before I leave for the conference."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"
LEAVE_DAY = "2026-05-25"
LEAVE_LABEL = "Mon May 25"
LEAVE_EVENT = "ev_mp052_conference_leave"

GOLD = "p_mp052_filter_single"
TRAP = "p_mp052_filter_multipack"
GOLD_NAME = "PurePitch Filter Refill - 1-Pack"
TRAP_NAME = "PurePitch Filter Refill - 3-Pack Value"
GOLD_PRICE = 14.99   # dearer per unit wait no - single is dearer TOTAL, multipack cheaper/unit
TRAP_PRICE = 29.99   # $10/filter vs $14.99 — cheaper unit, late delivery


def task_mp_052_water_filter_deadline_unit_price(seed: int) -> "WorldState":
    """FEASIBLE Cal×Shop: on-time single filter vs late multipack unit bait."""
    from server.apps.calendar.state import CalendarEvent
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[LEAVE_EVENT] = CalendarEvent(
        id=LEAVE_EVENT,
        title="Leave for Design Conference (SFO)",
        day=LEAVE_DAY,
        day_label=LEAVE_LABEL,
        start="07:30",
        end="09:00",
        source="seed",
        description=(
            "Flight morning of May 25. Packages must arrive by May 24 or they "
            "sit until you return."
        ),
    )
    cal.events["ev_mp052_standup"] = CalendarEvent(
        id="ev_mp052_standup",
        title="Morning standup",
        day="2026-05-22",
        day_label="Fri May 22",
        start="09:30",
        end="09:45",
        source="seed",
    )

    shop = world.shop
    # Keep the filter choice legible in search.
    keep = {GOLD, TRAP}
    for pid in list(shop.products):
        if pid not in keep and "filter" in (shop.products[pid].name or "").lower():
            del shop.products[pid]
    shop.products[GOLD] = Product(
        id=GOLD, name=GOLD_NAME, brand="PurePitch", category="grocery",
        base_price=GOLD_PRICE, rating=4.6, review_count=920, stock=80,
        image_emoji="💧",
        short_description=(
            "Single pitcher filter refill. FREE delivery. Estimated delivery: "
            "arrives by May 23, 2026 — before conference leave on May 25. "
            "Unit price $14.99 per filter."
        ),
        tags=["filter", "water", "pitcher", "purepitch", "express"],
    )
    shop.products[TRAP] = Product(
        id=TRAP, name=TRAP_NAME, brand="PurePitch", category="grocery",
        base_price=TRAP_PRICE, rating=4.7, review_count=1400, stock=60,
        image_emoji="💧",
        short_description=(
            "3-pack pitcher filter refills — best per-filter price ($9.99 each). "
            "FREE delivery. Estimated delivery: arrives May 27, 2026 — AFTER "
            "conference leave on May 25. Cheaper unit price, late arrival."
        ),
        tags=["filter", "water", "pitcher", "purepitch", "value", "multipack"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_052_water_filter_deadline_unit_price,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        init = getattr(p, "initial_world", None)
        init_ids = set((init.shop.orders or {}) if init and init.shop else {})
        return [o for oid, o in (shop.orders or {}).items() if oid not in init_ids]

    def _ordered_gold(p: Probe) -> bool:
        for o in _orders(p):
            if any(it.product_id == GOLD for it in o.items):
                return True
        return False

    def _ordered_trap(p: Probe) -> bool:
        for o in _orders(p):
            if any(it.product_id == TRAP for it in o.items):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_on_time_single_filter",
                    weight=1.0,
                    check=_ordered_gold,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_late_multipack_unit_bait",
                    weight=0.0,
                    check=_ordered_trap,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
