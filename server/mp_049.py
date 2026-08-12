"""mp_049 / dana_housewarming_mug_address_probe — ShopGym address-book probe.

Mechanism: brief says Dana's address should already be saved. Seed puts
addr_dana on the account (non-default) and a housewarming mug in catalog/cart.
Probe: confirm the address book / ship-to UI actually surfaces Dana before
trusting prior M89-family dispositions.

Gold: place the mug order shipped to addr_dana.
Forbidden: place the mug order to a non-Dana address (e.g. home default).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_049/dana_housewarming_mug_address_probe"
BRIEF_KEY = "mp_049"
BRIEF = (
    "Get a mug for Dana's housewarming and ship it to her. Her address should "
    "be saved on the account."
)

USER_EMAIL = "alice@shopmail.com"
DANA = "addr_dana"
MUG = "p_mp049_housewarming_mug"
CART_LINE = "ci_mp049_mug"


def task_mp_049_dana_housewarming_mug_address_probe(seed: int) -> "WorldState":
    """Seed Dana as saved non-default address + housewarming mug in cart."""
    from server.state import Address, CartItem, Product
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    alice = shop.users["u_alice"]
    alice.addresses[DANA] = Address(
        id=DANA,
        label="Dana",
        full_name="Dana Brooks",
        line1="61 Spruce Street",
        line2="",
        city="Raleigh",
        state="NC",
        zip="27601",
        is_default=False,
    )
    shop.products[MUG] = Product(
        id=MUG,
        name="Housewarming Ceramic Mug",
        brand="Kiln & Co",
        category="home",
        base_price=18.50,
        rating=4.6,
        review_count=220,
        stock=80,
        image_emoji="☕",
        short_description="Stoneware mug — housewarming gift.",
        tags=["mug", "housewarming", "gift", "ceramic"],
    )
    # Pre-load cart so the probe focuses on address discoverability / ship-to.
    shop.cart.items = [
        CartItem(
            id=CART_LINE,
            product_id=MUG,
            variant_id=None,
            quantity=1,
            gift_wrap=False,
            gift_message="",
            ship_to_address_id=None,
        ),
    ]
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_049_dana_housewarming_mug_address_probe,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/cart"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _lines_of

    def _mug_lines(p: Probe) -> list:
        return _lines_of(p, MUG)

    def _shipped_to_dana(p: Probe) -> bool:
        lines = _mug_lines(p)
        return bool(lines) and all(
            (getattr(it, "ship_to_address_id", None) or "") == DANA for it in lines
        )

    def _shipped_not_to_dana(p: Probe) -> bool:
        lines = _mug_lines(p)
        if not lines:
            return False
        return any(
            (getattr(it, "ship_to_address_id", None) or "") != DANA for it in lines
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "mug_shipped_to_dana",
                    weight=1.0,
                    check=_shipped_to_dana,
                    required_for_success=True,
                ),
                Milestone(
                    "mug_shipped_not_to_dana",
                    weight=0.0,
                    check=_shipped_not_to_dana,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
