"""Ambient (browse-only) food content for GymEats.

Fills out the cuisine categories so the app doesn't feel empty. This is APPENDED
to the projection's restaurants/menuItems/reviews/orders — it never touches the
gym engine world, so no verifier sees it (verifiers read p.world.food). Every id
is amb_* so it can't collide with a task's restaurant/dish/order id.

Deterministic: no randomness, so a re-seed reproduces the same catalog.
"""

from __future__ import annotations

# cuisine -> (restaurants, dishes). Each restaurant: (name, rating, delivery_fee,
# eta_label). Each dish: (name, price, image_key, dietary_tags). Every restaurant
# in a cuisine serves that cuisine's dish list (its own dish instances).
_CUISINES: dict[str, dict] = {
    "Pizza": {
        "restaurants": [("Napoli Slice", 4.7, 1.99, "25-35 min"),
                        ("Crust & Co.", 4.5, 2.49, "30-40 min"),
                        ("Slice House", 4.3, 0.0, "20-30 min")],
        "dishes": [("Margherita Pizza", 13.99, "rest_pizza", ["vegetarian"]),
                   ("Pepperoni Pizza", 15.49, "rest_pizza", []),
                   ("Garlic Knots", 6.49, "garlic_knots", ["vegetarian"]),
                   ("Caprese Salad", 8.99, "salad", ["vegetarian"]),
                   ("Tiramisu", 6.99, "cake", ["vegetarian"])],
    },
    "Burgers": {
        "restaurants": [("Patty Palace", 4.6, 2.99, "20-30 min"),
                        ("The Grind House", 4.4, 1.49, "25-35 min"),
                        ("Smash Shack", 4.8, 0.0, "15-25 min")],
        "dishes": [("Classic Cheeseburger", 11.99, "cheeseburger", []),
                   ("Bacon Deluxe Burger", 13.49, "cheeseburger", []),
                   ("Veggie Burger", 10.99, "veggie_burger", ["vegetarian"]),
                   ("Crispy Fries", 4.49, "fries", ["vegetarian", "vegan"]),
                   ("Chocolate Shake", 5.49, "shake", ["vegetarian"])],
    },
    "Sushi": {
        "restaurants": [("Tokyo Bay", 4.7, 3.49, "30-45 min"),
                        ("Wasabi Grove", 4.5, 2.49, "25-40 min")],
        "dishes": [("Salmon Avocado Roll", 9.99, "sushi", []),
                   ("Spicy Tuna Bowl", 13.49, "poke_bowl", []),
                   ("Miso Soup", 3.99, "miso_soup", ["vegetarian"]),
                   ("Vegetable Spring Rolls", 6.49, "spring_rolls", ["vegetarian", "vegan"]),
                   ("Edamame Salad", 5.99, "salad", ["vegetarian", "vegan"])],
    },
    "Chinese": {
        "restaurants": [("Golden Dragon", 4.4, 1.99, "30-40 min"),
                        ("Panda Garden", 4.2, 0.0, "25-35 min"),
                        ("Wok This Way", 4.6, 2.49, "20-30 min")],
        "dishes": [("Pork Dumplings", 8.49, "dumplings", []),
                   ("Vegetable Spring Rolls", 5.99, "spring_rolls", ["vegetarian", "vegan"]),
                   ("Chicken Ramen", 11.99, "ramen", []),
                   ("Kung Pao Noodles", 10.49, "pad_thai", []),
                   ("Fortune Cookie Cheesecake", 6.49, "cake", ["vegetarian"])],
    },
    "Mexican": {
        "restaurants": [("El Sombrero", 4.6, 2.49, "25-35 min"),
                        ("Taco Fiesta", 4.5, 1.49, "20-30 min"),
                        ("Casa Verde", 4.3, 0.0, "30-40 min")],
        "dishes": [("Carnitas Tacos", 10.99, "tacos", []),
                   ("Beef Burrito", 11.49, "burrito", []),
                   ("Veggie Burrito", 9.99, "burrito", ["vegetarian"]),
                   ("Chips & Guacamole", 6.49, "salad", ["vegetarian", "vegan"]),
                   ("Churros", 5.49, "donut", ["vegetarian"])],
    },
    "Indian": {
        "restaurants": [("Taj Spice", 4.7, 2.99, "35-45 min"),
                        ("Curry Leaf", 4.5, 1.99, "30-40 min"),
                        ("Mumbai Masala", 4.4, 0.0, "30-45 min")],
        "dishes": [("Butter Chicken Curry", 14.49, "curry", ["gluten_free"]),
                   ("Chicken Biryani", 13.99, "biryani", ["gluten_free"]),
                   ("Paneer Tikka Masala", 12.99, "curry", ["vegetarian", "gluten_free"]),
                   ("Vegetable Samosas", 5.99, "spring_rolls", ["vegetarian", "vegan"]),
                   ("Mango Lassi", 4.49, "shake", ["vegetarian"])],
    },
    "Thai": {
        "restaurants": [("Bangkok Street", 4.6, 2.49, "30-40 min"),
                        ("Thai Orchid", 4.4, 1.99, "25-35 min")],
        "dishes": [("Pad Thai", 12.49, "pad_thai", []),
                   ("Green Curry", 13.49, "thai_curry", ["gluten_free"]),
                   ("Tom Yum Soup", 6.99, "miso_soup", ["gluten_free"]),
                   ("Thai Spring Rolls", 5.99, "spring_rolls", ["vegetarian", "vegan"]),
                   ("Mango Sticky Rice", 6.49, "cake", ["vegetarian", "vegan"])],
    },
    "Italian": {
        "restaurants": [("Bella Napoli", 4.7, 2.99, "30-45 min"),
                        ("Trattoria Roma", 4.5, 1.99, "35-45 min"),
                        ("Pasta Fresca", 4.6, 0.0, "25-40 min")],
        "dishes": [("Spaghetti Bolognese", 13.99, "pasta", []),
                   ("Baked Lasagna", 14.49, "lasagna", []),
                   ("Margherita Pizza", 12.99, "rest_pizza", ["vegetarian"]),
                   ("Caprese Salad", 8.49, "salad", ["vegetarian"]),
                   ("Tiramisu", 6.99, "cake", ["vegetarian"])],
    },
    "Healthy": {
        "restaurants": [("Green Bowl", 4.6, 1.99, "20-30 min"),
                        ("Fresh & Fit", 4.5, 0.0, "20-30 min")],
        "dishes": [("Vegan Buddha Bowl", 12.99, "vegan_platter", ["vegetarian", "vegan"]),
                   ("Salmon Poke Bowl", 13.99, "poke_bowl", ["gluten_free"]),
                   ("Garden Salad", 8.99, "salad", ["vegetarian", "vegan", "gluten_free"]),
                   ("Quinoa Power Bowl", 11.49, "vegan_platter", ["vegetarian", "vegan"]),
                   ("Green Smoothie", 5.99, "shake", ["vegetarian", "vegan"])],
    },
    "Dessert": {
        "restaurants": [("Sweet Tooth", 4.8, 1.49, "20-30 min"),
                        ("Sugar Rush", 4.6, 0.0, "15-25 min"),
                        ("Scoops", 4.7, 2.49, "20-30 min")],
        "dishes": [("Chocolate Cake Slice", 6.99, "cake", ["vegetarian"]),
                   ("Ice Cream Sundae", 5.99, "ice_cream", ["vegetarian"]),
                   ("Glazed Donuts (6)", 7.49, "donut", ["vegetarian"]),
                   ("Butter Croissant", 3.99, "croissant", ["vegetarian"]),
                   ("Vanilla Milkshake", 5.49, "shake", ["vegetarian"])],
    },
    "Coffee": {
        "restaurants": [("The Daily Grind", 4.7, 0.99, "15-25 min"),
                        ("Brew Lab", 4.6, 0.0, "15-20 min")],
        "dishes": [("Oat Milk Latte", 5.25, "latte", ["vegetarian", "vegan"]),
                   ("Cappuccino", 4.75, "latte", ["vegetarian"]),
                   ("Butter Croissant", 3.99, "croissant", ["vegetarian"]),
                   ("Blueberry Muffin", 3.49, "cake", ["vegetarian"]),
                   ("Coffee Pods (24-pack)", 18.99, "coffee_pods", [])],
    },
    "Breakfast": {
        "restaurants": [("Sunny Side Up", 4.6, 1.99, "20-30 min"),
                        ("Morning Glory", 4.5, 0.0, "20-30 min")],
        "dishes": [("Pancake Stack", 9.49, "pancakes", ["vegetarian"]),
                   ("Oatmeal Breakfast Box", 6.99, "breakfast_box", ["vegetarian", "vegan"]),
                   ("Avocado Toast", 8.49, "sandwich", ["vegetarian"]),
                   ("Butter Croissant", 3.99, "croissant", ["vegetarian"]),
                   ("Fresh Latte", 4.75, "latte", ["vegetarian"])],
    },
    "Sandwiches": {
        "restaurants": [("The Deli Counter", 4.5, 1.49, "20-30 min"),
                        ("Sub Culture", 4.4, 0.0, "20-30 min")],
        "dishes": [("Club Sandwich", 10.49, "sandwich", []),
                   ("Chicken Gyro Wrap", 9.99, "gyro", []),
                   ("Veggie Wrap", 8.99, "burrito", ["vegetarian", "vegan"]),
                   ("Crispy Fries", 4.49, "fries", ["vegetarian", "vegan"]),
                   ("Garden Salad", 7.99, "salad", ["vegetarian", "vegan"])],
    },
}

