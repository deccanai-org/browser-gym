"""Export a gym task's seed world into the cua-hub / cua-gym `mock_states` shape.

Pipeline:  dump  ->  transform  ->  load

  dump       the gym's full per-app world for a (task_id, seed)  [reuses build_wrapped]
  transform  per app, gym shape  ->  cua-hub mock_states JSON shape
  load       mint a seed_sid per (task, mock); INSERT into cua-gym mock_states +
             an initial `set` mock_state_events row

All five transforms are complete. The mocks deep-merge a seed over their own
defaults and run per-key array normalizers, which strip fields they don't know:
anything the mock would drop but a verifier needs rides in a sibling `_gym_*`
key, which every mock passes through verbatim.

load is DRY-RUN by default. Pass --commit + CUA_GYM_DSN to write straight to
Postgres, or --post/--mock-map to go through the hub's state API.

Run:
  python -m tools.seed_to_cuagym --task M1 --seed 0            # dry-run, prints JSON
  python -m tools.seed_to_cuagym --task M1 --seed 0 --app mail
  CUA_GYM_DSN=postgres://... python -m tools.seed_to_cuagym --task M1 --seed 0 --commit
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import hashlib
import json
import os
import pathlib

from tools import ambient_catalog as _amb
from tools.ambient_calendar import build_calendar as _ambient_calendar_events
import re
import sys
import uuid
from typing import Any, Callable

from server.apps.calendar.state import TODAY
from server.seeddb._equiv import build_wrapped

# Bumped whenever a transform changes shape; lands in each app's _gym_meta so a
# seeded sid can be traced back to the code that produced it.
PROJECTION_VERSION = "2"

# gym app key -> cua-hub mock key (the `mock` column in cua-gym.mock_state_events)
APP_TO_MOCK = {
    "shop": "amazon_mock",
    "mail": "gmail_mock",
    "market": "ebay_mock",
    "calendar": "google_calendar_mock",
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
def _gym_meta(state: dict, app: str) -> dict:
    """Provenance stamped into every seeded app state.

    The mocks echo their whole state back on each `set_current`, so this rides
    along into every mock_state_events row: a trace says which task it belongs to
    without a registry lookup, and a state with NO _gym_meta is a dead giveaway
    that the sid was never seeded and the mock is showing its stock demo data.
    """
    return {"task_id": state.get("task_id"), "seed": state.get("seed"), "app": app,
            "today": TODAY, "projection_version": PROJECTION_VERSION}


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


_RE_PREFIX = re.compile(r"^\s*(?:re|fwd|fw)\s*:\s*", re.I)


def _thread_id(subject: str) -> str:
    """Group a conversation by its subject, the way a mail client does.

    "Dinner tonight" and "Re: dinner tonight" belong to one thread; keying on the
    message id instead gave every reply its own inbox row.
    """
    s = subject or ""
    while True:
        stripped = _RE_PREFIX.sub("", s)
        if stripped == s:
            break
        s = stripped
    key = " ".join(s.split()).casefold() or "no-subject"
    return "thread_" + hashlib.sha1(key.encode()).hexdigest()[:12]


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
            subject = e.get("subject") or ""
            labels = list(e.get("labels") or [])
            emails.append({
                "id": e.get("id"),
                # Thread by CONVERSATION, not by message. Keying the thread on the
                # message id made every reply its own inbox row, so a task that
                # says "read the thread" showed one message and hid the rest.
                "threadId": _thread_id(subject),
                "from": {"name": _display_name(e.get("sender")), "email": e.get("sender")},
                "to": [{"name": _display_name(to_addr), "email": to_addr}],
                "cc": [],
                "bcc": [],
                "subject": subject,
                "body": (e.get("body") or "").replace("\n", "<br>"),
                "timestamp": _iso(e.get("received_at")),
                "read": bool(e.get("read")),
                # The gym has no starred/important flags, but leaving them all
                # false left those folders permanently empty. Derive them from the
                # labels it does have so the mailbox looks lived-in.
                "starred": "starred" in labels or bool(e.get("order_id")),
                "important": "important" in labels or bool(e.get("order_id")),
                "labels": labels,
                # Everything stays in Primary. Deriving the category from labels
                # looked tidier but filed order mail under Updates — a tab this
                # mailbox has switched OFF — so the mail a task depends on simply
                # wasn't on screen. Labels still drive the sidebar filters.
                "category": "primary",
                "folder": e.get("folder") or folder,
                "attachments": [],
            })
    # browse-only filler so Sent/Drafts/Snoozed and the category tabs aren't empty
    emails = emails + _amb.build_mail(lambda d: f"2026-05-{d:02d}T12:00:00")
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
        "_gym_meta": _gym_meta(mail, "mail"),
    }


# Realistic licensed product photos (Adobe Stock free collection) live in each
# mock's public/assets/products/<id>.jpg. The manifest lists which product ids
# have one; anything not yet sourced gets a deterministic gradient tile (a
# self-contained data URI) instead of an external host — the gym seed must never
# depend on picsum.photos, which is non-deterministic and offline-fragile.
# Relative URL so it resolves on both the local preview and the hosted deployments.
_IMG_MANIFEST = pathlib.Path(__file__).with_name("product_images.json")
try:
    _PRODUCT_IMAGES = set(json.loads(_IMG_MANIFEST.read_text())) if _IMG_MANIFEST.exists() else set()
except Exception:
    _PRODUCT_IMAGES = set()


# Products that reuse a photo we already have, keyed by product id -> the asset's
# basename. 148 of the 190 ids the engine can produce had no photo of their own,
# so `_product_image` handed back a gradient letter tile — including the wool
# socks and the camp mug, the very items a task prompt names. Sourcing 148 new
# photos is a different project; pointing them at the 99 real ones already here is
# not, and an alias costs no disk (the file is shared, not copied).
#
# Deliberately incomplete: a product with no honest match keeps the tile. A wrong
# photo is worse than an obvious placeholder, and a warranty or an installation
# service has nothing to photograph at all.
_ALIAS_MANIFEST = pathlib.Path(__file__).with_name("product_image_aliases.json")
try:
    _IMAGE_ALIASES = json.loads(_ALIAS_MANIFEST.read_text()) if _ALIAS_MANIFEST.exists() else {}
except Exception:
    _IMAGE_ALIASES = {}


def _product_image(pid: str, name: str | None = None) -> str:
    if pid in _PRODUCT_IMAGES:
        return f"/assets/products/{pid}.jpg"
    if pid in _IMAGE_ALIASES:
        return f"/assets/products/{_IMAGE_ALIASES[pid]}.jpg"
    return _svg_tile(name or pid, pid)


def _svg_tile(text: str, seed: str) -> str:
    """A self-contained gradient tile (data URI) with the item's initial — used
    for listings we have no real photo for, so nothing falls back to picsum. Color
    is deterministic from the seed; no external host."""
    import hashlib
    import urllib.parse
    hue = int(hashlib.sha1(seed.encode()).hexdigest(), 16) % 360
    initial = (text or "?").strip()[:1].upper() or "?"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue},52%,46%)"/>'
        f'<stop offset="1" stop-color="hsl({(hue + 38) % 360},52%,34%)"/>'
        '</linearGradient></defs><rect width="400" height="400" fill="url(#g)"/>'
        f'<text x="200" y="250" font-family="Arial,Helvetica,sans-serif" font-size="190" '
        f'font-weight="700" fill="rgba(255,255,255,0.92)" text-anchor="middle">{initial}</text></svg>'
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg)


def _market_image(pid: str, name: str) -> str:
    """ValueMart mirrors the shop catalog with vm_ ids; reuse the real product
    photo when one matches, else a gradient tile. Never picsum."""
    if pid in _PRODUCT_IMAGES:
        return f"/assets/products/{pid}.jpg"
    alt = "p_" + pid[3:] if pid.startswith("vm_") else pid
    if alt in _PRODUCT_IMAGES:
        return f"/assets/products/{alt}.jpg"
    # The same aliases the shop uses, under either id — ValueMart mirrors the
    # catalog with vm_ ids, so a match on the shop's id is a match here.
    for key in (pid, alt):
        if key in _IMAGE_ALIASES:
            return f"/assets/products/{_IMAGE_ALIASES[key]}.jpg"
    return _svg_tile(name or pid, pid)


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
    # emit the status the uber mock's Orders/OrderTracking readers recognize
    "on_the_way": "out_for_delivery", "out_for_delivery": "out_for_delivery",
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
# The one account holder, identical across all five apps. Verifiers key on
# alice@shopgym.com (152 refs), so this is both the canonical and the safe value.
ALICE_NAME = "Alice Anderson"
ALICE_EMAIL = "alice@shopgym.com"

# The gym's frozen "now" (ms), 2026-05-21 12:00 UTC — the same instant the
# calendar/market/food projections freeze to. Projected so every app computes
# dates against the gym clock instead of the real Date.now(); without it a
# date-dependent ShopGym task (delivery windows, "arrives by", deal countdowns)
# drifts with the wall clock and stops reproducing. Mirrors market's inline
# literal at transform_market and _FOOD_EPOCH_MS.
_GYM_NOW_MS = int(_dt.datetime(2026, 5, 21, 12, 0, 0, tzinfo=_dt.timezone.utc).timestamp() * 1000)


def _acct_email(raw: str | None) -> str:
    """Normalise the account email to the canonical address, but keep a genuinely
    task-set one (e.g. a change-email task's alice.new@shopgym.com). The engine
    seeds a bare @example.com placeholder that should read as alice@shopgym.com."""
    if not raw or str(raw).endswith("@example.com"):
        return ALICE_EMAIL
    return raw

_UBER_ADDR = {"id": "addr_1", "label": "Home", "street": "100 Park Avenue", "apt": "Apt 4B", "city": "Brooklyn",
              "state": "NY", "zip": "11201", "instructions": "", "isDefault": True}
_UBER_PAY = {"id": "pay_1", "type": "visa", "label": "Visa •••• 4242", "last4": "4242", "expiry": "08/27", "isDefault": True}
# A couple more cards so the checkout "Choose payment" actually has options to
# pick between (the food user profile is client-side; no verifier reads it).
# expiry so the Account page can show it (model identifies cards there).
_UBER_PAYS = [
    dict(_UBER_PAY),
    {"id": "pay_2", "type": "mastercard", "label": "Mastercard •••• 5309", "last4": "5309", "expiry": "03/26", "isDefault": False},
    {"id": "pay_3", "type": "paypal", "label": "PayPal", "last4": "", "expiry": "", "isDefault": False},
]
# The gym has no courier model, but order tracking hides its driver card without
# one — a fixed stand-in keeps the page complete and the runs deterministic.
_UBER_COURIER = {"id": "courier_1", "name": "Jordan Lee", "vehicleType": "car",
                 "rating": 4.9, "phone": "(415) 555-0142"}
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


def _order_payment(pay_by_id: dict, payment_id: str | None, def_pay: dict) -> dict:
    """The card an order was actually charged to.

    An order can reference a card the user has since REMOVED (the dead-card
    tasks turn on exactly that), so falling back to the account default would
    erase the thing under test. Keep the real id and synthesize a stub.
    """
    if not payment_id:
        return def_pay
    known = pay_by_id.get(payment_id)
    if known:
        return known
    return {"id": payment_id, "last4": "0000", "brand": "Removed card",
            "expiry": "", "isDefault": False}


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
            "image": _product_image(p["id"], p.get("name")),
            "images": [_product_image(p["id"], p.get("name"))],
            "description": p.get("long_description") or p.get("short_description") or "",
            "bulletPoints": p.get("tags") or [],
            "specs": {"Brand": p.get("brand"), "Weight": f"{p.get('weight_kg')} kg", "Emoji": p.get("image_emoji")},
            "category": _AMAZON_CAT.get((p.get("category") or "").lower(), "Electronics"),
            "brand": p.get("brand"), "prime": True, "inStock": stock > 0, "stockCount": stock,
            # The store is branded ShopGym; the old value re-introduced on every
            # product the exact name the rebrand took out of the mock.
            "seller": "ShopGym", "badges": (["Best Seller"] if (p.get("rating") or 0) >= 4.5 else []),
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
    # An order must carry the card/address it ACTUALLY used, not the account
    # default -- 26 of the breakers hinge on `payment_id == pay_visa`. The mock's
    # own Checkout writes the whole selected payment object (id included), so a
    # seeded order and an agent-placed one end up the same shape.
    pay_by_id = {p["id"]: p for p in pays}
    addr_by_id = {a["id"]: a for a in addrs}
    user = {"id": (gu or {}).get("id", "u1"), "name": (gu or {}).get("full_name") or ALICE_NAME,
            "email": _acct_email((gu or {}).get("email")),
            # Profile's 2FA section reads user.two_fa_enabled; without it the UI
            # never showed the enabled state even after a successful engine enable.
            "two_fa_enabled": bool((gu or {}).get("two_fa_enabled")),
            "address": def_addr, "addresses": addrs, "paymentMethod": def_pay, "paymentMethods": pays}

    agg: dict = {}
    lopts: dict = {}
    for it in ((shop.get("cart") or {}).get("items") or []):
        pid = it.get("product_id")
        agg[pid] = agg.get(pid, 0) + (it.get("quantity") or 1)
        # Carry each line's gift-wrap / gift-message / ship-to / scheduled-date
        # onto the projected line. The engine owns them, but the old projection
        # dropped them so the Cart's gift controls always rendered empty and a
        # typed message never round-tripped. Last non-empty value wins per pid.
        o = lopts.setdefault(pid, {})
        for k in ("gift_wrap", "gift_message", "ship_to_address_id", "scheduled_delivery"):
            v = it.get(k)
            if v not in (None, "", False) or k not in o:
                o[k] = v
    cart = [{"productId": pid, "quantity": q,
             "gift_wrap": bool(lopts.get(pid, {}).get("gift_wrap")),
             "gift_message": lopts.get(pid, {}).get("gift_message") or "",
             "ship_to_address_id": lopts.get(pid, {}).get("ship_to_address_id") or "",
             "scheduled_delivery": lopts.get(pid, {}).get("scheduled_delivery") or ""}
            for pid, q in agg.items()]

    # returns: a gym ReturnRequest flips its order's amazon status to "Returned"
    returned_order_ids = {r.get("order_id") for r in (shop.get("returns") or {}).values()}
    orders = []
    for o in (shop.get("orders") or {}).values():
        status = "Returned" if o.get("id") in returned_order_ids else \
            _AMZ_STATUS.get((o.get("status") or "").lower(), "Delivered")
        orders.append({"id": o.get("id"), "date": o.get("placed_at") or "2024-01-01T00:00:00.000Z",
                       "status": status, "total": o.get("total"),
                       # keep the real order-ITEM id (initiate_return validates
                       # against it, not the product id) so returns can succeed.
                       "items": [{"id": i.get("id"), "productId": i.get("product_id"),
                                  "quantity": i.get("quantity") or 1}
                                 for i in (o.get("items") or [])],
                       # gym ship-to is per LINE; order level = the first line's.
                       "shippingAddress": addr_by_id.get(
                           ((o.get("items") or [{}])[0]).get("ship_to_address_id")) or def_addr,
                       "paymentMethod": _order_payment(pay_by_id, o.get("payment_id"), def_pay),
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

    products = products + _amb.build_shop()   # browse-only filler (projection-only)
    return {"products": products, "user": user, "cart": cart,
            # The gym's frozen clock, so the mock computes "today", delivery
            # windows and deal countdowns against it instead of real Date.now().
            "_gym_now": _GYM_NOW_MS,
            # recentlyViewed/recentSearches are the mock's only native engagement
            # signal (ProductDetail + Header write them as the agent browses), so
            # they MUST start empty -- pre-filling them forges "the agent looked".
            "wishlist": [], "savedForLater": [],
            "orders": orders, "reviews": reviews,
            "recentSearches": [], "recentlyViewed": [],
            # No native amazon UI for these gym concepts -> preserved (not dropped),
            # available in state/verification even though the mock can't render them.
            "_gym_subscriptions": list((shop.get("subscriptions") or {}).values()),
            "_gym_promotions": list((shop.get("promotions") or {}).values()),
            # The mock's normalizeOrder/normalizeCartItem reduce every line to
            # {productId, quantity} and drop payment/address ids, so the fields the
            # gift-wrap, split-ship and payment breakers verify against are kept here.
            "_gym_orders": list((shop.get("orders") or {}).values()),
            "_gym_cart_detail": {"items": (shop.get("cart") or {}).get("items") or [],
                                 "applied_promo": (shop.get("cart") or {}).get("applied_promo")},
            "_gym_returns": list((shop.get("returns") or {}).values()),
            "_gym_meta": _gym_meta(shop, "shop")}


# --- ebay (gym market / ValueMart) -------------------------------------------
_EBAY_CAT = {"electronics": "Electronics", "audio": "Electronics", "home": "Home", "grocery": "Other"}


def transform_market(m: dict) -> dict:
    """gym MarketState -> ebay_mock (listings[], users[], cart[])."""
    store = m.get("store_name") or "ValueMart"
    seller_id, buyer_id = "user_valuemart", "user_1"
    buyer = {"id": buyer_id, "username": ALICE_NAME, "email": ALICE_EMAIL,
             "avatar": _svg_tile(ALICE_NAME, "buyer"), "feedbackScore": 154, "feedbackRating": 98.5}
    seller = {"id": seller_id, "username": store, "email": "store@valuemart.example.com",
              "avatar": _svg_tile(store, "seller"), "feedbackScore": 500, "feedbackRating": 99.0}
    # UTC-pinned: a naive datetime here made the projection (and therefore any
    # content hash of it) depend on the operator's local timezone.
    end_ms = int(_dt.datetime(2026, 5, 28, 12, 0, 0,
                              tzinfo=_dt.timezone.utc).timestamp() * 1000)

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
            "description": p.get("description") or "", "images": [_market_image(pid, p.get("name"))],
            "type": "fixed", "startingBid": None, "currentBid": None, "price": price,
            "buyItNowPrice": price, "bids": [], "watchers": [], "views": 0, "endTime": end_ms,
            "condition": "New", "shippingCost": 0.0, "location": "United States",
            "status": "sold" if pid in ordered_pids else "active",
            "quantity": 1 if p.get("in_stock") else 0,
            "category": _EBAY_CAT.get((p.get("category") or "").lower(), "Other"),
        })
    cart = [it.get("product_id") for it in ((m.get("cart") or {}).get("items") or []) if it.get("product_id")]
    # Ship-to addresses + payment methods on file, so ValueMart checkout has a
    # real address/payment selection (was: only a cosmetic country dropdown).
    addresses = [{"id": a.get("id"), "fullName": a.get("full_name"), "street": a.get("street"),
                  "city": a.get("city"), "state": a.get("state"), "zip": a.get("zip"),
                  "country": a.get("country"), "isDefault": bool(a.get("is_default"))}
                 for a in (m.get("addresses") or {}).values()]
    payment_methods = [{"id": p.get("id"), "brand": p.get("brand"), "last4": p.get("last4"),
                        "expiry": p.get("expiry"),
                        "label": (f"{p.get('brand')} •••• {p.get('last4')}" if p.get("last4") else p.get("brand")),
                        "isDefault": bool(p.get("is_default"))}
                       for p in (m.get("payments") or {}).values()]
    orders = []
    for oid, o in (m.get("orders") or {}).items():
        pids = [it.get("product_id") for it in (o.get("items") or [])]
        orders.append({"id": oid, "buyerId": buyer_id, "sellerId": seller_id,
                       "items": pids, "listingId": pids[0] if pids else None,
                       "amount": o.get("total"), "total": o.get("total"),
                       "shippingAddressId": o.get("shipping_address_id"), "paymentId": o.get("payment_id"),
                       "status": "completed", "created": end_ms, "date": end_ms})
    amb_listings, amb_sellers = _amb.build_market(_svg_tile)   # browse-only filler
    listings = listings + amb_listings
    return {"currentUser": buyer, "users": [buyer, seller] + amb_sellers, "listings": listings, "orders": orders,
            "messages": [], "notifications": [], "feedbacks": [], "cart": cart,
            "addresses": addresses, "paymentMethods": payment_methods,
            # derive the default from the isDefault flags (the world dict is asdict(),
            # which carries the raw fields but not the computed default_*_id helpers)
            "defaultAddressId": next((a["id"] for a in addresses if a.get("isDefault")),
                                     (addresses[0]["id"] if addresses else None)),
            "defaultPaymentId": next((p["id"] for p in payment_methods if p.get("isDefault")),
                                     (payment_methods[0]["id"] if payment_methods else None)),
            # the applied coupon so Cart.jsx can show the "coupon applied" banner +
            # discount (the engine stores + charges it, but it wasn't projected).
            "coupon": (m.get("cart") or {}).get("applied_coupon"),
            # the gym's frozen "now" (ms) so auction time-left is computed against
            # the frozen clock, not the real Date.now() (which marks all "Ended").
            "_gym_now": int(_dt.datetime(2026, 5, 21, 12, 0, 0,
                                         tzinfo=_dt.timezone.utc).timestamp() * 1000),
            # Delivery pricing, so the cart's Total matches what the engine
            # actually charges (subtotal - discount + delivery). Without these
            # the mock showed a total $5.99 short on every sub-threshold cart.
            "deliveryFee": m.get("delivery_fee"),
            "freeDeliveryOver": m.get("free_delivery_over"),
            # eBay has no coupon UI -> preserved (not dropped), plus the priced cart detail.
            "_gym_coupons": list((m.get("coupons") or {}).values()),
            "_gym_cart_detail": (m.get("cart") or {}).get("items") or [],
            "_gym_orders": list((m.get("orders") or {}).values()),
            "_gym_meta": _gym_meta(m, "market")}


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

# calendar id -> chip color, so a projected event shows its own calendar's color
# instead of everything rendering default-blue.
_CAL_COLOR = {c["id"]: c["color"] for c in _CAL_DEFAULTS}


def transform_calendar(cal: dict) -> dict:
    """gym CalendarState -> google_calendar_mock (events[] + fixed calendar scaffolding)."""
    name = cal.get("account_name") or ALICE_NAME
    email = ALICE_EMAIL
    user = {"id": "u1", "username": name, "email": email, "avatar": None}
    ordered = sorted((cal.get("events") or {}).values(), key=lambda e: (e.get("day", ""), e.get("start", "")))
    events = []
    for e in ordered:
        day = e.get("day")
        # `source` is what the gym uses to tell a seeded event from an agent-made
        # one. normalizeEvent strips it from the live state, but it survives in the
        # raw initial_state, so a verifier can still diff new-since-seed by id.
        # LOCAL wall-clock, no Z. The gym stores "09:00 on 2026-05-21" as a wall
        # time; stamping it Zulu meant a browser behind UTC parsed it as the
        # previous day, so Day view came up empty while Week/Month looked right.
        # Honor the event's real calendar_id (the engine stores it when a user
        # picks Work/Family/... in the event modal). Hardcoding "c1" here snapped
        # every event back to the default calendar on the next bridge poll.
        cid = e.get("calendar_id") or "c1"
        events.append({"id": e.get("id"), "calendarId": cid, "title": e.get("title") or "(No Title)",
                       "start": f"{day}T{e.get('start')}:00", "end": f"{day}T{e.get('end')}:00",
                       "allDay": bool(e.get("all_day")), "location": e.get("location") or "",
                       "description": e.get("description") or "",
                       "color": _CAL_COLOR.get(cid, "#039BE5"), "recurring": e.get("recurring") or "none",
                       "reminderMinutes": e.get("reminder_minutes"),
                       "source": e.get("source") or "seed"})
    # Browse-only ambient events so the week isn't near-empty. Off the two frozen
    # gym-gate days, source='seed', new ids — invisible to the calendar verifiers.
    events = events + _ambient_calendar_events()
    return {"user": user, "calendars": _CAL_DEFAULTS, "otherCalendars": _CAL_OTHER, "events": events,
            # the gym's FROZEN today (stable, unlike currentDate which the user
            # navigates) so "Today"/create-defaults/today-highlight don't jump to
            # the real system date where there are no seed events.
            "_gym_today": f"{TODAY}T00:00:00",
            # The frozen gym clock, NOT the earliest event -- deriving it from the
            # events opened 23 tasks on the wrong "today".
            "view": "week", "currentDate": f"{TODAY}T00:00:00", "sidebarOpen": True,
            "settings": {"weekStart": 0, "defaultDuration": 60, "defaultView": "week",
                         "defaultReminder": {"type": "popup", "minutes": 10}, "timeFormat": "12h",
                         "showWeekNumbers": False, "showDeclinedEvents": False},
            "_gym_meta": _gym_meta(cal, "calendar")}


# --- uber eats (gym food) ----------------------------------------------------
_DIETARY = {"vegetarian": "Vegetarian", "vegan": "Vegan", "gluten-free": "Gluten-Free",
            "gluten_free": "Gluten-Free", "halal": "Halal", "kosher": "Kosher"}


def _price_range(fee) -> str:
    fee = fee or 0
    return "$" if fee < 2 else ("$$" if fee < 4 else "$$$")


# Fixed order timestamp: normalizeOrder defaults `created` to Date.now(), which
# would make the projection differ on every run.
_FOOD_EPOCH_MS = int(_dt.datetime(2026, 5, 21, 12, 0, 0,
                                  tzinfo=_dt.timezone.utc).timestamp() * 1000)


# Food photos (Adobe Stock free collection) live at /assets/food/<key>.jpg in
# the uber_eats mock. Restaurants map by id; dishes map by id, else by a keyword
# on the dish name so a new dish still gets a plausible photo instead of blank.
_REST_IMAGE = {"r_sushi": "rest_sushi", "r_burger": "rest_burger",
               "r_bean": "rest_bean", "r_tony": "rest_pizza"}
_DISH_IMAGE = {
    "d_salmon_roll": "sushi", "d_av_roll": "sushi", "d_avocado_veg_roll": "sushi",
    "d_veg_platter_342": "sushi", "d_party_platter": "sushi", "d_tuna_bowl": "poke_bowl",
    "d_miso": "miso_soup", "d_classic": "cheeseburger", "d_veggie": "veggie_burger",
    "d_veg_burger": "veggie_burger", "d_veggie_box_342": "veggie_burger", "d_fries": "fries",
    "d_pods": "coffee_pods", "d_latte": "latte", "d_croissant": "croissant",
    "d_vegan_platter": "vegan_platter", "d_welcome_veg_354": "vegan_platter",
    "d_veg_dinner_343": "vegan_platter", "d_garden_dumplings": "dumplings",
    "d_midnight_shake": "shake", "d_large_pizza": "rest_pizza", "d_garlic_knots": "garlic_knots",
    "d_oat_breakfast_343": "breakfast_box", "d_family_feast": "lunch_box",
    "d_interview_lunch_346": "lunch_box", "d_group_dinner_348": "lunch_box",
    "d_lunch_box_349": "lunch_box", "d_m379_standard": "lunch_box",
    "d_m379_vegetarian": "lunch_box", "d_m379_gluten_free": "lunch_box",
}
_DISH_KEYWORDS = [
    ("pizza", "rest_pizza"), ("roll", "sushi"), ("sushi", "sushi"), ("burger", "cheeseburger"),
    ("fries", "fries"), ("latte", "latte"), ("coffee", "coffee_pods"), ("croissant", "croissant"),
    ("dumpling", "dumplings"), ("shake", "shake"), ("soup", "miso_soup"), ("bowl", "poke_bowl"),
    ("vegan", "vegan_platter"), ("breakfast", "breakfast_box"), ("oat", "breakfast_box"),
    ("box", "lunch_box"), ("platter", "lunch_box"), ("feast", "lunch_box"),
    ("lunch", "lunch_box"), ("dinner", "lunch_box"),
]


def _food_img(key: str) -> str:
    return f"/assets/food/{key}.jpg" if key else ""


def _rest_image(rid: str) -> str:
    return _food_img(_REST_IMAGE.get(rid, ""))


def _dish_image(did: str, name: str) -> str:
    key = _DISH_IMAGE.get(did)
    if not key:
        low = (name or "").lower()
        key = next((k for kw, k in _DISH_KEYWORDS if kw in low), "")
    return _food_img(key)


def transform_food(food: dict) -> dict:
    """gym FoodState -> uber_eats_mock (restaurants[], menuItems[])."""
    restaurants, menu_items = [], []
    for rid, r in (food.get("restaurants") or {}).items():
        for d in (r.get("dishes") or []):
            tags = d.get("tags") or []
            menu_items.append({"id": d.get("id"), "restaurantId": rid,
                               "category": (tags[0].title() if tags else "Menu"), "name": d.get("name"),
                               "description": d.get("description") or "", "price": d.get("price"),
                               "imageUrl": _dish_image(d.get("id"), d.get("name")),
                               "isPopular": bool(d.get("popular")), "isAvailable": True,
                               "dietaryTags": [_DIETARY[t.lower()] for t in tags if t.lower() in _DIETARY],
                               "customizationGroups": []})
        restaurants.append({"id": rid, "name": r.get("name"), "imageUrl": _rest_image(rid),
                            "cuisineType": [r.get("cuisine")] if r.get("cuisine") else [],
                            "rating": r.get("rating"), "reviewCount": 60 + (len(rid) * 11) % 240,
                            "priceRange": _price_range(r.get("delivery_fee")), "deliveryFee": r.get("delivery_fee"),
                            # etaLabel is the gym's absolute arrival time ("7:20 PM"). The mock
                            # only has a generic min/max window, so tasks gated on "will it get
                            # here by 7pm" need the real label carried alongside it.
                            "etaLabel": r.get("eta_label"),
                            "deliveryTimeMin": 20, "deliveryTimeMax": 40, "distance": 1.0, "isOpen": True,
                            "hours": "", "address": "", "phone": "", "isSponsored": False, "promotions": [],
                            "categories": [], "tags": [], "supportsPickup": True,
                            "pickupTimeMin": 10, "pickupTimeMax": 20})

    # Ambient browse content so the cuisine categories aren't near-empty. Purely
    # additive and projection-only (see tools/ambient_food.py) -> no verifier sees
    # it. Real task restaurants also get a couple of reviews so their store page
    # isn't blank.
    from tools.ambient_food import (build_ambient, ambient_orders,
                                    AMBIENT_FAVORITES, _REVIEW_POOL)
    amb_rests, amb_menu, reviews = build_ambient(_food_img, _svg_tile)
    for i, rr in enumerate(restaurants):
        for j in range(2):
            who, stars, text = _REVIEW_POOL[(i * 2 + j) % len(_REVIEW_POOL)]
            reviews.append({"id": f"rev_{rr['id']}_{j}", "restaurantId": rr["id"],
                            "userName": who, "rating": stars, "comment": text,
                            "createdAt": "2026-05-1%dT12:00:00" % ((i + j) % 9 + 1)})
    restaurants = restaurants + amb_rests
    menu_items = menu_items + amb_menu

    user = {"id": "user_1", "name": ALICE_NAME, "email": ALICE_EMAIL,
            "phone": "(718) 555-0100", "avatarUrl": "",
            "addresses": [dict(_UBER_ADDR)], "defaultAddressId": _UBER_ADDR["id"],
            "paymentMethods": [dict(p) for p in _UBER_PAYS], "defaultPaymentId": _UBER_PAY["id"],
            "uberOneActive": False, "favoriteRestaurantIds": list(AMBIENT_FAVORITES)}
    # The mock's normalizeCartItem/normalizeOrderItem both want
    # {cartItemId, menuItem:{...}, quantity, modifiers, instructions} and nest the
    # dish as a whole object -- emitting a flat {menuItemId, name, price} made every
    # seeded line render blank, because `menuItem` fell back to {}.
    by_dish = {m["id"]: m for m in menu_items}

    def _line(it, i, prefix):
        q = it.get("quantity") or 1
        return {"cartItemId": f"{prefix}_{i}", "menuItem": by_dish.get(it.get("dish_id")) or
                {"id": it.get("dish_id"), "name": it.get("name"), "price": it.get("unit_price")},
                "quantity": q, "modifiers": {}, "instructions": it.get("note") or ""}

    # cart: gym FoodCart -> uber cart. deepMergeWithDefaults rebuilds `cart` as
    # {restaurantId, items} only, so tip/mode/delivery_note are kept in _gym_food_cart.
    fc = food.get("cart") or {}
    cart = {"restaurantId": fc.get("restaurant_id"),
            "items": [_line(it, i, "cart_item") for i, it in enumerate(fc.get("items") or [])]}

    # orders: gym FoodOrder -> uber order
    orders = []
    for o in (food.get("orders") or {}).values():
        sub = o.get("subtotal") or 0
        fee = o.get("delivery_fee") or 0
        # The receipt reads serviceFee/tax off the ORDER, not off `total`; leaving
        # them undefined rendered "$NaN". The gym's total is authoritative (tasks
        # quote it), so split whatever it leaves over subtotal+delivery rather than
        # inventing percentages that wouldn't add up on screen.
        total = o.get("total")
        if total is None:
            tax = round(sub * 0.08, 2)
            service = round(sub * 0.05, 2)
            total = round(sub + fee + tax + service, 2)
        else:
            residual = round(total - sub - fee, 2)
            tax = round(residual * 0.6, 2) if residual > 0 else 0.0
            service = round(residual - tax, 2) if residual > 0 else 0.0
        orders.append({"id": o.get("id"), "userId": user["id"], "restaurantId": o.get("restaurant_id"),
                       "restaurantName": o.get("restaurant_name"),
                       "items": [_line(it, i, f"{o.get('id')}_item")
                                 for i, it in enumerate(o.get("items") or [])],
                       "status": _FOOD_STATUS.get((o.get("status") or "").lower(), "placed"),
                       # normalizeOrder wants `created` (ms) and an object `total`;
                       # a bare number there rendered as $0.
                       "created": _FOOD_EPOCH_MS, "placedAt": o.get("placed_at"),
                       "subtotal": sub, "deliveryFee": fee, "serviceFee": service, "tax": tax,
                       # Tracking hides the courier card and falls back to the
                       # placeholder "delivery address" without these two.
                       "deliveryAddress": dict(_UBER_ADDR),
                       "deliveryPerson": dict(_UBER_COURIER),
                       "deliveryDetails": {"note": o.get("delivery_note") or "",
                                           "address": dict(_UBER_ADDR)},
                       # Tracking + receipt read order.paymentMethod; without it they
                       # printed "Paid with undefined".
                       "paymentMethod": _UBER_PAY["label"],
                       "total": {"subtotal": sub, "fee": fee, "tax": tax,
                                 "serviceFee": service, "total": total}})
    active = orders[-1]["id"] if orders else None
    # ambient past orders (delivered) fill the order history / reorder; appended
    # AFTER active so they never become the active order.
    orders = orders + ambient_orders(by_dish)

    # the checkout promo box needs real codes behind it, and the applied one
    promos = [{"code": c, "percentOff": pct, "description": f"{int(pct * 100)}% off your order"}
              for c, pct in (food.get("promos") or {}).items()]
    return {"user": user, "categories": list(_UBER_CATEGORIES), "restaurants": restaurants, "menuItems": menu_items,
            "cart": cart, "orders": orders, "activeOrderId": active,
            "promotions": promos, "appliedPromoCode": (fc.get("promo_code") or ""), "reviews": reviews,
            "ui": {"selectedAddressId": _UBER_ADDR["id"], "deliveryMode": "delivery", "searchQuery": "",
                   "recentSearches": [], "activeFilters": {"sort": "recommended", "priceRange": [], "dietary": [],
                                                           "maxDeliveryFee": None, "deals": False}},
            # delivery_note is the whole harm surface of the delivery-disclosure
            # breakers and the mock drops it on both cart and order.
            "_gym_food_cart": fc,
            "_gym_food_orders": list((food.get("orders") or {}).values()),
            "_gym_meta": _gym_meta(food, "food")}


TRANSFORMERS: dict[str, Callable[[dict], dict]] = {
    "shop": transform_shop,
    "mail": transform_mail,
    "market": transform_market,
    "calendar": transform_calendar,
    "food": transform_food,
}


# ------------------------------------------------------- build seed rows -------
def transform_world(world: dict[str, Any], apps: list[str] | None = None,
                    task_id: str | None = None) -> dict[str, tuple[str, dict]]:
    """{app: (mock_key, state)} for an already-dumped world dict.

    Split out from transformed_states so the live bridge can re-project the
    RUNNING engine's world (asdict of SESSION.world) after each action, not just
    a freshly-built seed. `world` is the asdict shape (per-app store under its
    app key), same as dump_world returns.
    """
    # Only the shop store carries task_id/seed; stamp them onto every app so each
    # mock's _gym_meta identifies the task it belongs to. Prefer the REQUESTED id:
    # arm variants (…_armB) build the same base world and would otherwise all
    # report the base id, which is what the seed sid is derived from.
    shop = world.get("shop") or {}
    task_id, seed = task_id or shop.get("task_id"), shop.get("seed")

    out: dict[str, tuple[str, dict]] = {}
    for app in (apps or list(APP_TO_MOCK)):
        if app not in world or world[app] is None:
            continue
        transform = TRANSFORMERS.get(app)
        if transform is None:
            continue
        try:
            state = transform(world[app])
        except NotImplementedError as exc:
            print(f"  skip {app}: {exc}", file=sys.stderr)
            continue
        meta = state.get("_gym_meta")
        if meta is not None:
            meta["task_id"], meta["seed"] = task_id, seed
        out[app] = (APP_TO_MOCK[app], state)
    return out


def transformed_states(task_id: str, seed: int, apps: list[str] | None = None) -> dict[str, tuple[str, dict]]:
    """{app: (mock_key, state)} — the transformed mock state per app, no sid assigned.

    The reusable core: seeding (build_seed_rows) and the session manager both call this.
    """
    return transform_world(dump_world(task_id, seed), apps, task_id=task_id)


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
