"""Ambient (browse-only) content for Xmazon, Xbay and Xmail.

Same idea as tools/ambient_food.py: purely additive data appended to the
projection so the apps look full. It never touches the gym engine world, so no
verifier sees it (verifiers read p.world.*). All ids are amb_* to avoid clashing
with any task's product / listing / email id. Deterministic — no randomness.
"""

from __future__ import annotations

import json as _json
import pathlib as _pathlib

# A larger batch of generated browse-only filler (products / listings / emails /
# events), validated to use only real image keys, no monitors and no
# premise-conflicting content. Kept as data next to the code.
_BULK = _json.loads((_pathlib.Path(__file__).with_name("ambient_bulk.json")).read_text())

# Product ids that have their OWN dedicated photo (sourced to break up same-type
# image reuse). A bulk product uses amb_bp_<j> / amb_bl_<j> when that key is
# present here, otherwise it falls back to its shared type photo.
_IMG_SET = set(_json.loads((_pathlib.Path(__file__).with_name("product_images.json")).read_text()))


def _img(key: str) -> str:
    return f"/assets/products/{key}.jpg"


def _uimg(unique_key: str, type_key: str) -> str:
    """Dedicated per-product photo if we sourced one, else the shared type photo."""
    return _img(unique_key if unique_key in _IMG_SET else type_key)


# ---------------------------------------------------------------- Xmazon ------
# (title, price, original_price|None, image_key, brand)
_SHOP: dict[str, list] = {
    "Electronics": [
        ("Pro Tablet 11\"", 429.99, 499.99, "amb_tablet", "LumeTab"),
        ("Wireless Earbuds Pro", 89.99, 129.99, "amb_earbuds", "SoundCore"),
        ("Mirrorless Camera X100", 749.99, None, "amb_camera", "OptiShot"),
        ("20000mAh Power Bank", 34.99, 49.99, "amb_power_bank", "Anker"),
        ("Portable Bluetooth Speaker", 59.99, None, "p_speaker", "JBL"),
        ("Studio Headphones", 149.99, 199.99, "p_hp_studio", "Audio-Technica"),
    ],
    "Toys & Games": [
        ("Building Blocks Set (500 pcs)", 39.99, 49.99, "amb_lego", "BrickWorks"),
        ("Family Board Game Night", 24.99, None, "amb_board_game", "TableTop Co."),
        ("Classic Teddy Bear Plush", 19.99, 24.99, "amb_plush", "CuddleCraft"),
        ("Beginner Camera Drone", 79.99, 119.99, "amb_drone", "SkyLite"),
        ("1000-Piece Jigsaw Puzzle", 14.99, None, "amb_puzzle", "PuzzleMaster"),
    ],
    "Beauty": [
        ("Hydrating Face Cream", 22.99, 29.99, "amb_skincare", "GlowLab"),
        ("Matte Lipstick Duo", 16.99, None, "amb_lipstick", "Rouge"),
        ("Eau de Parfum 50ml", 64.99, 84.99, "amb_perfume", "Maison Nuit"),
        ("Pro Eyeshadow Palette", 34.99, 44.99, "amb_makeup", "ColorPop"),
    ],
    "Home & Kitchen": [
        ("High-Speed Blender 1200W", 79.99, 99.99, "amb_blender", "VitaWhirl"),
        ("6 Qt Digital Air Fryer", 99.99, 139.99, "amb_air_fryer", "CrispPro"),
        ("Espresso Coffee Maker", 129.99, None, "amb_coffee_maker", "BaristaOne"),
        ("Modern Desk Lamp", 34.99, None, "p_home_lamp", "IKEA"),
        ("Ceramic Mug Set (4)", 27.99, 34.99, "p_home_mug", "Le Creuset"),
    ],
    "Fashion": [
        ("Running Sneakers", 89.99, 119.99, "amb_shoes", "StridePro"),
        ("Leather Shoulder Bag", 119.99, 159.99, "amb_handbag", "Milano"),
        ("Pullover Hoodie", 44.99, None, "p_clothing_hoodie", "Champion"),
        ("Cotton Polo Shirt", 29.99, None, "p_clothing_polo", "Everlane"),
    ],
    "Sports & Outdoors": [
        ("Non-Slip Yoga Mat", 29.99, 39.99, "amb_yoga_mat", "ZenFlex"),
        ("Adjustable Dumbbell Pair", 149.99, 199.99, "amb_dumbbells", "IronCore"),
        ("Official Size Basketball", 24.99, None, "amb_basketball", "Spalding"),
    ],
    "Books": [
        ("The Art of Simple Cooking", 18.99, None, "p_book_cook", "Scribner"),
        ("A Short History of Everything", 16.49, 22.00, "p_book_history", "Harper"),
        ("Starbound (A Novel)", 14.99, None, "p_book_sci_fi", "Ballantine"),
        ("The Builders (Hardcover)", 24.99, 32.00, "p_book_oos", "Knopf"),
    ],
}


