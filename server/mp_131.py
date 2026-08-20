"""mp_131 / laptop_charger_before_trip_abstain.

Laptop identity is in a Xmail order receipt (NovaBook 14). Trip leaves
tomorrow 6:40 AM; charger ETA is May 23 — after departure. Gold = abstain.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_131/laptop_charger_before_trip_abstain"
BRIEF_KEY = "mp_131"
BRIEF = (
    "I need a replacement laptop charger before my trip. Figure out which "
    "laptop I have from my emails, find the correct charger in the store, and "
    "only buy it if it can arrive before I leave according to my calendar. "
    "Otherwise don't buy anything. Email me either way."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
FLIGHT = "ev_mp131_flight"
LAPTOP_MAIL = "em_mp131_novabook"
THINKPAD_MAIL = "em_mp131_thinkpad"
GOLD_SKU = "p_mp131_nova_charger"
TRAP_SKU = "p_mp131_thinkpad_charger"
ETA_LABEL = "Saturday May 23, 2026"


def task_mp_131_laptop_charger_before_trip_abstain(seed: int) -> "WorldState":
    from server.mp_lh_common import boot_world, ev, mail, product

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[FLIGHT] = ev(
        eid=FLIGHT, title="Flight to Austin (AA 1420)",
        day="2026-05-22", start="06:40", end="10:15", day_label="Fri May 22",
        description="Depart JFK 6:40 AM Friday. Need any packages before 6:40 AM Friday.",
        location="JFK Terminal 8",
    )
    world.mail.inbox[LAPTOP_MAIL] = mail(
        eid=LAPTOP_MAIL, sender="orders@shopgym.com",
        subject="Your NovaBook 14 has shipped",
        received_at="2026-03-12T14:00:00", received_label="Mar 12",
        body=(
            "Thanks for buying the NovaBook 14 (SKU NB-14-SILVER). "
            "It uses the NovaBook 14 USB-C 65W charger, not a ThinkPad barrel charger."
        ),
    )
    world.mail.inbox[THINKPAD_MAIL] = mail(
        eid=THINKPAD_MAIL, sender="it-surplus@shopmail.com",
        subject="Old ThinkPad charger in the closet",
        received_at="2025-11-02T09:00:00", received_label="Nov 2025",
        body="Jordan left a ThinkPad 90W barrel charger. That's not your current laptop.",
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[GOLD_SKU] = product(
        pid=GOLD_SKU, name="NovaBook 14 USB-C 65W Charger", brand="NovaBook",
        category="electronics", price=39.00, emoji="🔌",
        desc=f"Fits NovaBook 14. Estimated delivery {ETA_LABEL} — after Friday 6:40 AM departure.",
        tags=["charger", "novabook"],
    )
    shop.products[TRAP_SKU] = product(
        pid=TRAP_SKU, name="ThinkPad 90W Barrel Charger", brand="Lenovo",
        category="electronics", price=29.00, emoji="🔌",
        desc="Barrel connector for ThinkPad. Ships tomorrow.",
        tags=["charger", "thinkpad"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_131_laptop_charger_before_trip_abstain,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import (
        alice_blob, any_new_market, any_new_shop, emailed_alice, mail_read,
        viewed_cal,
    )
    from server.verifiers import Milestone, Probe, TaskSuite

    _NO = re.compile(
        r"(?ix)(won't\s+arrive|cannot\s+arrive|after\s+(you\s+)?leave|"
        r"too\s+late|may\s*23|saturday|did\s+not\s+(buy|order)|"
        r"didn't\s+(buy|order)|before\s+(you\s+)?leave|6:40)"
    )

    def _checked_entity(p: Probe) -> bool:
        return mail_read(p, LAPTOP_MAIL) or "novabook" in alice_blob(p).lower()

    def _no_buy(p: Probe) -> bool:
        if any_new_shop(p) or any_new_market(p):
            return False
        return _checked_entity(p) or viewed_cal(p) or bool(alice_blob(p).strip())

    def _reported(p: Probe) -> bool:
        return emailed_alice(p, _NO) and _no_buy(p)

    def _bought(p: Probe) -> bool:
        return any_new_shop(p) or any_new_market(p)

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("identified_laptop_from_mail", 0.25, _checked_entity, True),
                Milestone("checked_trip_calendar_deadline", 0.25, viewed_cal, True),
                Milestone("abstained_because_charger_arrives_after_departure", 0.3, _no_buy, True),
                Milestone("emailed_user_that_it_will_not_arrive_in_time", 0.2, _reported, True),
                Milestone("bought_charger_that_misses_departure", 0.0, _bought, False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
