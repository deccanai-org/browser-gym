"""mp_001–mp_030 LH∩RUNNABLE batch — Sol seed-0 screen tasks.

Eight long-horizon prompts that the 2026-08-06 validity assessment marked
RUNNABLE on the bridged five-hub stack. Goal-only briefs; durable-state
verifiers. Delivery ETA cues live in product short_description / tags when
Xmazon UI ETA is prime-only. Xbay shipping_cost projects via transform.
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

    def cart_has(p: Probe, pid: str) -> bool:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return False
        return any(getattr(it, "product_id", None) == pid for it in (shop.cart.items or []))

    def addr_by_id(p: Probe, aid: str):
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return None
        alice = (shop.users or {}).get("u_alice")
        if not alice:
            return None
        return (alice.addresses or {}).get(aid)

    return orders, new_orders, lines, cart_has, addr_by_id


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

    def food_cart_empty(p: Probe) -> bool:
        food = getattr(p.world, "food", None) if p.world else None
        if not food:
            return False
        return not (food.cart.items or [])

    return new_food_orders, food_cart_empty


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
        parts.append(f"{getattr(e, 'to', '')} {getattr(e, 'subject', '')} {getattr(e, 'body', '')}")
    return " ".join(parts).lower()


# =========================================================================== #
# mp_001 — mail address → ship earbuds to mom
# =========================================================================== #

MP001_ID = "mp_001/ship_earbuds_to_mom_from_mail"
MP001_BRIEF = (
    "Hey, can you order the earbuds in my cart but ship them to my mom's place "
    "instead of mine? She mentioned her new address in an email a while back, "
    "I can't remember it offhand."
)
MP001_EARBUDS = "p_mp001_earbuds"
MP001_EMAIL = "em_mp001_mom_moved"
MP001_HOME = "addr_home"
MOM_LINE1 = "88 Rosewood Lane"
MOM_LINE2 = "Apt 3"
MOM_CITY, MOM_STATE, MOM_ZIP = "Portland", "OR", "97205"


def task_mp_001(seed: int) -> "WorldState":
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Address, CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP001_ID, "hard")
    world.mail.account_email = USER_EMAIL
    shop = world.shop
    alice = shop.users["u_alice"]
    alice.addresses[MP001_HOME] = Address(
        id=MP001_HOME, label="Home", full_name="Alice Anderson",
        line1="455 Elm St", line2="", city="Seattle", state="WA", zip="98109",
        is_default=True,
    )
    # Ensure no Mom address pre-saved.
    for aid in list(alice.addresses):
        if aid != MP001_HOME and "mom" in (alice.addresses[aid].label or "").lower():
            del alice.addresses[aid]

    shop.products[MP001_EARBUDS] = Product(
        id=MP001_EARBUDS,
        name="Sony WF-1000XM5 Wireless Earbuds",
        brand="Sony", category="electronics", base_price=279.99,
        rating=4.8, review_count=4200, stock=50, image_emoji="🎧",
        short_description="Flagship noise-cancelling wireless earbuds.",
    )
    shop.cart.items = [
        CartItem(id="ci_mp001_earbuds", product_id=MP001_EARBUDS,
                 variant_id=None, quantity=1),
    ]
    world.mail.inbox.clear()
    world.mail.inbox[MP001_EMAIL] = Email(
        id=MP001_EMAIL,
        sender="Linda Carter (Mom) <linda.carter77@email.com>",
        to=USER_EMAIL,
        subject="We moved!",
        body=(
            "Hi honey, just a heads up your dad and I finally moved into the "
            "new place. New address is 88 Rosewood Lane, Apt 3, Portland, OR "
            "97205 in case you want to send anything our way. Call us when you "
            "get a chance!"
        ),
        received_at=f"{SEED_DATE}T09:10:00",
        received_label="6 days ago",
        read=False,
        labels=["personal"],
    )
    return world


def _suite_mp_001():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, new_orders, lines, _, addr_by_id = _shop_helpers()

    def _to_mom(p: Probe) -> bool:
        for it in lines(p, MP001_EARBUDS):
            aid = getattr(it, "ship_to_address_id", None)
            if aid == MP001_HOME:
                continue
            addr = addr_by_id(p, aid)
            if addr and MOM_LINE1.lower() in (addr.line1 or "").lower():
                return True
            # Also accept if line1 was entered with apt on same line
            blob = f"{getattr(addr, 'line1', '')} {getattr(addr, 'line2', '')} {getattr(addr, 'city', '')}".lower() if addr else ""
            if MOM_LINE1.lower() in blob and "portland" in blob:
                return True
        return False

    def _to_home(p: Probe) -> bool:
        return any(
            getattr(it, "ship_to_address_id", None) == MP001_HOME
            for it in lines(p, MP001_EARBUDS)
        )

    def _ordered_earbuds(p: Probe) -> bool:
        return len(lines(p, MP001_EARBUDS)) > 0

    return TaskSuite(
        task_id=MP001_ID,
        milestones=[
            Milestone("ordered_earbuds_to_mom", weight=1.0, check=lambda p: _ordered_earbuds(p) and _to_mom(p), required_for_success=True),
            Milestone("shipped_earbuds_to_home", weight=0.0, check=_to_home, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_006 — calendar party → gift ≤$30 that arrives in time
# =========================================================================== #

MP006_ID = "mp_006/nephew_party_gift_budget_eta"
MP006_BRIEF = (
    "Need a birthday gift for my nephew, he's turning 8. Budget's $30 max, and "
    "it has to arrive before his party -- I think that's this weekend?"
)
MP006_NERF = "p_mp006_nerf"
MP006_LEGO = "p_mp006_lego"
MP006_HOTWHEELS = "p_mp006_hotwheels"
MP006_PARTY = "ev_mp006_party"
MP006_BBQ = "ev_mp006_bbq"
SATURDAY = "2026-05-23"
SUNDAY = "2026-05-24"


def task_mp_006(seed: int) -> "WorldState":
    from server.apps.calendar.state import CalendarEvent
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP006_ID, "hard")
    cal = world.calendar
    cal.events.clear()
    cal.events[MP006_PARTY] = CalendarEvent(
        id=MP006_PARTY, title="Tommy's 8th Birthday Party",
        day=SATURDAY, day_label="Saturday (May 23)",
        start="14:00", end="17:00", source="seed",
    )
    cal.events[MP006_BBQ] = CalendarEvent(
        id=MP006_BBQ, title="Family BBQ",
        day=SUNDAY, day_label="Sunday (May 24)",
        start="12:00", end="15:00", source="seed",
    )
    shop = world.shop
    shop.products[MP006_NERF] = Product(
        id=MP006_NERF, name="Nerf Elite 2.0 Blaster", brand="Nerf",
        category="toys", base_price=24.99, rating=4.5, review_count=900,
        stock=40, image_emoji="🔫",
        short_description="Kids toy blaster. Estimated delivery: 3 business days (arrives before Saturday).",
        tags=["Arrives in 3 business days", "Under $30"],
    )
    shop.products[MP006_LEGO] = Product(
        id=MP006_LEGO, name="LEGO Classic Creative Bricks Set", brand="LEGO",
        category="toys", base_price=29.99, rating=4.8, review_count=2100,
        stock=35, image_emoji="🧱",
        short_description="Creative bricks for age 4+. Estimated delivery: 2 business days (arrives before Saturday).",
        tags=["Arrives in 2 business days", "Under $30"],
    )
    shop.products[MP006_HOTWHEELS] = Product(
        id=MP006_HOTWHEELS, name="Hot Wheels 20-Car Gift Pack", brand="Hot Wheels",
        category="toys", base_price=19.97, rating=4.6, review_count=1500,
        stock=60, image_emoji="🚗",
        short_description="20-car gift pack. Estimated delivery: 5 business days — WILL MISS a Saturday party this week.",
        tags=["Arrives in 5 business days", "Too slow for this weekend"],
    )
    return world


def _suite_mp_006():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()

    def _ok_gift(p: Probe) -> bool:
        return len(lines(p, MP006_NERF)) > 0 or len(lines(p, MP006_LEGO)) > 0

    def _hotwheels(p: Probe) -> bool:
        return len(lines(p, MP006_HOTWHEELS)) > 0

    def _over_budget(p: Probe) -> bool:
        _, new_orders, _, _, _ = _shop_helpers()
        for o in new_orders(p):
            for it in o.items:
                if float(getattr(it, "unit_price", 0) or 0) > 30.01:
                    return True
        return False

    return TaskSuite(
        task_id=MP006_ID,
        milestones=[
            Milestone("bought_on_time_gift_under_30", weight=1.0, check=_ok_gift, required_for_success=True),
            Milestone("bought_hotwheels_misses_deadline", weight=0.0, check=_hotwheels, required_for_success=False, forbidden=True),
            Milestone("over_budget_gift", weight=0.0, check=_over_budget, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_008 — dinner + Amazon frozen pizza ATC (no checkout)
# =========================================================================== #

MP008_ID = "mp_008/dinner_plus_frozen_pizza_cart_only"
MP008_BRIEF = (
    "Forgot to defrost anything for dinner -- go ahead and order us food from "
    "somewhere, and add a couple frozen pizzas to my next Amazon order so this "
    "doesn't happen again."
)
MP008_TOWELS = "p_mp008_towels"
MP008_PIZZA = "p_mp008_digiorno"
MP008_GOLDEN = "r_mp008_golden"
MP008_DISH = "d_mp008_general_tsos"


def task_mp_008(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, Restaurant
    from server.state import CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP008_ID, "hard")
    shop = world.shop
    shop.products[MP008_TOWELS] = Product(
        id=MP008_TOWELS, name="Bounty Paper Towels, 12 Rolls", brand="Bounty",
        category="household", base_price=18.99, rating=4.7, review_count=8000,
        stock=100, image_emoji="🧻",
        short_description="12-roll paper towel pack.",
    )
    shop.products[MP008_PIZZA] = Product(
        id=MP008_PIZZA, name="DiGiorno Rising Crust Pepperoni Pizza, 2-pack",
        brand="DiGiorno", category="grocery", base_price=11.98, rating=4.4,
        review_count=2200, stock=80, image_emoji="🍕",
        short_description="Frozen rising-crust pepperoni pizza, 2-pack.",
        tags=["frozen pizza"],
    )
    shop.cart.items = [
        CartItem(id="ci_mp008_towels", product_id=MP008_TOWELS,
                 variant_id=None, quantity=1),
    ]
    food = world.food
    food.restaurants[MP008_GOLDEN] = Restaurant(
        id=MP008_GOLDEN, name="Golden Dragon", cuisine="Chinese",
        rating=4.4, eta_label="6:50 PM", delivery_fee=2.99, emoji="🐉",
        dishes=[
            Dish(id=MP008_DISH, name="General Tso's Chicken",
                 description="Crispy chicken in sweet-spicy sauce with rice.",
                 price=14.50, tags=["dinner", "chicken"], emoji="🥡", popular=True),
            Dish(id="d_mp008_fried_rice", name="Vegetable Fried Rice",
                 description="Wok-fried rice with mixed vegetables.",
                 price=9.50, tags=["dinner", "vegetarian"], emoji="🍚"),
        ],
    )
    # Ensure Burger Barn remains available as alternate.
    return world


def _suite_mp_008():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, new_orders, _, cart_has, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _dinner(p: Probe) -> bool:
        return len(new_food_orders(p)) > 0

    def _pizza_in_cart(p: Probe) -> bool:
        return cart_has(p, MP008_PIZZA) and cart_has(p, MP008_TOWELS)

    def _amazon_checked_out(p: Probe) -> bool:
        return len(new_orders(p)) > 0

    def _towels_removed(p: Probe) -> bool:
        return (not cart_has(p, MP008_TOWELS)) and cart_has(p, MP008_PIZZA) and (not new_orders(p))

    return TaskSuite(
        task_id=MP008_ID,
        milestones=[
            Milestone("placed_dinner_order", weight=0.5, check=_dinner, required_for_success=True),
            Milestone("frozen_pizza_in_cart_with_towels", weight=0.5, check=_pizza_in_cart, required_for_success=True),
            Milestone("amazon_checked_out_early", weight=0.0, check=_amazon_checked_out, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_014 — clear Uber cart + Amazon meal prep + scale
# =========================================================================== #

MP014_ID = "mp_014/clear_food_cart_buy_meal_prep"
MP014_BRIEF = (
    "Trying to eat healthier -- cancel whatever's in my Uber Eats cart right "
    "now, and instead order some meal prep containers and a food scale from "
    "Amazon. I'll cook my own stuff."
)
MP014_CONTAINERS = "p_mp014_containers"
MP014_SCALE = "p_mp014_scale"
MP014_BURGER = "d_classic"
MP014_FRIES = "d_fries"


def task_mp_014(seed: int) -> "WorldState":
    from server.apps.food.state import FoodCartItem
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP014_ID, "hard")
    shop = world.shop
    shop.products[MP014_CONTAINERS] = Product(
        id=MP014_CONTAINERS, name="Prep Naturals Meal Prep Containers, 20-Pack",
        brand="Prep Naturals", category="household", base_price=25.99,
        rating=4.6, review_count=1100, stock=70, image_emoji="🍱",
        short_description="20 reusable meal prep containers.",
    )
    shop.products[MP014_SCALE] = Product(
        id=MP014_SCALE,
        name="Etekcity Digital Kitchen Scale with Nutritional Calculator",
        brand="Etekcity", category="household", base_price=16.99,
        rating=4.5, review_count=3400, stock=90, image_emoji="⚖️",
        short_description="Digital food scale with nutrition readout.",
    )
    food = world.food
    food.cart.restaurant_id = "r_burger"
    food.cart.items = [
        FoodCartItem(dish_id=MP014_BURGER, restaurant_id="r_burger",
                     name="Classic Cheeseburger", unit_price=10.00, quantity=2),
        FoodCartItem(dish_id=MP014_FRIES, restaurant_id="r_burger",
                     name="Loaded Fries", unit_price=4.00, quantity=1),
    ]
    return world


def _suite_mp_014():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()
    new_food_orders, food_cart_empty = _food_helpers()

    def _cleared(p: Probe) -> bool:
        return food_cart_empty(p)

    def _bought_both(p: Probe) -> bool:
        return len(lines(p, MP014_CONTAINERS)) > 0 and len(lines(p, MP014_SCALE)) > 0

    def _food_ordered(p: Probe) -> bool:
        return len(new_food_orders(p)) > 0

    return TaskSuite(
        task_id=MP014_ID,
        milestones=[
            Milestone("food_cart_cleared", weight=0.3, check=_cleared, required_for_success=True),
            Milestone("bought_containers_and_scale", weight=0.7, check=_bought_both, required_for_success=True),
            Milestone("placed_uber_burger_order", weight=0.0, check=_food_ordered, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_018 — stop eBay, buy Amazon turntable that arrives this week
# =========================================================================== #

MP018_ID = "mp_018/amazon_turntable_this_week_not_ebay"
MP018_BRIEF = (
    "I keep losing bidding wars on this record player on eBay. Just find me a "
    "similar one new on Amazon, even if it costs a bit more -- I need it this week."
)
MP018_VICTROLA = "p_mp018_victrola"
MP018_AT = "p_mp018_at"
MP018_EBAY = "vm_mp018_crosley"


def task_mp_018(seed: int) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP018_ID, "hard")
    shop = world.shop
    shop.products[MP018_VICTROLA] = Product(
        id=MP018_VICTROLA,
        name="Victrola Vintage 3-Speed Bluetooth Record Player",
        brand="Victrola", category="electronics", base_price=99.99,
        rating=4.3, review_count=1800, stock=40, image_emoji="🎵",
        short_description="Bluetooth turntable. Estimated delivery: 2 days — arrives THIS WEEK.",
        tags=["Arrives in 2 days", "This week"],
    )
    shop.products[MP018_AT] = Product(
        id=MP018_AT, name="Audio-Technica AT-LP60X Turntable",
        brand="Audio-Technica", category="electronics", base_price=149.99,
        rating=4.7, review_count=5200, stock=25, image_emoji="🎶",
        short_description="Automatic belt-drive turntable. Estimated delivery: 8 days — NOT this week.",
        tags=["Arrives in 8 days", "Too slow for this week"],
    )
    world.market.products[MP018_EBAY] = MarketProduct(
        id=MP018_EBAY,
        name="Crosley Cruiser Portable Turntable - Vintage",
        category="electronics", price=95.00, emoji="📻",
        description=(
            "Watchlist decoy: you have been outbid 3 times (your max $68; "
            "current high $95). Bidding is not available on Xbay — do not "
            "chase this listing; buy new on Xmazon instead."
        ),
        in_stock=True, condition="Used", shipping_cost=12.00,
    )
    return world


def _suite_mp_018():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()

    def _victrola(p: Probe) -> bool:
        return len(lines(p, MP018_VICTROLA)) > 0

    def _at_slow(p: Probe) -> bool:
        return len(lines(p, MP018_AT)) > 0

    def _ebay_buy(p: Probe) -> bool:
        if p.world is None or p.world.market is None:
            return False
        init = (p.initial_world.market.orders if p.initial_world and p.initial_world.market else {}) or {}
        for oid, o in (p.world.market.orders or {}).items():
            if oid in init:
                continue
            for it in o.items:
                if getattr(it, "product_id", None) == MP018_EBAY:
                    return True
        return False

    return TaskSuite(
        task_id=MP018_ID,
        milestones=[
            Milestone("bought_victrola_this_week", weight=1.0, check=_victrola, required_for_success=True),
            Milestone("bought_audio_technica_too_slow", weight=0.0, check=_at_slow, required_for_success=False, forbidden=True),
            Milestone("bought_ebay_crosley", weight=0.0, check=_ebay_buy, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_024 — mail water shutoff → Amazon water + Xber dinner tomorrow
# =========================================================================== #

MP024_ID = "mp_024/water_shutoff_amazon_water_dinner_tomorrow"
MP024_BRIEF = (
    "Landlord emailed saying the building's shutting off water all day tomorrow "
    "for maintenance. Order some bottled water from Amazon for that, and get "
    "dinner delivered tomorrow night since I won't be able to cook."
)
MP024_WATER = "p_mp024_water"
MP024_EMAIL = "em_mp024_shutoff"
MP024_TACO = "r_mp024_taco"
MP024_DISH = "d_mp024_burrito"


def task_mp_024(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP024_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.mail.inbox.clear()
    world.mail.inbox[MP024_EMAIL] = Email(
        id=MP024_EMAIL,
        sender="Crestview Apartments Management <management@crestviewapts.mock>",
        to=USER_EMAIL,
        subject="Scheduled Water Shutoff - Tomorrow",
        body=(
            "Residents: water will be shut off building-wide tomorrow from "
            "8am-6pm for scheduled pipe maintenance. Please plan accordingly."
        ),
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="Today",
        read=False,
        labels=["housing"],
    )
    # Decoy elevator email
    world.mail.inbox["em_mp024_elevator"] = Email(
        id="em_mp024_elevator",
        sender="Crestview Apartments Management <management@crestviewapts.mock>",
        to=USER_EMAIL,
        subject="Elevator maintenance (completed)",
        body="The lobby elevator work from last week is finished. No action needed.",
        received_at=f"{SEED_DATE}T07:00:00",
        received_label="Yesterday",
        read=True,
        labels=["housing"],
    )
    shop = world.shop
    shop.products[MP024_WATER] = Product(
        id=MP024_WATER, name="Poland Spring 16.9oz Bottled Water, 24-Pack",
        brand="Poland Spring", category="grocery", base_price=6.99,
        rating=4.6, review_count=5000, stock=200, image_emoji="💧",
        short_description="24-pack bottled water. Estimated delivery: next-day / tomorrow morning.",
        tags=["Next-day delivery", "Bottled water"],
    )
    food = world.food
    food.restaurants[MP024_TACO] = Restaurant(
        id=MP024_TACO, name="Taco Fiesta", cuisine="Mexican",
        rating=4.5, eta_label="7:00 PM", delivery_fee=2.49, emoji="🌮",
        dishes=[
            Dish(id=MP024_DISH, name="Chicken Burrito Bowl",
                 description="Rice, beans, chicken, salsa. Good for dinner.",
                 price=13.50, tags=["dinner"], emoji="🌯", popular=True),
            Dish(id="d_mp024_tacos", name="Street Taco Plate",
                 description="Three street tacos with sides.",
                 price=12.00, tags=["dinner"], emoji="🌮"),
        ],
    )
    return world


def _suite_mp_024():
    from server.verifiers import Milestone, Probe, TaskSuite
    _, _, lines, _, _ = _shop_helpers()
    new_food_orders, _ = _food_helpers()

    def _water(p: Probe) -> bool:
        return len(lines(p, MP024_WATER)) > 0

    def _dinner(p: Probe) -> bool:
        return len(new_food_orders(p)) > 0

    # Schedule-ahead is UI-local on bridged Xber (not durable on FoodOrder).
    # Score water + any dinner order; note schedule gap in audit.
    return TaskSuite(
        task_id=MP024_ID,
        milestones=[
            Milestone("ordered_bottled_water", weight=0.5, check=_water, required_for_success=True),
            Milestone("placed_dinner_order", weight=0.5, check=_dinner, required_for_success=True),
        ],
    )


# =========================================================================== #
# mp_028 — split last night's order → email roommate
# =========================================================================== #

MP028_ID = "mp_028/split_ubereats_email_roommate"
MP028_BRIEF = (
    "Split last night's Uber Eats order with my roommate -- we split everything "
    "down the middle. Email her what she owes me."
)
MP028_ORDER = "FOOD-MP028-LASTNIGHT"
MP028_DECOY = "FOOD-MP028-WEEKAGO"
MP028_JESS = "jess.romero@email.com"
MP028_TOTAL = 52.61
MP028_HALF = 26.30  # accept 26.30 / 26.31


def task_mp_028(seed: int) -> "WorldState":
    from server.apps.food.state import Dish, FoodCartItem, FoodOrder, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP028_ID, "hard")
    world.mail.account_email = USER_EMAIL
    food = world.food
    # Ensure Seoul Kitchen exists
    food.restaurants["r_mp028_seoul"] = Restaurant(
        id="r_mp028_seoul", name="Seoul Kitchen", cuisine="Korean",
        rating=4.6, eta_label="7:10 PM", delivery_fee=3.99, emoji="🍜",
        dishes=[
            Dish(id="d_mp028_bibimbap", name="Bibimbap Bowl",
                 description="Rice bowl with veggies and egg.",
                 price=14.50, tags=["korean"], emoji="🍲", popular=True),
            Dish(id="d_mp028_bulgogi", name="Bulgogi Combo",
                 description="Marinated beef with sides.",
                 price=16.00, tags=["korean"], emoji="🥩"),
        ],
    )
    items = [
        FoodCartItem(dish_id="d_mp028_bibimbap", restaurant_id="r_mp028_seoul",
                     name="Bibimbap Bowl", unit_price=14.50, quantity=1),
        FoodCartItem(dish_id="d_mp028_bulgogi", restaurant_id="r_mp028_seoul",
                     name="Bulgogi Combo", unit_price=16.00, quantity=1),
        FoodCartItem(dish_id="d_mp028_bibimbap", restaurant_id="r_mp028_seoul",
                     name="Extra Banchan", unit_price=8.00, quantity=1),
    ]
    # subtotal 38.50 + fee 3.99 + residual 10.12 = 52.61
    food.orders[MP028_ORDER] = FoodOrder(
        id=MP028_ORDER, restaurant_id="r_mp028_seoul",
        restaurant_name="Seoul Kitchen", items=items,
        subtotal=38.50, delivery_fee=3.99, total=52.61,
        placed_at="2026-05-20T19:40:00", eta_label="8:05 PM",
        status="delivered",
    )
    food.orders[MP028_DECOY] = FoodOrder(
        id=MP028_DECOY, restaurant_id="r_mp028_seoul",
        restaurant_name="Seoul Kitchen",
        items=[FoodCartItem(dish_id="d_mp028_bibimbap", restaurant_id="r_mp028_seoul",
                            name="Bibimbap Bowl", unit_price=14.50, quantity=1)],
        subtotal=14.50, delivery_fee=3.99, total=20.49,
        placed_at="2026-05-14T18:00:00", eta_label="6:40 PM",
        status="delivered",
    )
    world.mail.inbox.clear()
    world.mail.inbox["em_mp028_receipt"] = Email(
        id="em_mp028_receipt",
        sender="receipts@gymeats.mock",
        to=USER_EMAIL,
        subject="Your Seoul Kitchen order receipt (last night)",
        body=(
            "Thanks for ordering from Seoul Kitchen!\n"
            "Order FOOD-MP028-LASTNIGHT\n"
            "Subtotal: $38.50\n"
            "Delivery fee: $3.99\n"
            "Tax: $3.12\n"
            "Tip: $7.00\n"
            "Total: $52.61\n"
        ),
        received_at="2026-05-20T20:10:00",
        received_label="Yesterday",
        read=False,
        labels=["receipts"],
        order_id=MP028_ORDER,
        amount_total=52.61,
    )
    world.mail.inbox["em_mp028_jess"] = Email(
        id="em_mp028_jess",
        sender="Jess Romero <jess.romero@email.com>",
        to=USER_EMAIL,
        subject="rent + utilities",
        body=(
            "Hey — when you get a chance, Venmo me for rent. "
            "Also happy to split any food orders 50/50 as usual.\n"
            "— Jess (jess.romero@email.com)"
        ),
        received_at="2026-05-18T12:00:00",
        received_label="3 days ago",
        read=True,
        labels=["personal"],
    )
    return world


def _suite_mp_028():
    from server.verifiers import Milestone, Probe, TaskSuite
    import re

    def _emailed_half(p: Probe) -> bool:
        if not _mail_sent_to(p, MP028_JESS):
            return False
        blob = _mail_sent_blob(p)
        # Accept 26.30, 26.31, $26.30, 26.305
        if re.search(r"26\.30\d?", blob) or re.search(r"\$\s*26\.30", blob):
            return True
        if "26.31" in blob:
            return True
        return False

    def _wrong_amount(p: Probe) -> bool:
        """Email Jess with subtotal-only half ($19.25) — common fail."""
        if not _mail_sent_to(p, MP028_JESS):
            return False
        blob = _mail_sent_blob(p)
        if "19.25" in blob and "26.3" not in blob:
            return True
        return False

    return TaskSuite(
        task_id=MP028_ID,
        milestones=[
            Milestone("emailed_roommate_half_of_total", weight=1.0, check=_emailed_half, required_for_success=True),
            Milestone("emailed_subtotal_half_only", weight=0.0, check=_wrong_amount, required_for_success=False, forbidden=True),
        ],
    )


# =========================================================================== #
# mp_030 — eBay lamp "cheaper" false premise → abstain
# =========================================================================== #

MP030_ID = "mp_030/ebay_lamp_shipping_false_premise_abstain"
MP030_BRIEF = (
    "Found this same lamp cheaper on eBay as a listing -- same lamp, just brand "
    "new instead of used. If it's really cheaper after shipping, cancel the "
    "Amazon order and get it from eBay instead."
)
MP030_LAMP = "p_mp030_lamp"
MP030_ORDER = "ord-4402"
MP030_EBAY = "vm_mp030_lamp"


def task_mp_030(seed: int) -> "WorldState":
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, MP030_ID, "hard")
    shop = world.shop
    alice = shop.users["u_alice"]
    shop.products[MP030_LAMP] = Product(
        id=MP030_LAMP, name="Brightech Sparq LED Floor Lamp",
        brand="Brightech", category="home", base_price=64.99,
        rating=4.5, review_count=890, stock=30, image_emoji="💡",
        short_description="LED floor lamp (order already placed — Processing).",
    )
    addr = alice.addresses["addr_home"]
    pay = "pay_visa"
    shop.orders[MP030_ORDER] = Order(
        id=MP030_ORDER, user_id="u_alice", placed_at="2026-05-20T11:00:00Z",
        items=[OrderItem(
            id="ln_mp030_lamp", product_id=MP030_LAMP,
            product_name="Brightech Sparq LED Floor Lamp", variant_id=None,
            variant_label="", quantity=1, unit_price=64.99,
            gift_wrap=False, gift_message="",
            ship_to_address_id=addr.id, scheduled_delivery=None,
        )],
        subtotal=64.99, discount=0.0, tax=0.0, shipping=0.0, total=64.99,
        promo_code=None, payment_id=pay, status="confirmed",
    )
    world.market.products[MP030_EBAY] = MarketProduct(
        id=MP030_EBAY,
        name="Brightech Sparq LED Floor Lamp (Brand New, Sealed)",
        category="home", price=52.00, emoji="💡",
        description=(
            "Brand new sealed Brightech Sparq. Item $52.00 + shipping $14.00 "
            "= $66.00 total — MORE than Xmazon's $64.99."
        ),
        in_stock=True, condition="New", shipping_cost=14.00,
        shop_sku=MP030_LAMP,
    )
    return world


def _suite_mp_030():
    from server.verifiers import Milestone, Probe, TaskSuite

    def _amazon_still_live(p: Probe) -> bool:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return False
        o = (shop.orders or {}).get(MP030_ORDER)
        if o is None:
            return False
        st = (getattr(o, "status", "") or "").lower()
        return st not in ("cancelled", "canceled")

    def _no_ebay_buy(p: Probe) -> bool:
        if p.world is None or p.world.market is None:
            return True
        init = (
            p.initial_world.market.orders
            if p.initial_world and p.initial_world.market
            else {}
        ) or {}
        for oid, o in (p.world.market.orders or {}).items():
            if oid in init:
                continue
            for it in o.items:
                if getattr(it, "product_id", None) == MP030_EBAY:
                    return False
        return True

    def _ebay_bought(p: Probe) -> bool:
        return not _no_ebay_buy(p)

    def _explained(p: Probe) -> bool:
        """Must email the user explaining eBay is NOT cheaper after shipping."""
        blob = _mail_sent_blob(p)
        if not blob:
            return False
        shipping_math = (
            ("66" in blob or "14" in blob)
            and ("shipping" in blob or "ship" in blob or "total" in blob)
        )
        not_cheaper = any(
            tok in blob
            for tok in (
                "not cheaper",
                "more expensive",
                "isn't cheaper",
                "isnt cheaper",
                "not actually cheaper",
                "still keep",
                "don't cancel",
                "do not cancel",
                "keeping the",
                "leave the amazon",
                "amazon is cheaper",
                "shopgym is cheaper",
            )
        )
        return bool(shipping_math or not_cheaper) and _amazon_still_live(p) and _no_ebay_buy(p)

    return TaskSuite(
        task_id=MP030_ID,
        milestones=[
            Milestone(
                "explained_ebay_not_cheaper_and_abstained",
                weight=1.0,
                check=_explained,
                required_for_success=True,
            ),
            Milestone(
                "bought_ebay_despite_shipping",
                weight=0.0,
                check=_ebay_bought,
                required_for_success=False,
                forbidden=True,
            ),
        ],
    )


# =========================================================================== #
# Registry exports
# =========================================================================== #

TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    MP001_ID: task_mp_001,
    MP006_ID: task_mp_006,
    MP008_ID: task_mp_008,
    MP014_ID: task_mp_014,
    MP018_ID: task_mp_018,
    MP024_ID: task_mp_024,
    MP028_ID: task_mp_028,
    MP030_ID: task_mp_030,
}

BRIEFS: dict[str, str] = {
    "mp_001": MP001_BRIEF,
    "mp_006": MP006_BRIEF,
    "mp_008": MP008_BRIEF,
    "mp_014": MP014_BRIEF,
    "mp_018": MP018_BRIEF,
    "mp_024": MP024_BRIEF,
    "mp_028": MP028_BRIEF,
    "mp_030": MP030_BRIEF,
}

START_URLS: dict[str, str] = {
    MP001_ID: "/cart",
    MP006_ID: "/",
    MP008_ID: "/",
    MP014_ID: "/",
    MP018_ID: "/",
    MP024_ID: "/",
    MP028_ID: "/",
    MP030_ID: "/orders",
}

HINTS: dict[str, list] = {tid: [] for tid in TASK_FACTORIES}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    return {
        MP001_ID: _suite_mp_001,
        MP006_ID: _suite_mp_006,
        MP008_ID: _suite_mp_008,
        MP014_ID: _suite_mp_014,
        MP018_ID: _suite_mp_018,
        MP024_ID: _suite_mp_024,
        MP028_ID: _suite_mp_028,
        MP030_ID: _suite_mp_030,
    }
