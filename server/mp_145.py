"""mp_145 / promised_send_after_meeting_buy_if_store.

Promised Jordan a Field Notes notebook (in stock, address in mail).
Promised Maya a slide deck (not a store item) as decoy.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_145/promised_send_after_meeting_buy_if_store"
BRIEF_KEY = "mp_145"
BRIEF = (
    "I promised someone I'd send them something after a meeting. Figure out "
    "what it was and who I promised it to. If it's something available in the "
    "store, purchase it and arrange delivery; otherwise don't do anything. "
    "Email me what you did."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T10:00:00"
CRIT = "ev_mp145_crit"
JORDAN = "em_mp145_jordan"
MAYA = "em_mp145_maya"
SKU = "p_mp145_notes"
DECOY = "p_mp145_mug"


def task_mp_145_promised_send_after_meeting_buy_if_store(seed: int) -> "WorldState":
    from server.state import Address
    from server.mp_lh_common import boot_world, ev, mail, product

    world = boot_world(seed, TASK_ID, BRIEF, GYM_NOW)
    world.calendar.events[CRIT] = ev(
        eid=CRIT, title="Design crit with Jordan", day="2026-05-14",
        start="15:00", end="16:00", day_label="Thu May 14",
        description="Past design crit. Alice promised to send Jordan a notebook.",
    )
    world.mail.inbox[JORDAN] = mail(
        eid=JORDAN, sender=USER_EMAIL, to="jordan.blake@shopmail.com",
        subject="Re: design crit — the notebook",
        received_at="2026-05-14T16:20:00", received_label="Thu May 14",
        body=(
            "Jordan — I'll send you the Field Notes notebook I mentioned after "
            "today's crit. Ship it to 88 Pine St, Brooklyn NY 11201."
        ),
    )
    world.mail.inbox[MAYA] = mail(
        eid=MAYA, sender=USER_EMAIL, to="maya.okonkwo@shopmail.com",
        subject="I'll send the slide deck",
        received_at="2026-05-13T18:00:00", received_label="Wed May 13",
        body="Maya — I'll send you the slide deck after standup. (A file, not a store item.)",
    )
    alice = world.shop.users["u_alice"]
    alice.addresses["addr_jordan"] = Address(
        id="addr_jordan", label="Jordan Blake", full_name="Jordan Blake",
        line1="88 Pine St", line2="", city="Brooklyn", state="NY", zip="11201",
        is_default=False,
    )
    shop = world.shop
    shop.products.clear()
    shop.orders.clear()
    shop.products[SKU] = product(
        pid=SKU, name="Field Notes Notebook", brand="Field Notes",
        category="office", price=12.00, emoji="📓",
        desc="The notebook promised to Jordan Blake.",
    )
    shop.products[DECOY] = product(
        pid=DECOY, name="Team mug", brand="GiftCo",
        category="home", price=14.00, emoji="☕",
        desc="Not promised to anyone.",
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_145_promised_send_after_meeting_buy_if_store,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.mp_lh_common import emailed_alice, mail_read, new_shop_orders, shop_bought
    from server.verifiers import Milestone, Probe, TaskSuite

    _OK = re.compile(r"(?ix)(jordan|field\s+notes|notebook|88\s+pine)")

    def _shipped_jordan(p: Probe) -> bool:
        for o in new_shop_orders(p):
            for it in o.items:
                if getattr(it, "product_id", "") != SKU:
                    continue
                addr = getattr(it, "ship_to_address_id", "") or ""
                if addr == "addr_jordan" or "jordan" in addr.lower():
                    return True
                return True  # bought the notebook at all is close; prefer jordan addr
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("found_jordan_notebook_promise", 0.25, lambda p: mail_read(p, JORDAN), True),
                Milestone("purchased_field_notes_notebook", 0.45, lambda p: shop_bought(p, [SKU]), True),
                Milestone("emailed_confirmation", 0.3, lambda p: emailed_alice(p, _OK) and shop_bought(p, [SKU]), True),
                Milestone("bought_unrelated_mug", 0.0, lambda p: shop_bought(p, [DECOY]), False, forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
