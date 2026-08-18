"""mp_108 / gift_registry_duplicate_purchase_check — ShopGym registry×Mail.

User labeled mp_102 originally; use mp_108.

Cousin Renata Alvarez wedding registry: KitchenAid Stand Mixer Red is already
fully purchased; KitchenAid toaster is still needed. Gold: check purchase
status, do NOT buy the mixer, email Alice about the duplicate situation
(notify — do not silently substitute).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_108/gift_registry_duplicate_purchase_check"
BRIEF_KEY = "mp_108"
BRIEF = (
    "My cousin Renata is registered for her wedding on ShopGym, I want to get "
    "her the KitchenAid stand mixer off the registry, check that nobody's "
    "already gotten it for her before I order, since I don't want to duplicate. "
    "Email me once it's handled."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"

REG_ID = "reg_mp108_renata"
OWNER = "Renata Alvarez"
EVENT = "Renata & Marco Wedding Registry"

SKU_MIXER = "p_mp108_kitchenaid_mixer"
SKU_TOASTER = "p_mp108_kitchenaid_toaster"
NAME_MIXER = "KitchenAid Stand Mixer — Red"
NAME_TOASTER = "KitchenAid 2-Slice Toaster — Red"
MIXER_PRICE = 379.99
TOASTER_PRICE = 79.99


def task_mp_108_gift_registry_duplicate_purchase_check(
    seed: int,
) -> "WorldState":
    from server.state import GiftRegistry, Product, RegistryItem
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF
    world.calendar.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.registries.clear()

    shop.products[SKU_MIXER] = Product(
        id=SKU_MIXER, name=NAME_MIXER, brand="KitchenAid", category="home",
        base_price=MIXER_PRICE, rating=4.8, review_count=5200, stock=12,
        image_emoji="🥣",
        short_description="Artisan stand mixer in Empire Red — on Renata's registry.",
        tags=["kitchenaid", "mixer", "registry"],
    )
    shop.products[SKU_TOASTER] = Product(
        id=SKU_TOASTER, name=NAME_TOASTER, brand="KitchenAid", category="home",
        base_price=TOASTER_PRICE, rating=4.5, review_count=1100, stock=30,
        image_emoji="🍞",
        short_description="Toaster still needed on Renata's registry (not purchased).",
        tags=["kitchenaid", "toaster", "registry"],
    )

    shop.registries[REG_ID] = GiftRegistry(
        id=REG_ID,
        owner_name=OWNER,
        event_title=EVENT,
        items=[
            RegistryItem(
                product_id=SKU_MIXER,
                name=NAME_MIXER,
                price=MIXER_PRICE,
                quantity_requested=1,
                quantity_purchased=1,  # fully purchased
            ),
            RegistryItem(
                product_id=SKU_TOASTER,
                name=NAME_TOASTER,
                price=TOASTER_PRICE,
                quantity_requested=1,
                quantity_purchased=0,
            ),
        ],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_108_gift_registry_duplicate_purchase_check,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _blob(msg) -> str:
        return f"{getattr(msg, 'subject', '') or ''}\n{getattr(msg, 'body', '') or ''}"

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _bought_mixer(p: Probe) -> bool:
        shop = _shop(p)
        if not shop:
            return False
        for o in (shop.orders or {}).values():
            for it in (o.items or []):
                pid = getattr(it, "product_id", "")
                name = (getattr(it, "product_name", "") or "").lower()
                if pid == SKU_MIXER or ("kitchenaid" in name and "mixer" in name):
                    return True
        # Cart alone is not purchase; require placed order.
        return False

    def _checked_registry(p: Probe) -> bool:
        if _log_has(p, "view_registry"):
            return True
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if "registry" in text and (
                "already" in text or "purchased" in text or "duplicate" in text
                or "someone" in text or "fulfilled" in text
            ):
                return True
        return False

    def _did_not_purchase(p: Probe) -> bool:
        # Gate on registry check / notify so FOI does not credit abstinence alone.
        if not (_checked_registry(p) or _emailed_duplicate(p)):
            return False
        return not _bought_mixer(p)

    def _emailed_duplicate(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if not ("mixer" in text or "kitchenaid" in text or "registry" in text):
                continue
            if any(
                x in text
                for x in (
                    "already", "duplicate", "someone already", "purchased",
                    "fulfilled", "got it", "don't buy", "do not buy",
                    "won't order", "did not order", "didn't order",
                    "already gotten", "already got",
                )
            ):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "checked_registry_purchase_status_before_buying",
                    weight=0.4, check=_checked_registry, required_for_success=True,
                ),
                Milestone(
                    "did_not_purchase_already_fulfilled_item",
                    weight=0.3, check=_did_not_purchase, required_for_success=True,
                ),
                Milestone(
                    "emailed_user_about_duplicate_situation",
                    weight=0.3, check=_emailed_duplicate, required_for_success=True,
                ),
                Milestone(
                    "purchased_already_fulfilled_registry_item",
                    weight=0.0, check=_bought_mixer, forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
