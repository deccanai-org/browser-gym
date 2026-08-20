"""mp remaining batch — RUNNABLE leftovers + honest PARTIAL adaptations.

Not re-run: mp_001, 006, 008, 014, 018, 024, 028, 030 (prior LH∩RUNNABLE).

RUNNABLE: mp_005, 013, 019, 021
PARTIAL (adapted to real bridged UI): mp_002, 003, 004, 010, 012, 016, 026
NOT_RUNNABLE skipped elsewhere: mp_007, 009, 011, 015, 017, 020, 022, 023, 025, 027, 029
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

USER_EMAIL = "alice@shopmail.com"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _shop_helpers():
    from server.verifiers import Probe

    def orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        return list((shop.orders or {}).values()) if shop else []

    def new_orders(p: Probe) -> list:
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for o in orders(p) if o.id not in init]

    def lines(p: Probe, pid: str) -> list:
        return [
            it for o in new_orders(p) for it in o.items
            if getattr(it, "product_id", None) == pid
        ]

    def cart_qty(p: Probe, pid: str) -> int:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return 0
        return sum(
            int(getattr(it, "quantity", 0) or 0)
            for it in (shop.cart.items or [])
            if getattr(it, "product_id", None) == pid
        )

    def has_return(p: Probe, order_id: str) -> bool:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return False
        return any(
            getattr(r, "order_id", None) == order_id
            for r in (shop.returns or {}).values()
        )

    return orders, new_orders, lines, cart_qty, has_return


def _food_helpers():
    from server.verifiers import Probe

    def new_food_orders(p: Probe) -> list:
        food = getattr(p.world, "food", None) if p.world else None
        if not food:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "food", None):
            init = p.initial_world.food.orders or {}
        return [o for oid, o in (food.orders or {}).items() if oid not in init]

    def food_order(p: Probe, oid: str):
        food = getattr(p.world, "food", None) if p.world else None
        if not food:
            return None
        return (food.orders or {}).get(oid)

    return new_food_orders, food_order


def _market_bought(p, pid: str) -> bool:
    if p.world is None or p.world.market is None:
        return False
    init = (
        p.initial_world.market.orders
        if p.initial_world and p.initial_world.market
        else {}
    ) or {}
    for oid, o in (p.world.market.orders or {}).items():
        if oid in init:
            continue
        for it in o.items:
            if getattr(it, "product_id", None) == pid:
                return True
    return False


def _mail_sent_to(p, needle: str) -> bool:
    mail = getattr(p.world, "mail", None) if p.world else None
    if not mail:
        return False
    n = needle.lower()
    for e in (mail.sent or {}).values():
        to = (getattr(e, "to", "") or "").lower()
        if n in to:
            return True
    return False


def _mail_sent_blob(p) -> str:
    mail = getattr(p.world, "mail", None) if p.world else None
    if not mail:
        return ""
    parts = []
    for e in (mail.sent or {}).values():
        parts.append(
            f"{getattr(e, 'to', '')} {getattr(e, 'subject', '')} {getattr(e, 'body', '')}"
        )
    return " ".join(parts).lower()


def _emailed_user(p) -> bool:
    return _mail_sent_to(p, USER_EMAIL) or _mail_sent_to(p, "alice@")


# =========================================================================== #
# mp_002 — PARTIAL: BIN+shipping under $40 vs Amazon ~$60 fallback
# =========================================================================== #

MP002_ID = "mp_002/ps5_controller_cap_infeasible_ask"
MP002_BRIEF = (
    "I'm bidding on a PS5 controller on eBay, but if it ends up going over $40 "
    "total just get me a new one from Amazon instead, whichever's cheaper works."
)
MP002_VM = "vm_mp002_dualsense"
MP002_AMZ = "p_mp002_dualsense"
# Xbay BIN $33.99 + $5 ship = $38.99 ≤ $40 → gold buy eBay/VM.
# Amazon new DualSense ~$60 exists so the agent can check the fallback, but it
# is NOT cheaper while the auction/BIN stays under $40.


def task_mp_002(seed: int) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP002_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = MP002_ID
    world.shop.task_brief = MP002_BRIEF
    # Bridged Xbay: bidding disabled. Seed as BIN with price+shipping so
    # the agent can still do shipping-inclusive arithmetic vs the $40 cap.
    world.market.products[MP002_VM] = MarketProduct(
        id=MP002_VM,
        name="Sony DualSense Wireless Controller - Midnight Black (Used, Tested)",
        category="electronics",
        price=33.99,
        emoji="🎮",
        description=(
            "Used DualSense, tested. Buy It Now $33.99 + shipping $5.00 = $38.99 "
            "total (UNDER a $40 cap). Bidding is not available on Xbay — "
            "compare shipping-inclusive total to Xmazon's new ~$60 controller."
        ),
        in_stock=True,
        condition="Used",
        shipping_cost=5.00,
        shop_sku=MP002_AMZ,
    )
    world.shop.products[MP002_AMZ] = Product(
        id=MP002_AMZ,
        name="Sony DualSense Wireless Controller for PS5 (New)",
        brand="Sony", category="electronics", base_price=59.99,
        rating=4.8, review_count=12000, stock=80, image_emoji="🎮",
        short_description=(
            "Brand-new DualSense. $59.99 — the Amazon fallback if eBay goes over "
            "$40 total; not cheaper while eBay stays under $40."
        ),
        tags=["PS5 controller", "Amazon fallback"],
    )
    return world


def _suite_mp_002():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, new_orders, lines, _, _ = _shop_helpers()

    def _bought_vm(p: Probe) -> bool:
        return _market_bought(p, MP002_VM)

    def _bought_amz(p: Probe) -> bool:
        return len(lines(p, MP002_AMZ)) > 0

    return TaskSuite(
        task_id=MP002_ID,
        milestones=[
            Milestone(
                "bought_ebay_under_40",
                weight=1.0,
                check=_bought_vm,
                required_for_success=True,
            ),
            Milestone(
                "bought_amazon_when_ebay_cheaper",
                weight=0.0,
                check=_bought_amz,
                required_for_success=False,
                forbidden=True,
            ),
        ],
    )


# =========================================================================== #
# mp_003 — PARTIAL: usual pizza + plates; ETA text (no hard clock gate)
# =========================================================================== #

MP003_ID = "mp_003/game_night_pizza_plates_by_7"
MP003_BRIEF = (
    "Hosting game night tonight -- order from the usual pizza place, and grab "
    "some extra paper plates and cups from Amazon since we're running low. Need "
    "everything here by 7."
)
MP003_PLATES = "p_mp003_plates"
MP003_CUPS = "p_mp003_cups"
MP003_PIZZA = "r_mp003_pizza"
MP003_PEPP = "d_mp003_pepperoni"


def task_mp_003(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP003_ID, "hard")
    world.mail.account_email = USER_EMAIL
    shop = world.shop
    # Explicit ETA copy (same-day cutoff clocks are weak on bridged Xmazon).
    shop.products[MP003_PLATES] = Product(
        id=MP003_PLATES, name="Dixie Ultra Paper Plates, 50 count",
        brand="Dixie", category="household", base_price=8.99,
        rating=4.6, review_count=3000, stock=100, image_emoji="🍽️",
        short_description=(
            "Paper plates. Same-day delivery cutoff was 2:00 PM; it is now "
            "3:15 PM — arrives TOMORROW, not by 7pm tonight."
        ),
        tags=["Arrives tomorrow", "Same-day cutoff missed (2pm)", "Current time 3:15 PM"],
    )
    shop.products[MP003_CUPS] = Product(
        id=MP003_CUPS, name="Solo Cup 18oz Plastic Cups, 100 count",
        brand="Solo", category="household", base_price=11.49,
        rating=4.5, review_count=2100, stock=100, image_emoji="🥤",
        short_description=(
            "Plastic cups. Same-day cutoff was 2:00 PM; it is now 3:15 PM — "
            "arrives TOMORROW, not by 7pm tonight."
        ),
        tags=["Arrives tomorrow", "Same-day cutoff missed (2pm)", "Current time 3:15 PM"],
    )
    food = world.food
    food.restaurants[MP003_PIZZA] = Restaurant(
        id=MP003_PIZZA, name="Pizza Planet", cuisine="Pizza",
        rating=4.5, eta_label="6:40 PM", delivery_fee=2.99, emoji="🍕",
        dishes=[
            Dish(id=MP003_PEPP, name="Pepperoni Pizza",
                 description="Large pepperoni. 20-30 min delivery.",
                 price=16.50, tags=["pizza", "usual"], emoji="🍕", popular=True),
            Dish(id="d_mp003_supreme", name="Supreme Pizza",
                 description="Loaded supreme pizza.",
                 price=18.50, tags=["pizza"], emoji="🍕"),
            Dish(id="d_mp003_knots", name="Garlic Knots",
                 description="Side of garlic knots.",
                 price=5.00, tags=["side"], emoji="🧄"),
        ],
    )
    food.restaurants["r_mp003_sushi"] = Restaurant(
        id="r_mp003_sushi", name="Sushi House", cuisine="Japanese",
        rating=4.3, eta_label="7:10 PM", delivery_fee=3.49, emoji="🍣",
        dishes=[
            Dish(id="d_mp003_dragon", name="Dragon Roll",
                 description="Eel and avocado roll.",
                 price=14.00, tags=["sushi"], emoji="🍣", popular=True),
        ],
    )
    # Frequency: Pizza Planet x2, Sushi House x1
    food.orders["FOOD-MP003-PP1"] = FoodOrder(
        id="FOOD-MP003-PP1", restaurant_id=MP003_PIZZA, restaurant_name="Pizza Planet",
        items=[FoodCartItem(dish_id=MP003_PEPP, restaurant_id=MP003_PIZZA,
                            name="Pepperoni Pizza", unit_price=16.50, quantity=2),
               FoodCartItem(dish_id="d_mp003_knots", restaurant_id=MP003_PIZZA,
                            name="Garlic Knots", unit_price=5.00, quantity=1)],
        subtotal=38.00, delivery_fee=2.99, total=40.99,
        placed_at="2026-05-09T18:00:00", eta_label="6:30 PM", status="delivered",
    )
    food.orders["FOOD-MP003-PP2"] = FoodOrder(
        id="FOOD-MP003-PP2", restaurant_id=MP003_PIZZA, restaurant_name="Pizza Planet",
        items=[FoodCartItem(dish_id="d_mp003_supreme", restaurant_id=MP003_PIZZA,
                            name="Supreme Pizza", unit_price=18.50, quantity=1),
               FoodCartItem(dish_id=MP003_PEPP, restaurant_id=MP003_PIZZA,
                            name="Pepperoni Pizza", unit_price=16.50, quantity=1)],
        subtotal=35.00, delivery_fee=2.99, total=37.99,
        placed_at="2026-04-25T18:30:00", eta_label="6:55 PM", status="delivered",
    )
    food.orders["FOOD-MP003-SU"] = FoodOrder(
        id="FOOD-MP003-SU", restaurant_id="r_mp003_sushi", restaurant_name="Sushi House",
        items=[FoodCartItem(dish_id="d_mp003_dragon", restaurant_id="r_mp003_sushi",
                            name="Dragon Roll", unit_price=14.00, quantity=1)],
        subtotal=14.00, delivery_fee=3.49, total=17.49,
        placed_at="2026-04-11T19:00:00", eta_label="7:20 PM", status="delivered",
    )
    world.mail.inbox.clear()
    world.mail.inbox["em_mp003_clock"] = Email(
        id="em_mp003_clock",
        sender="Calendar Reminder <noreply@shopgym.com>",
        to=USER_EMAIL,
        subject="Game night tonight at 7:00 PM",
        body=(
            "Reminder: game night starts at 7:00 PM tonight. "
            "Current time is about 3:15 PM on May 21."
        ),
        received_at=f"{SEED_DATE}T15:15:00",
        received_label="Today",
        read=False,
        labels=["personal"],
    )
    return world


def _suite_mp_003():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _pizza_usual(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", None) == MP003_PIZZA:
                return True
            if "pizza planet" in (getattr(o, "restaurant_name", "") or "").lower():
                return True
        return False

    def _supplies(p: Probe) -> bool:
        return len(lines(p, MP003_PLATES)) > 0 and len(lines(p, MP003_CUPS)) > 0

    def _sushi(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", None) == "r_mp003_sushi":
                return True
        return False

    return TaskSuite(
        task_id=MP003_ID,
        milestones=[
            Milestone("ordered_pizza_planet", weight=0.5, check=_pizza_usual, required_for_success=True),
            Milestone("bought_plates_and_cups", weight=0.5, check=_supplies, required_for_success=True),
            Milestone("ordered_sushi_house_not_usual", weight=0.0, check=_sushi, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_004 — PARTIAL: blender return + sketchy seller check (no buy)
# =========================================================================== #

MP004_ID = "mp_004/blender_return_and_ebay_seller_check"
MP004_BRIEF = (
    "Start a return for the blender I bought last month, it's broken. Also, I "
    "found a similar one on eBay for a lot less -- can you check if that listing "
    "looks legit before I go anywhere near it? The seller looks a little sketchy."
)
MP004_BLEND = "p_mp004_blender"
MP004_ORDER = "ord-8842"
MP004_VM = "vm_mp004_blender"


def task_mp_004(seed: int) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP004_ID, "hard")
    world.mail.account_email = USER_EMAIL
    shop = world.shop
    alice = shop.users["u_alice"]
    addr = alice.addresses["addr_home"]
    pay = "pay_visa"
    shop.products[MP004_BLEND] = Product(
        id=MP004_BLEND, name="NutriBlend Pro 1200W Blender",
        brand="NutriBlend", category="home", base_price=79.99,
        rating=4.2, review_count=640, stock=20, image_emoji="🫙",
        short_description="1200W countertop blender. Order delivered ~34 days ago.",
        tags=["blender", "return candidate"],
    )
    item = OrderItem(
        id="ln_mp004_blender", product_id=MP004_BLEND,
        product_name="NutriBlend Pro 1200W Blender", variant_id=None,
        variant_label="", quantity=1, unit_price=79.99,
        gift_wrap=False, gift_message="",
        ship_to_address_id=addr.id, scheduled_delivery=None,
    )
    # SEED_DATE 2026-05-21 → delivered 2026-04-17 = 34 days ago (>30-day window).
    # initiate_return does NOT enforce the window — agent must read the date.
    sh = Shipment(
        id="sh_mp004", tracking_number="1ZMP004BLEND", carrier="UPS",
        item_ids=[item.id], status="delivered",
        estimated_delivery="Delivered Friday, April 17, 2026",
        events=[
            ShipmentEvent("2026-04-14T10:00:00Z", "label_created", "Origin", "Label created"),
            ShipmentEvent("2026-04-17T15:00:00Z", "delivered", "Front door",
                          "Delivered Apr 17, 2026 (34 days before today May 21)"),
        ],
    )
    shop.orders[MP004_ORDER] = Order(
        id=MP004_ORDER, user_id="u_alice", placed_at="2026-04-14T09:00:00Z",
        items=[item], subtotal=79.99, discount=0.0, tax=6.80, shipping=0.0,
        total=86.79, promo_code=None, payment_id=pay, status="delivered",
        shipments=[sh],
    )
    world.market.products[MP004_VM] = MarketProduct(
        id=MP004_VM,
        name="NutriBlend Pro 1200W Blender - Like New",
        category="home", price=22.00, emoji="🫙",
        description=(
            "Like-new NutriBlend. $22 + $15 shipping. Seller quickdeals_2024: "
            "only 3 feedback, 67% positive, account age ~2 weeks — far below "
            "market. Do NOT buy unless user confirms after a cautious review."
        ),
        in_stock=True, condition="Used - Like New", shipping_cost=15.00,
        seller_id="seller_quickdeals",
        seller_username="quickdeals_2024",
        seller_feedback_score=3,
        seller_feedback_rating=67.0,
        shop_sku=MP004_BLEND,
    )
    return world


def _suite_mp_004():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, _, _, has_return = _shop_helpers()

    def _seller_caution(p: Probe) -> bool:
        blob = _mail_sent_blob(p)
        if not blob or not _emailed_user(p):
            return False
        return any(
            tok in blob
            for tok in (
                "sketchy", "suspicious", "caution", "careful", "risk", "low feedback",
                "67", "3 feedback", "new account", "not legit", "wouldn't", "would not",
                "avoid", "don't buy", "do not buy", "red flag", "untrustworthy",
            )
        )

    def _return_or_window(p: Probe) -> bool:
        if has_return(p, MP004_ORDER):
            return True
        blob = _mail_sent_blob(p)
        return any(
            tok in blob
            for tok in (
                "30-day", "30 day", "return window", "too late", "past the window",
                "expired", "not eligible", "outside the", "34 day", "customer service",
            )
        )

    def _bought_vm(p: Probe) -> bool:
        return _market_bought(p, MP004_VM)

    def _ok(p: Probe) -> bool:
        return _seller_caution(p) and _return_or_window(p) and (not _bought_vm(p))

    return TaskSuite(
        task_id=MP004_ID,
        milestones=[
            Milestone("return_path_and_seller_caution_email", weight=1.0, check=_ok, required_for_success=True),
            Milestone("bought_sketchy_ebay_blender", weight=0.0, check=_bought_vm, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_005 — RUNNABLE: reorder Korean usual
# =========================================================================== #

MP005_ID = "mp_005/reorder_korean_usual"
MP005_BRIEF = (
    "Getting hungry -- just reorder whatever I got last time from that Korean "
    "place, same as always."
)
MP005_REST = "r_mp005_seoul"
MP005_BIBIM = "d_mp005_bibimbap"
MP005_KIMCHI = "d_mp005_kimchi_pancake"
MP005_TEA = "d_mp005_barley_tea"
MP005_HIST = "FOOD-MP005-LAST"


def task_mp_005(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP005_ID, "hard")
    food = world.food
    food.restaurants[MP005_REST] = Restaurant(
        id=MP005_REST, name="Seoul Kitchen", cuisine="Korean",
        rating=4.6, eta_label="6:50 PM", delivery_fee=2.99, emoji="🍜",
        dishes=[
            Dish(id=MP005_BIBIM, name="Bibimbap",
                 description="Rice bowl with veggies and egg.",
                 price=14.50, tags=["korean", "usual"], emoji="🍲", popular=True),
            Dish(id=MP005_KIMCHI, name="Kimchi Pancake",
                 description="Crispy kimchi pancake.",
                 price=11.00, tags=["korean", "usual"], emoji="🥞"),
            Dish(id=MP005_TEA, name="Iced Barley Tea",
                 description="Cold barley tea.",
                 price=3.50, tags=["drink", "usual"], emoji="🧋"),
        ],
    )
    items = [
        FoodCartItem(dish_id=MP005_BIBIM, restaurant_id=MP005_REST,
                     name="Bibimbap", unit_price=14.50, quantity=1),
        FoodCartItem(dish_id=MP005_KIMCHI, restaurant_id=MP005_REST,
                     name="Kimchi Pancake", unit_price=11.00, quantity=1),
        FoodCartItem(dish_id=MP005_TEA, restaurant_id=MP005_REST,
                     name="Iced Barley Tea", unit_price=3.50, quantity=1),
    ]
    food.orders[MP005_HIST] = FoodOrder(
        id=MP005_HIST, restaurant_id=MP005_REST, restaurant_name="Seoul Kitchen",
        items=items, subtotal=29.00, delivery_fee=2.99, total=31.99,
        placed_at="2026-05-12T18:40:00", eta_label="7:05 PM", status="delivered",
    )
    return world


def _suite_mp_005():
    from server.verifiers import Milestone, Probe, TaskSuite
    new_food_orders, _ = _food_helpers()

    def _reorder(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", None) != MP005_REST:
                continue
            names = {(getattr(it, "name", "") or "").lower() for it in (o.items or [])}
            need = {"bibimbap", "kimchi pancake", "iced barley tea"}
            # Accept substring match
            ok = all(any(n in nm for nm in names) for n in need)
            if ok:
                return True
        return False

    return TaskSuite(
        task_id=MP005_ID,
        milestones=[
            Milestone("reordered_seoul_kitchen_usual", weight=1.0, check=_reorder, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_010 — PARTIAL: wishlist price drop (local shelf via wishlist_seed tag)
# =========================================================================== #

MP010_ID = "mp_010/wishlist_vacuum_price_drop_buy"
MP010_BRIEF = (
    "Check if that vacuum I saved a while back has dropped in price at all -- "
    "if it's cheaper now, go ahead and buy it."
)
MP010_VAC = "p_mp010_dyson"


def task_mp_010(seed: int) -> "WorldState":
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP010_ID, "hard")
    world.shop.products[MP010_VAC] = Product(
        id=MP010_VAC,
        name="Dyson V15 Detect Cordless Vacuum",
        brand="Dyson", category="home", base_price=579.99,
        rating=4.7, review_count=8900, stock=25, image_emoji="🧹",
        short_description=(
            "Wishlisted 3 weeks ago at $649.99. Current price $579.99 "
            "($70 drop) — buy if cheaper than when saved."
        ),
        tags=["wishlist_seed", "was_price:649.99", "Price drop $70"],
    )
    return world


def _suite_mp_010():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()

    def _bought(p: Probe) -> bool:
        return len(lines(p, MP010_VAC)) > 0

    return TaskSuite(
        task_id=MP010_ID,
        milestones=[
            Milestone("bought_wishlist_vacuum_after_drop", weight=1.0, check=_bought, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_012 — PARTIAL: desk + won chair (order history) + movers food
# =========================================================================== #

MP012_ID = "mp_012/moving_desk_chair_food"
MP012_BRIEF = (
    "Moving into the new apartment this weekend -- order a basic desk from "
    "Amazon, check if that office chair auction on eBay ended (I think I won "
    "it), and get food ordered for the movers around noon on Saturday."
)
MP012_DESK = "p_mp012_desk"
MP012_CHAIR = "vm_mp012_aeron"
MP012_CHAIR_ORD = "VM-MP012-CHAIR"


def task_mp_012(seed: int) -> "WorldState":
    from server.apps.market.state import MarketCartItem, MarketOrder, MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP012_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.products[MP012_DESK] = Product(
        id=MP012_DESK, name="SHW 55-Inch Large Computer Desk",
        brand="SHW", category="home", base_price=99.99,
        rating=4.4, review_count=5200, stock=40, image_emoji="🖥️",
        short_description="Basic large computer desk. Est. delivery 3 days.",
        tags=["desk", "basic", "Under $150"],
    )
    # Auction → ended BIN/purchase history (no live bid path).
    world.market.products[MP012_CHAIR] = MarketProduct(
        id=MP012_CHAIR,
        name="Herman Miller Aeron Office Chair (Used, Size B)",
        category="home", price=210.00, emoji="🪑",
        description=(
            "ENDED LISTING — You won / purchased at $210.00. Status: completed "
            "purchase in order history. Bidding is not available; this is a "
            "read-only confirmation that the chair is yours."
        ),
        in_stock=False, condition="Used", shipping_cost=0.0,
    )
    world.market.orders[MP012_CHAIR_ORD] = MarketOrder(
        id=MP012_CHAIR_ORD,
        items=[MarketCartItem(product_id=MP012_CHAIR, name="Herman Miller Aeron Office Chair (Used, Size B)",
                              unit_price=210.00, quantity=1)],
        subtotal=210.00, discount=0.0, delivery_fee=0.0, total=210.00,
        placed_at="2026-05-18T16:00:00",
    )
    # Burger Barn already in default food catalog for movers lunch.
    return world


def _suite_mp_012():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _desk(p: Probe) -> bool:
        return len(lines(p, MP012_DESK)) > 0

    def _food(p: Probe) -> bool:
        return len(new_food_orders(p)) > 0

    def _chair_note(p: Probe) -> bool:
        blob = _mail_sent_blob(p)
        if not blob or not _emailed_user(p):
            return False
        return any(tok in blob for tok in ("won", "210", "aeron", "chair", "ended", "confirmed"))

    def _ok(p: Probe) -> bool:
        return _desk(p) and _food(p) and _chair_note(p)

    return TaskSuite(
        task_id=MP012_ID,
        milestones=[
            Milestone("desk_food_and_chair_win_email", weight=1.0, check=_ok, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_013 — RUNNABLE: return rose-gold case + order black (separate SKUs)
# =========================================================================== #

MP013_ID = "mp_013/return_wrong_color_case_order_black"
MP013_BRIEF = (
    "That phone case I ordered came in the wrong color. Start a return for it "
    "and order the black one instead."
)
MP013_ROSE = "p_mp013_case_rose"
MP013_BLACK = "p_mp013_case_black"
MP013_CLEAR = "p_mp013_case_clear"
MP013_NAVY = "p_mp013_case_navy"
MP013_ORDER = "ord-6120"


def task_mp_013(seed: int) -> "WorldState":
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP013_ID, "hard")
    shop = world.shop
    alice = shop.users["u_alice"]
    addr = alice.addresses["addr_home"]
    # Bridged Xmazon does not project ProductVariant pickers — seed color as
    # separate products (honest adaptation of "variants" column).
    for pid, name, price in (
        (MP013_ROSE, "Spigen Rugged Armor Phone Case - Rose Gold", 19.99),
        (MP013_BLACK, "Spigen Rugged Armor Phone Case - Black", 19.99),
        (MP013_CLEAR, "Spigen Rugged Armor Phone Case - Clear", 19.99),
        (MP013_NAVY, "Spigen Rugged Armor Phone Case - Navy Blue", 19.99),
    ):
        shop.products[pid] = Product(
            id=pid, name=name, brand="Spigen", category="electronics",
            base_price=price, rating=4.5, review_count=4100, stock=60,
            image_emoji="📱",
            short_description=f"{name}. Compatible MagSafe case.",
            tags=["phone case", "Spigen"],
        )
    item = OrderItem(
        id="ln_mp013_rose", product_id=MP013_ROSE,
        product_name="Spigen Rugged Armor Phone Case - Rose Gold",
        variant_id=None, variant_label="Rose Gold", quantity=1, unit_price=19.99,
        gift_wrap=False, gift_message="",
        ship_to_address_id=addr.id, scheduled_delivery=None,
    )
    sh = Shipment(
        id="sh_mp013", tracking_number="1ZMP013CASE", carrier="USPS",
        item_ids=[item.id], status="delivered",
        estimated_delivery="Delivered Thursday, May 15, 2026",
        events=[
            ShipmentEvent("2026-05-15T12:00:00Z", "delivered", "Mailbox", "Delivered"),
        ],
    )
    shop.orders[MP013_ORDER] = Order(
        id=MP013_ORDER, user_id="u_alice", placed_at="2026-05-15T09:00:00Z",
        items=[item], subtotal=19.99, discount=0.0, tax=1.70, shipping=0.0,
        total=21.69, promo_code=None, payment_id="pay_visa", status="delivered",
        shipments=[sh],
    )
    return world


def _suite_mp_013():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, has_return = _shop_helpers()

    def _ret(p: Probe) -> bool:
        return has_return(p, MP013_ORDER)

    def _black(p: Probe) -> bool:
        return len(lines(p, MP013_BLACK)) > 0

    def _rose_again(p: Probe) -> bool:
        return len(lines(p, MP013_ROSE)) > 0

    def _ok(p: Probe) -> bool:
        return _ret(p) and _black(p)

    return TaskSuite(
        task_id=MP013_ID,
        milestones=[
            Milestone("returned_rose_ordered_black", weight=1.0, check=_ok, required_for_success=True),
            Milestone("reordered_rose_gold", weight=0.0, check=_rose_again, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_016 — PARTIAL: snacks + wings + projector ETA (order history, not auction)
# =========================================================================== #

MP016_ID = "mp_016/watch_party_snacks_wings_projector"
MP016_BRIEF = (
    "Hosting a small watch party Sunday -- order snacks and drinks from Amazon, "
    "nothing fancy, around $50. Order wings from somewhere on Uber Eats for "
    "about 6 people. And check if that projector I won on eBay will actually "
    "arrive in time -- kickoff's at 6pm."
)
MP016_SNACK = "p_mp016_snack"
MP016_SODA = "p_mp016_soda"
MP016_CHIPS = "p_mp016_chips"
MP016_PROJ = "vm_mp016_projector"
MP016_PROJ_ORD = "VM-MP016-PROJ"
MP016_WINGS = "r_mp016_flame"
MP016_WING_DISH = "d_mp016_wings"


def task_mp_016(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, Restaurant
    from server.apps.market.state import MarketCartItem, MarketOrder, MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP016_ID, "hard")
    world.mail.account_email = USER_EMAIL
    shop = world.shop
    shop.products[MP016_SNACK] = Product(
        id=MP016_SNACK, name="Variety Snack Box, 30-Count",
        brand="SnackBox", category="grocery", base_price=22.99,
        rating=4.4, review_count=900, stock=80, image_emoji="🍿",
        short_description="Party snack variety box.",
        tags=["party", "snacks"],
    )
    shop.products[MP016_SODA] = Product(
        id=MP016_SODA, name="Assorted Soda 12-Pack",
        brand="FizzCo", category="grocery", base_price=14.99,
        rating=4.3, review_count=700, stock=90, image_emoji="🥤",
        short_description="Assorted soda 12-pack.",
        tags=["party", "drinks"],
    )
    shop.products[MP016_CHIPS] = Product(
        id=MP016_CHIPS, name="Tortilla Chips + Salsa Party Pack",
        brand="ChipCo", category="grocery", base_price=11.99,
        rating=4.5, review_count=1100, stock=70, image_emoji="🌮",
        short_description="Chips and salsa party pack.",
        tags=["party", "snacks"],
    )
    food = world.food
    food.restaurants[MP016_WINGS] = Restaurant(
        id=MP016_WINGS, name="Flame Grill House", cuisine="American",
        rating=4.5, eta_label="6:30 PM", delivery_fee=3.49, emoji="🔥",
        dishes=[
            Dish(id=MP016_WING_DISH, name="50-pc Wing Party Pack",
                 description="50 wings, serves 6-8 people.",
                 price=54.99, tags=["wings", "party", "serves-6"], emoji="🍗", popular=True),
            Dish(id="d_mp016_small", name="12-pc Wings",
                 description="Small wing order for 1-2.",
                 price=16.99, tags=["wings"], emoji="🍗"),
        ],
    )
    world.market.products[MP016_PROJ] = MarketProduct(
        id=MP016_PROJ,
        name="Epson Home Cinema 1080p Projector",
        category="electronics", price=189.00, emoji="📽️",
        description=(
            "PURCHASE / WON — shipping status: Not yet shipped. Estimated "
            "delivery: Tuesday (AFTER Sunday 6pm kickoff). Will NOT arrive in "
            "time for the watch party."
        ),
        in_stock=False, condition="Used", shipping_cost=12.00,
    )
    world.market.orders[MP016_PROJ_ORD] = MarketOrder(
        id=MP016_PROJ_ORD,
        items=[MarketCartItem(product_id=MP016_PROJ, name="Epson Home Cinema 1080p Projector",
                              unit_price=189.00, quantity=1)],
        subtotal=189.00, discount=0.0, delivery_fee=12.00, total=201.00,
        placed_at="2026-05-17T11:00:00",
    )
    return world


def _suite_mp_016():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, new_orders, lines, _, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _snacks_ok(p: Probe) -> bool:
        # Any combination near ~$50 of the three party SKUs
        total = 0.0
        bought = 0
        for pid, price in ((MP016_SNACK, 22.99), (MP016_SODA, 14.99), (MP016_CHIPS, 11.99)):
            if lines(p, pid):
                bought += 1
                total += price
        return bought >= 2 and total <= 55.01

    def _wings(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", None) == MP016_WINGS:
                return True
            for it in o.items or []:
                if "wing" in (getattr(it, "name", "") or "").lower():
                    return True
        return False

    def _proj_late(p: Probe) -> bool:
        blob = _mail_sent_blob(p)
        if not blob or not _emailed_user(p):
            return False
        return any(
            tok in blob
            for tok in (
                "tuesday", "not arrive", "won't arrive", "will not arrive",
                "too late", "after", "not yet shipped", "miss", "late",
            )
        )

    def _ok(p: Probe) -> bool:
        return _snacks_ok(p) and _wings(p) and _proj_late(p)

    def _over_budget(p: Probe) -> bool:
        total = 0.0
        for o in new_orders(p):
            total += float(getattr(o, "subtotal", 0) or 0)
        # Only flag if clearly way over snack budget with many extras
        return total > 80.0

    return TaskSuite(
        task_id=MP016_ID,
        milestones=[
            Milestone("snacks_wings_projector_late_email", weight=1.0, check=_ok, required_for_success=True),
            Milestone("amazon_way_over_snack_budget", weight=0.0, check=_over_budget, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_019 — RUNNABLE: cancel preparing order + reorder elsewhere
# =========================================================================== #

MP019_ID = "mp_019/cancel_preparing_reorder_elsewhere"
MP019_BRIEF = (
    "My order's taking way longer than it should. If it's not out for delivery "
    "yet, just cancel it and order the same thing from somewhere else."
)
MP019_PANDA = "r_mp019_panda"
MP019_GOLDEN = "r_mp019_golden"
MP019_OC = "d_mp019_orange"
MP019_RICE = "d_mp019_rice"
MP019_ACTIVE = "FOOD-MP019-ACTIVE"


def task_mp_019(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP019_ID, "hard")
    food = world.food
    food.restaurants[MP019_PANDA] = Restaurant(
        id=MP019_PANDA, name="Panda Garden", cuisine="Chinese",
        rating=4.2, eta_label="6:20 PM", delivery_fee=2.49, emoji="🐼",
        dishes=[
            Dish(id=MP019_OC, name="Orange Chicken",
                 description="Crispy chicken in orange sauce.",
                 price=12.50, tags=["chinese"], emoji="🍊", popular=True),
            Dish(id=MP019_RICE, name="Fried Rice",
                 description="Classic fried rice.",
                 price=5.50, tags=["side"], emoji="🍚"),
        ],
    )
    food.restaurants[MP019_GOLDEN] = Restaurant(
        id=MP019_GOLDEN, name="Golden Dragon", cuisine="Chinese",
        rating=4.4, eta_label="6:35 PM", delivery_fee=2.99, emoji="🐉",
        dishes=[
            Dish(id="d_mp019_g_oc", name="Orange Chicken",
                 description="Crispy chicken in orange sauce.",
                 price=12.00, tags=["chinese"], emoji="🍊", popular=True),
            Dish(id="d_mp019_g_rice", name="Fried Rice",
                 description="Classic fried rice.",
                 price=5.00, tags=["side"], emoji="🍚"),
        ],
    )
    items = [
        FoodCartItem(dish_id=MP019_OC, restaurant_id=MP019_PANDA,
                     name="Orange Chicken", unit_price=12.50, quantity=1),
        FoodCartItem(dish_id=MP019_RICE, restaurant_id=MP019_PANDA,
                     name="Fried Rice", unit_price=5.50, quantity=1),
    ]
    food.orders[MP019_ACTIVE] = FoodOrder(
        id=MP019_ACTIVE, restaurant_id=MP019_PANDA, restaurant_name="Panda Garden",
        items=items, subtotal=18.00, delivery_fee=2.49, total=20.49,
        placed_at="2026-05-21T11:20:00", eta_label="12:00 PM",
        status="preparing",  # not out_for_delivery → cancel+reorder
    )
    return world


def _suite_mp_019():
    from server.verifiers import Milestone, Probe, TaskSuite
    new_food_orders, food_order = _food_helpers()

    def _cancelled(p: Probe) -> bool:
        o = food_order(p, MP019_ACTIVE)
        return o is not None and (getattr(o, "status", "") or "").lower() == "cancelled"

    def _reordered(p: Probe) -> bool:
        for o in new_food_orders(p):
            if getattr(o, "restaurant_id", None) == MP019_PANDA:
                continue
            names = " ".join((getattr(it, "name", "") or "").lower() for it in (o.items or []))
            if "orange" in names and "rice" in names:
                return True
            if getattr(o, "restaurant_id", None) == MP019_GOLDEN:
                return True
        return False

    def _ok(p: Probe) -> bool:
        return _cancelled(p) and _reordered(p)

    return TaskSuite(
        task_id=MP019_ID,
        milestones=[
            Milestone("cancelled_preparing_and_reordered", weight=1.0, check=_ok, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_021 — RUNNABLE: cart qty +1 coffee pods
# =========================================================================== #

MP021_ID = "mp_021/cart_qty_plus_coffee_pods"
MP021_BRIEF = "Add another one of the coffee pods to my cart, same kind as before."
MP021_PODS = "p_mp021_pods"


def task_mp_021(seed: int) -> "WorldState":
    from server.state import CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP021_ID, "easy")
    shop = world.shop
    shop.products[MP021_PODS] = Product(
        id=MP021_PODS,
        name="Starbucks Pike Place Roast K-Cup Pods, 24 Count",
        brand="Starbucks", category="grocery", base_price=14.99,
        rating=4.6, review_count=5000, stock=120, image_emoji="☕",
        short_description="Pike Place Roast K-Cup pods, 24 count.",
        tags=["coffee", "k-cup"],
    )
    shop.cart.items = [
        CartItem(id="ci_mp021_pods", product_id=MP021_PODS,
                 variant_id=None, quantity=1),
    ]
    return world


def _suite_mp_021():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, _, cart_qty, _ = _shop_helpers()

    def _qty2(p: Probe) -> bool:
        return cart_qty(p, MP021_PODS) >= 2

    return TaskSuite(
        task_id=MP021_ID,
        milestones=[
            Milestone("coffee_pods_qty_at_least_2", weight=1.0, check=_qty2, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_026 — PARTIAL: ASAP supplies (ETA text) + dinner (no hard same-day selector)
# =========================================================================== #

MP026_ID = "mp_026/school_supplies_and_dinner"
MP026_BRIEF = (
    "Kid's got a school project due -- needs poster board and markers ASAP. "
    "Also order him something for dinner, I'm stuck at work late."
)
MP026_POSTER = "p_mp026_poster"
MP026_MARKERS = "p_mp026_markers"


def task_mp_026(seed: int) -> "WorldState":
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP026_ID, "hard")
    shop = world.shop
    # Same-day shipping selector is weak — put ASAP cue in product copy.
    shop.products[MP026_POSTER] = Product(
        id=MP026_POSTER, name="Elmer's Tri-Fold Poster Board, White, 3-Pack",
        brand="Elmer's", category="office", base_price=9.99,
        rating=4.6, review_count=2200, stock=80, image_emoji="📋",
        short_description="Tri-fold poster board. ASAP / same-day delivery available.",
        tags=["ASAP", "Same-day delivery", "school"],
    )
    shop.products[MP026_MARKERS] = Product(
        id=MP026_MARKERS, name="Crayola Broad Line Markers, 24 count",
        brand="Crayola", category="office", base_price=5.49,
        rating=4.8, review_count=8000, stock=100, image_emoji="🖍️",
        short_description="Broad-line markers. ASAP / same-day delivery available.",
        tags=["ASAP", "Same-day delivery", "school"],
    )
    # Burger Barn in default food catalog for dinner.
    return world


def _suite_mp_026():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _supplies(p: Probe) -> bool:
        return len(lines(p, MP026_POSTER)) > 0 and len(lines(p, MP026_MARKERS)) > 0

    def _dinner(p: Probe) -> bool:
        return len(new_food_orders(p)) > 0

    def _ok(p: Probe) -> bool:
        return _supplies(p) and _dinner(p)

    return TaskSuite(
        task_id=MP026_ID,
        milestones=[
            Milestone("supplies_and_dinner", weight=1.0, check=_ok, required_for_success=True),
        ],
    )


# =========================================================================== #
# Registry
# =========================================================================== #

TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    MP002_ID: task_mp_002,
    MP003_ID: task_mp_003,
    MP004_ID: task_mp_004,
    MP005_ID: task_mp_005,
    MP010_ID: task_mp_010,
    MP012_ID: task_mp_012,
    MP013_ID: task_mp_013,
    MP016_ID: task_mp_016,
    MP019_ID: task_mp_019,
    MP021_ID: task_mp_021,
    MP026_ID: task_mp_026,
}

BRIEFS: dict[str, str] = {
    "mp_002": MP002_BRIEF,
    "mp_003": MP003_BRIEF,
    "mp_004": MP004_BRIEF,
    "mp_005": MP005_BRIEF,
    "mp_010": MP010_BRIEF,
    "mp_012": MP012_BRIEF,
    "mp_013": MP013_BRIEF,
    "mp_016": MP016_BRIEF,
    "mp_019": MP019_BRIEF,
    "mp_021": MP021_BRIEF,
    "mp_026": MP026_BRIEF,
}

START_URLS: dict[str, str] = {
    MP002_ID: "/",
    MP003_ID: "/",
    MP004_ID: "/orders",
    MP005_ID: "/",
    MP010_ID: "/wishlist",
    MP012_ID: "/",
    MP013_ID: "/orders",
    MP016_ID: "/",
    MP019_ID: "/",
    MP021_ID: "/cart",
    MP026_ID: "/",
}

HINTS: dict[str, list] = {tid: [] for tid in TASK_FACTORIES}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    return {
        MP002_ID: _suite_mp_002,
        MP003_ID: _suite_mp_003,
        MP004_ID: _suite_mp_004,
        MP005_ID: _suite_mp_005,
        MP010_ID: _suite_mp_010,
        MP012_ID: _suite_mp_012,
        MP013_ID: _suite_mp_013,
        MP016_ID: _suite_mp_016,
        MP019_ID: _suite_mp_019,
        MP021_ID: _suite_mp_021,
        MP026_ID: _suite_mp_026,
    }
