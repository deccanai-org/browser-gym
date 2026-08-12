"""mp_155 / trip_purchases_only_essential_forgotten.

Austin trip Thu. Adapter already ordered (arrives Wed). Email names travel
pillow as essential forgotten item. Gold = pillow only.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_155/trip_purchases_only_essential_forgotten"
BRIEF_KEY = "mp_155"
BRIEF = (
    "Find all purchases associated with my upcoming trip. If I forgot something "
    "essential, order it. Don't buy things merely because they might be useful. "
    "Email me what you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-20T16:00:00"
FLIGHT = "ev_mp155_flight"
PACK = "em_mp155_pack"
PILLOW = "p_mp155_pillow"
SNACK = "p_mp155_snack"
GUIDE = "p_mp155_guide"
ADAPTER = "p_mp155_adapter"
AD_ORD = "ORD-MP155-ADAPTER"


def task_mp_155_trip_purchases_only_essential_forgotten(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail, oitem, product, shipment, shop_order

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[FLIGHT] = ev(
        eid=FLIGHT, title="Flight to Austin (AA 1420)",
        day="2026-05-21", start="06:40", end="10:15", day_label="Thu May 21",
        description="Work trip. Adapter already ordered.",
        location="JFK",
    )
    world.mail.inbox[PACK] = mail(
        eid=PACK, sender=USER_EMAIL, to="assistant@shopmail.com",
        subject="Austin trip packing",
        received_at="2026-05-18T09:00:00", received_label="Mon 9:00 AM",
        body=(
            "Adapter is already ordered. Don't forget the travel pillow — I "
            "never sleep on planes without it. That's essential. Snacks and a "
            "guidebook would be nice-to-haves, not essential."
        ),
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[PILLOW] = product(
        pid=PILLOW, name="Travel pillow", brand="RestAir",
        category="travel", price=22.00, emoji="🧳",
        desc="Essential for the plane. Not yet purchased.",
    )
    shop.products[SNACK] = product(
        pid=SNACK, name="Airport snack mix", brand="GrazeCo",
        category="grocery", price=9.00, emoji="🥜",
        desc="Nice-to-have.",
    )
    shop.products[GUIDE] = product(
        pid=GUIDE, name="Austin guidebook", brand="Lonely",
        category="books", price=16.00, emoji="📘",
        desc="Nice-to-have.",
    )
    shop.products[ADAPTER] = product(
        pid=ADAPTER, name="TripPlug travel adapter", brand="TripPlug",
        category="electronics", price=24.00, emoji="🔌",
        desc="Already on the way.",
    )
    shop.orders[AD_ORD] = shop_order(
        oid=AD_ORD,
        items=[oitem(iid="ln_mp155_ad", pid=ADAPTER, name="TripPlug travel adapter", price=24.00)],
        placed_at="2026-05-18T12:00:00Z",
        status="shipped",
        shipments=[shipment(sid="sh_mp155_ad", item_ids=["ln_mp155_ad"], status="shipped",
                            eta="Wednesday May 20, 2026",
                            detail="Arrives Wednesday before Thursday 6:40 AM departure.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_155_trip_purchases_only_essential_forgotten,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, shop_bought, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(pillow|essential|adapter)")
    EXTRA = {SNACK, GUIDE, ADAPTER}

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_trip_on_calendar", 0.15, viewed_cal, True),
                Milestone("read_packing_essential_note", 0.25, lambda p: mail_read(p, PACK), True),
                Milestone("ordered_only_forgotten_travel_pillow", 0.4, lambda p: shop_bought(p, [PILLOW]), True),
                Milestone("emailed_what_was_ordered", 0.2, lambda p: emailed_alice(p, _OK) and shop_bought(p, [PILLOW]), True),
                Milestone("bought_nice_to_have_or_duplicate_adapter", 0.0, lambda p: shop_bought(p, EXTRA), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