# Per-dish-name photo override. The cuisine tables above reuse ~32 generic keys,
# so different dishes (e.g. Mango Lassi + Chocolate Shake) collapsed onto one
# photo. These give every DISTINCT dish name its own image; the same dish served
# at several restaurants still shares its photo (which is realistic). Keys resolve
# to /assets/food/<key>.jpg like any other. Projection-only -> no verifier sees it.
_DISH_NAME_IMAGE = {
    "Veggie Burrito": "dish_veggie_burrito", "Veggie Wrap": "dish_veggie_wrap",
    "Blueberry Muffin": "dish_blueberry_muffin", "Chocolate Cake Slice": "dish_chocolate_cake",
    "Fortune Cookie Cheesecake": "dish_cheesecake", "Mango Sticky Rice": "dish_mango_sticky_rice",
    "Bacon Deluxe Burger": "dish_bacon_burger", "Paneer Tikka Masala": "dish_paneer_tikka",
    "Churros": "dish_churros", "Cappuccino": "dish_cappuccino", "Fresh Latte": "dish_fresh_latte",
    "Tom Yum Soup": "dish_tom_yum", "Kung Pao Noodles": "dish_kung_pao",
    "Salmon Poke Bowl": "dish_salmon_poke", "Pepperoni Pizza": "dish_pepperoni_pizza",
    "Caprese Salad": "dish_caprese", "Chips & Guacamole": "dish_guacamole",
    "Edamame Salad": "dish_edamame", "Chocolate Shake": "dish_chocolate_shake",
    "Green Smoothie": "dish_green_smoothie", "Mango Lassi": "dish_mango_lassi",
    "Avocado Toast": "dish_avocado_toast", "Thai Spring Rolls": "dish_thai_spring_rolls",
    "Vegetable Samosas": "dish_samosas", "Quinoa Power Bowl": "dish_quinoa_bowl",
}