def build_shop():
    out = []
    for cat, items in _SHOP.items():
        for i, (title, price, orig, key, brand) in enumerate(items):
            pid = f"amb_p_{key}_{i}"
            # each named product prefers its OWN generated photo (keyed by id) so
            # two "perfume" products don't share one type image; falls back to the
            # type image only if the per-product one isn't in the manifest.
            pimg = _uimg(pid, key)
            out.append({
                "id": pid, "title": title, "price": price, "originalPrice": orig,
                "rating": round(4.0 + ((len(title) * 7) % 10) / 10, 1),
                "reviewCount": 30 + (len(title) * 13) % 900,
                "image": pimg, "images": [pimg],
                "description": f"{title} — a customer favorite. Fast, reliable and built to last.",
                "bulletPoints": ["Top rated in its category", "Ships with Prime", "1-year warranty"],
                "specs": {"Brand": brand, "Weight": "0.8 kg", "Emoji": ""},
                "category": cat, "brand": brand, "prime": True,
                "inStock": True, "stockCount": 25 + i * 3,
                "seller": "Xmazon", "badges": (["Best Seller"] if orig else []),
                "createdAt": "2024-01-01T00:00:00.000Z",
            })
    for j, p in enumerate(_BULK.get("shop", [])):
        key, title, brand = p["image_key"], p["title"], p.get("brand", "Xmazon")
        orig = p.get("originalPrice")
        pimg = _uimg(f"amb_bp_{j}", key)
        out.append({
            "id": f"amb_bp_{j}", "title": title, "price": p["price"], "originalPrice": orig,
            "rating": round(4.0 + ((len(title) * 7) % 10) / 10, 1),
            "reviewCount": 30 + (len(title) * 13) % 900,
            "image": pimg, "images": [pimg],
            "description": f"{title} — a customer favorite. Fast, reliable and built to last.",
            "bulletPoints": ["Top rated in its category", "Ships with Prime", "1-year warranty"],
            "specs": {"Brand": brand, "Weight": "0.8 kg", "Emoji": ""},
            "category": p.get("category", "Electronics"), "brand": brand, "prime": True,
            "inStock": True, "stockCount": 20 + (j * 7) % 80,
            "seller": "Xmazon", "badges": (["Best Seller"] if orig else []),
            "createdAt": "2024-01-01T00:00:00.000Z",
        })
    return out


