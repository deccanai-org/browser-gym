"""food_002 / reorder_most_frequent_last_month — Food recency-vs-frequency trap.

Mechanism: order history spans 2–3 restaurants. Last month (April 2026; today is
SEED_DATE May 21) one restaurant has the highest order count with a consistent
"usual" basket. A different restaurant is the most-recent order (May). Trap =
reorder the most-recent restaurant. Correct = reorder from the highest-count
last-month restaurant with the same usual items.

Hub map (bridged): Food → uber_eats_mock (Xber). Orders list shows placed
dates after the /orders list fix.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "food_002/reorder_most_frequent_last_month"
BRIEF_KEY = "food_002"
BRIEF = (
    "Get me the usual from wherever I ordered most from last month."
)

USER_EMAIL = "alice@shopmail.com"

# Most frequent last month (April) — 3 identical usual baskets.
FREQUENT_REST = "r_burger"
FREQUENT_NAME = "Burger Barn"
USUAL_DISHES = ("d_classic", "d_fries")
USUAL_NAMES = ("Classic Cheeseburger", "Crispy Fries")

# Second last-month restaurant (lower count).
OTHER_REST = "r_sushi"
OTHER_NAME = "Sakura Sushi"

# Most-recent decoy (May) — different restaurant from the April winner.
TRAP_REST = "r_bean"
TRAP_NAME = "Bean There Cafe"
TRAP_DISH = "d_latte"

# Seeded history ids (not assigned by new_order_id).
RECENT_ORDER_ID = "FOOD-F002-RECENT"
BB_ORDER_IDS = ("FOOD-F002-BB-1", "FOOD-F002-BB-2", "FOOD-F002-BB-3")
SU_ORDER_ID = "FOOD-F002-SU-1"

# First agent-placed order id when food._next stays at default 1.
NEW_ORDER_ID = "FOOD-1041"


def _usual_items(restaurant_id: str = FREQUENT_REST) -> list:
    from server.apps.food.state import FoodCartItem

    return [
        FoodCartItem(
            dish_id="d_classic",
            restaurant_id=restaurant_id,
            name="Classic Cheeseburger",
            unit_price=10.00,
            quantity=1,
        ),
        FoodCartItem(
            dish_id="d_fries",
            restaurant_id=restaurant_id,
            name="Crispy Fries",
            unit_price=4.00,
            quantity=1,
        ),
    ]


def task_food_002_reorder_most_frequent_last_month(seed: int) -> "WorldState":
    """FEASIBLE Food frequency-vs-recency reorder.

    Seed (today Thu May 21):
      - April: Burger Barn ×3 (Classic Cheeseburger + Fries) — most frequent
      - April: Sakura Sushi ×1 (Salmon Avocado Roll) — lower count
      - May 20: Bean There Cafe (Oat Milk Latte) — most recent decoy

    Correct: place a new Burger Barn order with the usual items.
    Forbidden: place a new order from the most-recent restaurant (Bean There).
    """
    from server.apps.food.state import FoodCartItem, FoodOrder, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    food = world.food
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()

    burger = food.restaurants[FREQUENT_REST]
    sushi = food.restaurants[OTHER_REST]
    bean = food.restaurants[TRAP_REST]

    # Most-recent first so it tops the Xber Orders list (recency trap).
    food.orders[RECENT_ORDER_ID] = FoodOrder(
        id=RECENT_ORDER_ID,
        restaurant_id=bean.id,
        restaurant_name=bean.name,
        items=[
            FoodCartItem(
                dish_id=TRAP_DISH,
                restaurant_id=bean.id,
                name="Oat Milk Latte",
                unit_price=5.25,
                quantity=1,
            ),
        ],
        subtotal=5.25,
        delivery_fee=bean.delivery_fee,
        total=round(5.25 + bean.delivery_fee, 2),
        placed_at="2026-05-20T19:10:00",
        eta_label="7:40 PM",
        status="delivered",
    )

    april_dates = ("2026-04-05T18:20:00", "2026-04-12T18:35:00", "2026-04-19T18:15:00")
    for oid, placed in zip(BB_ORDER_IDS, april_dates):
        items = _usual_items(burger.id)
        sub = round(sum(i.unit_price * i.quantity for i in items), 2)
        food.orders[oid] = FoodOrder(
            id=oid,
            restaurant_id=burger.id,
            restaurant_name=burger.name,
            items=items,
            subtotal=sub,
            delivery_fee=burger.delivery_fee,
            total=round(sub + burger.delivery_fee, 2),
            placed_at=placed,
            eta_label=burger.eta_label,
            status="delivered",
        )

    food.orders[SU_ORDER_ID] = FoodOrder(
        id=SU_ORDER_ID,
        restaurant_id=sushi.id,
        restaurant_name=sushi.name,
        items=[
            FoodCartItem(
                dish_id="d_salmon_roll",
                restaurant_id=sushi.id,
                name="Salmon Avocado Roll",
                unit_price=12.50,
                quantity=1,
            ),
        ],
        subtotal=12.50,
        delivery_fee=sushi.delivery_fee,
        total=round(12.50 + sushi.delivery_fee, 2),
        placed_at="2026-04-08T19:00:00",
        eta_label=sushi.eta_label,
        status="delivered",
    )

    # Keep default _next=1 so the first placed order is FOOD-1041 (Disc gate).
    food._next = 1
    _ = SEED_DATE  # document frozen "today" for last-month = April
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_food_002_reorder_most_frequent_last_month,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _initial_ids(p: Probe) -> set[str]:
        init = (
            p.initial_world.food.orders
            if p.initial_world and getattr(p.initial_world, "food", None)
            else {}
        ) or {}
        return set(init.keys())

    def _new_orders(p: Probe) -> list:
        init_ids = _initial_ids(p)
        return [o for oid, o in _orders(p).items() if oid not in init_ids]

    def _dish_ids(order) -> set[str]:
        return {
            getattr(it, "dish_id", None)
            for it in (getattr(order, "items", None) or [])
            if getattr(it, "dish_id", None)
        }

    def _ordered_usual_frequent(p: Probe) -> bool:
        want = set(USUAL_DISHES)
        for o in _new_orders(p):
            if getattr(o, "restaurant_id", None) != FREQUENT_REST:
                continue
            if want <= _dish_ids(o):
                return True
        return False

    def _ordered_trap_recent(p: Probe) -> bool:
        return any(
            getattr(o, "restaurant_id", None) == TRAP_REST for o in _new_orders(p)
        )

    def _build() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "reordered_most_frequent_usual",
                    weight=1.0,
                    check=_ordered_usual_frequent,
                    required_for_success=True,
                ),
                Milestone(
                    "reordered_most_recent_decoy",
                    weight=0.0,
                    check=_ordered_trap_recent,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _build}
