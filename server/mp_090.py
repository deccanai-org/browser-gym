"""mp_090 / reactivate_subscription_and_update_default_address — ShopGym only.

Flat work-ticket: cancel existing coffee-pod Subscribe & Save, recreate same
product+cadence, then add Bellwood Ave address and set it as default shipping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_090/reactivate_subscription_and_update_default_address"
BRIEF_KEY = "mp_090"
BRIEF = (
    "Your address is now 1442 Bellwood Ave, Apt 3B, Austin, TX 78704. "
    "Cancel the current Subscribe & Save order for the coffee pods, then set "
    "up a new Subscribe & Save order for the same product and cadence. The "
    "expected outcome is that the subscriptions page shows only the new "
    "subscription as Active. Now add the new address to your account and set "
    "it as the default. The expected outcome is that the address book shows "
    "1442 Bellwood Ave as the default shipping address."
)

USER_EMAIL = "alice@shopmail.com"
SUB_OLD = "SUB-MP090-COFFEE"
P_COFFEE = "p_mp090_coffee_pods"
CADENCE = "monthly"
TARGET_ZIP = "78704"


def task_mp_090_reactivate_subscription_and_update_default_address(
    seed: int,
) -> "WorldState":
    from server.state import Address, Product, Subscription
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    alice = shop.users["u_alice"]

    # One clearly non-target default address so set-default is unambiguous.
    alice.addresses.clear()
    alice.addresses["addr_home"] = Address(
        id="addr_home", label="Home", full_name="Alice Anderson",
        line1="100 Park Avenue", line2="Apt 4B",
        city="Brooklyn", state="NY", zip="11201", is_default=True,
    )

    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.subscriptions.clear()

    shop.products[P_COFFEE] = Product(
        id=P_COFFEE,
        name="Morning Roast Coffee Pods (24ct)",
        brand="BrewHaus",
        category="grocery",
        base_price=22.00,
        rating=4.6,
        review_count=2100,
        stock=80,
        image_emoji="☕",
        short_description="Subscribe & save coffee pods.",
        tags=["coffee", "pods", "subscription"],
        is_subscribable=True,
    )
    shop.subscriptions[SUB_OLD] = Subscription(
        id=SUB_OLD, user_id="u_alice", product_id=P_COFFEE,
        variant_id=None, quantity=1, cadence=CADENCE,
        deliveries_remaining=6, next_delivery_date="2026-05-28",
        address_id="addr_home", payment_id="pay_visa",
        loyalty_discount_pct=0.0, status="active",
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_090_reactivate_subscription_and_update_default_address,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _subs(p: Probe) -> dict:
        shop = _shop(p)
        return dict(shop.subscriptions or {}) if shop else {}

    def _addrs(p: Probe) -> dict:
        shop = _shop(p)
        if shop is None:
            return {}
        u = (shop.users or {}).get("u_alice")
        return dict(u.addresses or {}) if u else {}

    def _addr_blob(a) -> str:
        return " ".join([
            str(getattr(a, "line1", "") or ""),
            str(getattr(a, "line2", "") or ""),
            str(getattr(a, "city", "") or ""),
            str(getattr(a, "state", "") or ""),
            str(getattr(a, "zip", "") or ""),
        ]).lower()

    def _is_bellwood(a) -> bool:
        blob = _addr_blob(a)
        return (
            "1442" in blob
            and "bellwood" in blob
            and TARGET_ZIP in blob
        )

    def _cancelled_existing(p: Probe) -> bool:
        s = _subs(p).get(SUB_OLD)
        return bool(s and getattr(s, "status", "") == "cancelled")

    def _recreated(p: Probe) -> bool:
        for sid, s in _subs(p).items():
            if sid == SUB_OLD:
                continue
            if getattr(s, "product_id", "") != P_COFFEE:
                continue
            if getattr(s, "cadence", "") != CADENCE:
                continue
            if getattr(s, "status", "") != "active":
                continue
            return True
        return False

    def _only_new_active(p: Probe) -> bool:
        if not _cancelled_existing(p):
            return False
        active = [
            s for s in _subs(p).values()
            if getattr(s, "status", "") == "active"
        ]
        if len(active) != 1:
            return False
        s = active[0]
        return (
            getattr(s, "id", "") != SUB_OLD
            and getattr(s, "product_id", "") == P_COFFEE
            and getattr(s, "cadence", "") == CADENCE
        )

    def _added_address(p: Probe) -> bool:
        return any(_is_bellwood(a) for a in _addrs(p).values())

    def _address_default(p: Probe) -> bool:
        for a in _addrs(p).values():
            if _is_bellwood(a) and bool(getattr(a, "is_default", False)):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "cancelled_existing_subscription", weight=0.25,
                    check=_cancelled_existing, required_for_success=True,
                ),
                Milestone(
                    "recreated_subscription_same_product_and_cadence", weight=0.25,
                    check=_recreated, required_for_success=True,
                ),
                Milestone(
                    "only_new_subscription_shows_active", weight=0.15,
                    check=_only_new_active, required_for_success=True,
                ),
                Milestone(
                    "added_new_address", weight=0.15,
                    check=_added_address, required_for_success=True,
                ),
                Milestone(
                    "address_set_as_default", weight=0.2,
                    check=_address_default, required_for_success=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
