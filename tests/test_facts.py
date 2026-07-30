"""Pure-logic tests for the per-step fact extractors (harness/facts.py).

No browser: extractors are pure functions over a world-snapshot dict.
"""

from __future__ import annotations

from harness.facts import (get_fact_extractor, _facts_m2, _facts_m3,
                           _facts_generic)


def test_m2_extractor_pulls_order_id_and_tracking():
    world = {
        "shop": {"orders": {"ORD-1042": {"total": 24.99}}},
        "mail": {"inbox": {
            "em_9": {"order_id": "ORD-1042",
                     "tracking_url": "/account/orders/ORD-1042/track",
                     "labels": ["orders"]},
            "em_1": {"order_id": None, "tracking_url": None,
                     "labels": ["updates"]},
        }},
    }
    f = _facts_m2(world, "/account/orders/ORD-1042/track")
    assert f["shop.order_id"] == "ORD-1042"
    assert f["mail.order_id"] == "ORD-1042"
    assert f["mail.tracking_url"] == "/account/orders/ORD-1042/track"


def test_m2_extractor_empty_before_order():
    # Mid-episode the world may have no order / no confirmation yet.
    assert _facts_m2({"shop": {"orders": {}}, "mail": {"inbox": {}}}, "/") == {}
    assert _facts_m2({}, "/") == {}                  # defensive: missing keys


def test_m3_extractor_pulls_food_and_receipt():
    world = {
        "food": {"orders": {"FOOD-1041": {"total": 16.00}}},
        "mail": {"inbox": {
            "em_5": {"order_id": "FOOD-1041", "amount_total": 16.00,
                     "eta": "7:20 PM", "labels": ["receipts"]},
        }},
    }
    f = _facts_m3(world, "/mail")
    assert f["food.order_id"] == "FOOD-1041"
    assert f["food.total"] == 16.00
    assert f["mail.receipt_total"] == 16.00
    assert f["mail.eta"] == "7:20 PM"


def test_registry_maps_bespoke_tasks_and_falls_back_generic():
    # Bespoke extractors still take precedence...
    assert get_fact_extractor("M2/order_then_track_via_email") is _facts_m2
    assert get_fact_extractor("M3/dinner_then_receipt") is _facts_m3
    # ...and any task without one gets the generic fallback (never None).
    assert get_fact_extractor("A1/buy_wireless_mouse") is _facts_generic


def test_generic_fallback_extracts_cross_app_facts():
    world = {
        "shop": {
            "orders": {"ORD-1": {"status": "confirmed"},
                       "ORD-2": {"status": "delivered"}},
            "cart": {"items": [{"product_id": "p_x"}]},
            "subscriptions": {"s1": {"status": "active"}},
        },
        "mail": {"inbox": {
            "e1": {"subject": "Hi", "read": False,
                   "received_at": "2026-05-21T09:00:00"},
            "e2": {"subject": "Older", "read": True,
                   "received_at": "2026-05-20T09:00:00"},
        }},
        "calendar": {"events": {
            "ev1": {"title": "Team sync", "source": "seed"},
            "ev2": {"title": "Dinner", "source": "user"},
        }},
        "food": {"orders": {"F1": {"status": "preparing"}}, "cart_count": 0},
        "market": {"orders": {"VM-1": {}}, "cart_count": 2},
    }
    f = _facts_generic(world, "/")
    assert f["shop.orders_count"] == 2
    assert f["shop.open_orders_count"] == 1          # ORD-1 confirmed, not ORD-2
    assert f["shop.cart_items"] == 1
    assert f["shop.active_subscriptions"] == 1
    assert f["mail.unread_count"] == 1
    assert f["mail.latest_inbox_subjects"][0] == "Hi"   # newest first
    assert f["calendar.event_count"] == 2
    assert f["calendar.user_event_count"] == 1
    assert f["food.active_orders_count"] == 1
    assert f["market.orders_count"] == 1
    assert f["market.cart_count"] == 2


def test_generic_fallback_is_defensive_on_empty_and_missing():
    assert _facts_generic({}, "/") == {}
    assert _facts_generic(None, "/") == {}            # never throws
    # Missing apps produce no keys, not crashes.
    assert _facts_generic({"shop": {}}, "/") == {}
