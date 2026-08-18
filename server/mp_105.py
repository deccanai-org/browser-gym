"""mp_105 / dinner_party_headcount_venue_and_grocery_run — Mail×Shop.

User labeled mp_099 originally; that ID is silent_noop monitor — use mp_105.

Book-club dinner on the 14th: RSVP thread yields net headcount; inventory note
says rice/olive oil/wine already owned; pasta-night menu; distractor red-wine
vinegar vs balsamic needed. Gold: order only missing items sized to headcount.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_105/dinner_party_headcount_venue_and_grocery_run"
BRIEF_KEY = "mp_105"
BRIEF = (
    "I'm hosting dinner for the book club on the 14th, check the group email for "
    "who's actually coming and get whatever groceries I'm missing from ShopGym. "
    "Skip anything I already have. Email me the final list and total once it's ordered."
)

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T11:00:00"
DINNER_DAY = "2026-06-14"
# 5 yes RSVPs; one decline; one yes brings a sister → net guests = 6 (+ host optional).
# Score headcount as 6 dinner guests from the thread (5 confirmed + sister).
NET_HEADCOUNT = 6

# Owned (must NOT reorder)
OWNED = ("rice", "olive oil", "wine")
# Needed for pasta night (per headcount)
SKU_PASTA = "p_mp105_pasta"
SKU_SAUCE = "p_mp105_marinara"
SKU_BALSAMIC = "p_mp105_balsamic"
SKU_PARM = "p_mp105_parmesan"
SKU_GARLIC = "p_mp105_garlic"
# Distractors / owned
SKU_RICE = "p_mp105_rice"
SKU_OIL = "p_mp105_olive_oil"
SKU_WINE = "p_mp105_red_wine"
SKU_VINEGAR = "p_mp105_red_wine_vinegar"  # distractor — not balsamic

NEEDED = {SKU_PASTA, SKU_SAUCE, SKU_BALSAMIC, SKU_PARM, SKU_GARLIC}
FORBIDDEN_BUY = {SKU_RICE, SKU_OIL, SKU_WINE, SKU_VINEGAR}


def task_mp_105_dinner_party_headcount_venue_and_grocery_run(
    seed: int,
) -> "WorldState":
    from server.apps.mail.state import Email, SEED_DATE
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

    catalog = [
        (SKU_PASTA, "Linguine Pasta 1lb", 3.49, "🍝", "pasta"),
        (SKU_SAUCE, "Marinara Sauce 24oz", 4.29, "🍅", "sauce"),
        (SKU_BALSAMIC, "Balsamic Vinegar 16oz", 8.99, "🍾", "balsamic"),
        (SKU_PARM, "Parmesan Wedge 8oz", 6.50, "🧀", "parmesan"),
        (SKU_GARLIC, "Fresh Garlic 3-pack", 2.49, "🧄", "garlic"),
        (SKU_RICE, "Jasmine Rice 2lb", 4.99, "🍚", "rice"),
        (SKU_OIL, "Extra Virgin Olive Oil 750ml", 11.99, "🫒", "olive oil"),
        (SKU_WINE, "Chianti Red Wine 750ml", 14.99, "🍷", "wine"),
        (SKU_VINEGAR, "Red Wine Vinegar 16oz", 3.99, "🧴", "red wine vinegar"),
    ]
    for pid, name, price, emoji, tag in catalog:
        shop.products[pid] = Product(
            id=pid, name=name, brand="PantryCo", category="grocery",
            base_price=price, rating=4.4, review_count=200, stock=80,
            image_emoji=emoji,
            short_description=f"Grocery item for pasta night ({tag}).",
            tags=["grocery", "pasta night", tag],
        )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp105_rsvp"] = Email(
        id="em_mp105_rsvp",
        sender="bookclub@lists.example.com",
        to=USER_EMAIL,
        subject="Re: Book club dinner on the 14th — RSVPs",
        body=(
            "Thread: Book club dinner (pasta night) on June 14.\n\n"
            "RSVPs so far:\n"
            "1. Priya — YES\n"
            "2. Marcus — YES\n"
            "3. Jin — YES (bringing my sister Lena too)\n"
            "4. Sam — YES\n"
            "5. Nora — YES\n"
            "6. Devon — NO, can't make it\n\n"
            "That's five yes + Jin's sister Lena. Devon declined.\n"
            f"Net headcount for food: {NET_HEADCOUNT} guests.\n\n"
            "— Book club list"
        ),
        received_at=f"{SEED_DATE}T09:05:00",
        received_label="9:05 AM",
        read=False,
        labels=["social"],
    )
    mail.inbox["em_mp105_inventory"] = Email(
        id="em_mp105_inventory",
        sender="alice@shopmail.com",
        to=USER_EMAIL,
        subject="Note to self — pantry before book club dinner",
        body=(
            "Inventory note before pasta night:\n"
            "- Rice: already have a full bag\n"
            "- Olive oil: already have\n"
            "- Red wine: already have a bottle\n"
            "Still need: pasta, marinara, balsamic vinegar (NOT red wine vinegar), "
            "parmesan, garlic — scale for the RSVP headcount.\n"
        ),
        received_at=f"{SEED_DATE}T09:20:00",
        received_label="9:20 AM",
        read=False,
        labels=["notes"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_105_dinner_party_headcount_venue_and_grocery_run,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

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

    def _new_order_items(p: Probe) -> list:
        shop = _shop(p)
        if not shop:
            return []
        items = []
        for o in (shop.orders or {}).values():
            items.extend(list(o.items or []))
        return items

    def _pids(p: Probe) -> set[str]:
        return {getattr(it, "product_id", "") for it in _new_order_items(p)}

    def _qty_map(p: Probe) -> dict[str, int]:
        out: dict[str, int] = {}
        for it in _new_order_items(p):
            pid = getattr(it, "product_id", "")
            out[pid] = out.get(pid, 0) + int(getattr(it, "quantity", 1) or 1)
        return out

    def _computed_headcount(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if re.search(r"\b(6|six)\b", text) and re.search(
                r"\b(guest|headcount|coming|rsvp|people|person)\b", text
            ):
                return True
            if "lena" in text and ("sister" in text or "jin" in text):
                return True
        # Also accept correct scaled order as durable proxy for headcount use.
        qm = _qty_map(p)
        if SKU_PASTA in qm and qm[SKU_PASTA] >= 2:
            return True
        return False

    def _checked_inventory(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if any(x in text for x in ("already have", "skipped", "pantry", "inventory", "didn't buy rice", "did not buy rice")):
                return True
        # Proxy: ordered needed items without owned ones.
        pids = _pids(p)
        return bool(pids & NEEDED) and not (pids & {SKU_RICE, SKU_OIL, SKU_WINE})

    def _did_not_reorder_owned(p: Probe) -> bool:
        pids = _pids(p)
        # Require a grocery order was placed; empty cart/orders must not pass FOI.
        if not (pids & NEEDED):
            return False
        return not bool(pids & {SKU_RICE, SKU_OIL, SKU_WINE})

    def _ordered_missing(p: Probe) -> bool:
        pids = _pids(p)
        # Must include core pasta-night set; balsamic not vinegar.
        need_ok = {SKU_PASTA, SKU_SAUCE, SKU_BALSAMIC}.issubset(pids)
        no_vinegar = SKU_VINEGAR not in pids
        qm = _qty_map(p)
        # Pasta qty should scale (~1 unit per 2–3 guests → at least 2 for 6).
        pasta_ok = qm.get(SKU_PASTA, 0) >= 2
        return need_ok and no_vinegar and pasta_ok

    def _emailed_list_total(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            has_list = any(x in text for x in ("pasta", "marinara", "balsamic", "garlic", "parmesan"))
            has_total = "$" in text or "total" in text
            return has_list and has_total
        return False

    def _reordered_owned(p: Probe) -> bool:
        return bool(_pids(p) & {SKU_RICE, SKU_OIL, SKU_WINE})

    def _qty_mismatch(p: Probe) -> bool:
        qm = _qty_map(p)
        if not qm:
            return False
        # Single pasta box for 6 guests is mismatched.
        if SKU_PASTA in qm and qm[SKU_PASTA] == 1 and len(qm) >= 2:
            return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "computed_correct_headcount_from_thread",
                    weight=0.2, check=_computed_headcount, required_for_success=True,
                ),
                Milestone(
                    "checked_existing_inventory_before_ordering",
                    weight=0.2, check=_checked_inventory, required_for_success=True,
                ),
                Milestone(
                    "did_not_reorder_owned_items",
                    weight=0.25, check=_did_not_reorder_owned, required_for_success=True,
                ),
                Milestone(
                    "ordered_correct_missing_items_for_headcount",
                    weight=0.2, check=_ordered_missing, required_for_success=True,
                ),
                Milestone(
                    "emailed_final_list_and_total",
                    weight=0.15, check=_emailed_list_total, required_for_success=True,
                ),
                Milestone(
                    "reordered_item_already_owned",
                    weight=0.0, check=_reordered_owned, forbidden=True,
                ),
                Milestone(
                    "ordered_quantity_mismatched_to_headcount",
                    weight=0.0, check=_qty_mismatch, forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
