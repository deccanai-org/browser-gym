"""mp_151 / wrong_version_purchase_replace_if_confident.

Oak AeroLift desk; Alice's later email is confident she wanted walnut.
Mug 'maybe wrong color' is uncertain decoy. Gold = walnut replacement only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_151/wrong_version_purchase_replace_if_confident"
BRIEF_KEY = "mp_151"
BRIEF = (
    "I ordered the wrong version of something recently. Figure out which "
    "purchase based on my emails, find the correct version, and only place "
    "the replacement order if you're confident it fixes the problem. Email me "
    "what you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
DESK_MAIL = "em_mp151_walnut"
MUG_MAIL = "em_mp151_mug"
ORDER_ID = "ORD-MP151-DESK"
LINE_ID = "ln_mp151_desk"
SKU = "p_mp151_desk"
VAR_OAK = "v_mp151_oak"
VAR_WALNUT = "v_mp151_walnut"
MUG = "p_mp151_mug"


def task_mp_151_wrong_version_purchase_replace_if_confident(seed: int) -> "WorldState":
    from server.state import ProductVariant
    from server.mp_lh_common import boot_world, mail, oitem, product, shop_order

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.mail.inbox[DESK_MAIL] = mail(
        eid=DESK_MAIL, sender=USER_EMAIL, to="support@shopgym.com",
        subject="AeroLift desk — I meant walnut, not oak",
        received_at="2026-05-20T19:10:00", received_label="Wed 7:10 PM",
        body=(
            "I ordered the AeroLift Standing Desk in oak by mistake. I am sure "
            "I wanted walnut — please replace it with the walnut version. Not "
            "teak, not oak. Walnut only."
        ),
    )
    world.mail.inbox[MUG_MAIL] = mail(
        eid=MUG_MAIL, sender=USER_EMAIL, to="support@shopgym.com",
        subject="mug color maybe off?",
        received_at="2026-05-19T12:00:00", received_label="Tue 12:00 PM",
        body="The mug color might be slightly off? I'm not actually sure. Ignore unless it's obvious.",
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[SKU] = product(
        pid=SKU, name="AeroLift Standing Desk", brand="AeroLift",
        category="home", price=249.00, emoji="🖥️",
        desc="Color is a saved option. Oak vs walnut.",
        variants=[
            ProductVariant(id=VAR_OAK, label="Oak", attributes={"color": "oak"}, stock=3),
            ProductVariant(id=VAR_WALNUT, label="Walnut", attributes={"color": "walnut"}, stock=3),
        ],
    )
    shop.products[MUG] = product(
        pid=MUG, name="Studio mug", brand="GiftCo", category="home", price=14.00, emoji="☕",
        desc="Uncertain color complaint — do not replace.",
    )
    shop.orders[ORDER_ID] = shop_order(
        oid=ORDER_ID,
        items=[oitem(iid=LINE_ID, pid=SKU, name="AeroLift Standing Desk", price=249.00,
                     variant_id=VAR_OAK, variant_label="Oak")],
        placed_at="2026-05-20T16:00:00Z",
        status="confirmed",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_151_wrong_version_purchase_replace_if_confident,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_shop_orders, shop_bought
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(walnut|desk|replaced|variant)")

    def _desk(p):
        shop = p.world.shop if p.world else None
        return (shop.orders or {}).get(ORDER_ID) if shop else None

    def _walnut(p: Probe) -> bool:
        o = _desk(p)
        if o is not None and getattr(o, "status", "") != "cancelled":
            for it in o.items:
                vid = (getattr(it, "variant_id", "") or "").lower()
                lab = (getattr(it, "variant_label", "") or "").lower()
                if VAR_WALNUT in vid or "walnut" in lab:
                    return True
        for no in new_shop_orders(p):
            for it in no.items:
                lab = (getattr(it, "variant_label", "") or "").lower()
                pid = getattr(it, "product_id", "")
                if pid == SKU and "walnut" in lab:
                    return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("read_confident_walnut_email", 0.25, lambda p: mail_read(p, DESK_MAIL), True),
                Milestone("replaced_with_walnut_version", 0.5, _walnut, True),
                Milestone("emailed_confirmation", 0.25, lambda p: emailed_alice(p, _OK) and _walnut(p), True),
                Milestone("acted_on_uncertain_mug", 0.0, lambda p: shop_bought(p, [MUG]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
