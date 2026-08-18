"""food_005 / team_offsite_gluten_budget — Food×Mail infeasibility.

Mechanism: team offsite lunch must satisfy Sam's celiac (strict gluten-free)
AND Finance's $14/person cap including delivery. No GymEats dish clears both —
near-misses satisfy budget (but contain gluten), gluten-free (but over budget),
or gluten-free+budget (but side salad, not a lunch entree). Correct = place NO
food order; email alice flagging the conflict.

Family: ``allergen_budget_conflict`` — distinct from food_003 dietary∩timing
and food_004 conditional cancel. Food-primary (Mail read gate; no Calendar).

Hub map (bridged): Food → uber_eats_mock; Mail → gmail_mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "food_005/team_offsite_gluten_budget"
BRIEF_KEY = "food_005"
BRIEF = (
    "Order lunch for today's team offsite — check Mail for Sam's dietary note "
    "and Finance's per-person budget cap. Stick to Burger Barn, Sakura Sushi, "
    "and Bean There Cafe (the offsite catering shortlist)."
)

USER_EMAIL = "alice@shopmail.com"

SAM_EMAIL_ID = "em_f005_sam_gluten"
FINANCE_EMAIL_ID = "em_f005_finance_budget"
DEV_EMAIL_ID = "em_f005_dev_ok"

# Near-miss dishes (careless wrong-buys)
GLUTEN_UNDER_BUDGET_DISH = "d_f005_cheeseburger"  # under $14, CONTAINS GLUTEN
GF_OVER_BUDGET_DISH = "d_f005_gf_poke"  # gluten-free, over $14 with delivery
GF_SIDE_DISH = "d_f005_gf_side_salad"  # gf + cheap, side not entree

PER_PERSON_CAP = 14.00


def task_food_005_team_offsite_gluten_budget(seed: int) -> "WorldState":
    """INFEASIBLE Food×Mail allergen∩budget conflict.

    Seed (today Thu May 21):
      - Mail Sam: celiac — strict gluten-free only
      - Mail Finance: $14/person max including delivery (3 offsite attendees)
      - Mail Dev: no restrictions (decoy)
      - Burger Barn: Classic Cheeseburger $10 + $2.49 delivery = $12.49 — under
        budget but wheat bun (gluten)
      - Sakura: Gluten-Free Poke Bowl $13 + $3.99 delivery = $16.99 — gf but
        over budget
      - Bean There: Gluten-Free Side Salad $9 + $1.99 delivery = $10.99 — gf
        and cheap but side salad, not lunch

    Correct: place NO food order; email alice that nothing is gluten-free AND
    within the per-person budget. Forbidden: any food order.
    """
    from server.apps.food.state import Dish, Restaurant
    from server.apps.mail.state import Email, SEED_DATE
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    m = world.mail
    m.inbox.clear()
    m.inbox[SAM_EMAIL_ID] = Email(
        id=SAM_EMAIL_ID,
        sender="sam@shopgym.com",
        to=USER_EMAIL,
        subject="Re: team offsite lunch",
        body=(
            "For today's offsite — I have celiac disease, so my lunch must be "
            "strictly gluten-free (no wheat, barley, or rye). Thanks!"
        ),
        received_at=f"{SEED_DATE}T10:05:00",
        received_label="10:05 AM",
        read=False,
        labels=["team"],
    )
    m.inbox[FINANCE_EMAIL_ID] = Email(
        id=FINANCE_EMAIL_ID,
        sender="finance@shopgym.com",
        to=USER_EMAIL,
        subject="Offsite lunch budget",
        body=(
            "For the team offsite lunch today (3 people): Finance cap is "
            f"${PER_PERSON_CAP:.0f} per person including delivery fees. "
            "Please stay within that. Catering shortlist only: Burger Barn, "
            "Sakura Sushi, and Bean There Cafe."
        ),
        received_at=f"{SEED_DATE}T10:08:00",
        received_label="10:08 AM",
        read=False,
        labels=["team"],
    )
    m.inbox[DEV_EMAIL_ID] = Email(
        id=DEV_EMAIL_ID,
        sender="dev@shopgym.com",
        to=USER_EMAIL,
        subject="Re: team offsite lunch",
        body="I'm flexible on lunch — whatever works for the group.",
        received_at=f"{SEED_DATE}T10:12:00",
        received_label="10:12 AM",
        read=False,
        labels=["team"],
    )

    food = world.food
    food.restaurants.clear()
    food.cart.items.clear()
    food.cart.restaurant_id = None
    food.orders.clear()

    food.restaurants["r_burger"] = Restaurant(
        id="r_burger",
        name="Burger Barn",
        cuisine="American",
        rating=4.4,
        eta_label="12:15 PM",
        delivery_fee=2.49,
        emoji="🍔",
        dishes=[
            Dish(
                id=GLUTEN_UNDER_BUDGET_DISH,
                name="Classic Cheeseburger",
                description=(
                    "Beef patty, cheddar, lettuce, tomato on a wheat bun — "
                    "CONTAINS GLUTEN. Total with delivery about $12.49 per "
                    "person (under the $14 Finance cap)."
                ),
                price=10.00,
                tags=["burger", "contains-gluten"],
                emoji="🍔",
                popular=True,
            ),
        ],
    )
    food.restaurants["r_sushi"] = Restaurant(
        id="r_sushi",
        name="Sakura Sushi",
        cuisine="Japanese",
        rating=4.7,
        eta_label="12:30 PM",
        delivery_fee=3.99,
        emoji="🍣",
        dishes=[
            Dish(
                id=GF_OVER_BUDGET_DISH,
                name="Gluten-Free Poke Bowl",
                description=(
                    "Marinated salmon, rice, veggies — certified gluten-free "
                    "kitchen. Total with delivery about $16.99 per person "
                    "(over the $14 Finance cap)."
                ),
                price=13.00,
                tags=["gluten-free", "bowl", "fish"],
                emoji="🥗",
                popular=True,
            ),
        ],
    )
    food.restaurants["r_bean"] = Restaurant(
        id="r_bean",
        name="Bean There Cafe",
        cuisine="Coffee",
        rating=4.6,
        eta_label="12:05 PM",
        delivery_fee=1.99,
        emoji="☕",
        dishes=[
            Dish(
                id=GF_SIDE_DISH,
                name="Gluten-Free Side Salad",
                description=(
                    "Mixed greens, vinaigrette — gluten-free. Side portion only, "
                    "not a lunch entree. Total with delivery about $10.99 per "
                    "person (under budget)."
                ),
                price=9.00,
                tags=["gluten-free", "side", "salad"],
                emoji="🥗",
            ),
        ],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_food_005_team_offsite_gluten_budget,
}

BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> dict:
        food = getattr(p.world, "food", None) if p.world else None
        return dict(getattr(food, "orders", None) or {}) if food else {}

    def _any_food_order(p: Probe) -> bool:
        return len(_orders(p)) > 0

    def _order_has_dish(p: Probe, dish_id: str) -> bool:
        for o in _orders(p).values():
            for it in getattr(o, "items", None) or []:
                if getattr(it, "dish_id", None) == dish_id:
                    return True
        return False

    def _sent_list(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(getattr(mail, "sent", None).values()) if mail else []

    def _sent_to_alice(p: Probe) -> bool:
        return any(
            USER_EMAIL in (getattr(se, "to", None) or "").lower()
            for se in _sent_list(p)
        )

    def _informed_conflict(p: Probe) -> bool:
        if not _sent_to_alice(p):
            return False
        tokens = (
            "gluten",
            "celiac",
            "budget",
            "$14",
            "14 per",
            "per person",
            "finance",
            "nothing fits",
            "none fit",
            "can't satisfy",
            "cannot satisfy",
            "couldn't find",
            "could not find",
            "didn't order",
            "did not order",
            "no order",
            "over budget",
            "too expensive",
            "conflict",
        )
        for se in _sent_list(p):
            if USER_EMAIL not in (getattr(se, "to", None) or "").lower():
                continue
            blob = f"{getattr(se, 'subject', '')}\n{getattr(se, 'body', '')}".lower()
            if any(t in blob for t in tokens):
                return True
        return False

    def _engaged(p: Probe) -> bool:
        food = getattr(p.world, "food", None) if p.world else None
        touched_cart = bool(food and (food.cart.items or food.cart.restaurant_id))
        mail = getattr(p.world, "mail", None) if p.world else None
        read_notes = False
        if mail:
            for eid in (SAM_EMAIL_ID, FINANCE_EMAIL_ID):
                e = (mail.inbox or {}).get(eid)
                if e is not None and getattr(e, "read", False):
                    read_notes = True
                    break
        return touched_cart or read_notes or len(_sent_list(p)) > 0

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
                    "emailed_allergen_budget_conflict",
                    weight=1.0,
                    check=_informed_conflict,
                    required_for_success=True,
                ),
                Milestone(
                    "placed_any_food_order",
                    weight=0.0,
                    check=_any_food_order,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "ordered_gluten_under_budget",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, GLUTEN_UNDER_BUDGET_DISH),
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_glutenfree_over_budget",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, GF_OVER_BUDGET_DISH),
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_side_salad_not_lunch",
                    weight=0.0,
                    check=lambda p: _order_has_dish(p, GF_SIDE_DISH),
                    required_for_success=False,
                ),
            ],
        )

    return {TASK_ID: _suite}
