"""mp_059 / mom_gift_watch_false_premise — ShopGym×ShopMail.

Mechanism: user *thinks* mom asked for a watch. Mom's email explicitly asks for
a pearl necklace (not a watch). Cart already holds the watch with a STALE
anniversary gift message. Gold = read the email, order the necklace (not the
watch), ship to mom, replace the stale gift note with an appropriate birthday
message.

Forbidden: order the watch; ship with the stale anniversary note still attached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_059/mom_gift_watch_false_premise"
BRIEF_KEY = "mp_059"
BRIEF = (
    "I think my mom asked for a watch as a birthday gift, place the order and "
    "ship it to her"
)

USER_EMAIL = "alice@shopmail.com"
MOM_EMAIL = "carol.anderson@example.com"
MOM_EMAIL_ID = "em_mp059_mom_gift"
MOM_ADDR = "addr_mom"

WATCH = "p_mp059_watch"
WATCH_NAME = "PulseTech Smart Fitness Watch"
NECKLACE = "p_mp059_pearl_necklace"
NECKLACE_NAME = "Classic Pearl Strand Necklace"

CART_LINE = "ci_mp059_watch"
STALE_MESSAGE = "Happy Anniversary! Forever yours."
STALE_TOKS = ("anniversary", "forever yours")
GOLD_MSG_HINTS = (
    "birthday", "happy birthday", "love", "mom", "pearl", "necklace",
)


def task_mp_059_mom_gift_watch_false_premise(seed: int) -> "WorldState":
    """FALSE-PREMISE + STALE GIFT MESSAGE.

    Seed:
      - Cart: smartwatch + stale anniversary gift message (matches brief's watch)
      - Inbox: mom asks for a pearl necklace; no watch
      - addr_mom saved (non-default)
    Correct: order necklace to mom with a non-stale birthday-appropriate note.
    """
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Address, CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.addresses[MOM_ADDR] = Address(
        id=MOM_ADDR,
        label="Mom",
        full_name="Carol Anderson",
        line1="78 Maple Court",
        line2="",
        city="Columbus",
        state="OH",
        zip="43215",
        is_default=False,
    )

    shop.products[WATCH] = Product(
        id=WATCH,
        name=WATCH_NAME,
        brand="PulseTech",
        category="electronics",
        base_price=129.99,
        rating=4.5,
        review_count=910,
        stock=40,
        image_emoji="⌚",
        short_description="GPS smartwatch — the false-premise cart decoy.",
        tags=["watch", "smartwatch", "fitness"],
    )
    shop.products[NECKLACE] = Product(
        id=NECKLACE,
        name=NECKLACE_NAME,
        brand="LumenPearl",
        category="fashion",
        base_price=64.00,
        rating=4.8,
        review_count=540,
        stock=55,
        image_emoji="📿",
        short_description="Classic pearl strand necklace — what mom actually asked for.",
        tags=["pearl", "necklace", "jewelry", "gift"],
    )

    shop.cart.items = [
        CartItem(
            id=CART_LINE,
            product_id=WATCH,
            variant_id=None,
            quantity=1,
            gift_wrap=False,
            gift_message=STALE_MESSAGE,
            ship_to_address_id=MOM_ADDR,
        ),
    ]

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox[MOM_EMAIL_ID] = Email(
        id=MOM_EMAIL_ID,
        sender=f"Mom <{MOM_EMAIL}>",
        to=USER_EMAIL,
        subject="Birthday wish — a pearl necklace, please",
        body=(
            "Hi honey,\n\n"
            "For my birthday this year I would love a classic pearl necklace — "
            "something simple I can wear every day. Please do NOT get me a watch "
            "or any fitness gadget; I already have one and don't want another.\n\n"
            "Love,\nMom"
        ),
        received_at=f"{SEED_DATE}T09:15:00",
        received_label="9:15 AM",
        read=False,
        labels=["personal"],
    )
    mail.inbox["em_mp059_noise"] = Email(
        id="em_mp059_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Watch week deals",
        body="Unrelated promo for fitness watches.",
        received_at=f"{SEED_DATE}T08:05:00",
        received_label="8:05 AM",
        read=False,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_059_mom_gift_watch_false_premise,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _orders(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        return list((shop.orders or {}).values()) if shop else []

    def _new_orders(p: Probe) -> list:
        init = {}
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = p.initial_world.shop.orders or {}
        return [o for o in _orders(p) if o.id not in init]

    def _lines(p: Probe, product_id: str) -> list:
        return [
            it
            for o in _new_orders(p)
            for it in o.items
            if getattr(it, "product_id", None) == product_id
        ]

    def _msg_stale(msg: str) -> bool:
        low = (msg or "").lower()
        return any(tok in low for tok in STALE_TOKS)

    def _ordered_necklace_to_mom_fresh(p: Probe) -> bool:
        lines = _lines(p, NECKLACE)
        for it in lines:
            if getattr(it, "ship_to_address_id", None) != MOM_ADDR:
                continue
            msg = (getattr(it, "gift_message", None) or "").strip()
            if not msg or _msg_stale(msg):
                continue
            # Prefer a birthday-appropriate note, but any non-stale non-empty
            # replacement counts as an update of the seeded anniversary text.
            return True
        return False

    def _ordered_watch(p: Probe) -> bool:
        return len(_lines(p, WATCH)) > 0

    def _shipped_stale(p: Probe) -> bool:
        for o in _new_orders(p):
            for it in o.items:
                if _msg_stale(getattr(it, "gift_message", "") or ""):
                    return True
        return False

    def _read_mom_email(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        e = (mail.inbox or {}).get(MOM_EMAIL_ID)
        return bool(e and getattr(e, "read", False))

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "ordered_necklace_to_mom_fresh_message",
                    weight=1.0,
                    check=_ordered_necklace_to_mom_fresh,
                    required_for_success=True,
                ),
                Milestone(
                    "read_mom_email",
                    weight=0.0,
                    check=_read_mom_email,
                    required_for_success=False,
                ),
                Milestone(
                    "ordered_watch_against_mom",
                    weight=0.0,
                    check=_ordered_watch,
                    required_for_success=False,
                    forbidden=True,
                ),
                Milestone(
                    "shipped_stale_gift_message",
                    weight=0.0,
                    check=_shipped_stale,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
