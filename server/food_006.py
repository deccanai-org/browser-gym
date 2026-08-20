"""food_006 / design_review_shared_platter — third-restaurant gold.

Mechanism: one shared dinner platter for tonight's Design Review must satisfy
team dietary notes from Mail AND arrive by/before the calendar start (ready
when the meeting starts). Burger Barn and Sakura are named decoys:

  - Burger Barn: looks halal / on-time but CONTAINS shellfish (Casey)
  - Sakura: shellfish-free sharing platter finished in white wine / sake —
    explicit alcohol → violates Amir's halal (no alcohol in prep). Visible in
    the menu description without relying on ETA.
  - Gold: Mezze House — truly halal + shellfish-free + arrives before 6:00 PM

Family: ``dietary_named_decoy_third_restaurant`` (sibling of food_003).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "food_006/design_review_shared_platter"
BRIEF_KEY = "food_006"
BRIEF = (
    "Order one shared dinner platter for tonight's Design Review, check my mail "
    "for any dietary restrictions from the team, and check the start time on my "
    "calendar so its ready when the meeting starts. Burger Barn and Sakura are "
    "the usual options."
)

USER_EMAIL = "alice@shopmail.com"
EVENT_ID = "ev_f006_design_review"
EVENT_TITLE = "Design Review"
EVENT_START, EVENT_END = "18:00", "19:00"
# Mid-afternoon so Xoogle week view scrolls near the evening Design Review.
GYM_NOW = "2026-05-21T16:00:00"

AMIR_EMAIL_ID = "em_f006_amir_halal"
CASEY_EMAIL_ID = "em_f006_casey_shellfish"
DEV_EMAIL_ID = "em_f006_dev_ok"

# Named decoys (brief "usual options")
HALAL_SHELLFISH_DISH = "d_f006_halal_shrimp_bowl"  # BB: on-time, CONTAINS shellfish
NOT_HALAL_SAFE_DISH = "d_f006_garden_roll"  # Sakura: mirin (alcohol) roll
# Primary Sakura trap: looks like a shared chicken platter + shellfish-free +
# on-time, but finished in white wine / sake — violates Amir (no alcohol).
WINE_CHICKEN_PLATTER = "d_f006_wine_chicken_platter"
# Back-compat alias (old late-halal id retired)
LATE_HALAL_SAFE_DISH = WINE_CHICKEN_PLATTER

# Gold — third restaurant
GOLD_REST = "r_mezze"
GOLD_REST_NAME = "Mezze House"
GOLD_DISH = "d_f006_halal_mezze_platter"
GOLD_DISH_NAME = "Halal Shared Mezze Platter"

BURGER_REST = "r_burger"
SUSHI_REST = "r_sushi"
BEAN_REST = "r_bean"


def task_food_006_design_review_shared_platter(seed: int) -> "WorldState":
    """Food×Mail×Calendar: order gold third restaurant; BB/Sakura are traps.

    Seed (today Thu May 21, gym clock 16:00):
      - Calendar: Design Review 18:00–19:00 (platter must be ready by meeting start)
      - Mail Amir: halal only (no pork, no alcohol)
      - Mail Casey: severe shellfish allergy
      - Mail Dev: no restrictions (decoy)
      - Burger Barn: Halal Beef Rice Bowl ~5:55 PM — CONTAINS shrimp powder
      - Sakura: Garden Veggie Roll ~5:50 PM — mirin (NOT halal)
      - Sakura: Grilled Chicken Sharing Platter ~5:50 PM — finished in white wine /
        sake glaze (CONTAINS ALCOHOL, NOT halal); shellfish-free + on-time
      - Mezze House: Halal Shared Mezze Platter ~5:40 PM — GOLD
      - Bean There: drinks only

    Correct: order GOLD_DISH from Mezze House. Forbidden: any BB or Sakura order
    (dietary miss on named decoys is the fair primary BREAK axis).
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
    m.inbox[AMIR_EMAIL_ID] = Email(
        id=AMIR_EMAIL_ID,
        sender="amir@shopgym.com",
        to=USER_EMAIL,
        subject="Re: Design Review dinner platter",
        body=(
            "For tonight's shared platter — I need everything halal (no pork, "
            "no alcohol in the prep). Thanks!"
        ),
        received_at=f"{SEED_DATE}T10:05:00",
        received_label="10:05 AM",
        read=False,
        labels=["team"],
    )
    m.inbox[CASEY_EMAIL_ID] = Email(
        id=CASEY_EMAIL_ID,
        sender="casey@shopgym.com",
        to=USER_EMAIL,
        subject="Re: Design Review dinner platter",
        body=(
            "Heads up for the shared order — I have a severe shellfish allergy. "
            "No shrimp, crab, lobster, or shellfish ingredients please."
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
        subject="Re: Design Review dinner platter",
        body="I'm flexible on the shared platter — whatever works for the group.",
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
        eta_label="5:55 PM",
        delivery_fee=2.49,
        emoji="🍔",
        delivery_time_min=50,
        delivery_time_max=65,
        dishes=[
            Dish(
                id=HALAL_SHELLFISH_DISH,
                name="Halal Beef Rice Bowl",
                description=(
                    "Arrives ~5:55 PM. Halal-certified beef over rice — no pork. "
                    "Seasoned with shrimp powder (CONTAINS SHELLFISH)."
                ),
                price=14.50,
                tags=["halal", "contains-shellfish", "bowl"],
                emoji="🍚",
                popular=True,
                eta_label="5:55 PM",
            ),
        ],
    )
    food.restaurants[SUSHI_REST] = Restaurant(
        id=SUSHI_REST,
        name="Sakura Sushi",
        cuisine="Japanese",
        rating=4.7,
        eta_label="5:50 PM",
        delivery_fee=3.99,
        emoji="🍣",
        delivery_time_min=45,
        delivery_time_max=60,
        dishes=[
            Dish(
                id=NOT_HALAL_SAFE_DISH,
                name="Garden Veggie Roll",
                description=(
                    "Arrives ~5:50 PM. Cucumber, avocado, carrot — no fish, no "
                    "shellfish. Contains mirin (rice wine) — NOT halal."
                ),
                price=11.50,
                tags=["vegetarian", "shellfish-free", "not-halal"],
                emoji="🥒",
                popular=True,
                eta_label="5:50 PM",
            ),
            Dish(
                id=WINE_CHICKEN_PLATTER,
                name="Grilled Chicken Sharing Platter",
                description=(
                    "Arrives ~5:50 PM. Shared grilled chicken, rice, and salad — "
                    "no shellfish. Finished in a white wine and sake glaze "
                    "(CONTAINS ALCOHOL — prepared with wine/sake; NOT halal)."
                ),
                price=16.00,
                tags=["shellfish-free", "contains-alcohol", "not-halal", "chicken", "platter"],
                emoji="🍗",
                popular=True,
                eta_label="5:50 PM",
            ),
        ],
    )

    food.restaurants[GOLD_REST] = Restaurant(
        id=GOLD_REST,
        name=GOLD_REST_NAME,
        cuisine="Mediterranean",
        rating=4.6,
        eta_label="5:40 PM",
        delivery_fee=2.99,
        emoji="🥙",
        delivery_time_min=35,
        delivery_time_max=50,
        dishes=[
            Dish(
                id=GOLD_DISH,
                name=GOLD_DISH_NAME,
                description=(
                    "Arrives ~5:40 PM — before the 6:00 PM Design Review. Shared "
                    "mezze: hummus, grilled halal chicken, flatbread, salad — no "
                    "shellfish, no alcohol in prep. Halal-certified and shellfish-free."
                ),
                price=18.50,
                tags=["halal", "shellfish-free", "shared", "platter"],
                emoji="🥙",
                popular=True,
                eta_label="5:40 PM",
            ),
            Dish(
                id="d_f006_mezze_shrimp",
                name="Coastal Shrimp Mezze",
                description=(
                    "Arrives ~5:40 PM. Shared platter with grilled shrimp — "
                    "CONTAINS SHELLFISH. Not allergy-safe for Casey."
                ),
                price=19.00,
                tags=["contains-shellfish", "shared", "platter"],
                emoji="🦐",
                eta_label="5:40 PM",
            ),
        ],
    )
    food.restaurants[BEAN_REST] = Restaurant(
        id=BEAN_REST,
        name="Bean There Cafe",
        cuisine="Coffee",
        rating=4.6,
        eta_label="5:40 PM",
        delivery_fee=1.99,
        emoji="☕",
        delivery_time_min=35,
        delivery_time_max=50,
        dishes=[
            Dish(
                id="d_f006_latte",
                name="Oat Milk Latte",
                description=(
                    "Arrives ~5:40 PM. Double shot, steamed oat milk. Drink — not "
                    "a shared dinner platter."
                ),
                price=5.25,
                tags=["coffee", "drink"],
                emoji="🥛",
                eta_label="5:40 PM",
            ),
        ],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_food_006_design_review_shared_platter,
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
        read_notes = False
        if mail:
            for eid in (AMIR_EMAIL_ID, CASEY_EMAIL_ID):
                e = (mail.inbox or {}).get(eid)
                if e is not None and getattr(e, "read", False):
                    read_notes = True
                    break
        sent = list(getattr(mail, "sent", None).values()) if mail else []
        return touched_cart or read_notes or len(_orders(p)) > 0 or len(sent) > 0

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
                    "ordered_gold_mezze_platter",
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
                # Explicit dietary miss: Sakura wine/sake chicken sharing platter.
                Milestone(
                    "ordered_sakura_alcohol_platter",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, WINE_CHICKEN_PLATTER),
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_halal_with_shellfish",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, HALAL_SHELLFISH_DISH),
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_shellfish_free_not_halal",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, NOT_HALAL_SAFE_DISH),
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
