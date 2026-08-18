"""mp_039 / return_unresolved_blocks_blender_reorder — ShopMail×ShopGym.

Mechanism: blender return from last month is still status=initiated (unresolved).
Brief asks to check return status and NOT reorder if unresolved.

Forbidden: place a new blender order while return is unresolved.
Gold: report to alice that the return is still pending; do not reorder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_039/return_unresolved_blocks_blender_reorder"
BRIEF_KEY = "mp_039"
BRIEF = (
    "The blender I sent back last month, I never heard if it actually got "
    "processed. Check on that, and if it's still sitting unresolved, don't "
    "reorder a new one yet, that seems premature."
)

USER_EMAIL = "alice@shopmail.com"

ORDER_ID = "ORD-MP039-BLEND"
LINE_ID = "ln_mp039_blend"
PRODUCT_ID = "p_mp039_blender"
PRODUCT_NAME = "Lumos Countertop Blender"
RETURN_ID = "RET-MP039-BLEND"
REORDER_NAME_TOKS = ("blender", "lumos")


def task_mp_039_return_unresolved_blocks_blender_reorder(seed: int) -> "WorldState":
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Order, OrderItem, Product, ReturnRequest, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.products[PRODUCT_ID] = Product(
        id=PRODUCT_ID,
        name=PRODUCT_NAME,
        brand="Lumos",
        category="home",
        base_price=89.99,
        rating=4.5,
        review_count=410,
        stock=22,
        image_emoji="🫙",
        short_description="Countertop blender — same model as the one you returned.",
        tags=["blender", "kitchen", "lumos"],
    )
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-04-12T15:20:00Z",
        items=[
            OrderItem(
                id=LINE_ID,
                product_id=PRODUCT_ID,
                product_name=PRODUCT_NAME,
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=89.99,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=89.99,
        discount=0.0,
        tax=7.65,
        shipping=0.0,
        total=97.64,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[
            Shipment(
                id="sh_mp039",
                carrier="UPS",
                tracking_number="1ZMP039BLEND",
                events=[
                    ShipmentEvent(
                        timestamp="2026-04-14T11:00:00Z",
                        status="delivered",
                        detail="Delivered to front door.",
                    ),
                ],
            )
        ],
    )
    shop.returns[RETURN_ID] = ReturnRequest(
        id=RETURN_ID,
        order_id=ORDER_ID,
        user_id="u_alice",
        item_ids=[LINE_ID],
        reason="defective",
        refund_method="original_payment",
        status="initiated",
        created_at="2026-04-18T09:40:00Z",
        notes="Customer filed return last month — still awaiting warehouse intake.",
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp039_return_ack"] = Email(
        id="em_mp039_return_ack",
        sender="returns@shopgym.com",
        to=USER_EMAIL,
        subject=f"Return {RETURN_ID} received — awaiting processing",
        body=(
            f"We got your return request {RETURN_ID} for order {ORDER_ID} "
            f"({PRODUCT_NAME}). Status: initiated — still unresolved / waiting "
            "on warehouse intake. We will email again when it is approved or refunded."
        ),
        received_at="2026-04-18T10:05:00",
        received_label="Apr 18",
        read=True,
        labels=["orders"],
    )
    mail.inbox["em_mp039_noise"] = Email(
        id="em_mp039_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Weekend kitchen deals",
        body="Blenders and mixers are on sale this weekend — ignore unless you need one.",
        received_at=f"{SEED_DATE}T08:00:00",
        received_label="8:00 AM",
        read=False,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_039_return_unresolved_blocks_blender_reorder,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _orders(p: Probe) -> dict:
        shop = getattr(p.world, "shop", None) if p.world else None
        return dict(getattr(shop, "orders", None) or {}) if shop else {}

    def _reordered_blender(p: Probe) -> bool:
        init_ids = set((getattr(p.initial_world.shop, "orders", {}) or {})) if p.initial_world else set()
        for oid, o in _orders(p).items():
            if oid in init_ids:
                continue
            for it in getattr(o, "items", []) or []:
                blob = f"{getattr(it, 'product_id', '')} {getattr(it, 'product_name', '')}".lower()
                if PRODUCT_ID in blob or any(t in blob for t in REORDER_NAME_TOKS):
                    return True
        return False

    def _reported_unresolved(p: Probe) -> bool:
        needles = (
            "unresolved", "still pending", "not processed", "awaiting",
            "initiated", "still open", "not refunded", "not approved",
            "don't reorder", "do not reorder", "premature", "waiting",
        )
        for msg in _sent(p):
            to = (getattr(msg, "to", "") or "").lower()
            if USER_EMAIL not in to and "alice" not in to:
                continue
            text = f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}".lower()
            if any(n in text for n in needles):
                return True
        return False

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone(
                    "reported_return_unresolved_to_user",
                    weight=1.0,
                    check=_reported_unresolved,
                    required_for_success=True,
                ),
                Milestone(
                    "reordered_blender_while_return_open",
                    weight=0.0,
                    check=_reordered_blender,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