# A few short reviews reused (deterministically) across restaurants.
_REVIEW_POOL = [
    ("Jordan M.", 5, "Fast delivery and everything was still hot. Will order again!"),
    ("Priya S.", 4, "Great food, generous portions. Packaging could be better."),
    ("Sam T.", 5, "One of my favorites in the area. The flavors are spot on."),
    ("Alex R.", 4, "Solid choice for a weeknight. Arrived a little early too."),
    ("Casey L.", 3, "Good but a bit pricey for what you get."),
    ("Dana W.", 5, "Consistently excellent. Highly recommend the specials."),
]


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


import json as _json
import pathlib as _pathlib

# Each ambient restaurant now has its OWN unique menu — unique dish names and a
# unique generated photo per dish (gf_<restaurant>_<i>). No two restaurants share
# a dish or an image, so the app stops looking like a copy-paste. Authored offline
# (see tools/ambient_food_menus.json); ids stay amb_r_<slug>/amb_d_<slug>_<i> so
# ambient orders + favourites below keep resolving.
_MENUS = _json.loads((_pathlib.Path(__file__).with_name("ambient_food_menus.json")).read_text())


def build_ambient(_food_img, _svg_tile):
    """Return (restaurants, menu_items, reviews). Images resolved via the passed
    projection helpers so there's a single source of truth for asset paths."""
    restaurants, menu_items, reviews = [], [], []
    rev_i = 0
    for r in _MENUS:
        rname = r["name"]; cuisine = r["cuisine"]; rid = f"amb_r_{_slug(rname)}"
        fee = r["fee"]; eta = r["eta"]
        for di, d in enumerate(r["dishes"]):
            menu_items.append({
                "id": f"amb_d_{_slug(rname)}_{di}", "restaurantId": rid,
                "category": cuisine, "name": d["name"], "description": f"{d['name']} from {rname}.",
                "price": d["price"], "imageUrl": _food_img(d["image_key"]),
                "isPopular": di == 0, "isAvailable": True,
                "dietaryTags": d.get("tags", []), "customizationGroups": [],
            })
        restaurants.append({
            "id": rid, "name": rname,
            "imageUrl": _food_img(r["dishes"][0]["image_key"]),
            "cuisineType": [cuisine], "rating": r["rating"],
            "reviewCount": 40 + (len(rname) * 7) % 260,
            "priceRange": "$$", "deliveryFee": fee, "etaLabel": eta,
            "deliveryTimeMin": int(eta.split("-")[0]), "deliveryTimeMax": int(eta.split("-")[1].split()[0]),
            "distance": round(0.5 + (len(rname) % 5) * 0.4, 1), "isOpen": True,
            "hours": "10:00 AM - 10:00 PM", "address": "", "phone": "", "isSponsored": False,
            "promotions": (["$0 Delivery Fee"] if fee == 0 else []),
            "categories": [cuisine], "tags": [], "supportsPickup": True,
            "pickupTimeMin": 10, "pickupTimeMax": 20,
        })
        # two deterministic reviews per restaurant
        for _ in range(2):
            who, stars, text = _REVIEW_POOL[rev_i % len(_REVIEW_POOL)]
            reviews.append({"id": f"amb_rev_{_slug(rname)}_{rev_i}", "restaurantId": rid,
                            "userName": who, "rating": stars, "comment": text,
                            "createdAt": "2026-05-1%dT12:00:00" % (rev_i % 9 + 1)})
            rev_i += 1
    return restaurants, menu_items, reviews


