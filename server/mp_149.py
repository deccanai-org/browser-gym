"""mp_149 / birthday_gift_from_calendar_dinner_emails_budget.

Priya birthday dinner Sat. Email wants ceramic pour-over kettle $55.
Past gift was a candle. Mom's June birthday is a decoy.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_149/birthday_gift_from_calendar_dinner_emails_budget"
BRIEF_KEY = "mp_149"
BRIEF = (
    "Buy a birthday gift for the person whose birthday dinner is on my "
    "calendar this weekend. Use my emails to figure out what they might like. "
    "Spend $40–$80 and don't buy something I've given them before. Email me "
    "what you ordered."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
DINNER = "ev_mp149_priya"
LIKE = "em_mp149_kettle"
CANDLE_ORD = "ORD-MP149-CANDLE"
KETTLE = "p_mp149_kettle"
CANDLE = "p_mp149_candle"
MUG = "p_mp149_mug"
ESPRESSO = "p_mp149_espresso"


def task_mp_149_birthday_gift_from_calendar_dinner_emails_budget(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail, oitem, product, shipment, shop_order

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[DINNER] = ev(
        eid=DINNER, title="Birthday dinner — Priya Raman",
        day="2026-05-23", start="19:00", end="21:30", day_label="Sat May 23",
        description="Priya's birthday dinner this weekend.",
        location="Nona's Table",
    )
    world.calendar.events["ev_mp149_mom"] = ev(
        eid="ev_mp149_mom", title="Mom's birthday",
        day="2026-06-08", start="00:00", end="23:59", day_label="Mon Jun 8",
        description="Not this weekend.",
    )
    world.mail.inbox[LIKE] = mail(
        eid=LIKE, sender="priya.raman@shopmail.com",
        subject="random — ceramic pour-over kettle",
        received_at="2026-04-22T20:10:00", received_label="Apr 22",
        body="I've been wanting a ceramic pour-over kettle for weekend coffee. The Hario-style ones are perfect.",
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[KETTLE] = product(
        pid=KETTLE, name="Ceramic pour-over kettle", brand="Hearth",
        category="home", price=55.00, emoji="☕",
        desc="Priya mentioned this. $55, inside $40–$80.",
    )
    shop.products[CANDLE] = product(
        pid=CANDLE, name="Scented soy candle", brand="Glow",
        category="home", price=22.00, emoji="🕯️",
        desc="Given to Priya last year.",
    )
    shop.products[MUG] = product(
        pid=MUG, name="Coffee mug", brand="GiftCo",
        category="home", price=18.00, emoji="mug",
        desc="Under $40.",
    )
    shop.products[ESPRESSO] = product(
        pid=ESPRESSO, name="BaristaPro espresso machine", brand="BaristaPro",
        category="home", price=199.00, emoji="☕",
        desc="Over $80.",
    )
    shop.orders[CANDLE_ORD] = shop_order(
        oid=CANDLE_ORD,
        items=[oitem(iid="ln_mp149_c", pid=CANDLE, name="Scented soy candle", price=22.00)],
        placed_at="2025-05-20T12:00:00Z",
        shipments=[shipment(sid="sh_mp149_c", item_ids=["ln_mp149_c"], status="delivered",
                            eta="May 2025", delivered_at="2025-05-22T12:00:00Z",
                            detail="Gift for Priya Raman birthday 2025.")],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_149_birthday_gift_from_calendar_dinner_emails_budget,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_spend, shop_bought, viewed_cal
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(priya|kettle|pour-over|55)")

    def _band(p: Probe) -> bool:
        return shop_bought(p, [KETTLE]) and 40.0 <= new_spend(p) <= 80.0 + 1e-6

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_weekend_birthday_dinner", 0.2, viewed_cal, True),
                Milestone("read_preference_email", 0.2, lambda p: mail_read(p, LIKE), True),
                Milestone("bought_new_gift_in_40_80_band", 0.4, _band, True),
                Milestone("emailed_order", 0.2, lambda p: emailed_alice(p, _OK) and _band(p), True),
                Milestone("rebought_previous_candle_gift", 0.0, lambda p: shop_bought(p, [CANDLE]), False, forbidden=True),
                Milestone("spent_outside_40_80", 0.0, lambda p: shop_bought(p, [MUG, ESPRESSO]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
