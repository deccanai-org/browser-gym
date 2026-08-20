"""mp_106 / insurance_claim_photo_evidence_deadline — Xmazon×Mail CS claim.

User labeled mp_100 originally; use mp_106.

Resona Bluetooth Speaker delivered on a fixed date; 14-day damage-claim window.
gym_now is near end of window but still open. File CS claim referencing correct
order ID before window closes; distractor second delivered order.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe, TaskSuite

TASK_ID = "mp_106/insurance_claim_photo_evidence_deadline"
BRIEF_KEY = "mp_106"
BRIEF = (
    "The package that showed up from Xmazon had a cracked speaker inside, I need "
    "to file a damage claim before the window closes. Check when it was delivered "
    "and get the claim in on time, referencing the actual order. Email me once "
    "it's filed."
)

USER_EMAIL = "alice@shopmail.com"
# Delivered May 10 → window window closes May 24. gym_now May 22 (still open).
DELIVERED_DAY = "2026-05-10"
CLAIM_DEADLINE = "2026-05-24"
GYM_NOW = "2026-05-22T11:00:00"
CLAIM_WINDOW_DAYS = 14

ORDER_SPEAKER = "ORD-MP106-RESONA"
LINE_SPEAKER = "ln_mp106_resona"
SKU_SPEAKER = "p_mp106_resona"
NAME_SPEAKER = "Resona Bluetooth Speaker"

ORDER_DECOY = "ORD-MP106-LAMP"
LINE_DECOY = "ln_mp106_lamp"
SKU_DECOY = "p_mp106_lamp"

_CLAIM_RE = re.compile(
    r"(?ix)\b(damage|cracked|broken|claim|insurance|defective|speaker)\b"
)
_ORDER_RE = re.compile(r"(?ix)\bord-mp106-resona\b")
_WRONG_ORDER_RE = re.compile(r"(?ix)\bord-mp106-lamp\b")
_DATE_RE = re.compile(
    r"(?ix)\b(may\s*10|2026-05-10|5/10|05/10|delivered\s+on)\b"
)
_WINDOW_RE = re.compile(
    r"(?ix)\b(14[\s-]?day|fourteen|claim\s+window|by\s+may\s*24|deadline|"
    r"before\s+(the\s+)?window|still\s+open)\b"
)


def task_mp_106_insurance_claim_photo_evidence_deadline(
    seed: int,
) -> "WorldState":
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Order, OrderItem, Product, Shipment, ShipmentEvent
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
    shop.support_tickets.clear()

    shop.products[SKU_SPEAKER] = Product(
        id=SKU_SPEAKER, name=NAME_SPEAKER, brand="Resona", category="electronics",
        base_price=79.99, rating=4.5, review_count=880, stock=30,
        image_emoji="🔊",
        short_description=(
            f"Portable Bluetooth speaker. Delivered {DELIVERED_DAY}. "
            f"Damage claims accepted within {CLAIM_WINDOW_DAYS} days of delivery "
            f"(window closes {CLAIM_DEADLINE})."
        ),
        tags=["resona", "speaker", "bluetooth"],
    )
    shop.products[SKU_DECOY] = Product(
        id=SKU_DECOY, name="Lumina Desk Lamp", brand="Lumina", category="home",
        base_price=34.99, rating=4.2, review_count=400, stock=50,
        image_emoji="💡",
        short_description="Decoy delivered order — not the cracked speaker.",
        tags=["lamp", "decoy"],
    )

    addr = shop.users["u_alice"].addresses["addr_home"]
    shop.orders[ORDER_SPEAKER] = Order(
        id=ORDER_SPEAKER, user_id="u_alice",
        placed_at="2026-05-05T12:00:00Z",
        items=[OrderItem(
            id=LINE_SPEAKER, product_id=SKU_SPEAKER, product_name=NAME_SPEAKER,
            variant_id=None, variant_label="", quantity=1, unit_price=79.99,
            gift_wrap=False, gift_message="", ship_to_address_id=addr.id,
            scheduled_delivery=None,
        )],
        subtotal=79.99, discount=0.0, tax=6.80, shipping=0.0,
        total=86.79, promo_code=None, payment_id="pay_visa",
        status="delivered",
        shipments=[Shipment(
            id="sh_mp106_resona", tracking_number="1Z999MP106RES",
            carrier="UPS", item_ids=[LINE_SPEAKER], status="delivered",
            estimated_delivery=f"Delivered May 10, 2026",
            events=[
                ShipmentEvent(
                    "2026-05-10T15:30:00Z", "delivered", "Brooklyn, NY",
                    "Delivered — left at front door. Damage claims: 14 days from delivery.",
                ),
            ],
        )],
    )
    shop.orders[ORDER_DECOY] = Order(
        id=ORDER_DECOY, user_id="u_alice",
        placed_at="2026-05-12T10:00:00Z",
        items=[OrderItem(
            id=LINE_DECOY, product_id=SKU_DECOY, product_name="Lumina Desk Lamp",
            variant_id=None, variant_label="", quantity=1, unit_price=34.99,
            gift_wrap=False, gift_message="", ship_to_address_id=addr.id,
            scheduled_delivery=None,
        )],
        subtotal=34.99, discount=0.0, tax=2.97, shipping=0.0,
        total=37.96, promo_code=None, payment_id="pay_visa",
        status="delivered",
        shipments=[Shipment(
            id="sh_mp106_lamp", tracking_number="1Z999MP106LMP",
            carrier="UPS", item_ids=[LINE_DECOY], status="delivered",
            estimated_delivery="Delivered May 18, 2026",
        )],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp106_policy"] = Email(
        id="em_mp106_policy",
        sender="care@shopgym.com",
        to=USER_EMAIL,
        subject="Xmazon damage claim window reminder",
        body=(
            "Reminder: file shipping-damage claims within 14 days of delivery "
            "via Customer Service Contact Us. Include your order number. "
            f"Today's gym date context: claims for May 10 deliveries close {CLAIM_DEADLINE}."
        ),
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=False,
        labels=["shopping"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_106_insurance_claim_photo_evidence_deadline,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _tickets(p: Probe) -> list:
        shop = getattr(p.world, "shop", None) if p.world else None
        if not shop:
            return []
        t = getattr(shop, "support_tickets", None) or {}
        return list(t.values()) if isinstance(t, dict) else list(t)

    def _tblob(t) -> str:
        if isinstance(t, dict):
            return f"{t.get('subject', '')}\n{t.get('body', '')}"
        return f"{getattr(t, 'subject', '')}\n{getattr(t, 'body', '')}"

    def _blob(msg) -> str:
        return f"{getattr(msg, 'subject', '') or ''}\n{getattr(msg, 'body', '') or ''}"

    def _to_alice(msg) -> bool:
        to = (getattr(msg, "to", "") or "").lower()
        return USER_EMAIL in to or "alice" in to

    def _identified_delivery(p: Probe) -> bool:
        if _log_has(p, "view_order") or _log_has(p, "view_tracking"):
            return True
        for msg in _sent(p):
            if _to_alice(msg) and _DATE_RE.search(_blob(msg)):
                return True
        for t in _tickets(p):
            if _DATE_RE.search(_tblob(t)):
                return True
        return False

    def _computed_window(p: Probe) -> bool:
        for msg in _sent(p):
            if _to_alice(msg) and _WINDOW_RE.search(_blob(msg)):
                return True
        for t in _tickets(p):
            if _WINDOW_RE.search(_tblob(t)):
                return True
        # Proxy: timely claim filed referencing speaker order while window open.
        return _filed_on_time(p) and _referenced_correct(p)

    def _filed_on_time(p: Probe) -> bool:
        for t in _tickets(p):
            text = _tblob(t)
            if _CLAIM_RE.search(text) and _ORDER_RE.search(text):
                return True
        return False

    def _referenced_correct(p: Probe) -> bool:
        for t in _tickets(p):
            if _ORDER_RE.search(_tblob(t)):
                return True
        return False

    def _emailed(p: Probe) -> bool:
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if "claim" in text or "filed" in text or "resona" in text or "speaker" in text:
                return True
        return False

    def _wrong_order(p: Probe) -> bool:
        for t in _tickets(p):
            text = _tblob(t)
            if _WRONG_ORDER_RE.search(text) and not _ORDER_RE.search(text):
                return True
            if _CLAIM_RE.search(text) and _WRONG_ORDER_RE.search(text) and "lamp" in text.lower():
                if not _ORDER_RE.search(text):
                    return True
        return False

    def _filed_after_closed(p: Probe) -> bool:
        # Window still open at gym_now — only fires if agent claims window closed
        # and therefore did NOT file, while also not filing. Soft: agent emails
        # that window closed when it was still open AND no ticket filed.
        filed = bool(_tickets(p))
        if filed:
            return False
        for msg in _sent(p):
            if not _to_alice(msg):
                continue
            text = _blob(msg).lower()
            if re.search(r"(?ix)(window\s+(has\s+)?closed|too\s+late|deadline\s+passed|missed\s+the\s+window)", text):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "identified_correct_delivery_date",
                    weight=0.2, check=_identified_delivery, required_for_success=True,
                ),
                Milestone(
                    "computed_claim_window_correctly",
                    weight=0.2, check=_computed_window, required_for_success=True,
                ),
                Milestone(
                    "filed_claim_before_window_closes",
                    weight=0.3, check=_filed_on_time, required_for_success=True,
                ),
                Milestone(
                    "referenced_correct_order_id",
                    weight=0.15, check=_referenced_correct, required_for_success=True,
                ),
                Milestone(
                    "emailed_user_confirmation",
                    weight=0.15, check=_emailed, required_for_success=True,
                ),
                Milestone(
                    "referenced_wrong_order_id",
                    weight=0.0, check=_wrong_order, forbidden=True,
                ),
                Milestone(
                    "filed_after_window_closed_when_window_was_still_open",
                    weight=0.0, check=_filed_after_closed, forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
