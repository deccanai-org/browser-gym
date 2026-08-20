"""food_003 / team_dinner_named_restaurants — third-restaurant gold.

Mechanism: brief names Burger Barn and Sakura as "usual options" but allows
other places. Mail requires vegan ∩ nut-free; Team Meeting starts 18:30.
BB on-time options fail diet; Sakura's safe roll arrives after the meeting.
Only Leaf & Grain's Sesame-Free Garden Bowl is vegan + nut-free + on time.

Family: ``dietary_named_decoy_third_restaurant``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "food_003/team_dinner_named_restaurants"
BRIEF_KEY = "food_003"
BRIEF = (
    "Order dinner for tonight so it comes by the time of the Team Meeting, "
    "check dietary notes in Mail and the time on my calendar. Burger Barn and "
    "Sakura are the usual options, but other places are fine too."
)

USER_EMAIL = "alice@shopmail.com"
EVENT_ID = "ev_food003_team_meeting"
EVENT_TITLE = "Team Meeting"
# Arrive-by meeting start (visible on Thu week view after Xoogle scroll fix).
EVENT_START, EVENT_END = "18:30", "20:30"
# Mid-afternoon so week-view default scroll + now-line sit near evening hours.
GYM_NOW = "2026-05-21T16:00:00"

MAYA_EMAIL_ID = "em_food003_maya_vegan"
JORDAN_EMAIL_ID = "em_food003_jordan_nuts"
DEV_EMAIL_ID = "em_food003_dev_ok"

# Named decoys (brief "usual options")
VEGAN_NUTS_DISH = "d_f003_vegan_peanut"       # BB on-time vegan, CONTAINS NUTS
CHICKEN_NUTFREE_DISH = "d_f003_chicken_safe"  # BB on-time nut-free, NOT vegan
LATE_SAFE_DISH = "d_f003_vegan_safe"          # Sakura vegan+nut-free, AFTER 18:30

# Gold — third restaurant
GOLD_REST = "r_leaf"
GOLD_REST_NAME = "Leaf & Grain"
GOLD_DISH = "d_f003_garden_bowl"
GOLD_DISH_NAME = "Sesame-Free Garden Bowl"

BURGER_REST = "r_burger"
SUSHI_REST = "r_sushi"
BEAN_REST = "r_bean"


def task_food_003_team_dinner_named_restaurants(seed: int) -> "WorldState":
    """Food×Mail×Calendar: order gold third restaurant; BB/Sakura are traps.

    Seed (today Thu May 21, gym clock 16:00):
      - Calendar: Team Meeting 18:30–20:30 (dinner must arrive by 6:30 PM)
      - Mail Maya: vegan only
      - Mail Jordan: severe nut allergy / nut-free only
      - Mail Dev: no restrictions (decoy)
      - Burger Barn ETA 6:20 PM: vegan peanut bowl (nuts) + nut-free chicken
      - Sakura ETA 6:50 PM: vegan+nut-free roll (too late for 6:30 meeting)
      - Leaf & Grain ETA 6:15 PM: Sesame-Free Garden Bowl (vegan + nut-free) — GOLD
      - Bean There: coffee/bakery only

    Correct: order GOLD_DISH from Leaf & Grain. Forbidden: any BB or Sakura order.
    """
    from server.apps.calendar.state import CalendarEvent, TODAY
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
    cal.events[EVENT_ID] = CalendarEvent(
        id=EVENT_ID,
        title=EVENT_TITLE,
        day=TODAY,
        day_label="Today (Thu May 21)",
        start=EVENT_START,
        end=EVENT_END,
        source="seed",
    )

    m = world.mail
    m.inbox.clear()
    m.inbox[MAYA_EMAIL_ID] = Email(
        id=MAYA_EMAIL_ID,
        sender="maya@shopgym.com",
        to=USER_EMAIL,
        subject="Re: team dinner tonight?",
        body=(
            "I'll be at the Team Meeting tonight — please make sure dinner "
            "is vegan / fully plant-based for me. Thanks!"
        ),
        received_at=f"{SEED_DATE}T10:05:00",
        received_label="10:05 AM",
        read=False,
        labels=["team"],
    )
    m.inbox[JORDAN_EMAIL_ID] = Email(
        id=JORDAN_EMAIL_ID,
        sender="jordan@shopgym.com",
        to=USER_EMAIL,
        subject="Re: team dinner tonight?",
        body=(
            "Quick heads-up for tonight's Team Meeting dinner — I have a "
            "severe nut allergy. Nothing with peanuts or tree nuts, please. "
            "Nut-free only."
        ),
        received_at=f"{SEED_DATE}T10:12:00",
        received_label="10:12 AM",
        read=False,
        labels=["team"],
    )
    m.inbox[DEV_EMAIL_ID] = Email(
        id=DEV_EMAIL_ID,
        sender="dev@shopgym.com",
        to=USER_EMAIL,
        subject="Re: team dinner tonight?",
        body=(
            "I'm good with whatever for the Team Meeting — no dietary "
            "restrictions on my end."
        ),
        received_at=f"{SEED_DATE}T10:18:00",
        received_label="10:18 AM",
        read=False,
        labels=["team"],
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()

    food.restaurants[BURGER_REST] = Restaurant(
        id=BURGER_REST,
        name="Burger Barn",
        cuisine="American",
        rating=4.4,
        eta_label="6:20 PM",
        delivery_fee=2.49,
        emoji="🍔",
        delivery_time_min=65,
        delivery_time_max=80,
        dishes=[
            Dish(
                id=VEGAN_NUTS_DISH,
                name="Thai Peanut Buddha Bowl",
                description=(
                    "100% plant-based grain bowl with Thai peanut sauce — "
                    "CONTAINS PEANUTS. Vegan. Burger Barn deliveries typically "
                    "arrive around 6:20 PM."
                ),
                price=14.50,
                tags=["vegan", "contains-nuts", "bowl"],
                emoji="🥗",
                popular=True,
            ),
            Dish(
                id=CHICKEN_NUTFREE_DISH,
                name="Nut-Free Grilled Chicken Plate",
                description=(
                    "Grilled chicken, steamed veggies, rice — prepared in a "
                    "nut-free kitchen. Not vegetarian. Burger Barn deliveries "
                    "typically arrive around 6:20 PM."
                ),
                price=15.00,
                tags=["nut-free", "chicken", "dinner"],
                emoji="🍗",
                popular=True,
            ),
            Dish(
                id="d_f003_fries",
                name="Crispy Fries",
                description=(
                    "Hand-cut fries, sea salt. Fried in a shared fryer with "
                    "chicken — not vegan, not allergy-safe. Side only."
                ),
                price=4.00,
                tags=["side"],
                emoji="🍟",
            ),
        ],
    )
    food.restaurants[SUSHI_REST] = Restaurant(
        id=SUSHI_REST,
        name="Sakura Sushi",
        cuisine="Japanese",
        rating=4.7,
        eta_label="6:50 PM",  # AFTER Team Meeting 6:30 PM start
        delivery_fee=3.99,
        emoji="🍣",
        delivery_time_min=95,
        delivery_time_max=110,
        dishes=[
            Dish(
                id=LATE_SAFE_DISH,
                name="Avocado Cucumber Roll",
                description=(
                    "Avocado and cucumber — fully plant-based, no fish, "
                    "no nuts. Vegan and nut-free. Note: Sakura deliveries "
                    "typically arrive around 6:50 PM — after a 6:30 PM start."
                ),
                price=12.50,
                tags=["vegan", "nut-free", "sushi"],
                emoji="🥑",
                popular=True,
            ),
            Dish(
                id="d_f003_salmon_roll",
                name="Salmon Avocado Roll",
                description=(
                    "Fresh salmon, avocado, sushi rice. Sakura deliveries "
                    "typically arrive around 6:50 PM."
                ),
                price=12.50,
                tags=["sushi", "fish"],
                emoji="🍣",
            ),
        ],
    )
    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name=GOLD_REST_NAME,
        cuisine="Healthy",
        rating=4.6,
        eta_label="6:15 PM",
        delivery_fee=2.99,
        emoji="🥬",
        delivery_time_min=60,
        delivery_time_max=75,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name=GOLD_DISH_NAME,
                description=(
                    "Roasted vegetables, quinoa, tahini-free herb dressing — "
                    "fully plant-based, no peanuts or tree nuts. Vegan and "
                    "nut-free. Leaf & Grain deliveries typically arrive "
                    "around 6:15 PM."
                ),
                price=13.75,
                tags=["vegan", "nut-free", "bowl"],
                emoji="🥗",
                popular=True,
            ),
            Dish(
                id="d_f003_leaf_cashew",
                name="Cashew Crunch Buddha Bowl",
                description=(
                    "Plant-based bowl with roasted cashews — CONTAINS TREE "
                    "NUTS. Vegan but not allergy-safe. Leaf & Grain "
                    "deliveries typically arrive around 6:15 PM."
                ),
                price=14.25,
                tags=["vegan", "contains-nuts", "bowl"],
                emoji="🥜",
            ),
        ],
    )
    food.restaurants[BEAN_REST] = Restaurant(
        id=BEAN_REST,
        name="Bean There Cafe",
        cuisine="Coffee",
        rating=4.6,
        eta_label="6:10 PM",
        delivery_fee=1.99,
        emoji="☕",
        delivery_time_min=50,
        delivery_time_max=70,
        dishes=[
            Dish(
                id="d_f003_latte",
                name="Oat Milk Latte",
                description=(
                    "Double shot, steamed oat milk. Drink — not dinner. "
                    "Bean There deliveries typically arrive around 6:10 PM."
                ),
                price=5.25,
                tags=["coffee", "drink"],
                emoji="🥛",
            ),
            Dish(
                id="d_f003_croissant",
                name="Butter Croissant",
                description=(
                    "Flaky pastry with real butter. Bakery — not a team dinner. "
                    "Bean There deliveries typically arrive around 6:10 PM."
                ),
                price=3.75,
                tags=["bakery"],
                emoji="🥐",
            ),
        ],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_food_003_team_dinner_named_restaurants,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _order_has_dish(p: Probe, dish_id: str) -> bool:
        for o in _orders(p).values():
            for it in getattr(o, "items", None) or []:
                if getattr(it, "dish_id", None) == dish_id:
                    return True
        return False

    def _order_from_rest(p: Probe, rest_id: str) -> bool:
        for o in _orders(p).values():
            if getattr(o, "restaurant_id", None) == rest_id:
                return True
            # Bridged snapshots sometimes only keep the display name.
            name = (getattr(o, "restaurant_name", None) or "").lower()
            if rest_id == BURGER_REST and "burger barn" in name:
                return True
            if rest_id == SUSHI_REST and "sakura" in name:
                return True
        return False

    def _engaged(p: Probe) -> bool:
        food = getattr(p.world, "food", None) if p.world else None
        touched_cart = bool(food and (food.cart.items or food.cart.restaurant_id))
        mail = getattr(p.world, "mail", None) if p.world else None
        read_dietary = False
        if mail:
            for eid in (MAYA_EMAIL_ID, JORDAN_EMAIL_ID):
                e = (mail.inbox or {}).get(eid)
                if e is not None and getattr(e, "read", False):
                    read_dietary = True
                    break
        sent = list(getattr(mail, "sent", None).values()) if mail else []
        return touched_cart or read_dietary or len(_orders(p)) > 0 or len(sent) > 0

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "engaged_mail_or_food",
                    weight=0.0,
                    check=_engaged,
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_gold_garden_bowl",
                    weight=1.0,
                    check=lambda p: _order_has_dish(p, GOLD_DISH),
                    required_for_success=True,
                ),
                Milestone(
                    "ordered_burger_barn",
                    weight=0.0,
                    check=lambda p: _order_from_rest(p, BURGER_REST),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_sakura",
                    weight=0.0,
                    check=lambda p: _order_from_rest(p, SUSHI_REST),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_vegan_with_nuts",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, VEGAN_NUTS_DISH)
                    or _order_has_dish(p, "d_f003_leaf_cashew"),
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_chicken_nutfree",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, CHICKEN_NUTFREE_DISH),
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_late_safe_roll",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, LATE_SAFE_DISH),
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
