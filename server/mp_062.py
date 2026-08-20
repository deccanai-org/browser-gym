"""mp_062 / return_window_and_replacement_stock — Xmazon×Xbay×(gym_now).

Extended: two delivered shoe orders — only one inside the 30-day return window.
Agent must return the in-window order, find a matching replacement on Xmazon
by spec (not the Xbay lookalike), pick an in-stock size, and stay at or
below the original paid price.

Note: returns are Xmazon-native (Xbay has no initiate_return). Purchase
orders live on Xmazon; Xbay holds a lookalike decoy for cross-shop match.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import TaskSuite

TASK_ID = "mp_062/return_window_and_replacement_stock"
BRIEF_KEY = "mp_062"
BRIEF = "These shoes don't fit right, can you deal with it."

USER_EMAIL = "alice@shopmail.com"
GYM_NOW = "2026-05-21T12:00:00"

# Returnable (delivered May 5 → 16 days ago, inside 30-day window)
ORDER_OK = "ORD-MP062-SHOES"
LINE_OK = "ln_mp062_shoes"
# Expired (delivered Apr 2 → 49 days ago)
ORDER_EXPIRED = "ORD-MP062-OLDSHOES"
LINE_EXPIRED = "ln_mp062_oldshoes"

ORIG_PRODUCT = "p_mp062_trailrun_orig"
ORIG_NAME = "TrailRun Flex Trainer"
ORIG_PRICE = 89.00
ORIG_SIZE = "9"

# Replacement catalog on Xmazon (same model family, size variants)
REPL_PRODUCT = "p_mp062_trailrun_repl"
REPL_NAME = "TrailRun Flex Trainer (Current)"
SIZE_OOS = "v_mp062_size9"      # size 9 out of stock
SIZE_OK = "v_mp062_size10"      # size 10 in stock, ≤ original
SIZE_PREMIUM = "v_mp062_size10x"  # size 10 premium > original

# Xbay decoy — similar name, wrong model / no size stock field parity
VM_DECOY = "vm_mp062_lookalike"


def task_mp_062_return_window_and_replacement_stock(seed: int) -> "WorldState":
    """FEASIBLE Shop×Market: return in-window shoes, reorder in-stock size ≤ paid."""
    from server.apps.calendar.state import CalendarEvent  # noqa: F401 — gym_now via cal
    from server.apps.mail.state import Email, SEED_DATE
    from server.apps.market.state import MarketProduct
    from server.state import Order, OrderItem, Product, ProductVariant, Shipment, ShipmentEvent
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, TASK_ID, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = TASK_ID
    world.shop.task_brief = BRIEF

    cal = world.calendar
    cal.gym_now = GYM_NOW

    shop = world.shop
    shop.products.clear()
    shop.cart.items.clear()
    shop.orders.clear()
    shop.returns.clear()

    shop.products[ORIG_PRODUCT] = Product(
        id=ORIG_PRODUCT, name=ORIG_NAME, brand="TrailRun", category="footwear",
        base_price=ORIG_PRICE, rating=4.4, review_count=880, stock=0,
        image_emoji="👟",
        short_description=(
            "TrailRun Flex Trainer size 9 — original purchase. "
            "Xmazon returns: 30 days from delivery."
        ),
        tags=["shoes", "trailrun", "original"],
    )
    shop.products[REPL_PRODUCT] = Product(
        id=REPL_PRODUCT, name=REPL_NAME, brand="TrailRun", category="footwear",
        base_price=85.00, rating=4.4, review_count=920, stock=0,
        image_emoji="👟",
        short_description=(
            "TrailRun Flex Trainer — same model as ORD-MP062-SHOES. "
            "Choose size; check stock before ordering."
        ),
        long_description=(
            "Spec match for the Flex Trainer: mesh upper, 8mm drop, road/trail. "
            "Size 9 currently out of stock. Size 10 standard in stock at $85. "
            "Size 10 Premium Carbon plate is $120."
        ),
        tags=["shoes", "trailrun", "replacement"],
        variants=[
            ProductVariant(
                id=SIZE_OOS, label="Size 9",
                attributes={"size": "9"}, price_delta=0.0, stock=0,
            ),
            ProductVariant(
                id=SIZE_OK, label="Size 10",
                attributes={"size": "10"}, price_delta=0.0, stock=14,
            ),
            ProductVariant(
                id=SIZE_PREMIUM, label="Size 10 Premium Carbon",
                attributes={"size": "10", "edition": "premium"},
                price_delta=35.00, stock=6,
            ),
        ],
    )

    def _shoe_order(oid, lid, placed, delivered, status_detail):
        item = OrderItem(
            id=lid, product_id=ORIG_PRODUCT, product_name=ORIG_NAME,
            variant_id=None, variant_label=f"Size {ORIG_SIZE}",
            quantity=1, unit_price=ORIG_PRICE,
            gift_wrap=False, gift_message="",
            ship_to_address_id="addr_home", scheduled_delivery=None,
        )
        sh = Shipment(
            id=f"sh_{oid}", tracking_number=f"1Z{oid[-6:]}", carrier="UPS",
            item_ids=[lid], status="delivered",
            estimated_delivery=f"Delivered {delivered[:10]}",
            events=[
                ShipmentEvent(placed, "label_created", "Origin", "Label created"),
                ShipmentEvent(delivered, "delivered", "Front door", status_detail),
            ],
        )
        shop.orders[oid] = Order(
            id=oid, user_id="u_alice", placed_at=placed,
            items=[item], subtotal=ORIG_PRICE, discount=0.0, tax=7.56,
            shipping=0.0, total=96.56, promo_code=None, payment_id="pay_visa",
            status="delivered", shipments=[sh],
        )

    _shoe_order(
        ORDER_OK, LINE_OK,
        "2026-05-02T14:00:00Z", "2026-05-05T16:00:00Z",
        "Delivered May 5, 2026 (16 days before today May 21) — inside 30-day return window.",
    )
    _shoe_order(
        ORDER_EXPIRED, LINE_EXPIRED,
        "2026-03-28T14:00:00Z", "2026-04-02T16:00:00Z",
        "Delivered Apr 2, 2026 (49 days before today May 21) — outside 30-day return window.",
    )

    world.market.store_name = "Xbay"
    world.market.products.clear()
    world.market.cart.items.clear()
    world.market.orders.clear()
    world.market.products[VM_DECOY] = MarketProduct(
        id=VM_DECOY,
        name="TrailRunner Flex-ish Trainer (Xbay)",
        category="footwear", price=72.00, emoji="👟",
        description=(
            "Lookalike name only — different last and drop. Not a spec match "
            "for the TrailRun Flex Trainer. Do not use as the replacement."
        ),
        in_stock=True, condition="New", shipping_cost=5.99,
        shop_sku=None,
    )

    mail = world.mail
    mail.inbox.clear()
    mail.sent.clear()
    mail.inbox["em_mp062_noise"] = Email(
        id="em_mp062_noise",
        sender="deals@shopgym.com",
        to=USER_EMAIL,
        subject="Running shoe clearance",
        body="Unrelated promo.",
        received_at=f"{SEED_DATE}T08:10:00",
        received_label="8:10 AM",
        read=True,
        labels=["promo"],
    )
    return world


TASK_FACTORIES: dict[str, Callable[[int], "WorldState"]] = {
    TASK_ID: task_mp_062_return_window_and_replacement_stock,
}
BRIEFS: dict[str, str] = {BRIEF_KEY: BRIEF}
START_URLS: dict[str, str] = {TASK_ID: "/"}
HINTS: dict[str, list] = {TASK_ID: []}


def suite_factories() -> dict[str, Callable[[], "TaskSuite"]]:
    from server.verifiers import Milestone, Probe, TaskSuite, _log_has

    def _shop(p: Probe):
        return getattr(p.world, "shop", None) if p.world else None

    def _returns(p: Probe) -> list:
        shop = _shop(p)
        return list((shop.returns or {}).values()) if shop else []

    def _new_orders(p: Probe) -> list:
        shop = _shop(p)
        if shop is None:
            return []
        init = set()
        if p.initial_world and getattr(p.initial_world, "shop", None):
            init = set((p.initial_world.shop.orders or {}) or {})
        return [
            o for oid, o in (shop.orders or {}).items()
            if oid not in init and (getattr(o, "status", "") or "") != "cancelled"
        ]

    def _return_on(p: Probe, oid: str) -> bool:
        return any(getattr(r, "order_id", "") == oid for r in _returns(p))

    def _identified_correct(p: Probe) -> bool:
        # Proxy: opened orders (or URL) and initiated return on the in-window order.
        viewed = _log_has(p, "view_orders") or "/orders" in (p.active_tab_url or p.url or "")
        return viewed and _return_on(p, ORDER_OK)

    def _did_not_touch_expired(p: Probe) -> bool:
        # Only credit after the correct return exists (avoids vacuous FOI true).
        return _return_on(p, ORDER_OK) and not _return_on(p, ORDER_EXPIRED)

    def _initiated_ok(p: Probe) -> bool:
        return _return_on(p, ORDER_OK)

    def _found_cross_shop(p: Probe) -> bool:
        # Viewed replacement product or has it in new orders / cart history via action log
        if _log_has(p, "view_product") or _log_has(p, "viewed_product"):
            # Accept if gold variant ordered or product page visited for REPL
            pass
        pids = {
            getattr(it, "product_id", "")
            for o in _new_orders(p) for it in (o.items or [])
        }
        shop = _shop(p)
        cart_pids = {
            getattr(it, "product_id", "")
            for it in ((shop.cart.items if shop else []) or [])
        }
        return REPL_PRODUCT in pids or REPL_PRODUCT in cart_pids or _log_has(p, "add_to_cart")

    def _checked_stock(p: Probe) -> bool:
        # Proxy: ordered in-stock size OR viewed product then did not order OOS
        return _reordered_ok(p) or (
            _log_has(p, "view_product") and not _reordered_oos(p)
        )

    def _repl_lines(p: Probe) -> list:
        return [
            it for o in _new_orders(p) for it in (o.items or [])
            if getattr(it, "product_id", "") == REPL_PRODUCT
        ]

    def _reordered_ok(p: Probe) -> bool:
        return any(getattr(it, "variant_id", None) == SIZE_OK for it in _repl_lines(p))

    def _reordered_oos(p: Probe) -> bool:
        return any(getattr(it, "variant_id", None) == SIZE_OOS for it in _repl_lines(p))

    def _price_ok(p: Probe) -> bool:
        lines = _repl_lines(p)
        if not lines:
            return False
        return all(
            float(getattr(it, "unit_price", 0) or 0) <= ORIG_PRICE + 1e-6
            for it in lines
        )

    def _returned_wrong(p: Probe) -> bool:
        return _return_on(p, ORDER_EXPIRED)

    def _paid_more(p: Probe) -> bool:
        return any(
            float(getattr(it, "unit_price", 0) or 0) > ORIG_PRICE + 1e-6
            for it in _repl_lines(p)
        )

    def _suite() -> TaskSuite:
        return TaskSuite(
            task_id=TASK_ID,
            milestones=[
                Milestone("identified_correct_returnable_order", weight=0.15,
                          check=_identified_correct, required_for_success=True),
                Milestone("did_not_touch_expired_order", weight=0.15,
                          check=_did_not_touch_expired, required_for_success=True),
                Milestone("initiated_return_correctly", weight=0.15,
                          check=_initiated_ok, required_for_success=True),
                Milestone("found_matching_item_cross_shop", weight=0.15,
                          check=_found_cross_shop, required_for_success=True),
                Milestone("checked_stock_before_ordering", weight=0.15,
                          check=_checked_stock, required_for_success=True),
                Milestone("reordered_in_stock_size", weight=0.15,
                          check=_reordered_ok, required_for_success=True),
                Milestone("price_at_or_below_original", weight=0.1,
                          check=_price_ok, required_for_success=True),
                Milestone("returned_wrong_order", weight=0.0,
                          check=_returned_wrong, required_for_success=False,
                          forbidden=True),
                Milestone("reordered_out_of_stock_size", weight=0.0,
                          check=_reordered_oos, required_for_success=False,
                          forbidden=True),
                Milestone("paid_more_than_original", weight=0.0,
                          check=_paid_more, required_for_success=False,
                          forbidden=True),
            ],
        )

    return {TASK_ID: _suite}
