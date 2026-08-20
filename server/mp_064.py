"""mp_064 / split_delivery_two_recipients_one_cart — Xmazon×Xmail.

Extended: three cart items. Brother email (vague steel-bottle description),
friend email (cheapest leftover), self by elimination. Per-person spend cap
from an earlier message. Route each item to the right saved address.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_064/split_delivery_two_recipients_one_cart"
BRIEF_KEY = "mp_064"
# Minimal brief tweak: "what's in my cart" (three items) — still goal-only.
BRIEF = (
    "Grab what's in my cart, one's for me and one's for my brother, get them "
    "where they need to go."
)

USER_EMAIL = "alice@shopmail.com"

BOTTLE = "p_mp064_steel_bottle"       # brother — "steel bottle thing"
BOTTLE_PRICE = 28.00
ORGANIZER = "p_mp064_desk_organizer"  # self — remaining after friend takes cheapest
ORGANIZER_PRICE = 22.00
MOUSE = "p_mp064_wireless_mouse"     # friend — cheapest leftover
MOUSE_PRICE = 18.00

PER_PERSON_CAP = 30.00

ADDR_HOME = "addr_home"
ADDR_BROTHER = "addr_brother"
ADDR_FRIEND = "addr_friend"

EM_BROTHER = "em_mp064_brother"
EM_FRIEND = "em_mp064_friend"
EM_CAP = "em_mp064_cap"


def task_mp_064_split_delivery_two_recipients_one_cart(seed: int) -> "WorldState":
    """FEASIBLE Shop×Mail: three-way split ship under per-person cap."""
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Address, CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.addresses[ADDR_BROTHER] = Address(
        id=ADDR_BROTHER, label="Brother", full_name="Ben Anderson",
        line1="14 Cedar Lane", line2="", city="Hoboken", state="NJ",
        zip="07030", is_default=False,
    )
    alice.addresses[ADDR_FRIEND] = Address(
        id=ADDR_FRIEND, label="Friend — Riley", full_name="Riley Chen",
        line1="88 Grove Street", line2="Apt 4B", city="Jersey City",
        state="NJ", zip="07302", is_default=False,
    )

    shop.products.clear()
    shop.orders.clear()
    shop.products[BOTTLE] = Product(
        id=BOTTLE, name="HydroSteel Insulated Bottle 32oz",
        brand="HydroSteel", category="outdoors", base_price=BOTTLE_PRICE,
        rating=4.7, review_count=1500, stock=40, image_emoji="🍾",
        short_description="Double-wall steel bottle — keeps drinks cold.",
        tags=["bottle", "steel", "insulated"],
    )
    shop.products[ORGANIZER] = Product(
        id=ORGANIZER, name="Bamboo Desk Organizer Tray",
        brand="DeskNest", category="home", base_price=ORGANIZER_PRICE,
        rating=4.5, review_count=640, stock=35, image_emoji="🗂️",
        short_description="Desktop organizer tray for pens and notes.",
        tags=["desk", "organizer"],
    )
    shop.products[MOUSE] = Product(
        id=MOUSE, name="LiteClick Wireless Mouse",
        brand="LiteClick", category="electronics", base_price=MOUSE_PRICE,
        rating=4.3, review_count=2200, stock=50, image_emoji="🖱️",
        short_description="Basic wireless mouse — cheapest item in the cart.",
        tags=["mouse", "wireless"],
    )

    shop.cart.items = [
        CartItem(id="ci_mp064_bottle", product_id=BOTTLE, variant_id=None,
                 quantity=1, ship_to_address_id=None),
        CartItem(id="ci_mp064_org", product_id=ORGANIZER, variant_id=None,
                 quantity=1, ship_to_address_id=None),
        CartItem(id="ci_mp064_mouse", product_id=MOUSE, variant_id=None,
                 quantity=1, ship_to_address_id=None),
    ]

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[EM_BROTHER] = Email(
        id=EM_BROTHER,
        sender="ben.anderson@email.com",
        to=USER_EMAIL,
        subject="that thing you mentioned",
        body=(
            "hey — whenever you get around to ordering stuff, can you send me "
            "that steel bottle thing you were talking about? the insulated one. "
            "my address should still be on your account from last year.\n\n"
            "— ben"
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=False,
        labels=["personal", "unread"],
    )
    mail.inbox[EM_FRIEND] = Email(
        id=EM_FRIEND,
        sender="riley.chen@email.com",
        to=USER_EMAIL,
        subject="if you're ordering anyway",
        body=(
            "yo if you've got a cart going just get me whatever's cheapest of "
            "what's left over, nothing fancy. my place is saved under Friend.\n\n"
            "thx\nriley"
        ),
        received_at="2026-05-20T18:20:00",
        received_label="May 20",
        read=False,
        labels=["personal", "unread"],
    )
    mail.inbox[EM_CAP] = Email(
        id=EM_CAP,
        sender="alice@shopmail.com",
        to=USER_EMAIL,
        subject="note to self — gift budget",
        body=(
            "reminder: keep each person's stuff under $30 so this doesn't get "
            "weird. per-person cap, not combined."
        ),
        received_at="2026-05-18T21:00:00",
        received_label="May 18",
        read=False,
        labels=["personal"],
    )
    mail.inbox["em_mp064_noise"] = Email(
        id="em_mp064_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Free shipping over $50",
        body="Unrelated promo.",
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_064_split_delivery_two_recipients_one_cart,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/cart"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    ROUTE = {
        BOTTLE: ADDR_BROTHER,
        MOUSE: ADDR_FRIEND,
        ORGANIZER: ADDR_HOME,
    }
    PRICES = {BOTTLE: BOTTLE_PRICE, MOUSE: MOUSE_PRICE, ORGANIZER: ORGANIZER_PRICE}

    def _new_orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if shop is None:
            return []
        init = set()
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = set((p.initial_world.shop.orders or {}) or {})
        return [
            o for oid, o in (shop.orders or {}).items()
            if oid not in init and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _lines(p: Probe) -> list:
        return [it for o in _new_orders(p) for it in (o.items or [])]

    def _line(p: Probe, pid: str):
        for it in _lines(p):
            if getattr(it, "product_id", "") == pid:
                return it
        return None

    def _mail_read(p: Probe, eid: str) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(eid)
        return bool(e and getattr(e, "read", False))

    def _matched_brother(p: Probe) -> bool:
        # Read brother email + bottle routed to brother (or at least present)
        it = _line(p, BOTTLE)
        return _mail_read(p, EM_BROTHER) and it is not None

    def _matched_friend(p: Probe) -> bool:
        it = _line(p, MOUSE)
        return _mail_read(p, EM_FRIEND) and it is not None

    def _identified_self(p: Probe) -> bool:
        return _line(p, ORGANIZER) is not None

    def _routed_brother(p: Probe) -> bool:
        it = _line(p, BOTTLE)
        return bool(it and getattr(it, "ship_to_address_id", None) == ADDR_BROTHER)

    def _routed_friend(p: Probe) -> bool:
        it = _line(p, MOUSE)
        return bool(it and getattr(it, "ship_to_address_id", None) == ADDR_FRIEND)

    def _kept_own_home(p: Probe) -> bool:
        it = _line(p, ORGANIZER)
        return bool(it and getattr(it, "ship_to_address_id", None) == ADDR_HOME)

    def _all_under_cap(p: Probe) -> bool:
        lines = _lines(p)
        if len(lines) < 3:
            return False
        # Per destination total ≤ cap
        by_addr: dict[str, float] = {}
        for it in lines:
            addr = getattr(it, "ship_to_address_id", "") or ""
            price = float(getattr(it, "unit_price", 0) or 0) * int(
                getattr(it, "quantity", 1) or 1
            )
            by_addr[addr] = by_addr.get(addr, 0.0) + price
        if not by_addr:
            return False
        return all(v <= PER_PERSON_CAP + 1e-6 for v in by_addr.values())

    def _misrouted(p: Probe) -> bool:
        for pid, want in ROUTE.items():
            it = _line(p, pid)
            if it is None:
                continue
            got = getattr(it, "ship_to_address_id", None)
            if got and got != want:
                return True
        return False

    def _over_cap(p: Probe) -> bool:
        lines = _lines(p)
        by_addr: dict[str, float] = {}
        for it in lines:
            addr = getattr(it, "ship_to_address_id", "") or ""
            price = float(getattr(it, "unit_price", 0) or 0) * int(
                getattr(it, "quantity", 1) or 1
            )
            by_addr[addr] = by_addr.get(addr, 0.0) + price
        return any(v > PER_PERSON_CAP + 1e-6 for v in by_addr.values())

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("matched_brothers_item_by_description", weight=0.15,
                          check=_matched_brother, required_for_success=True),
                Milestone("matched_friends_item_by_elimination", weight=0.2,
                          check=_matched_friend, required_for_success=True),
                Milestone("identified_remaining_item_for_self", weight=0.15,
                          check=_identified_self, required_for_success=True),
                Milestone("routed_brothers_item_correctly", weight=0.15,
                          check=_routed_brother, required_for_success=True),
                Milestone("routed_friends_item_correctly", weight=0.15,
                          check=_routed_friend, required_for_success=True),
                Milestone("kept_own_item_home", weight=0.1,
                          check=_kept_own_home, required_for_success=True),
                Milestone("all_items_under_per_person_cap", weight=0.1,
                          check=_all_under_cap, required_for_success=True),
                Milestone("misrouted_any_item", weight=0.0,
                          check=_misrouted, required_for_success=False,
                          forbidden=True),
                Milestone("any_item_over_cap", weight=0.0,
                          check=_over_cap, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