# ---------------------------------------------------------------- Xbay ----
# (title, price, image_key, category, condition, is_auction)
_MARKET: list = [
    ("Vintage Vinyl Record - Jazz Classics", 24.99, "amb_vinyl", "Collectibles", "Used", True),
    ("Luxury Automatic Wrist Watch", 189.00, "amb_watch", "Fashion", "New", True),
    ("Designer Leather Handbag", 145.00, "amb_handbag", "Fashion", "New", False),
    ("Mirrorless Camera Body", 620.00, "amb_camera", "Electronics", "Used", True),
    ("Beginner Camera Drone", 74.99, "amb_drone", "Electronics", "New", False),
    ("Wireless Earbuds (Sealed)", 69.99, "amb_earbuds", "Electronics", "New", False),
    ("Pro Tablet 11-inch", 399.00, "amb_tablet", "Electronics", "Refurbished", True),
    ("20000mAh Power Bank", 29.99, "amb_power_bank", "Electronics", "New", False),
    ("Adjustable Dumbbell Set", 135.00, "amb_dumbbells", "Sporting Goods", "Used", False),
    ("Official Basketball", 21.99, "amb_basketball", "Sporting Goods", "New", False),
    ("Non-Slip Yoga Mat", 24.99, "amb_yoga_mat", "Sporting Goods", "New", False),
    ("Retro Board Game (Complete)", 34.99, "amb_board_game", "Toys & Hobbies", "Used", True),
    ("Building Blocks Mega Set", 44.99, "amb_lego", "Toys & Hobbies", "New", False),
    ("Collector Teddy Bear", 39.99, "amb_plush", "Collectibles", "Used", False),
    ("High-Speed Kitchen Blender", 64.99, "amb_blender", "Home & Garden", "New", False),
    ("6 Qt Air Fryer", 79.99, "amb_air_fryer", "Home & Garden", "New", True),
    ("Espresso Coffee Maker", 109.00, "amb_coffee_maker", "Home & Garden", "Refurbished", False),
    ("Studio Headphones", 119.00, "p_hp_studio", "Electronics", "New", False),
    ("Bluetooth Speaker", 49.99, "p_speaker", "Electronics", "New", False),
    ("Running Sneakers Size 10", 74.99, "amb_shoes", "Fashion", "New", True),
    ("Perfume 50ml (Sealed)", 58.00, "amb_perfume", "Health & Beauty", "New", False),
    ("Pro Eyeshadow Palette", 29.99, "amb_makeup", "Health & Beauty", "New", False),
    ("Vintage Film Camera", 210.00, "amb_camera", "Collectibles", "Used", True),
    ("Mechanical Keyboard (RGB)", 89.99, "p_kb_mech", "Electronics", "New", False),
    # NB: no monitors here on purpose — breakers M40 (bogus price-match on the
    # 24" monitor) and M142 (no in-stock high-rated monitor) require monitor
    # scarcity/pricing to stay intact, so ambient never lists one.
]

_SELLERS = [
    ("amb_seller_techbay", "TechBay Deals", 4213, 99.2),
    ("amb_seller_vintage", "Vintage Finds Co.", 1876, 98.5),
    ("amb_seller_home", "HomeStyle Store", 3021, 99.0),
]


def build_market(svg_tile):
    listings, sellers = [], []
    for sid, name, score, rate in _SELLERS:
        sellers.append({"id": sid, "username": name, "email": f"{sid}@xbay.example.com",
                        "avatar": svg_tile(name, sid), "feedbackScore": score, "feedbackRating": rate})
    # deterministic end times spread over the coming days (ms since a fixed epoch)
    base = 1_780_000_000_000  # arbitrary fixed ms; TODAY is frozen so this is stable
    for i, (title, price, key, cat, cond, auction) in enumerate(_MARKET):
        sid = _SELLERS[i % len(_SELLERS)][0]
        end = base + (i + 1) * 86_400_000  # +i days
        bids = [{"bidderId": "amb_b1", "amount": round(price * 0.7, 2)},
                {"bidderId": "amb_b2", "amount": round(price * 0.82, 2)}] if auction else []
        listings.append({
            "id": f"amb_l_{key}_{i}", "sellerId": sid, "title": title,
            "description": f"{title}. Ships fast from a top-rated seller.",
            "images": [_uimg(f"amb_l_{key}_{i}", key)],
            "type": "auction" if auction else "fixed",
            "startingBid": round(price * 0.5, 2) if auction else None,
            "currentBid": round(price * 0.82, 2) if auction else None,
            "price": price, "buyItNowPrice": price, "bids": bids,
            "watchers": [f"w{n}" for n in range((i % 12) + 1)],
            "views": 40 + (len(title) * 17) % 900, "endTime": end,
            "condition": cond, "shippingCost": 0.0 if i % 3 else 4.99,
            "location": "United States", "status": "active",
            "quantity": 1, "category": cat,
        })
    off = len(_MARKET)
    for j, l in enumerate(_BULK.get("market", [])):
        key, price = l["image_key"], l["price"]
        auction = bool(l.get("is_auction"))
        sid = _SELLERS[j % len(_SELLERS)][0]
        end = base + (off + j + 1) * 86_400_000
        listings.append({
            "id": f"amb_bl_{j}", "sellerId": sid, "title": l["title"],
            "description": f"{l['title']}. Ships fast from a top-rated seller.",
            "images": [_uimg(f"amb_bl_{j}", key)],
            "type": "auction" if auction else "fixed",
            "startingBid": round(price * 0.5, 2) if auction else None,
            "currentBid": round(price * 0.82, 2) if auction else None,
            "price": price, "buyItNowPrice": price, "bids": [],
            "watchers": [f"w{n}" for n in range((j % 10) + 1)],
            "views": 40 + (len(l["title"]) * 17) % 900, "endTime": end,
            "condition": l.get("condition", "New"), "shippingCost": 0.0 if j % 3 else 4.99,
            "location": "United States", "status": "active",
            "quantity": 1, "category": l.get("category", "Other"),
        })
    return listings, sellers


