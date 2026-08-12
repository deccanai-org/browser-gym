"""mp_036 / study_group_diet_and_cups — GymEats×ValueMart×ShopMail.

Mechanism: a group email thread carries a dietary note that selects the
correct dinner. That dinner implies hot drinks, so ValueMart cups must be
heat-safe. The best-reviewed cups are cold-drink tumblers (decoy).

No chat hub — dietary surface is a ShopMail group thread (worded as group
email in the brief).

Forbidden: wrong dinner (miss dietary); cold cups with hot dinner.
Gold: dairy-free hot chili + heat-safe cups (best among heat-safe, not
global best reviews).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_036/study_group_diet_and_cups"
BRIEF_KEY = "mp_036"
BRIEF = (
    "Order dinner for tonight's study group, but check if anyone mentioned a "
    "dietary thing in the group email thread first. Also grab some cups from "
    "ValueMart — get the ones with the best reviews that will actually work "
    "for what we're drinking."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T16:30:00"

# Study block so dinner timing is discoverable (not the trap).
STUDY_ID = "ev_mp036_study_group"
STUDY_TITLE = "Study group dinner"
STUDY_START, STUDY_END = "19:00", "21:00"

THREAD_DIET_ID = "em_mp036_diet_note"
THREAD_OK_ID = "em_mp036_no_prefs"
THREAD_SCHED_ID = "em_mp036_when"

# Gold dinner: dairy-free hot chili (implies hot drinks / heat-safe cups)
GOLD_REST = "r_mp036_hearth"
GOLD_DISH = "d_mp036_vegan_chili"
GOLD_DISH_NAME = "Smoky Dairy-Free Chili Bowl"

# Diet traps
TRAP_DAIRY_DISH = "d_mp036_mac_cheese"      # highly rated, has dairy
TRAP_MEAT_DISH = "d_mp036_bbq_ribs"         # not dairy-free vegetarian path
TRAP_COLD_DISH = "d_mp036_poke"             # cold dinner → would need cold cups
DAIRY_REST = "r_mp036_comfort"
POKE_REST = "r_mp036_tide"

# ValueMart cups — reviews explicit; type is the real trap
# Best reviews overall = cold tumblers (decoy for this hot dinner)
COLD_BEST = "vm_mp036_cold_cups_best"
COLD_ALT = "vm_mp036_cold_cups_alt"
# Correct type (heat-safe); best among heat-safe, but worse reviews than cold
HOT_GOLD = "vm_mp036_hot_mugs"
HOT_LOW = "vm_mp036_hot_mugs_low"  # heat-safe but worse reviews than HOT_GOLD


def task_mp_036_study_group_diet_and_cups(seed: int) -> "WorldState":
    """FEASIBLE Food×Mail×ValueMart: dairy-free hot chili + heat-safe cups.

    Seed (today Thu May 21, gym clock 16:30):
      - Calendar: Study group dinner 19:00–21:00
      - Mail group thread: Alex dairy-free → chili + hot cocoa/tea (not iced)
      - Hearth Bowl: Smoky Dairy-Free Chili (GOLD)
      - Comfort Kitchen: Three-Cheese Mac (best rating, dairy trap)
      - Tide Poke: chilled poke (cold trap — wrong drink type pairing)
      - ValueMart: cold tumblers 4.9★ (best reviews, wrong type)
      - ValueMart: ThermoSafe ceramic mugs 4.5★ (correct type, gold)
      - ValueMart: budget hot mugs 3.9★ (correct type, worse reviews)

    Correct: order GOLD_DISH + buy HOT_GOLD cups.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.market.store_name = "ValueMart"
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW
    cal.events.clear()
    cal.events[STUDY_ID] = CalendarEvent(
        id=STUDY_ID,
        title=STUDY_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=STUDY_START,
        end=STUDY_END,
        source="seed",
        description="Study group dinner block.",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[THREAD_SCHED_ID] = Email(
        id=THREAD_SCHED_ID,
        sender="bea@shopgym.com",
        to=USER_EMAIL,
        cc="alex@shopgym.com, jordan@shopgym.com, cy@shopgym.com",
        subject="Re: study group dinner tonight?",
        body=(
            "Can someone order for the study group tonight around 7? I'll "
            "bring notebooks. — Bea"
        ),
        received_at=f"{SEED_DATE}T14:05:00",
        received_label="2:05 PM",
        read=True,
        labels=["team"],
    )
    mail.inbox[THREAD_OK_ID] = Email(
        id=THREAD_OK_ID,
        sender="jordan@shopgym.com",
        to=USER_EMAIL,
        cc="alex@shopgym.com, bea@shopgym.com, cy@shopgym.com",
        subject="Re: study group dinner tonight?",
        body=(
            "I'm flexible on food — whatever works for the group is fine."
        ),
        received_at=f"{SEED_DATE}T14:20:00",
        received_label="2:20 PM",
        read=True,
        labels=["team"],
    )
    mail.inbox[THREAD_DIET_ID] = Email(
        id=THREAD_DIET_ID,
        sender="alex@shopgym.com",
        to=USER_EMAIL,
        cc="bea@shopgym.com, jordan@shopgym.com, cy@shopgym.com",
        subject="Re: study group dinner tonight?",
        body=(
            "Dietary note for whoever's ordering: I'm dairy-free, so please "
            "skip mac and cheese / cream sauces. The Smoky Dairy-Free Chili "
            "from Hearth Bowl is perfect for everyone.\n\n"
            "That chili is a hot dinner — grab cups from ValueMart that fit "
            "what we'll actually be drinking with it (don't just grab whatever "
            "has the flashiest reviews)."
        ),
        received_at=f"{SEED_DATE}T15:10:00",
        received_label="3:10 PM",
        read=False,
        labels=["team", "unread"],
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()

    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name="Hearth Bowl",
        cuisine="Comfort",
        rating=4.5,
        eta_label="6:40 PM",
        delivery_fee=2.49,
        emoji="🍲",
        delivery_time_min=55,
        delivery_time_max=70,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name=GOLD_DISH_NAME,
                description=(
                    "Plant-based chili, no dairy. Served piping hot — pairs "
                    "with cocoa/tea. Hearth Bowl deliveries typically arrive "
                    "around 6:40 PM."
                ),
                price=13.50,
                tags=["vegan", "dairy-free", "hot", "chili"],
                emoji="🌶️",
                popular=True,
            ),
            Dish(
                id="d_mp036_side_cornbread",
                name="Skillet Cornbread",
                description="Side only — contains butter (dairy).",
                price=4.00,
                tags=["side", "contains-dairy"],
                emoji="🌽",
            ),
        ],
    )
    food.restaurants[DAIRY_REST] = Restaurant(
        id=DAIRY_REST,
        name="Comfort Kitchen",
        cuisine="American",
        rating=4.8,
        eta_label="6:35 PM",
        delivery_fee=2.99,
        emoji="🧀",
        delivery_time_min=50,
        delivery_time_max=65,
        dishes=[
            Dish(
                id=TRAP_DAIRY_DISH,
                name="Three-Cheese Mac Bowl",
                description=(
                    "Crowd favorite — CONTAINS DAIRY (cheddar, gouda, cream). "
                    "Comfort Kitchen deliveries typically arrive around 6:35 PM."
                ),
                price=12.75,
                tags=["contains-dairy", "pasta", "popular"],
                emoji="🧀",
                popular=True,
            ),
            Dish(
                id=TRAP_MEAT_DISH,
                name="BBQ Rib Plate",
                description=(
                    "Smoked ribs and slaw. Not the dairy-free chili Alex asked "
                    "for. Arrives around 6:35 PM."
                ),
                price=16.50,
                tags=["meat", "bbq"],
                emoji="🍖",
            ),
        ],
    )
    food.restaurants[POKE_REST] = Restaurant(
        id=POKE_REST,
        name="Tide Poke",
        cuisine="Hawaiian",
        rating=4.7,
        eta_label="6:45 PM",
        delivery_fee=3.49,
        emoji="🐟",
        delivery_time_min=60,
        delivery_time_max=75,
        dishes=[
            Dish(
                id=TRAP_COLD_DISH,
                name="Chilled Ahi Poke Bowl",
                description=(
                    "Cold poke bowl — dairy-free, but this is a chilled dinner "
                    "meant with iced drinks, not the hot chili + cocoa plan. "
                    "Tide Poke deliveries typically arrive around 6:45 PM."
                ),
                price=14.25,
                tags=["dairy-free", "cold", "poke"],
                emoji="🥗",
                popular=True,
            ),
        ],
    )

    market = world.market
    # Clear overlapping cup-like noise if any default seeds exist.
    for pid in list(market.products.keys()):
        name = (market.products[pid].name or "").lower()
        if "cup" in name or "mug" in name or "tumbler" in name:
            market.products.pop(pid, None)

    def _cup(
        pid: str,
        *,
        name: str,
        price: float,
        feedback: float,
        score: int,
        seller: str,
        description: str,
        emoji: str,
    ) -> None:
        market.products[pid] = MarketProduct(
            id=pid,
            name=name,
            category="home",
            price=price,
            emoji=emoji,
            description=description,
            in_stock=True,
            condition="New",
            shipping_cost=0.0,
            brand="CupCo",
            seller_id=f"seller_{pid}",
            seller_username=seller,
            seller_feedback_score=score,
            seller_feedback_rating=feedback,
        )

    _cup(
        COLD_BEST,
        name="CrystalClear Cold Drink Tumblers (set of 6)",
        price=18.99,
        feedback=99.8,
        score=9200,
        seller="SipGear_Official",
        emoji="🧊",
        description=(
            "Bestseller for iced drinks. Product reviews 4.9/5 (2,410 reviews) "
            "— highest-reviewed cups on ValueMart. BPA-free plastic; NOT rated "
            "for hot liquids (warps with cocoa/tea). Free shipping."
        ),
    )
    _cup(
        COLD_ALT,
        name="FrostBite Insulated Cold Tumblers (set of 6)",
        price=22.50,
        feedback=99.4,
        score=5100,
        seller="ColdSip_HQ",
        emoji="🥤",
        description=(
            "Double-wall cold tumblers for iced tea and soda. Reviews 4.8/5 "
            "(1,120 reviews). Keep drinks cold — not for hot cocoa. Free shipping."
        ),
    )
    _cup(
        HOT_GOLD,
        name="ThermoSafe Ceramic Mugs (set of 6)",
        price=24.00,
        feedback=98.2,
        score=3400,
        seller="HearthWare_Co",
        emoji="☕",
        description=(
            "Heat-safe ceramic mugs for coffee, tea, and hot cocoa. Reviews "
            "4.5/5 (890 reviews) — best among heat-safe cup listings on "
            "ValueMart, but lower than CrystalClear's 4.9 cold tumblers. "
            "Free shipping. Oven/microwave safe; designed for hot liquids "
            "served with a hot chili dinner."
        ),
    )
    _cup(
        HOT_LOW,
        name="Budget Heat Mugs (set of 6)",
        price=14.50,
        feedback=94.1,
        score=880,
        seller="BargainKitchen",
        emoji="🍵",
        description=(
            "Basic heat-safe mugs. Reviews only 3.9/5 (210 reviews) — works for "
            "hot drinks but not the best-reviewed heat-safe option. Free shipping."
        ),
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_036_study_group_diet_and_cups,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _food_orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _market_orders(p: Probe) -> list:
        market = getattr(p.world, "market", None) if p.world else None
        if not market:
            return []
        init = {}
        if p.initial_world and getattr(p.initial_world, "market", None):
            init = p.initial_world.market.orders or {}
        return [o for oid, o in (market.orders or {}).items() if oid not in init]

    def _ordered_dish(p: Probe, dish_id: str) -> bool:
        for o in _food_orders(p).values():
            for it in getattr(o, "items", None) or []:
                if getattr(it, "dish_id", None) == dish_id:
                    return True
        return False

    def _bought_cup(p: Probe, pid: str) -> bool:
        for o in _market_orders(p):
            for it in o.items or []:
                if getattr(it, "product_id", None) == pid:
                    return True
        return False

    def _gold_dinner(p: Probe) -> bool:
        return _ordered_dish(p, GOLD_DISH)

    def _gold_cups(p: Probe) -> bool:
        return _bought_cup(p, HOT_GOLD)

    def _success(p: Probe) -> bool:
        return _gold_dinner(p) and _gold_cups(p)

    def _wrong_dinner(p: Probe) -> bool:
        return (
            _ordered_dish(p, TRAP_DAIRY_DISH)
            or _ordered_dish(p, TRAP_MEAT_DISH)
            or _ordered_dish(p, TRAP_COLD_DISH)
        )

    def _cold_cups(p: Probe) -> bool:
        return _bought_cup(p, COLD_BEST) or _bought_cup(p, COLD_ALT)

    def _low_hot_cups(p: Probe) -> bool:
        # Heat-safe but not best-reviewed among heat-safe — incomplete if
        # chosen instead of HOT_GOLD; forbidden only when preferred over gold
        # after ordering dinner (shortcut on reviews within type).
        return _bought_cup(p, HOT_LOW) and not _bought_cup(p, HOT_GOLD)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_dairy_free_chili",
                    weight=0.5,
                    check=_gold_dinner,
                    required_for_success=True,
                ),
                Milestone(
                    "bought_best_heat_safe_cups",
                    weight=0.5,
                    check=_gold_cups,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_wrong_dinner",
                    weight=0.0,
                    check=_wrong_dinner,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "bought_cold_cups_for_hot_drinks",
                    weight=0.0,
                    check=_cold_cups,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "bought_worse_heat_safe_cups",
                    weight=0.0,
                    check=_low_hot_cups,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "full_gold_bundle",
                    weight=0.0,
                    check=_success,
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
