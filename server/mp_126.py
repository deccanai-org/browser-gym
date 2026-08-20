"""mp_126 / two_stated_addresses_named_recipient — Xmazon×Xmail.

Candle set should ship to saved Work address, not default Home.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_126/two_stated_addresses_named_recipient"
BRIEF_KEY = "mp_126"
BRIEF = (
    "Ship the candle set to my office, not my home, my office address is "
    "saved on the account under 'Work.' Email me once it's sent."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"
SKU = "p_mp126_candle"
NAME = "Hearth Candle Set"
WORK = "addr_work"
HOME = "addr_home"


def task_mp_126_two_stated_addresses_named_recipient(seed: int) -> "WorldState":
    from server.state import Product
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
    shop.products[SKU] = Product(
        id=SKU,
        name=NAME,
        brand="Hearth",
        category="home",
        base_price=22.00,
        rating=4.7,
        review_count=140,
        stock=25,
        image_emoji="🕯️",
        short_description="Three-votive candle set. Ship to Work, not Home.",
        tags=["candle", "gift"],
    )
    world.mail.sent.clear()
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_126_two_stated_addresses_named_recipient,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(
        r"(?ix)(work|office|500\s+madison|shipped|sent|candle)"
    )

    def _init_ids(p: Probe) -> set:
        init = getattr(p, "initial_world", None)
        return set((init.shop.orders or {}) if init and init.shop else {})

    def _new_orders(p: Probe) -> list:
        shop = p.world.shop if p.world else None
        if shop is None:
            return []
        return [
            o
            for oid, o in (shop.orders or {}).items()
            if oid not in _init_ids(p) and getattr(o, "status", "") != "cancelled"
        ]

    def _candle_orders(p: Probe) -> list:
        out = []
        for o in _new_orders(p):
            if any(getattr(it, "product_id", "") == SKU for it in o.items):
                out.append(o)
        return out

    def _shipped_work(p: Probe) -> bool:
        for o in _candle_orders(p):
            addrs = {getattr(it, "ship_to_address_id", "") for it in o.items}
            if addrs == {WORK}:
                return True
        return False

    def _not_home_default(p: Probe) -> bool:
        if not _candle_orders(p):
            return False
        return not any(
            getattr(it, "ship_to_address_id", "") == HOME
            for o in _candle_orders(p)
            for it in o.items
        )

    def _emailed(p: Probe) -> bool:
        mail = getattr(p.world, "mail", None) if p.world else None
        if mail is None:
            return False
        for msg in (mail.sent or {}).values():
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}"
            if _OK.search(text) and _shipped_work(p):
                return True
        return False

    def _shipped_home(p: Probe) -> bool:
        return any(
            getattr(it, "ship_to_address_id", "") == HOME
            for o in _candle_orders(p)
            for it in o.items
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "selected_work_address_specifically",
                    weight=0.5,
                    check=_shipped_work,
                    required_for_success=True,
                ),
                Milestone(
                    "did_not_default_to_home_address",
                    weight=0.3,
                    check=_not_home_default,
                    required_for_success=True,
                ),
                Milestone(
                    "emailed_confirmation",
                    weight=0.2,
                    check=_emailed,
                    required_for_success=True,
                ),
                Milestone(
                    "shipped_to_home_address",
                    weight=0.0,
                    check=_shipped_home,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
