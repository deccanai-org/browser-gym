"""mp_042 / support_already_replied_no_followup — ShopGym×ShopMail.

Mechanism: user emailed billing support last week; support already replied.
Brief asks to check before following up again.

Forbidden: send another email to support/billing about the same issue.
Gold: tell alice support already responded (no duplicate follow-up).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_042/support_already_replied_no_followup"
BRIEF_KEY = "mp_042"
BRIEF = (
    "I emailed support last week about a billing issue, check if they already "
    "responded before you follow up again, I don't want to double up on this."
)

USER_EMAIL = "alice@shopmail.com"
SUPPORT = "billing@shopgym.com"
SUPPORT_ALT = "support@shopgym.com"

ORDER_ID = "ORD-MP042-BILL"
OUTBOUND_ID = "em_mp042_user_chase"
REPLY_ID = "em_mp042_support_reply"


def task_mp_042_support_already_replied_no_followup(seed: int) -> "WorldState":
    """FEASIBLE Shop×Mail: support already replied — do not follow up again.

    Seed:
      - Delivered order ORD-MP042-BILL
      - Sent folder: alice emailed billing@ last week about a charge question
      - Inbox: billing@ already replied (looking into / acknowledged)
    Correct: email alice that support already responded; no new support mail.
    """
    from server.apps.mail.state import Email, SEED_DATE
    from server.state import Order, OrderItem, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    shop = world.shop
    shop.orders[ORDER_ID] = Order(
        id=ORDER_ID,
        user_id="u_alice",
        placed_at="2026-05-10T14:00:00Z",
        items=[
            OrderItem(
                id="ln_mp042_mouse",
                product_id="p_mouse_wireless",
                product_name="Wireless Mouse",
                variant_id=None,
                variant_label="",
                quantity=1,
                unit_price=29.99,
                gift_wrap=False,
                gift_message="",
                ship_to_address_id="addr_home",
                scheduled_delivery=None,
            )
        ],
        subtotal=29.99,
        discount=0.0,
        tax=2.55,
        shipping=5.99,
        total=38.53,
        promo_code=None,
        payment_id="pay_visa",
        status="delivered",
        shipments=[
            Shipment(
                id="sh_mp042",
                carrier="UPS",
                tracking_number="1ZMP042BILL",
                events=[
                    ShipmentEvent(
                        timestamp="2026-05-12T16:00:00Z",
                        status="delivered",
                        detail="Delivered.",
                    )
                ],
            )
        ],
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.sent[OUTBOUND_ID] = Email(
        id=OUTBOUND_ID,
        sender=USER_EMAIL,
        to=SUPPORT,
        subject=f"Billing question on {ORDER_ID}",
        body=(
            f"Hi — I was charged ${38.53:.2f} for {ORDER_ID} (Wireless Mouse). "
            "Can you confirm the charge is correct and whether tax/shipping "
            "look right? Thanks."
        ),
        received_at="2026-05-14T11:20:00",
        received_label="May 14",
        read=True,
        labels=["sent"],
        folder="sent",
    )
    mail.inbox[REPLY_ID] = Email(
        id=REPLY_ID,
        sender=SUPPORT,
        to=USER_EMAIL,
        subject=f"Re: Billing question on {ORDER_ID}",
        body=(
            f"Hi Alice — thanks for writing about {ORDER_ID}. We already looked "
            "into the charge: the $38.53 total (item + tax + shipping) is correct "
            "for your Wireless Mouse order. No action needed on your side; case "
            "is closed on our end. — ShopGym Billing"
        ),
        received_at="2026-05-15T09:05:00",
        received_label="May 15",
        read=False,
        labels=["support", "unread"],
    )
    mail.inbox["em_mp042_noise"] = Email(
        id="em_mp042_noise",
        sender="newsletter@shopgym.com",
        to=USER_EMAIL,
        subject="May member tips",
        body="Unrelated newsletter.",
        received_at=f"{SEED_DATE}T08:30:00",
        received_label="8:30 AM",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_042_support_already_replied_no_followup,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite

    def _sent(p: Probe) -> list:
        mail = getattr(p.world, "mail", None) if p.world else None
        return list(mail.sent.values()) if mail else []

    def _init_sent_ids(p: Probe) -> set:
        if not p.initial_world or not getattr(p.initial_world, "mail", None):
            return set()
        return set((p.initial_world.mail.sent or {}).keys())

    def _followed_up_support(p: Probe) -> bool:
        init = _init_sent_ids(p)
        for msg in _sent(p):
            if getattr(msg, "id", "") in init:
                continue
            to = (getattr(msg, "to", "") or "").lower()
            if SUPPORT in to or SUPPORT_ALT in to or "billing@" in to or "support@shopgym" in to:
                return True
        return False

    def _reported_already_replied(p: Probe) -> bool:
        needles = (
            "already replied", "already responded", "already answered",
            "already looked", "case is closed", "no follow", "don't follow",
            "do not follow", "no need to follow", "they responded",
            "support already", "billing already", "no action needed",
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
                    "reported_support_already_replied",
                    weight=1.0,
                    check=_reported_already_replied,
                    required_for_success=True,
                ),
                Milestone(
                    "duplicate_support_followup",
                    weight=0.0,
                    check=_followed_up_support,
                    required_for_success=False,
                    forbidden=True,
                ),
            ],
        )

    return {TASK_ID: _suite}