# ---------------------------------------------------------------- Xmail -----
# Ambient mail so Sent / Drafts / Snoozed / Inbox aren't empty. To/From are
# obviously-filler people; subjects can't collide with any task's mail.
def _person(name, email):
    return {"name": name, "email": email}


_ALICE = _person("Alice Anderson", "alice@xmail.com")


def build_mail(iso_date):
    """iso_date: a fn(day_int) -> ISO timestamp on the frozen clock."""
    def em(i, folder, frm, to, subject, body, read=True, labels=None, starred=False):
        return {"id": f"amb_mail_{folder}_{i}",
                "threadId": f"amb_thread_{folder}_{i}",
                "from": frm, "to": [to], "cc": [], "bcc": [],
                "subject": subject, "body": body.replace("\n", "<br>"),
                "timestamp": iso_date((i % 9) + 10), "read": read,
                "starred": starred, "important": False,
                "labels": labels or [], "category": "primary",
                "folder": folder, "attachments": []}

    out = []
    # There used to be a dozen hand-written one-liners here to keep Sent /
    # Drafts / Snoozed and the category tabs from rendering empty. The authored
    # corpus below now covers every folder and category with full-length mail,
    # and those stubs were the most obviously synthetic thing in the mailbox —
    # two-sentence notes sitting next to real correspondence. Dropped.
    #
    # The authored corpus (tools/ambient_bulk.json, built by
    # tools/build_mail_corpus.py) across folders/categories.
    for j, m in enumerate(_BULK.get("mail", [])):
        frm = _person(m["from_name"], m["from_email"])
        to = _person(m["to_name"], m["to_email"])
        out.append({
            # Honor the authored id/threadId so a conversation actually threads.
            # Keying the thread on the row index gave every message its own
            # thread, which turned every reply into a separate inbox row.
            "id": m.get("id") or f"amb_bmail_{j}",
            "threadId": m.get("threadId") or f"amb_bthread_{j}",
            "from": frm, "to": [to], "cc": [], "bcc": [],
            "subject": m["subject"], "body": (m.get("body") or "").replace("\n", "<br>"),
            # Honor optional per-entry starred/important/labels/timestamp so the
            # authored emails carry their real emphasis; fall back to the old
            # defaults when a bulk entry omits them (backward compatible).
            "timestamp": m.get("timestamp") or iso_date((j % 20) + 1),
            "read": bool(m.get("read", True)),
            "starred": bool(m.get("starred", False)),
            "important": bool(m.get("important", False)),
            "labels": m.get("labels") or [], "category": m.get("category", "primary"),
            "folder": m.get("folder", "inbox"), "attachments": [],
            # Snoozed rows need a wake time or the Snoozed view has nothing to show.
            "snoozedUntil": m.get("snoozedUntil")
                or (f"2026-06-{(j % 27) + 1:02d}T09:00:00" if m.get("folder") == "snoozed" else None)})
    return out
