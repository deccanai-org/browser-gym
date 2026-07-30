"""Export a gym task's seed world into the cua-hub / cua-gym `mock_states` shape.

Pipeline:  dump  ->  transform  ->  load

  dump       the gym's full per-app world for a (task_id, seed)  [reuses build_wrapped]
  transform  per app, gym shape  ->  cua-hub mock_states JSON shape
  load       mint a seed_sid per (task, mock); INSERT into cua-gym mock_states +
             an initial `set` mock_state_events row

Phase-1 pilot status:
  * dump + the MAIL transform are complete (the gmail_mock shape is known from
    real cua-gym rows).
  * shop/market/calendar/food transforms are STUBS — each needs the target
    mock_states schema from Kashyap (or read from cua-gym) before it can be filled.
  * load is DRY-RUN by default: the exact cua-gym write contract + DB access come
    from Kashyap/Ganesh. Pass --commit + CUA_GYM_DSN to actually write.

Run:
  python -m tools.seed_to_cuagym --task M1 --seed 0            # dry-run, prints JSON
  python -m tools.seed_to_cuagym --task M1 --seed 0 --app mail
  CUA_GYM_DSN=postgres://... python -m tools.seed_to_cuagym --task M1 --seed 0 --commit
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import uuid
from typing import Any, Callable

from server.seeddb._equiv import build_wrapped

# gym app key -> cua-hub mock key (the `mock` column in cua-gym.mock_state_events)
APP_TO_MOCK = {
    "shop": "amazon_mock",
    "mail": "gmail_mock",
    "market": "ebay_mock",
    "calendar": "google_calendar",
    "food": "uber_eats_mock",
}


# --------------------------------------------------------------- dump ----------
def dump_world(task_id: str, seed: int) -> dict[str, Any]:
    """The FULL per-app world for (task_id, seed) as plain dicts.

    Uses asdict (not to_json) so the whole graph is present — to_json drops the
    shop catalog and a few hidden fields, which a mock seed still needs.
    """
    return dataclasses.asdict(build_wrapped(task_id, seed))


# ----------------------------------------------------------- transforms --------
def _display_name(addr: str | None) -> str:
    if not addr:
        return ""
    local = addr.split("@", 1)[0]
    return local.replace(".", " ").replace("_", " ").title()


_GMAIL_LABELS = [
    {"id": "l1", "name": "Work", "color": "#ef4444"},
    {"id": "l2", "name": "Personal", "color": "#3b82f6"},
    {"id": "l3", "name": "Travel", "color": "#22c55e"},
    {"id": "l4", "name": "Finance", "color": "#eab308"},
]


def _iso(ts: str | None) -> str | None:
    if not ts:
        return None
    return ts if (ts.endswith("Z") or "+" in ts) else ts + "Z"


def transform_mail(mail: dict) -> dict:
    """gym MailState -> gmail_mock state (see CUA-Gym-Hub websites/gmail_mock/SCHEMA.md).

    gym:    {account_email, account_name, inbox/sent/drafts: {id: email}, ...}
    gmail:  {user:{userId,username,email,avatar}, emails:[{id, threadId, from, to:[{name,email}],
             cc, bcc, subject, body(html), timestamp, read, starred, important, labels,
             category, folder, attachments}], labels:[...], drafts:[], settings:{...}}
    """
    account = mail.get("account_email") or ""
    name = mail.get("account_name") or _display_name(account)
    emails: list[dict] = []
    for folder in ("inbox", "sent", "drafts"):
        for e in (mail.get(folder) or {}).values():
            to_addr = e.get("to") or account
            emails.append({
                "id": e.get("id"),
                "threadId": f"thread_{e.get('id')}",
                "from": {"name": _display_name(e.get("sender")), "email": e.get("sender")},
                "to": [{"name": _display_name(to_addr), "email": to_addr}],
                "cc": [],
                "bcc": [],
                "subject": e.get("subject") or "",
                "body": (e.get("body") or "").replace("\n", "<br>"),
                "timestamp": _iso(e.get("received_at")),
                "read": bool(e.get("read")),
                "starred": False,
                "important": False,
                "labels": [],
                "category": "primary",
                "folder": e.get("folder") or folder,
                "attachments": [],
            })
    return {
        "user": {"userId": "u1", "username": name, "email": account, "avatar": None},
        "emails": emails,
        "labels": list(_GMAIL_LABELS),
        "drafts": [],
        "settings": {"density": "default", "undoSend": 10, "signature": f"--\n{name}",
                     "categoryTabs": {"primary": True, "social": True, "promotions": True,
                                      "updates": False, "forums": False},
                     "replyBehavior": "Reply", "language": "English (US)",
                     "sysLabelShown": {}, "userLabelShown": {}},
    }


def _picsum(key: str, size: str = "400/400") -> str:
    return f"https://picsum.photos/seed/{key}/{size}"


# --- amazon (gym shop) -------------------------------------------------------
_AMAZON_CAT = {
    "electronics": "Electronics", "audio": "Electronics",
    "books": "Books", "book": "Books",
    "home": "Home & Kitchen", "kitchen": "Home & Kitchen", "grocery": "Home & Kitchen",
    "fashion": "Fashion", "clothing": "Fashion", "apparel": "Fashion",
    "toys": "Toys & Games", "games": "Toys & Games", "beauty": "Beauty",
}


_AMZ_STATUS = {
    "placed": "Processing", "pending": "Processing", "confirmed": "Processing",
    "paid": "Processing", "processing": "Processing", "preparing": "Processing",
    "shipped": "Shipped", "in_transit": "Shipped",
    "out_for_delivery": "Out for Delivery",
    "delivered": "Delivered", "completed": "Delivered",
    "cancelled": "Cancelled", "canceled": "Cancelled",
    "returned": "Returned", "refunded": "Returned",
}
_FOOD_STATUS = {
    "placed": "placed", "pending": "placed", "confirmed": "placed",
    "preparing": "preparing", "cooking": "preparing",
    "on_the_way": "on_the_way", "out_for_delivery": "on_the_way",
    "delivered": "delivered", "completed": "delivered", "cancelled": "cancelled",
}


_UBER_CATEGORIES = [
    {"id": "cat_1", "name": "Pizza", "icon": "\U0001F355"}, {"id": "cat_2", "name": "Burgers", "icon": "\U0001F354"},
    {"id": "cat_3", "name": "Sushi", "icon": "\U0001F363"}, {"id": "cat_4", "name": "Chinese", "icon": "\U0001F961"},
    {"id": "cat_5", "name": "Mexican", "icon": "\U0001F32E"}, {"id": "cat_6", "name": "Indian", "icon": "\U0001F35B"},
    {"id": "cat_7", "name": "Thai", "icon": "\U0001F35C"}, {"id": "cat_8", "name": "Italian", "icon": "\U0001F35D"},
    {"id": "cat_9", "name": "Healthy", "icon": "\U0001F957"}, {"id": "cat_10", "name": "Dessert", "icon": "\U0001F370"},
    {"id": "cat_11", "name": "Coffee", "icon": "☕"}, {"id": "cat_12", "name": "Breakfast", "icon": "\U0001F95E"},
    {"id": "cat_13", "name": "Sandwich", "icon": "\U0001F96A"}, {"id": "cat_14", "name": "Korean", "icon": "\U0001F372"},
    {"id": "cat_15", "name": "Mediterranean", "icon": "\U0001F959"},
]
_UBER_ADDR = {"id": "addr_1", "label": "Home", "street": "123 Main St", "apt": "", "city": "San Francisco",
              "state": "CA", "zip": "94102", "instructions": "", "isDefault": True}
_UBER_PAY = {"id": "pay_1", "type": "visa", "label": "Visa •••• 4242", "last4": "4242", "isDefault": True}
# Fallback amazon address/payment so checkout never renders zero options for a
# user-less task (real users map from the gym; this only fires when there is none).
_AMZ_ADDR = {"id": "addr_default", "fullName": "Alice Anderson", "street": "100 Park Avenue, Apt 4B",
             "city": "Brooklyn", "state": "NY", "zip": "11201", "country": "United States",
             "phone": "555-0123", "isDefault": True}
_AMZ_PAY = {"id": "pay_default", "last4": "4242", "brand": "Visa", "expiry": "08/27", "isDefault": True}


def _last4(label: str | None) -> str:
    import re
    m = re.search(r"(\d{4})", label or "")
    return m.group(1) if m else "0000"


def _pay_brand(pm: dict) -> str:
    kind = (pm.get("kind") or "").lower()
    label = pm.get("label") or ""
    if kind in ("credit_card", "card", ""):
        return label.split()[0] if label else "Card"
    return {"paypal": "PayPal", "apple_pay": "Apple Pay", "gift_card": "Gift Card"}.get(kind, kind.title() or "Card")


def _amazon_address(a: dict) -> dict:
    street = a.get("line1") or ""
    if a.get("line2"):
        street = f"{street}, {a['line2']}"
    return {"id": a.get("id"), "fullName": a.get("full_name"), "street": street,
            "city": a.get("city"), "state": a.get("state"), "zip": a.get("zip"),
            "country": "United States", "phone": "555-0123", "isDefault": bool(a.get("is_default"))}


def _amazon_payment(p: dict) -> dict:
    return {"id": p.get("id"), "last4": _last4(p.get("label")), "brand": _pay_brand(p),
            "expiry": p.get("expires") or "", "isDefault": bool(p.get("is_default"))}


def transform_shop(shop: dict) -> dict:
    """gym GymState -> amazon_mock (products[], user, cart[], orders[], reviews[])."""
    users = shop.get("users") or {}
    uid = shop.get("current_user_id")
    gu = users.get(uid) if uid else next(iter(users.values()), None)

    products, reviews = [], []
    for p in (shop.get("products") or {}).values():
        stock = p.get("stock") or 0
        products.append({
            "id": p["id"], "title": p.get("name"), "price": p.get("base_price"),
            "originalPrice": None, "rating": p.get("rating"), "reviewCount": p.get("review_count"),
            "image": _picsum(p["id"]), "images": [_picsum(p["id"])],
            "description": p.get("long_description") or p.get("short_description") or "",
            "bulletPoints": p.get("tags") or [],
            "specs": {"Brand": p.get("brand"), "Weight": f"{p.get('weight_kg')} kg", "Emoji": p.get("image_emoji")},
            "category": _AMAZON_CAT.get((p.get("category") or "").lower(), "Electronics"),
            "brand": p.get("brand"), "prime": True, "inStock": stock > 0, "stockCount": stock,
            "seller": "Amazon.com", "badges": (["Best Seller"] if (p.get("rating") or 0) >= 4.5 else []),
            "createdAt": "2024-01-01T00:00:00.000Z",
        })
        for r in (p.get("reviews") or []):
            reviews.append({"id": r.get("id"), "productId": p["id"], "userId": uid or "u1",
                            "userName": r.get("author"), "rating": r.get("rating"), "title": r.get("title"),
                            "content": r.get("body"), "date": "2024-01-01T00:00:00.000Z", "helpful": 0,
                            "verifiedPurchase": bool(r.get("verified_purchase"))})

    addrs = [_amazon_address(a) for a in ((gu or {}).get("addresses") or {}).values()]
    pays = [_amazon_payment(p) for p in ((gu or {}).get("payment_methods") or {}).values()]
    # Checkout renders zero radio options on an empty list -> always guarantee >=1.
    if not addrs:
        addrs = [dict(_AMZ_ADDR)]
    if not pays:
        pays = [dict(_AMZ_PAY)]
    def_addr = next((a for a in addrs if a["isDefault"]), addrs[0])
    def_pay = next((p for p in pays if p["isDefault"]), pays[0])
    user = {"id": (gu or {}).get("id", "u1"), "name": (gu or {}).get("full_name", "Alice Anderson"),
            "email": (gu or {}).get("email", "alice@example.com"),
            "address": def_addr, "addresses": addrs, "paymentMethod": def_pay, "paymentMethods": pays}

    agg: dict = {}
    for it in ((shop.get("cart") or {}).get("items") or []):
        pid = it.get("product_id")
        agg[pid] = agg.get(pid, 0) + (it.get("quantity") or 1)
    cart = [{"productId": pid, "quantity": q} for pid, q in agg.items()]

    # returns: a gym ReturnRequest flips its order's amazon status to "Returned"
    returned_order_ids = {r.get("order_id") for r in (shop.get("returns") or {}).values()}
    orders = []
    for o in (shop.get("orders") or {}).values():
        status = "Returned" if o.get("id") in returned_order_ids else \
            _AMZ_STATUS.get((o.get("status") or "").lower(), "Delivered")
        orders.append({"id": o.get("id"), "date": o.get("placed_at") or "2024-01-01T00:00:00.000Z",
                       "status": status, "total": o.get("total"),
                       "items": [{"productId": i.get("product_id"), "quantity": i.get("quantity") or 1}
                                 for i in (o.get("items") or [])],
                       "shippingAddress": user.get("address"), "paymentMethod": user.get("paymentMethod"),
                       # tracking # + eta come from the order's first shipment so the
                       # realistic UI actually shows the live tracking an agent must read.
                       "trackingNumber": (o.get("shipments") or [{}])[0].get("tracking_number"),
                       "estimatedDelivery": (o.get("shipments") or [{}])[0].get("estimated_delivery")})

    # promotions -> a strikethrough deal price on the targeted product (amazon's
    # only native deal field), plus the raw promos preserved for verification.
    promos = [p for p in (shop.get("promotions") or {}).values() if not p.get("expired")]
    by_id = {p["id"]: p for p in products}
    for pr in promos:
        pid, pct = pr.get("applies_to_product_id"), pr.get("discount_pct")
        prod = by_id.get(pid)
        if prod and pct and prod.get("price") and not prod.get("originalPrice"):
            frac = pct / 100.0 if pct > 1 else pct
            if 0 < frac < 1:
                prod["originalPrice"] = round(prod["price"] / (1 - frac), 2)

    seed_pids = [p["id"] for p in products[:3]]
    return {"products": products, "user": user, "cart": cart,
            "wishlist": seed_pids, "savedForLater": [],
            "orders": orders, "reviews": reviews,
            "recentSearches": [], "recentlyViewed": seed_pids,
            # No native amazon UI for these gym concepts -> preserved (not dropped),
            # available in state/verification even though the mock can't render them.
            "_gym_subscriptions": list((shop.get("subscriptions") or {}).values()),
            "_gym_promotions": list((shop.get("promotions") or {}).values())}


# --- ebay (gym market / ValueMart) -------------------------------------------
_EBAY_CAT = {"electronics": "Electronics", "audio": "Electronics", "home": "Home", "grocery": "Other"}


def transform_market(m: dict) -> dict:
    """gym MarketState -> ebay_mock (listings[], users[], cart[])."""
    import datetime
    store = m.get("store_name") or "ValueMart"
    seller_id, buyer_id = "user_valuemart", "user_1"
    buyer = {"id": buyer_id, "username": "admin", "email": "admin@example.com",
             "avatar": _picsum("user1", "100/100"), "feedbackScore": 154, "feedbackRating": 98.5}
    seller = {"id": seller_id, "username": store, "email": "store@valuemart.example.com",
              "avatar": _picsum("valuemart", "100/100"), "feedbackScore": 500, "feedbackRating": 99.0}
    end_ms = int(datetime.datetime(2026, 5, 28, 12, 0, 0).timestamp() * 1000)

    # which products have been ordered -> their listings show as "sold"
    ordered_pids = set()
    for o in (m.get("orders") or {}).values():
        for it in (o.get("items") or []):
            if it.get("product_id"):
                ordered_pids.add(it["product_id"])

    listings = []
    for pid, p in (m.get("products") or {}).items():
        price = p.get("price") if p.get("price") is not None else 0.0  # a fixed listing must have a price
        listings.append({
            "id": pid, "sellerId": seller_id, "title": p.get("name"),
            "description": p.get("description") or "", "images": [_picsum(pid)],
            "type": "fixed", "startingBid": None, "currentBid": None, "price": price,
            "buyItNowPrice": price, "bids": [], "watchers": [], "views": 0, "endTime": end_ms,
            "condition": "New", "shippingCost": 0.0, "location": "United States",
            "status": "sold" if pid in ordered_pids else "active",
            "quantity": 1 if p.get("in_stock") else 0,
            "category": _EBAY_CAT.get((p.get("category") or "").lower(), "Other"),
        })
    cart = [it.get("product_id") for it in ((m.get("cart") or {}).get("items") or []) if it.get("product_id")]
    orders = []
    for oid, o in (m.get("orders") or {}).items():
        pids = [it.get("product_id") for it in (o.get("items") or [])]
        orders.append({"id": oid, "buyerId": buyer_id, "sellerId": seller_id,
                       "items": pids, "listingId": pids[0] if pids else None,
                       "amount": o.get("total"), "total": o.get("total"),
                       "status": "completed", "created": end_ms, "date": end_ms})
    return {"currentUser": buyer, "users": [buyer, seller], "listings": listings, "orders": orders,
            "messages": [], "notifications": [], "feedbacks": [], "cart": cart,
            # eBay has no coupon UI -> preserved (not dropped), plus the priced cart detail.
            "_gym_coupons": list((m.get("coupons") or {}).values()),
            "_gym_cart_detail": (m.get("cart") or {}).get("items") or []}


# --- google calendar (gym calendar) ------------------------------------------
_CAL_DEFAULTS = [
    {"id": "c1", "name": "Personal", "color": "#039BE5", "visible": True, "userId": "u1", "isDefault": True},
    {"id": "c2", "name": "Work", "color": "#33B679", "visible": True, "userId": "u1", "isDefault": False},
    {"id": "c3", "name": "Family", "color": "#8E24AA", "visible": True, "userId": "u1", "isDefault": False},
    {"id": "c4", "name": "Holidays", "color": "#F4511E", "visible": True, "userId": "u1", "isDefault": False},
    {"id": "c5", "name": "Birthdays", "color": "#E67C73", "visible": True, "userId": "u1", "isDefault": False},
]
_CAL_OTHER = [
    {"id": "oc1", "name": "Holidays in United States", "color": "#0B8043", "visible": True},
    {"id": "oc2", "name": "Birthdays", "color": "#E67C73", "visible": True},
]


def transform_calendar(cal: dict) -> dict:
    """gym CalendarState -> google_calendar_mock (events[] + fixed calendar scaffolding)."""
    name = cal.get("account_name") or "Demo User"
    email = ".".join(name.lower().split()) + "@example.com"
    user = {"id": "u1", "username": name, "email": email, "avatar": _picsum("user1", "100/100")}
    ordered = sorted((cal.get("events") or {}).values(), key=lambda e: (e.get("day", ""), e.get("start", "")))
    events, current_date = [], None
    for e in ordered:
        day = e.get("day")
        if current_date is None:
            current_date = f"{day}T00:00:00.000Z"
        events.append({"id": e.get("id"), "calendarId": "c1", "title": e.get("title") or "(No Title)",
                       "start": f"{day}T{e.get('start')}:00.000Z", "end": f"{day}T{e.get('end')}:00.000Z",
                       "allDay": False, "location": "", "description": "", "guests": [],
                       "color": "#039BE5", "recurring": "none"})
    return {"user": user, "calendars": _CAL_DEFAULTS, "otherCalendars": _CAL_OTHER, "events": events,
            "view": "week", "currentDate": current_date or "2026-05-21T00:00:00.000Z", "sidebarOpen": True,
            "settings": {"weekStart": 0, "defaultDuration": 60, "defaultView": "week",
                         "defaultReminder": {"type": "popup", "minutes": 10}, "timeFormat": "12h",
                         "showWeekNumbers": False, "showDeclinedEvents": False}}


# --- uber eats (gym food) ----------------------------------------------------
_DIETARY = {"vegetarian": "Vegetarian", "vegan": "Vegan", "gluten-free": "Gluten-Free", "gluten_free": "Gluten-Free"}


def _price_range(fee) -> str:
    fee = fee or 0
    return "$" if fee < 2 else ("$$" if fee < 4 else "$$$")


def transform_food(food: dict) -> dict:
    """gym FoodState -> uber_eats_mock (restaurants[], menuItems[])."""
    restaurants, menu_items = [], []
    for rid, r in (food.get("restaurants") or {}).items():
        for d in (r.get("dishes") or []):
            tags = d.get("tags") or []
            menu_items.append({"id": d.get("id"), "restaurantId": rid,
                               "category": (tags[0].title() if tags else "Menu"), "name": d.get("name"),
                               "description": d.get("description") or "", "price": d.get("price"),
                               "imageUrl": "", "isPopular": bool(d.get("popular")), "isAvailable": True,
                               "dietaryTags": [_DIETARY[t.lower()] for t in tags if t.lower() in _DIETARY],
                               "customizationGroups": []})
        restaurants.append({"id": rid, "name": r.get("name"), "imageUrl": "",
                            "cuisineType": [r.get("cuisine")] if r.get("cuisine") else [],
                            "rating": r.get("rating"), "reviewCount": 0,
                            "priceRange": _price_range(r.get("delivery_fee")), "deliveryFee": r.get("delivery_fee"),
                            "deliveryTimeMin": 20, "deliveryTimeMax": 40, "distance": 1.0, "isOpen": True,
                            "hours": "", "address": "", "phone": "", "isSponsored": False, "promotions": [],
                            "categories": [], "tags": [], "supportsPickup": True,
                            "pickupTimeMin": 10, "pickupTimeMax": 20})
    user = {"id": "user_1", "name": "Alex Johnson", "email": "alex.johnson@email.com",
            "phone": "(415) 555-0100", "avatarUrl": "",
            "addresses": [dict(_UBER_ADDR)], "defaultAddressId": _UBER_ADDR["id"],
            "paymentMethods": [dict(_UBER_PAY)], "defaultPaymentId": _UBER_PAY["id"],
            "uberOneActive": False, "favoriteRestaurantIds": []}
    # cart: gym FoodCart -> uber cart
    fc = food.get("cart") or {}
    cart_items = []
    for it in (fc.get("items") or []):
        up, q = (it.get("unit_price") or 0), (it.get("quantity") or 1)
        cart_items.append({"menuItemId": it.get("dish_id"), "name": it.get("name"), "quantity": q,
                           "basePrice": up, "selectedOptions": [], "totalPrice": round(up * q, 2),
                           "specialInstructions": ""})
    cart = {"restaurantId": fc.get("restaurant_id"), "items": cart_items, "tipPercentage": 0,
            "tipAmount": 0, "promoDiscount": 0, "deliveryMode": "delivery", "scheduledTime": None}

    # orders: gym FoodOrder -> uber order
    orders = []
    for o in (food.get("orders") or {}).values():
        its = []
        for it in (o.get("items") or []):
            up, q = (it.get("unit_price") or 0), (it.get("quantity") or 1)
            its.append({"menuItemId": it.get("dish_id"), "name": it.get("name"), "quantity": q,
                        "unitPrice": up, "totalPrice": round(up * q, 2),
                        "selectedOptions": [], "specialInstructions": ""})
        orders.append({"id": o.get("id"), "restaurantId": o.get("restaurant_id"),
                       "restaurantName": o.get("restaurant_name"), "items": its,
                       "status": _FOOD_STATUS.get((o.get("status") or "").lower(), "placed"),
                       "placedAt": o.get("placed_at"), "subtotal": o.get("subtotal"),
                       "deliveryFee": o.get("delivery_fee"), "total": o.get("total")})
    active = orders[-1]["id"] if orders else None

    return {"user": user, "categories": list(_UBER_CATEGORIES), "restaurants": restaurants, "menuItems": menu_items,
            "cart": cart, "orders": orders, "activeOrderId": active, "promotions": [], "reviews": [],
            "ui": {"selectedAddressId": _UBER_ADDR["id"], "deliveryMode": "delivery", "searchQuery": "",
                   "recentSearches": [], "activeFilters": {"sort": "", "priceRange": [], "dietary": [],
                                                           "maxDeliveryFee": None, "deals": False}}}


TRANSFORMERS: dict[str, Callable[[dict], dict]] = {
    "shop": transform_shop,
    "mail": transform_mail,
    "market": transform_market,
    "calendar": transform_calendar,
    "food": transform_food,
}


# ------------------------------------------------------- build seed rows -------
def transform_world(world: dict[str, Any], apps: list[str] | None = None) -> dict[str, tuple[str, dict]]:
    """{app: (mock_key, state)} for an already-dumped world dict.

    Split out from transformed_states so the live bridge can re-project the
    RUNNING engine's world (asdict of SESSION.world) after each action, not just
    a freshly-built seed. `world` is the asdict shape (per-app store under its
    app key), same as dump_world returns.
    """
    out: dict[str, tuple[str, dict]] = {}
    for app in (apps or list(APP_TO_MOCK)):
        if app not in world or world[app] is None:
            continue
        transform = TRANSFORMERS.get(app)
        if transform is None:
            continue
        try:
            out[app] = (APP_TO_MOCK[app], transform(world[app]))
        except NotImplementedError as exc:
            print(f"  skip {app}: {exc}", file=sys.stderr)
    return out


def transformed_states(task_id: str, seed: int, apps: list[str] | None = None) -> dict[str, tuple[str, dict]]:
    """{app: (mock_key, state)} — the transformed mock state per app, no sid assigned.

    The reusable core: seeding (build_seed_rows) and the session manager both call this.
    """
    return transform_world(dump_world(task_id, seed), apps)


def build_seed_rows(task_id: str, seed: int, apps: list[str] | None = None) -> list[dict]:
    """[{app, mock, sid, state}] — one row per app that has a working transform."""
    return [
        {"app": app, "mock": mock, "sid": str(uuid.uuid4()), "state": state}
        for app, (mock, state) in transformed_states(task_id, seed, apps).items()
    ]


# ----------------------------------------------------------------- load --------
def load_rows(rows: list[dict], dsn: str) -> None:
    """INSERT each row into cua-gym: one mock_states row + one `set` event.

    Column names follow the observed cua-gym schema; confirm before committing.
    """
    import psycopg  # imported lazily so dry-run needs no driver

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for r in rows:
            state = json.dumps(r["state"])
            cur.execute(
                "INSERT INTO mock_states (mock, sid, state) VALUES (%s, %s, %s)",
                (r["mock"], r["sid"], state),
            )
            cur.execute(
                "INSERT INTO mock_state_events (mock, sid, action, state) VALUES (%s, %s, %s, %s)",
                (r["mock"], r["sid"], "set", state),
            )
        conn.commit()


def post_rows(rows: list[dict], base_url: str, admin_token: str | None = None) -> None:
    """Seed a RUNNING mock via its state API: POST /post?sid=<sid> {action:set, state}.

    This is the canonical CUA-Gym-Hub contract (works on the mock's own dev/preview
    server). Use with --app so all rows target the one mock at base_url.
    """
    import urllib.request

    base = base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if admin_token:
        headers["X-CUA-Admin-Token"] = admin_token
    for r in rows:
        payload = json.dumps({"action": "set", "state": r["state"]}).encode()
        req = urllib.request.Request(
            f"{base}/post?sid={r['sid']}", data=payload, method="POST", headers=headers,
        )
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
        print(f"seeded {r['mock']} sid={r['sid']} -> {body[:200]}")


# ------------------------------------------------------------------ cli --------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="gym task id, e.g. M1")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--app", action="append", help="limit to these gym apps (repeatable)")
    ap.add_argument("--commit", action="store_true", help="write to cua-gym Postgres (needs CUA_GYM_DSN)")
    ap.add_argument("--post", metavar="URL", help="seed a running mock via POST URL/post?sid (use with --app)")
    ap.add_argument("--mock-map", metavar="A=URL,...",
                    help="seed EVERY app of the task to its mock, e.g. shop=http://localhost:5201,mail=http://localhost:5203")
    ap.add_argument("--admin-token", help="X-CUA-Admin-Token for a hardened mock")
    args = ap.parse_args(argv)

    # Seed all of a task's apps across their mocks in one shot, print open URLs.
    if args.mock_map:
        mapping = dict(p.split("=", 1) for p in args.mock_map.split(",") if "=" in p)
        any_ok = False
        for app, url in mapping.items():
            rows = build_seed_rows(args.task, args.seed, [app])
            if not rows:
                continue
            post_rows(rows, url, args.admin_token)
            for r in rows:
                frag = "#/inbox" if r["mock"] == "gmail_mock" else ""
                print(f"open: {url.rstrip('/')}/?sid={r['sid']}{frag}")
            any_ok = True
        return 0 if any_ok else 1

    rows = build_seed_rows(args.task, args.seed, args.app)
    if not rows:
        print("no rows produced (no working transform for the requested apps)", file=sys.stderr)
        return 1

    if args.post:
        post_rows(rows, args.post, args.admin_token)
        return 0

    if args.commit:
        dsn = os.environ.get("CUA_GYM_DSN")
        if not dsn:
            print("--commit needs CUA_GYM_DSN in the env", file=sys.stderr)
            return 2
        load_rows(rows, dsn)
        for r in rows:
            print(f"loaded {r['mock']} seed_sid={r['sid']}")
        return 0

    # dry-run: show the mapping
    for r in rows:
        print(f"\n=== {r['app']} -> {r['mock']}  (seed_sid={r['sid']}) ===")
        print(json.dumps(r["state"], indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
