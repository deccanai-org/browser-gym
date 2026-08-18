"""ValueMart store — MarketState (catalog, cart, orders, coupons).

Wholly separate from the main ShopGym store (``GymState``); nothing here
references it. Prices/coupons/fees are FIXED so a reset for a given seed
reproduces an identical store — the environment-correctness gate requires
deterministic episodes.

ValueMart is the discount-retailer foil to ShopGym. Several products OVERLAP
ShopGym by name (so a cross-retailer price comparison is meaningful) but at
DIFFERENT prices — cheaper on some, pricier on others — plus a flat delivery
fee (free over a threshold) and a store-only coupon. So the cheaper store is
only knowable after computing the FINAL total (price - coupon + delivery), not
from the sticker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEED_DATE = "2026-05-21"


@dataclass
class MarketProduct:
    id: str
    name: str
    category: str
    price: float
    emoji: str = "📦"
    description: str = ""
    in_stock: bool = True
    # The ShopGym product_id this item overlaps (same physical product, other
    # store), or None for a ValueMart exclusive. Lets a cross-retailer verifier
    # line up "the same SKU" across the two stores without fuzzy name matching.
    shop_sku: str | None = None
    # Optional per-listing seller (ebay_mock / ValueMart). When set, transform
    # projects a distinct user with this feedback score/rating instead of the
    # single store-wide seller. Used by seller-rating comparison tasks.
    seller_id: str | None = None
    seller_username: str | None = None
    seller_feedback_score: int | None = None
    seller_feedback_rating: float | None = None
    # Optional listing condition (Used / New / …) for seller-create flows.
    condition: str | None = None
    # Per-listing BIN shipping (projected as listing.shipping / shippingCost).
    shipping_cost: float = 0.0
    # Explicit brand for ebay_mock Brand facet (Search.jsx prefers listing.brand
    # over title-keyword inference). Required when title keywords would map to
    # the wrong store brand (e.g. "coffee" → HomeChef).
    brand: str | None = None
    # Set on agent-created listings when the task supplies a fair-price band:
    # True = within band, False = outside. Catalog seed rows leave this None.
    fair_priced: bool | None = None
    # Optional local-pickup window copy projected to the tip PDP as a shipping-
    # style row (``pickupWindow``: truck + "Local pickup" + window). Prefer this
    # over burying hours only in ``description`` when a task scores schedule
    # alignment. Do not surface as a large amber banner.
    pickup_window: str | None = None


@dataclass
class MarketCartItem:
    product_id: str
    name: str
    unit_price: float
    quantity: int


@dataclass
class MarketCart:
    items: list[MarketCartItem] = field(default_factory=list)
    applied_coupon: str | None = None

    def subtotal(self) -> float:
        return round(sum(i.unit_price * i.quantity for i in self.items), 2)

    def count(self) -> int:
        return sum(i.quantity for i in self.items)


@dataclass
class MarketCoupon:
    code: str
    percent_off: float                 # 0.10 == 10% off
    min_subtotal: float = 0.0
    description: str = ""
    expired: bool = False              # a decoy code the store rejects at checkout


@dataclass
class MarketAddress:
    id: str
    full_name: str
    street: str
    city: str
    state: str
    zip: str
    country: str = "United States"
    is_default: bool = False


@dataclass
class MarketPayment:
    id: str
    brand: str            # "Visa", "Mastercard", "PayPal"
    last4: str = ""
    expiry: str = ""
    is_default: bool = False


@dataclass
class MarketOrder:
    id: str
    items: list[MarketCartItem]
    subtotal: float
    discount: float
    delivery_fee: float
    total: float
    placed_at: str
    coupon_code: str | None = None
    # The address + payment chosen at checkout (recorded on the order so a
    # verifier can confirm the order actually shipped/charged to a selection,
    # not to nothing). Default to the account defaults when none is passed.
    shipping_address_id: str | None = None
    payment_id: str | None = None
    # Optional fulfillment status for purchase-history UI / verifiers.
    status: str = "completed"


@dataclass
class MarketMessage:
    """Buyer↔seller message projected into ebay_mock ``messages[]``.

    ``from_id`` / ``to_id`` are mock user ids (``user_1`` buyer, or a
    ``seller_*`` id from ``MarketProduct.seller_id``).
    """
    id: str
    from_id: str
    to_id: str
    listing_id: str
    subject: str
    content: str
    read: bool = False
    # Unix ms — ebay_mock renders via ``new Date(timestamp)``.
    timestamp: int = 0




@dataclass
class MarketMembership:
    """ValueMart Plus (or similar) membership — used by confirmshame cancel tasks."""
    id: str = "vm_plus"
    plan_name: str = "ValueMart Plus"
    status: str = "active"  # active | cancelled
    price_monthly: float = 9.99
    perks_summary: str = "Free shipping + member deals"


@dataclass
class MarketSellerListing:
    """Agent-created durable seller listing (ValueMart sell flow)."""
    id: str
    title: str
    description: str
    price: float
    condition: str = "Used"
    category: str = "Electronics"
    shipping: float = 0.0
    status: str = "active"  # active | ended

@dataclass
class MarketState:
    store_name: str = "ValueMart"
    products: dict[str, MarketProduct] = field(default_factory=dict)
    cart: MarketCart = field(default_factory=MarketCart)
    orders: dict[str, MarketOrder] = field(default_factory=dict)
    coupons: dict[str, MarketCoupon] = field(default_factory=dict)
    addresses: dict[str, MarketAddress] = field(default_factory=dict)
    payments: dict[str, MarketPayment] = field(default_factory=dict)
    messages: list[MarketMessage] = field(default_factory=list)
    membership: MarketMembership | None = None
    seller_listings: dict[str, MarketSellerListing] = field(default_factory=dict)
    # When True, first create_listing call returns ok but does not persist (silent noop).
    silent_noop_first_listing: bool = False
    create_listing_attempts: int = 0
    enable_seller_create: bool = False
    enable_membership_cancel: bool = False
    delivery_fee: float = 5.99
    free_delivery_over: float = 35.0   # free delivery when SUBTOTAL >= this
    _next: int = 1
    _listing_next: int = 1

    # ----- helpers -------------------------------------------------------- #
    def new_order_id(self) -> str:
        oid = f"VM-{2200 + self._next}"
        self._next += 1
        return oid

    def new_listing_id(self) -> str:
        lid = f"lst_vm_{2200 + self._listing_next}"
        self._listing_next += 1
        return lid

    def product(self, product_id: str) -> MarketProduct | None:
        return self.products.get(product_id)

    def default_address_id(self) -> str | None:
        for a in self.addresses.values():
            if a.is_default:
                return a.id
        return next(iter(self.addresses), None)

    def default_payment_id(self) -> str | None:
        for p in self.payments.values():
            if p.is_default:
                return p.id
        return next(iter(self.payments), None)

    def delivery_for(self, subtotal: float) -> float:
        """Delivery is charged on the SUBTOTAL (pre-discount), free over the
        threshold — so adding a coupon never silently removes free shipping."""
        return 0.0 if subtotal >= self.free_delivery_over else self.delivery_fee

    def quote(self, *, subtotal: float, coupon_code: str | None) -> dict[str, float]:
        """Final-total breakdown for a given subtotal + optional coupon. Single
        source of truth used by mutations AND the cross-retailer verifier so the
        'which store is cheaper' math can never drift between them."""
        discount = 0.0
        c = self.coupons.get((coupon_code or "").upper()) if coupon_code else None
        if c is not None and not c.expired and subtotal >= c.min_subtotal:
            discount = round(subtotal * c.percent_off, 2)
        delivery = self.delivery_for(subtotal)
        total = round(subtotal - discount + delivery, 2)
        return {"subtotal": subtotal, "discount": discount,
                "delivery_fee": delivery, "total": total}

    # ----- snapshot ------------------------------------------------------- #
    def to_json(self) -> dict[str, Any]:
        return {
            "store_name": self.store_name,
            "products": {k: asdict(v) for k, v in self.products.items()},
            "cart": asdict(self.cart),
            "cart_count": self.cart.count(),
            "cart_subtotal": self.cart.subtotal(),
            "orders": {k: asdict(v) for k, v in self.orders.items()},
            "coupons": {k: asdict(v) for k, v in self.coupons.items()},
            "addresses": {k: asdict(v) for k, v in self.addresses.items()},
            "payments": {k: asdict(v) for k, v in self.payments.items()},
            "default_address_id": self.default_address_id(),
            "default_payment_id": self.default_payment_id(),
            "messages": [asdict(v) for v in self.messages],
            "membership": asdict(self.membership) if self.membership else None,
            "seller_listings": {k: asdict(v) for k, v in self.seller_listings.items()},
            "silent_noop_first_listing": self.silent_noop_first_listing,
            "create_listing_attempts": self.create_listing_attempts,
            "enable_seller_create": self.enable_seller_create,
            "enable_membership_cancel": self.enable_membership_cancel,
            "delivery_fee": self.delivery_fee,
            "free_delivery_over": self.free_delivery_over,
        }


# ShopGym overlaps: (vm_id, name, vm_price, shop_sku, shop_price_for_reference)
# Neither store is uniformly cheaper — ValueMart wins on mouse/keyboard/laptop,
# ShopGym wins on monitor/headphones — and ValueMart's $5.99 delivery (free over
# $35) + the VALUE10 coupon can flip the final-total comparison either way.
def make_marketstate(seed: int = 0) -> MarketState:
    m = MarketState()
    rows = [
        # id,               name,                          cat,           price,  emoji, shop_sku
        ("vm_mouse_wireless", "Wireless Mouse",            "electronics", 24.99, "🖱️", "p_mouse_wireless"),
        ("vm_kb_mech",        "Mechanical Keyboard",        "electronics", 109.99, "⌨️", "p_kb_mech"),
        ("vm_kb_wireless",    "Wireless Keyboard",          "electronics", 54.99, "⌨️", "p_kb_wireless"),
        ("vm_monitor_24",     "24-inch Monitor",            "electronics", 209.99, "🖥️", "p_monitor_24"),
        ("vm_laptop_studio",  "Studio Laptop 14",           "electronics", 879.99, "💻", "p_laptop_studio"),
        ("vm_hp_premium",     "Bluetooth Headphone Premium","audio",       259.99, "🎧", "p_hp_premium"),
        ("vm_coffee_pods",    "Coffee Pods (24-pack)",      "grocery",     9.49,  "☕", None),
        # ValueMart exclusives
        ("vm_usb_cable",      "USB-C Cable 2m",             "electronics", 6.99,  "🔌", None),
        ("vm_chair",          "Office Chair",               "home",        94.99, "🪑", None),
    ]
    descriptions = {
        "vm_mouse_wireless": "Everyday 2.4GHz wireless mouse with USB receiver.",
        "vm_kb_mech": "Hot-swappable mechanical keyboard, 75% layout.",
        "vm_kb_wireless": "Slim low-profile wireless keyboard.",
        "vm_monitor_24": "1080p 24-inch IPS monitor.",
        "vm_laptop_studio": "14-inch creator laptop, 16GB / 512GB.",
        "vm_hp_premium": "Over-ear ANC headphones, 30h battery.",
        "vm_coffee_pods": "Medium-roast espresso capsules, 24 count.",
        "vm_usb_cable": "Braided USB-C to USB-C cable, 2 meters.",
        "vm_chair": "Mesh-back ergonomic office chair.",
    }
    for pid, name, cat, price, emoji, sku in rows:
        m.products[pid] = MarketProduct(
            id=pid, name=name, category=cat, price=price, emoji=emoji,
            description=descriptions.get(pid, ""), in_stock=True, shop_sku=sku)
    # A store-ONLY coupon — the cross-retailer trap: it can flip which store is
    # cheaper, and it does NOT exist on ShopGym.
    m.coupons["VALUE10"] = MarketCoupon(
        code="VALUE10", percent_off=0.10, min_subtotal=0.0,
        description="10% off your ValueMart order")
    # A shipping address + payment methods on file, so checkout has a real
    # address/payment selection (matching ShopGym's Alice) instead of nothing.
    m.addresses["vm_addr_home"] = MarketAddress(
        id="vm_addr_home", full_name="Alice Anderson", street="100 Park Avenue, Apt 4B",
        city="Brooklyn", state="NY", zip="11201", country="United States", is_default=True)
    m.payments["vm_pay_visa"] = MarketPayment(
        id="vm_pay_visa", brand="Visa", last4="4242", expiry="08/27", is_default=True)
    m.payments["vm_pay_mc"] = MarketPayment(
        id="vm_pay_mc", brand="Mastercard", last4="5309", expiry="03/26")
    m.payments["vm_pay_paypal"] = MarketPayment(id="vm_pay_paypal", brand="PayPal")
    return m