# A couple of clearly-past ambient orders so the order history / reorder aren't
# empty. Delivered (not active), amb_ ids, projection-only -> no verifier sees them.
def ambient_orders(menu_by_id):
    def line(did, qty):
        m = menu_by_id.get(did) or {}
        return {"cartItemId": f"amb_line_{did}", "menuItem": m, "quantity": qty,
                "modifiers": {}, "instructions": ""}
    return [
        {"id": "amb_order_1", "restaurantId": "amb_r_patty_palace",
         "restaurantName": "Patty Palace", "status": "delivered",
         "items": [line("amb_d_patty_palace_0", 1), line("amb_d_patty_palace_3", 1)],
         "subtotal": 16.48, "deliveryFee": 2.99, "serviceFee": 1.50, "tax": 1.60,
         "tip": 3.00, "total": 25.57, "placedAt": "2026-05-18T19:20:00",
         "deliveryAddress": None, "etaLabel": "Delivered", "deliveryPerson": None},
        {"id": "amb_order_2", "restaurantId": "amb_r_the_daily_grind",
         "restaurantName": "The Daily Grind", "status": "delivered",
         "items": [line("amb_d_the_daily_grind_0", 2)],
         "subtotal": 10.50, "deliveryFee": 0.99, "serviceFee": 1.00, "tax": 1.05,
         "tip": 2.00, "total": 15.54, "placedAt": "2026-05-20T08:45:00",
         "deliveryAddress": None, "etaLabel": "Delivered", "deliveryPerson": None},
    ]


AMBIENT_FAVORITES = ["amb_r_patty_palace", "amb_r_tokyo_bay", "amb_r_green_bowl"]
