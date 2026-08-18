"""lh_001 / office_welcome_budget — long-horizon bridged pilot task.

Mechanism: combined Food+ValueMart budget cap ($35) + calendar-derived
delivery-timing (lunch must arrive before noon New Hire Welcome) + vegetarian
constraint. Two ValueMart signs create a budget fork: plain stays under cap with
veg lunch; deluxe pushes the pair over $35.

Hub map (bridged five-hub):
  Food     → uber_eats_mock  (:5403)
  eBay     → ebay_mock       (:5301)  ← gym ``market`` app / engine MarketState
  Calendar → google_calendar_mock (:5402)

Note: ebay_mock chrome still renders legacy "ValueMart" logo text; task brief,
oracle, Discriminator, and this factory name the hub **ValueMart** to match
what the agent sees.

Redesign 2026-08-04: name Bean There Cafe in the brief (family_001 lesson) so
agents skip ambient-decoy tax without shrinking the global amb_* catalog that
M343 still relies on. Price-display E16/E-VM-SHIP-ZERO left open — brief keeps
durable-total wording.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "lh_001/office_welcome_budget"
BRIEF_KEY = "lh_001"
BRIEF = (
    "Getting the office ready for the new hire tomorrow. Order the "
    "Vegetarian Welcome Lunch Box from Bean There Cafe on GymEats for the "
    "welcome, and grab a welcome sign from ValueMart too — whatever looks "
    "decent. Keep the combined charged order totals under $35 (the amounts "
    "the system records after placing, not the checkout page displays), and "
    "have lunch here before the New Hire Welcome starts."
)

VEG_DISH = "d_lh001_veg_lunch"
MEAT_DISH = "d_lh001_chicken_lunch"
PLAIN_SIGN = "eb_lh001_plain_sign"
DELUXE_SIGN = "eb_lh001_deluxe_sign"
EVENT_TITLE = "New Hire Welcome"
# Food: $16.00 + $2.99 delivery = $18.99
# Plain sign: $9.00 + $5.99 delivery = $14.99 → combined $33.98 ≤ $35
# Deluxe sign: $16.00 + $5.99 delivery = $21.99 → combined $40.98 > $35
VEG_PRICE = 16.00
MEAT_PRICE = 17.00
FOOD_DELIVERY = 2.99
PLAIN_PRICE = 9.00
DELUXE_PRICE = 16.00
MARKET_DELIVERY = 5.99
BUDGET_CAP = 35.0
ETA_LABEL = "11:20 AM"
EVENT_START = "12:00"


def task_lh_001_office_welcome_budget(seed: int) -> "WorldState":
    """FEASIBLE cross-store budget + timing + vegetarian lunch.

    Correct path: order vegetarian lunch (ETA before noon) + plain ValueMart
    sign; combined all-in ≤ $35. Deluxe sign with veg lunch exceeds budget.
    Non-veg lunch fails the dietary constraint even if under budget.
    """
    from server.apps.calendar.state import CalendarEvent, TOMORROW
    from server.apps.food.state import Dish
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = "alice@shopmail.com"
    # Chrome still says ValueMart; keep store_name aligned with brief/chrome.
    world.market.store_name = "ValueMart"

    cal = world.calendar
    cal.events.clear()
    cid = cal.new_id()
    cal.events[cid] = CalendarEvent(
        id=cid,
        title=EVENT_TITLE,
        day=TOMORROW,
        day_label="Tomorrow (Fri May 22)",
        start=EVENT_START,
        end="13:00",
        source="seed",
    )

    # Lunch restaurant with morning ETA before the noon welcome.
    # Only Bean There carries the welcome lunch boxes — keep other gym menus
    # free of "Welcome Lunch" / office-welcome naming so search lands here.
    cafe = world.food.restaurants["r_bean"]
    cafe.eta_label = ETA_LABEL
    cafe.delivery_fee = FOOD_DELIVERY
    cafe.dishes = [
        Dish(
            id=VEG_DISH,
            name="Vegetarian Welcome Lunch Box",
            description=(
                "Fully vegetarian lunch box for a new-hire welcome at Bean "
                "There Cafe. Arrives around 11:20 AM — before a noon event."
            ),
            price=VEG_PRICE,
            tags=["lunch", "vegetarian", "welcome", "office"],
            emoji="🥗",
            popular=True,
        ),
        Dish(
            id=MEAT_DISH,
            name="Chicken Welcome Lunch Box",
            description="Grilled chicken lunch box — not vegetarian.",
            price=MEAT_PRICE,
            tags=["lunch", "chicken", "welcome"],
            emoji="🍗",
            popular=False,
        ),
        # Keep a couple of cafe staples so the store page is not a two-item stub.
        *[
            d
            for d in cafe.dishes
            if d.id not in (VEG_DISH, MEAT_DISH)
            and "welcome" not in (d.name or "").lower()
        ][:3],
    ]

    # Demote competing veg-looking staples on the other gym-backed stores so
    # Dietary / "vegetarian" search surfaces Bean There's welcome box first.
    for rid in ("r_burger", "r_sushi"):
        rest = world.food.restaurants.get(rid)
        if rest is None:
            continue
        for d in rest.dishes:
            tags = [t for t in (d.tags or []) if t != "vegetarian"]
            d.tags = tags
            d.popular = False

    world.market.products[PLAIN_SIGN] = MarketProduct(
        id=PLAIN_SIGN,
        name="Plain Welcome Sign",
        category="home",
        price=PLAIN_PRICE,
        emoji="🪧",
        description="Simple foam-board office welcome sign.",
        in_stock=True,
        shop_sku=None,
    )
    world.market.products[DELUXE_SIGN] = MarketProduct(
        id=DELUXE_SIGN,
        name="Deluxe Welcome Sign",
        category="home",
        price=DELUXE_PRICE,
        emoji="✨",
        description="Premium printed deluxe welcome sign with foil lettering.",
        in_stock=True,
        shop_sku=None,
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_lh_001_office_welcome_budget,
}

BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def _build_suites() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _new_food_orders(p: Probe) -> list:
        if p.world is None or p.world.food is None:
            return []
        init = (
            p.initial_world.food.orders
            if p.initial_world and p.initial_world.food
            else {}
        ) or {}
        return [o for oid, o in (p.world.food.orders or {}).items() if oid not in init]

    def _new_market_orders(p: Probe) -> list:
        if p.world is None or p.world.market is None:
            return []
        init = (
            p.initial_world.market.orders
            if p.initial_world and p.initial_world.market
            else {}
        ) or {}
        return [o for oid, o in (p.world.market.orders or {}).items() if oid not in init]

    def _ordered_veg_lunch(p: Probe) -> bool:
        for o in _new_food_orders(p):
            for it in o.items:
                if getattr(it, "dish_id", None) == VEG_DISH:
                    return True
        return False

    def _ordered_plain_sign(p: Probe) -> bool:
        for o in _new_market_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == PLAIN_SIGN:
                    return True
        return False

    def _combined_under_budget(p: Probe) -> bool:
        food_total = sum(float(getattr(o, "total", 0) or 0) for o in _new_food_orders(p))
        market_total = sum(
            float(getattr(o, "total", 0) or 0) for o in _new_market_orders(p)
        )
        if food_total <= 0 or market_total <= 0:
            return False
        return (food_total + market_total) <= BUDGET_CAP + 1e-6

    def _lunch_eta_before_noon(p: Probe) -> bool:
        for o in _new_food_orders(p):
            eta = (getattr(o, "eta_label", "") or "").upper().replace(" ", "")
            if eta.endswith("AM"):
                try:
                    hour = int(eta.split(":")[0])
                    if 1 <= hour <= 11:
                        return True
                except ValueError:
                    pass
        return False

    def _over_budget(p: Probe) -> bool:
        food_total = sum(float(getattr(o, "total", 0) or 0) for o in _new_food_orders(p))
        market_total = sum(
            float(getattr(o, "total", 0) or 0) for o in _new_market_orders(p)
        )
        if food_total <= 0 or market_total <= 0:
            return False
        return (food_total + market_total) > BUDGET_CAP + 1e-6

    def _ordered_nonveg(p: Probe) -> bool:
        for o in _new_food_orders(p):
            for it in o.items:
                if getattr(it, "dish_id", None) == MEAT_DISH:
                    return True
        return False

    def _ordered_deluxe(p: Probe) -> bool:
        for o in _new_market_orders(p):
            for it in o.items:
                if getattr(it, "product_id", None) == DELUXE_SIGN:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_veg_lunch",
                    weight=0.25,
                    check=_ordered_veg_lunch,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_plain_ebay_sign",
                    weight=0.25,
                    check=_ordered_plain_sign,
                    required_for_success=True,
                ),
                Milestone(
                    "combined_under_35",
                    weight=0.25,
                    check=_combined_under_budget,
                    required_for_success=True,
                ),
                Milestone(
                    "lunch_eta_before_noon",
                    weight=0.25,
                    check=_lunch_eta_before_noon,
                    required_for_success=True,
                ),
                Milestone(
                    "over_budget_pair",
                    weight=0.0,
                    check=_over_budget,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_nonveg_lunch",
                    weight=0.0,
                    check=_ordered_nonveg,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_deluxe_ebay_sign",
                    weight=0.0,
                    check=_ordered_deluxe,
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
