"""mp_143 / conference_next_month_buy_needed_not_owned.

DevSummit Austin Jun 15–17. Adapter + shoes already owned; lanyard provided.
Gold = business cards only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_143/conference_next_month_buy_needed_not_owned"
BRIEF_KEY = "mp_143"
BRIEF = (
    "Find the conference I'm attending next month. Buy the things I'll need "
    "that I don't appear to own already. Don't buy anything unnecessary. "
    "Email me what you got."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
CONF = "ev_mp143_devsummit"
PACK = "em_mp143_pack"
CARDS = "p_mp143_cards"
ADAPTER = "p_mp143_adapter"
SHOES = "p_mp143_shoes"
LANYARD = "p_mp143_lanyard"
SOUVENIR = "p_mp143_mug"
OWNED_AD = "ORD-MP143-ADAPTER"
OWNED_SH = "ORD-MP143-SHOES"


def task_mp_143_conference_next_month_buy_needed_not_owned(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail, oitem, product, shipment, shop_order

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[CONF] = ev(
        eid=CONF, title="DevSummit 2026 — Austin",
        day="2026-06-15", start="09:00", end="18:00", day_label="Mon Jun 15",
        description="DevSummit 2026 Austin, Jun 15–17. Badge lanyard provided on site.",
        location="Austin Convention Center",
    )
    world.mail.inbox[PACK] = mail(
        eid=PACK, sender="alice@shopmail.com",
        to="assistant@shopmail.com",
        subject="DevSummit packing notes",
        received_at="2026-05-10T09:00:00", received_label="May 10",
        body=(
            "For DevSummit: badge lanyard (they provide), travel adapter, "
            "comfortable shoes, and a box of business cards. I think I already "
            "bought the adapter and the shoes."
        ),
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[CARDS] = product(
        pid=CARDS, name="Business Cards 100-pack", brand="PrintBox",
        category="office", price=18.00, emoji="🪪",
        desc="Needed for DevSummit. Not in order history.",
    )
    shop.products[ADAPTER] = product(
        pid=ADAPTER, name="TripPlug travel adapter", brand="TripPlug",
        category="electronics", price=24.00, emoji="🔌",
        desc="Already purchased May 10.",
    )
    shop.products[SHOES] = product(
        pid=SHOES, name="WalkLite travel shoes", brand="WalkLite",
        category="sports", price=64.00, emoji="👟",
        desc="Already purchased April 2.",
    )
    shop.products[LANYARD] = product(
        pid=LANYARD, name="Conference lanyard", brand="Expo",
        category="office", price=6.00, emoji="🎫",
        desc="Venue provides these. Unnecessary.",
    )
    shop.products[SOUVENIR] = product(
        pid=SOUVENIR, name="Austin skyline mug", brand="GiftCo",
        category="home", price=16.00, emoji="☕",
        desc="Souvenir. Not needed.",
    )
    shop.orders[OWNED_AD] = shop_order(
        oid=OWNED_AD,
        items=[oitem(iid="ln_mp143_ad", pid=ADAPTER, name="TripPlug travel adapter", price=24.00)],
        placed_at="2026-05-10T12:00:00Z",
        shipments=[shipment(sid="sh_mp143_ad", item_ids=["ln_mp143_ad"], status="delivered",
                            eta="May 12, 2026", delivered_at="2026-05-12T16:00:00Z",
                            detail="Delivered May 12.")],
    )
    shop.orders[OWNED_SH] = shop_order(
        oid=OWNED_SH,
        items=[oitem(iid="ln_mp143_sh", pid=SHOES, name="WalkLite travel shoes", price=64.00)],
        placed_at="2026-04-02T12:00:00Z",
        shipments=[shipment(sid="sh_mp143_sh", item_ids=["ln_mp143_sh"], status="delivered",
                            eta="April 6, 2026", delivered_at="2026-04-06T16:00:00Z",
                            detail="Delivered April 6.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_143_conference_next_month_buy_needed_not_owned,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, shop_bought, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(business\s+card|printbox|cards)")
    EXTRA = {ADAPTER, SHOES, LANYARD, SOUVENIR}

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_conference_on_calendar", 0.2, viewed_cal, True),
                Milestone("read_packing_notes", 0.2, lambda p: mail_read(p, PACK), True),
                Milestone("bought_only_missing_business_cards", 0.4, lambda p: shop_bought(p, [CARDS]), True),
                Milestone("emailed_what_was_bought", 0.2, lambda p: emailed_alice(p, _OK) and shop_bought(p, [CARDS]), True),
                Milestone("bought_already_owned_or_unnecessary", 0.0, lambda p: shop_bought(p, EXTRA), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
