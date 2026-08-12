"""Shared seed + verifier helpers for the mp_130–162 long-horizon suite.

Calendar has no guests field (M239) and no timezone field — attendees and
TZ offsets live in email bodies / event descriptions. Food schedule-ahead
is opted in per task via ``food.enable_schedule_ahead``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from server.apps.world import WorldState
    from server.verifiers import Probe

USER_EMAIL = "alice@shopmail.com"


def boot_world(seed: int, task_id: str, brief: str, gym_now: str) -> "WorldState":
    from server.tasks import _cross_app_world

    world = _cross_app_world(seed, task_id, "hard")
    world.mail.account_email = USER_EMAIL
    world.shop.task_id = task_id
    world.shop.task_brief = brief
    world.calendar.gym_now = gym_now
    world.calendar.events.clear()
    world.mail.inbox.clear()
    world.mail.sent.clear()
    world.food.restaurants.clear()
    world.food.cart.items.clear()
    world.food.orders.clear()
    world.shop.cart.items.clear()
    return world


def ev(
    *,
    eid: str,
    title: str,
    day: str,
    start: str,
    end: str,
    day_label: str = "",
    description: str = "",
    location: str = "",
    status: str = "confirmed",
    recurring: str = "none",
    source: str = "seed",
):
    from server.apps.calendar.state import CalendarEvent

    months = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
        "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
        "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
    }
    if not day_label and len(day) >= 10:
        y, m, d = day.split("-")
        day_label = f"{months.get(m, m)} {int(d)}"
    return CalendarEvent(
        id=eid,
        title=title,
        day=day,
        day_label=day_label or day,
        start=start,
        end=end,
        source=source,
        description=description,
        location=location,
        status=status,
        recurring=recurring,
    )


def mail(
    *,
    eid: str,
    sender: str,
    subject: str,
    body: str,
    received_at: str,
    received_label: str,
    to: str = USER_EMAIL,
    read: bool = False,
    cc: str = "",
):
    from server.apps.mail.state import Email

    return Email(
        id=eid,
        sender=sender,
        to=to,
        cc=cc,
        subject=subject,
        body=body,
        received_at=received_at,
        received_label=received_label,
        read=read,
        labels=[] if read else ["unread"],
    )


def dish(*, did: str, name: str, price: float, tags: list[str] | None = None,
         eta: str | None = None, desc: str = "", emoji: str = "🍽️", popular: bool = False):
    from server.apps.food.state import Dish

    return Dish(
        id=did,
        name=name,
        description=desc or name,
        price=price,
        tags=tags or [],
        emoji=emoji,
        popular=popular,
        eta_label=eta,
    )


def restaurant(*, rid: str, name: str, cuisine: str, eta: str, fee: float,
               dishes: list, rating: float = 4.5, emoji: str = "🍴",
               tmin: int = 20, tmax: int = 40):
    from server.apps.food.state import Restaurant

    return Restaurant(
        id=rid,
        name=name,
        cuisine=cuisine,
        rating=rating,
        eta_label=eta,
        delivery_fee=fee,
        emoji=emoji,
        dishes=dishes,
        delivery_time_min=tmin,
        delivery_time_max=tmax,
    )


def food_order(*, oid: str, rid: str, rname: str, items: list, fee: float,
               placed_at: str, eta: str, status: str = "delivered",
               scheduled: str | None = None, note: str = ""):
    from server.apps.food.state import FoodOrder

    sub = round(sum(i.unit_price * i.quantity for i in items), 2)
    return FoodOrder(
        id=oid,
        restaurant_id=rid,
        restaurant_name=rname,
        items=items,
        subtotal=sub,
        delivery_fee=fee,
        total=round(sub + fee, 2),
        placed_at=placed_at,
        eta_label=eta,
        status=status,
        delivery_note=note,
        scheduled_delivery=scheduled,
    )


def fitem(*, did: str, rid: str, name: str, price: float, qty: int = 1):
    from server.apps.food.state import FoodCartItem

    return FoodCartItem(
        dish_id=did, restaurant_id=rid, name=name, unit_price=price, quantity=qty,
    )


def product(*, pid: str, name: str, brand: str, category: str, price: float,
            stock: int = 12, desc: str = "", emoji: str = "📦", tags: list | None = None,
            variants: list | None = None):
    from server.state import Product

    return Product(
        id=pid,
        name=name,
        brand=brand,
        category=category,
        base_price=price,
        rating=4.4,
        review_count=80,
        stock=stock,
        image_emoji=emoji,
        short_description=desc or name,
        tags=tags or [],
        variants=variants or [],
    )


def mproduct(*, pid: str, name: str, category: str, price: float, desc: str = "",
             in_stock: bool = True, emoji: str = "📦", shop_sku: str | None = None):
    from server.apps.market.state import MarketProduct

    return MarketProduct(
        id=pid,
        name=name,
        category=category,
        price=price,
        emoji=emoji,
        description=desc or name,
        in_stock=in_stock,
        shop_sku=shop_sku,
    )


def shop_order(*, oid: str, items: list, placed_at: str, status: str = "delivered",
               total: float | None = None, shipping: float = 0.0, tax: float = 0.0,
               shipments: list | None = None):
    from server.state import Order

    sub = round(sum(it.unit_price * it.quantity for it in items), 2)
    return Order(
        id=oid,
        user_id="u_alice",
        placed_at=placed_at,
        items=items,
        subtotal=sub,
        discount=0.0,
        tax=tax,
        shipping=shipping,
        total=total if total is not None else round(sub + tax + shipping, 2),
        promo_code=None,
        payment_id="pay_visa",
        status=status,
        shipments=shipments or [],
    )


def oitem(*, iid: str, pid: str, name: str, price: float, qty: int = 1,
          variant_id=None, variant_label: str = "", addr: str = "addr_home"):
    from server.state import OrderItem

    return OrderItem(
        id=iid,
        product_id=pid,
        product_name=name,
        variant_id=variant_id,
        variant_label=variant_label,
        quantity=qty,
        unit_price=price,
        gift_wrap=False,
        gift_message="",
        ship_to_address_id=addr,
        scheduled_delivery=None,
    )


def shipment(*, sid: str, item_ids: list[str], status: str, eta: str,
             tracking: str = "1ZLH", delivered_at: str = "", detail: str = ""):
    from server.state import Shipment, ShipmentEvent

    events = []
    if delivered_at or detail:
        events.append(ShipmentEvent(
            timestamp=delivered_at or "2026-05-01T12:00:00Z",
            status=status,
            detail=detail or eta,
        ))
    return Shipment(
        id=sid,
        carrier="UPS",
        tracking_number=tracking,
        item_ids=item_ids,
        status=status,
        estimated_delivery=eta,
        events=events,
    )


def market_order(*, oid: str, items: list, placed_at: str, fee: float = 0.0,
                 status: str = "completed"):
    from server.apps.market.state import MarketOrder

    sub = round(sum(i.unit_price * i.quantity for i in items), 2)
    return MarketOrder(
        id=oid,
        items=items,
        subtotal=sub,
        discount=0.0,
        delivery_fee=fee,
        total=round(sub + fee, 2),
        placed_at=placed_at,
        status=status,
        shipping_address_id="addr_home",
        payment_id="pay_visa",
    )


def mitem(*, pid: str, name: str, price: float, qty: int = 1):
    from server.apps.market.state import MarketCartItem

    return MarketCartItem(product_id=pid, name=name, unit_price=price, quantity=qty)


# ----- verifier helpers ---------------------------------------------------- #

def new_cal_events(p: "Probe") -> list:
    cal = getattr(p.world, "calendar", None) if p.world else None
    init = getattr(p, "initial_world", None)
    init_ids = set(
        (init.calendar.events or {})
        if init and getattr(init, "calendar", None) else {}
    )
    if cal is None:
        return []
    return [e for eid, e in (cal.events or {}).items() if eid not in init_ids]


def cal_map(p: "Probe") -> dict:
    cal = getattr(p.world, "calendar", None) if p.world else None
    return dict(cal.events or {}) if cal else {}


def init_cal_map(p: "Probe") -> dict:
    init = getattr(p, "initial_world", None)
    if init and getattr(init, "calendar", None):
        return dict(init.calendar.events or {})
    return {}


def event_changed(p: "Probe", eid: str) -> bool:
    now = cal_map(p).get(eid)
    old = init_cal_map(p).get(eid)
    if now is None:
        return old is not None
    if old is None:
        return True
    return (now.start, now.end, now.day, now.status, now.title) != (
        old.start, old.end, old.day, old.status, old.title
    )


def event_deleted(p: "Probe", eid: str) -> bool:
    return eid in init_cal_map(p) and eid not in cal_map(p)


def new_food_orders(p: "Probe") -> list:
    food = getattr(p.world, "food", None) if p.world else None
    if food is None:
        return []
    init = getattr(p, "initial_world", None)
    init_ids = set(
        (init.food.orders or {}) if init and getattr(init, "food", None) else {}
    )
    return [
        o for oid, o in (food.orders or {}).items()
        if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
    ]


def new_shop_orders(p: "Probe") -> list:
    shop = getattr(p.world, "shop", None) if p.world else None
    if shop is None:
        return []
    init = getattr(p, "initial_world", None)
    init_ids = set(
        (init.shop.orders or {}) if init and getattr(init, "shop", None) else {}
    )
    return [
        o for oid, o in (shop.orders or {}).items()
        if oid not in init_ids and (getattr(o, "status", "") or "") != "cancelled"
    ]


def new_market_orders(p: "Probe") -> list:
    market = getattr(p.world, "market", None) if p.world else None
    if market is None:
        return []
    init = getattr(p, "initial_world", None)
    init_ids = set(
        (init.market.orders or {}) if init and getattr(init, "market", None) else {}
    )
    return [o for oid, o in (market.orders or {}).items() if oid not in init_ids]


def alice_blob(p: "Probe") -> str:
    mail_s = getattr(p.world, "mail", None) if p.world else None
    if mail_s is None:
        return ""
    parts = []
    for msg in (mail_s.sent or {}).values():
        to = (getattr(msg, "to", "") or "").lower()
        cc = (getattr(msg, "cc", "") or "").lower()
        if USER_EMAIL in to or "alice" in to or USER_EMAIL in cc or "alice" in cc:
            parts.append(f"{getattr(msg, 'subject', '')}\n{getattr(msg, 'body', '')}")
    return "\n".join(parts)


def emailed_alice(p: "Probe", pattern=None) -> bool:
    blob = alice_blob(p)
    if not blob.strip():
        return False
    if pattern is None:
        return True
    return bool(pattern.search(blob))


def mail_read(p: "Probe", eid: str) -> bool:
    from server.verifiers import _log_has

    mail_s = getattr(p.world, "mail", None) if p.world else None
    if mail_s and eid in (mail_s.inbox or {}) and mail_s.inbox[eid].read:
        return True
    return _log_has(p, "view_email", email_id=eid)


def viewed_cal(p: "Probe") -> bool:
    from server.verifiers import _log_has

    if _log_has(p, "viewed_calendar") or _log_has(p, "viewed_event_edit"):
        return True
    return "/calendar" in (p.active_tab_url or p.url or "")


def viewed_order(p: "Probe", oid: str | None = None) -> bool:
    from server.verifiers import _log_has

    if oid and (_log_has(p, "view_order", order_id=oid) or _log_has(p, "view_order_detail", order_id=oid)):
        return True
    return _log_has(p, "view_orders") or "/account/orders" in (p.url or "")


def shop_bought(p: "Probe", pids: Iterable[str]) -> bool:
    want = set(pids)
    for o in new_shop_orders(p):
        for it in getattr(o, "items", []) or []:
            if getattr(it, "product_id", "") in want:
                return True
    return False


def market_bought(p: "Probe", pids: Iterable[str]) -> bool:
    want = set(pids)
    for o in new_market_orders(p):
        for it in getattr(o, "items", []) or []:
            if getattr(it, "product_id", "") in want:
                return True
    return False


def food_from(p: "Probe", rids: Iterable[str]) -> bool:
    want = set(rids)
    return any(getattr(o, "restaurant_id", "") in want for o in new_food_orders(p))


def any_new_food(p: "Probe") -> bool:
    return bool(new_food_orders(p))


def any_new_shop(p: "Probe") -> bool:
    return bool(new_shop_orders(p))


def any_new_market(p: "Probe") -> bool:
    return bool(new_market_orders(p))


def new_spend(p: "Probe") -> float:
    total = 0.0
    for o in new_shop_orders(p):
        total += float(getattr(o, "total", 0) or 0)
    for o in new_market_orders(p):
        total += float(getattr(o, "total", 0) or 0)
    for o in new_food_orders(p):
        total += float(getattr(o, "total", 0) or 0)
    return round(total, 2)


def n_cal_mutations(p: "Probe") -> int:
    n = 0
    now = cal_map(p)
    old = init_cal_map(p)
    for eid, e in now.items():
        if eid not in old:
            n += 1
        elif event_changed(p, eid):
            n += 1
    for eid in old:
        if eid not in now:
            n += 1
    return n


def eta_compact(label: str) -> str:
    return (label or "").lower().replace(" ", "")
