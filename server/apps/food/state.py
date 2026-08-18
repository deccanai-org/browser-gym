"""Food app store — FoodState (restaurants, menus, cart, orders).

Wholly separate from the shop. Timestamps / ETAs are FIXED labels (not
``datetime.now()``) so a reset for a given seed reproduces an identical
menu and ETA — the environment-correctness gate requires deterministic
episodes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEED_DATE = "2026-05-21"


@dataclass
class Dish:
    id: str
    name: str
    description: str
    price: float
    tags: list[str] = field(default_factory=list)
    emoji: str = "🍽️"
    popular: bool = False          # "best-seller" flag (decoy_salience perturbation later)
    # Optional absolute arrival clock ("6:15 PM"). When set, cart/checkout/order
    # ETA prefer this over the restaurant-level eta_label (per-SKU late traps).
    eta_label: str | None = None


@dataclass
class Restaurant:
    id: str
    name: str
    cuisine: str
    rating: float
    eta_label: str                 # fixed display ETA, e.g. "7:20 PM"
    delivery_fee: float
    emoji: str = "🍴"
    dishes: list[Dish] = field(default_factory=list)
    delivery_time_min: int = 20
    delivery_time_max: int = 40

    def dish(self, dish_id: str) -> Dish | None:
        return next((d for d in self.dishes if d.id == dish_id), None)


@dataclass
class FoodCartItem:
    dish_id: str
    restaurant_id: str
    name: str
    unit_price: float
    quantity: int


@dataclass
class FoodCart:
    items: list[FoodCartItem] = field(default_factory=list)
    restaurant_id: str | None = None       # food carts are single-restaurant
    # Task-local (M362): courier/restaurant delivery instruction at checkout.
    delivery_note: str = ""
    # ISO date (YYYY-MM-DD) when scheduling delivery for a future day; None = ASAP.
    scheduled_delivery: str | None = None

    def subtotal(self) -> float:
        return round(sum(i.unit_price * i.quantity for i in self.items), 2)

    def count(self) -> int:
        return sum(i.quantity for i in self.items)


@dataclass
class FoodOrder:
    id: str
    restaurant_id: str
    restaurant_name: str
    items: list[FoodCartItem]
    subtotal: float
    delivery_fee: float
    total: float
    placed_at: str
    eta_label: str                 # "7:20 PM"
    status: str = "preparing"      # preparing | on_the_way | delivered
    delivery_note: str = ""        # persisted checkout instruction (M362)
    delivery_mode: str = "delivery"  # delivery | pickup
    # ISO date for schedule-ahead dinner nights; None = ASAP same-day.
    scheduled_delivery: str | None = None


@dataclass
class FoodState:
    restaurants: dict[str, Restaurant] = field(default_factory=dict)
    cart: FoodCart = field(default_factory=FoodCart)
    orders: dict[str, FoodOrder] = field(default_factory=dict)
    # code -> percent off. The checkout has always had a promo box; without any
    # codes behind it every entry was a silent no-op. A small default set makes
    # the control real (and gives a wrong code something to be wrong against).
    promos: dict[str, float] = field(default_factory=lambda: {
        "EATS10": 0.10, "WELCOME15": 0.15,
    })
    _next: int = 1
    # Task-local (M371): when set, the FoodOrderPlaced receipt subscriber DEFERS
    # delivery by this many steps (schedules DelayedFoodReceipt) instead of writing
    # Mail immediately. Not exposed in to_json. Cleared after the first deferral.
    defer_receipt_steps: int | None = None
    # Task-local (M362): when True, the food-cart checkout form exposes a
    # delivery-instruction field. Not required for other tasks.
    enable_delivery_notes: bool = False
    # Task-local: when True, cart checkout exposes a delivery-day picker and
    # place_food_order persists scheduled_delivery onto FoodOrder.
    enable_schedule_ahead: bool = False

    def new_order_id(self) -> str:
        oid = f"FOOD-{1040 + self._next}"
        self._next += 1
        return oid

    def to_json(self) -> dict[str, Any]:
        return {
            "restaurants": {k: asdict(v) for k, v in self.restaurants.items()},
            "cart": asdict(self.cart),
            "cart_count": self.cart.count(),
            "orders": {k: asdict(v) for k, v in self.orders.items()},
        }


def make_foodstate(seed: int = 0) -> FoodState:
    """Three restaurants with small menus. 'Bean There' carries coffee pods
    so the cross-store price-compare task (Phase 1, M5) has a shop-vs-food
    comparison to make. Popular dishes are flagged for the later
    decoy_salience UI perturbation."""
    f = FoodState()
    f.restaurants["r_sushi"] = Restaurant(
        id="r_sushi", name="Sakura Sushi", cuisine="Japanese",
        rating=4.7, eta_label="7:20 PM", delivery_fee=3.99, emoji="🍣",
        dishes=[
            Dish(id="d_salmon_roll", name="Salmon Avocado Roll",
                 description="Fresh salmon, avocado, sushi rice.",
                 price=12.50, tags=["sushi", "fish"], emoji="🍣", popular=True),
            Dish(id="d_tuna_bowl", name="Spicy Tuna Bowl",
                 description="Marinated tuna over rice with greens.",
                 price=14.00, tags=["bowl", "fish"], emoji="🥢"),
            Dish(id="d_miso", name="Miso Soup",
                 description="Classic soybean broth with tofu.",
                 price=3.50, tags=["soup", "vegetarian"], emoji="🍲"),
        ],
    )
    f.restaurants["r_burger"] = Restaurant(
        id="r_burger", name="Burger Barn", cuisine="American",
        rating=4.4, eta_label="6:55 PM", delivery_fee=2.49, emoji="🍔",
        dishes=[
            Dish(id="d_classic", name="Classic Cheeseburger",
                 description="Beef patty, cheddar, lettuce, tomato.",
                 price=10.00, tags=["burger"], emoji="🍔", popular=True),
            Dish(id="d_veggie", name="Veggie Burger",
                 description="House black-bean patty, all the fixings.",
                 price=9.50, tags=["burger", "vegetarian"], emoji="🥬"),
            Dish(id="d_fries", name="Crispy Fries",
                 description="Hand-cut, sea salt.",
                 price=4.00, tags=["side"], emoji="🍟"),
        ],
    )
    f.restaurants["r_bean"] = Restaurant(
        id="r_bean", name="Bean There Cafe", cuisine="Coffee",
        rating=4.6, eta_label="6:40 PM", delivery_fee=1.99, emoji="☕",
        dishes=[
            # Coffee pods here let M5 compare against the shop's coffee pods.
            Dish(id="d_pods", name="Coffee Pods (24-pack)",
                 description="Medium roast espresso capsules, 24 count.",
                 price=11.99, tags=["coffee", "pods"], emoji="☕", popular=True),
            Dish(id="d_latte", name="Oat Milk Latte",
                 description="Double shot, steamed oat milk.",
                 price=5.25, tags=["coffee", "drink"], emoji="🥛"),
            Dish(id="d_croissant", name="Butter Croissant",
                 description="Flaky, baked this morning.",
                 price=3.75, tags=["bakery"], emoji="🥐"),
        ],
    )
    return f
