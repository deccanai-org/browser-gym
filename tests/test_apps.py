"""Pure-logic tests for the multi-app layer.

Commit 1 scope: the :class:`WorldState` wrapper + the append-only cross-app
event log (:mod:`server.apps.bus`). No browser, no FastAPI server — these
run under plain ``pytest`` with no Playwright dependency.

The behaviours pinned here are the ones the whole failure-harvesting story
leans on:
  * the existing ``GymState`` is wrapped, never copied or mutated;
  * the event log is append-only with stable, ordered ids;
  * an event with NO subscriber stays ``delivered=False`` (env never
    produced the effect) — distinguishable from a delivered event
    (``delivered=True``) that the agent simply never consumed.
"""

from __future__ import annotations

import pytest

from server.tasks import TASKS, make_task
from server.apps import bus
from server.apps.bus import emit, subscribe, clear_subscribers
from server.apps.world import WorldState
from server.apps.mail.state import make_mailstate
from server.apps.mail import mutations as mail_mut
from server.apps.food.state import make_foodstate
from server.apps.food import mutations as food_mut
from server.apps.market.state import make_marketstate
from server.apps.market import mutations as market_mut
from server.apps import wiring as apps_wiring

# These tests wrap a bare shop GymState and exercise the WorldState wrapper's
# delegation (w.step property) and the shop store's mutable fields
# (w.shop.step, w.shop.flash_messages). Category-M factories now return a
# *WorldState* (multi-app); wrapping one would double-nest and hit WorldState's
# read-only `step` property. So pin a single-app task whose factory yields a
# plain GymState. A1 is the canonical discovery fixture.
_TASK_ID = "A1/buy_wireless_mouse"


def _mail_world() -> WorldState:
    return WorldState(shop=make_task(_TASK_ID, 0), mail=make_mailstate(0))


def _full_world() -> WorldState:
    return WorldState(
        shop=make_task(_TASK_ID, 0),
        mail=make_mailstate(0), food=make_foodstate(0),
    )


@pytest.fixture(autouse=True)
def _clean_subscribers():
    # Each test starts and ends with an empty subscriber registry so tests
    # can install fakes without leaking into one another.
    clear_subscribers()
    yield
    clear_subscribers()


def _world(task_id: str = _TASK_ID, seed: int = 0) -> WorldState:
    return WorldState(shop=make_task(task_id, seed))


# --------------------------------------------------------------------------- #
# WorldState wraps GymState (unchanged)
# --------------------------------------------------------------------------- #

def test_worldstate_wraps_gymstate_unchanged():
    shop = make_task(_TASK_ID, 0)
    w = WorldState(shop=shop)
    assert w.shop is shop                       # same object, not a copy
    assert w.task_id == shop.task_id            # metadata delegates to shop
    assert w.seed == shop.seed
    assert w.step == shop.step
    assert w.finished == shop.finished
    assert w.mail is None and w.food is None and w.calendar is None
    assert w.events == []


def test_metadata_tracks_shop_mutations():
    w = _world()
    w.shop.step = 5
    w.shop.finished = True
    assert w.step == 5 and w.finished is True   # property, not a stale copy


# --------------------------------------------------------------------------- #
# Append-only event log
# --------------------------------------------------------------------------- #

def test_event_log_is_append_only_with_sequential_ids():
    w = _world()
    e1 = emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
              payload={"order_id": "SHOP-1"})
    e2 = emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
              payload={"order_id": "SHOP-2"})
    assert [e.id for e in w.events] == ["evt_1", "evt_2"]
    assert w.events[0] is e1 and w.events[1] is e2          # order preserved
    assert w.events[0].payload["order_id"] == "SHOP-1"      # earlier event untouched


def test_emit_copies_payload_so_caller_mutation_does_not_leak():
    w = _world()
    payload = {"order_id": "SHOP-1"}
    emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
         payload=payload)
    payload["order_id"] = "MUTATED"
    assert w.events[0].payload["order_id"] == "SHOP-1"


def test_emit_defaults_step_from_world():
    w = _world()
    w.shop.step = 7
    e = emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
             payload={})
    assert e.step == 7


# --------------------------------------------------------------------------- #
# Delivery: the env-bug vs agent-fault discriminator
# --------------------------------------------------------------------------- #

def test_event_without_subscriber_is_not_delivered():
    w = _world()
    e = emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
             payload={"order_id": "SHOP-1"})
    # No subscriber registered -> recorded but NOT delivered. This is the
    # signal that an env effect was never produced (NOT an agent failure).
    assert e.delivered is False
    assert w.events[0].delivered is False
    assert bus.has_delivered(w, "ShopOrderPlaced") is False


def test_subscriber_delivers_and_flips_delivered_flag():
    w = _world()
    seen: list[str] = []

    def handler(world, event):
        # A real subscriber writes the TARGET store; here we just record it.
        seen.append(event.payload["order_id"])

    subscribe("ShopOrderPlaced", handler)
    e = emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
             payload={"order_id": "SHOP-42"})
    assert e.delivered is True
    assert seen == ["SHOP-42"]
    assert bus.has_delivered(w, "ShopOrderPlaced") is True


def test_only_subscribed_type_is_delivered():
    w = _world()
    subscribe("ShopOrderPlaced", lambda world, event: None)
    emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail", payload={})
    emit(w, type="FoodOrderPlaced", source_app="food", target_app="mail", payload={})
    assert bus.has_delivered(w, "ShopOrderPlaced") is True
    assert bus.has_delivered(w, "FoodOrderPlaced") is False   # no handler -> not delivered


# --------------------------------------------------------------------------- #
# Inspection helpers
# --------------------------------------------------------------------------- #

def test_events_are_inspectable_by_type():
    w = _world()
    emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail", payload={})
    emit(w, type="FoodOrderPlaced", source_app="food", target_app="mail", payload={})
    emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail", payload={})
    assert len(bus.events_of_type(w, "ShopOrderPlaced")) == 2
    assert len(bus.events_of_type(w, "FoodOrderPlaced")) == 1
    assert {e.target_app for e in w.events} == {"mail"}


def test_worldstate_to_json_shape():
    w = _world()
    emit(w, type="ShopOrderPlaced", source_app="shop", target_app="mail",
         payload={"order_id": "X"})
    j = w.to_json()
    assert j["task_id"] == w.task_id
    assert isinstance(j["shop"], dict)
    assert j["mail"] is None and j["food"] is None and j["calendar"] is None
    assert j["events"][0]["type"] == "ShopOrderPlaced"
    assert j["events"][0]["delivered"] is False


# --------------------------------------------------------------------------- #
# Mail app — store seeding + mutation isolation (mutations touch ONLY MailState)
# --------------------------------------------------------------------------- #

def test_make_mailstate_seeds_default_inbox():
    m = make_mailstate(0)
    assert len(m.inbox) >= 2
    assert m.unread_count() >= 1
    # newest-first ordering
    ordered = m.ordered_inbox()
    assert [e.received_at for e in ordered] == sorted(
        (e.received_at for e in ordered), reverse=True,
    )


def test_make_mailstate_is_deterministic_per_seed():
    a, b = make_mailstate(0), make_mailstate(0)
    assert a.to_json() == b.to_json()         # reset reproduces the same inbox


def test_search_inbox_filters_and_empty_returns_all():
    m = make_mailstate(0)
    all_emails = mail_mut.search_inbox(m, "")
    assert len(all_emails) == len(m.inbox)
    dinner = mail_mut.search_inbox(m, "dinner")
    assert dinner and all("dinner" in e.subject.lower()
                          or "dinner" in e.body.lower() for e in dinner)
    assert mail_mut.search_inbox(m, "zzz-nonexistent") == []


def test_mark_read_only_touches_mailstate():
    w = _mail_world()
    shop_before = w.shop.to_json()
    unread = next(e for e in w.mail.inbox.values() if not e.read)
    r = mail_mut.mark_read(w.mail, unread.id)
    assert r["ok"] is True
    assert w.mail.inbox[unread.id].read is True
    assert w.shop.to_json() == shop_before     # shop untouched
    # bad id is a clean no-op error
    assert mail_mut.mark_read(w.mail, "nope")["ok"] is False


def test_send_email_appends_to_sent_only():
    w = _mail_world()
    shop_before = w.shop.to_json()
    inbox_ids_before = set(w.mail.inbox)
    r = mail_mut.send_email(w.mail, to="alex@example.com",
                            subject="Dinner Thursday?", body="Works for me.")
    assert r["ok"] is True
    assert r["email_id"] in w.mail.sent
    assert set(w.mail.inbox) == inbox_ids_before    # inbox unchanged
    assert w.shop.to_json() == shop_before          # shop untouched


def test_send_email_validates_recipient_and_subject():
    m = make_mailstate(0)
    assert mail_mut.send_email(m, to="not-an-email", subject="x")["ok"] is False
    assert mail_mut.send_email(m, to="a@b.com", subject="")["ok"] is False
    assert m.sent == {}                              # nothing sent on failure


def test_mail_mutation_batch_never_mutates_shop():
    """The headline isolation guarantee: a run of mail operations leaves the
    shop's GymState byte-for-byte identical."""
    w = _mail_world()
    shop_before = w.shop.to_json()
    for e in list(w.mail.inbox.values()):
        mail_mut.mark_read(w.mail, e.id)
    mail_mut.send_email(w.mail, to="x@y.com", subject="hi", body="there")
    mail_mut.search_inbox(w.mail, "deals")
    assert w.shop.to_json() == shop_before


# --------------------------------------------------------------------------- #
# Food app — store seeding + the FoodOrderPlaced -> Mail cross-app chain
# --------------------------------------------------------------------------- #

def test_make_foodstate_seeds_restaurants_and_is_deterministic():
    f = make_foodstate(0)
    assert len(f.restaurants) >= 2
    # Coffee pods exist so the cross-store price-compare task (M5) is possible.
    assert any(
        "pods" in d.tags
        for r in f.restaurants.values() for d in r.dishes
    )
    assert make_foodstate(0).to_json() == make_foodstate(0).to_json()


def test_add_dish_only_touches_foodstate():
    w = _full_world()
    shop_before, mail_before = w.shop.to_json(), w.mail.to_json()
    r = food_mut.add_dish(w.food, restaurant_id="r_sushi",
                          dish_id="d_salmon_roll", quantity=2)
    assert r["ok"] is True and w.food.cart.count() == 2
    assert w.shop.to_json() == shop_before     # shop untouched
    assert w.mail.to_json() == mail_before      # mail untouched


def test_food_cart_is_single_restaurant():
    w = _full_world()
    assert food_mut.add_dish(w.food, restaurant_id="r_sushi",
                             dish_id="d_salmon_roll")["ok"] is True
    bad = food_mut.add_dish(w.food, restaurant_id="r_burger", dish_id="d_classic")
    assert bad["ok"] is False and bad["error"] == "cart_has_other_restaurant"


def test_place_food_order_emits_and_delivers_receipt():
    # Register the real subscriber, exactly as the server does at startup.
    apps_wiring.register_default_subscribers()
    w = _full_world()
    shop_before = w.shop.to_json()
    food_mut.add_dish(w.food, restaurant_id="r_sushi", dish_id="d_salmon_roll")
    food_mut.add_dish(w.food, restaurant_id="r_sushi", dish_id="d_miso")
    r = food_mut.place_food_order(w)
    assert r["ok"] is True
    # FoodState: order created, cart cleared
    assert r["order_id"] in w.food.orders
    assert w.food.cart.count() == 0
    # Event log: appended AND delivered
    evs = bus.events_of_type(w, "FoodOrderPlaced")
    assert len(evs) == 1 and evs[0].delivered is True
    # Mail: a receipt email with the matching total + ETA arrived
    receipts = [e for e in w.mail.inbox.values() if e.order_id == r["order_id"]]
    assert len(receipts) == 1
    assert abs((receipts[0].amount_total or 0) - r["total"]) < 1e-9
    assert receipts[0].eta == r["eta"]
    # Shop: completely untouched by the food->mail chain
    assert w.shop.to_json() == shop_before


def test_place_food_order_without_subscriber_records_but_not_delivered():
    # The autouse fixture cleared the registry; we deliberately do NOT
    # register a subscriber. This is the env-bug case: the order exists but
    # no receipt was produced — and that is VISIBLE as delivered=False,
    # NOT silently mislabeled as the agent failing to read mail.
    w = _full_world()
    food_mut.add_dish(w.food, restaurant_id="r_burger", dish_id="d_classic")
    r = food_mut.place_food_order(w)
    assert r["ok"] is True
    evs = bus.events_of_type(w, "FoodOrderPlaced")
    assert len(evs) == 1 and evs[0].delivered is False
    assert not any(e.order_id == r["order_id"] for e in w.mail.inbox.values())


def test_place_food_order_empty_cart_fails():
    w = _full_world()
    assert food_mut.place_food_order(w)["ok"] is False


# --------------------------------------------------------------------------- #
# Xbay (2nd e-commerce store) — overlapping SKUs, coupon+delivery math,
# and the MarketOrderPlaced -> Mail cross-app chain
# --------------------------------------------------------------------------- #

def _market_world() -> WorldState:
    return WorldState(
        shop=make_task(_TASK_ID, 0),
        mail=make_mailstate(0), market=make_marketstate(0),
    )


def test_make_marketstate_overlaps_shop_and_is_deterministic():
    m = make_marketstate(0)
    assert len(m.products) >= 5
    # At least one SKU overlaps the main Xmazon store (so price-compare works)
    # and at least one is Xbay-exclusive.
    skus = [p.shop_sku for p in m.products.values()]
    assert "p_mouse_wireless" in skus           # overlaps Xmazon
    assert any(s is None for s in skus)          # a Xbay exclusive
    assert "VALUE10" in m.coupons                # the store-only coupon
    assert make_marketstate(0).to_json() == make_marketstate(0).to_json()


def test_market_add_only_touches_marketstate():
    w = _market_world()
    shop_before, mail_before = w.shop.to_json(), w.mail.to_json()
    r = market_mut.add_to_cart(w.market, product_id="vm_mouse_wireless")
    assert r["ok"] is True and w.market.cart.count() == 1
    assert w.shop.to_json() == shop_before       # shop untouched
    assert w.mail.to_json() == mail_before        # mail untouched


def test_market_quote_coupon_and_delivery_math():
    m = make_marketstate(0)
    # Under the free-delivery threshold: pay delivery. Mouse 24.99 + VALUE10.
    q = m.quote(subtotal=24.99, coupon_code="VALUE10")
    assert q == {"subtotal": 24.99, "discount": 2.50,
                 "delivery_fee": 5.99, "total": 28.48}
    # Over the threshold: free delivery. Keyboard 109.99 + VALUE10.
    q2 = m.quote(subtotal=109.99, coupon_code="VALUE10")
    assert q2["delivery_fee"] == 0.0 and q2["total"] == 98.99
    # No coupon, under threshold: sticker + delivery.
    q3 = m.quote(subtotal=24.99, coupon_code=None)
    assert q3["discount"] == 0.0 and q3["total"] == 30.98


def test_place_market_order_emits_and_delivers_receipt():
    apps_wiring.register_default_subscribers()
    w = _market_world()
    shop_before = w.shop.to_json()
    market_mut.add_to_cart(w.market, product_id="vm_kb_mech")   # 109.99
    market_mut.apply_coupon(w.market, "VALUE10")
    r = market_mut.place_order(w)
    assert r["ok"] is True
    assert r["order_id"] in w.market.orders
    assert w.market.cart.count() == 0
    # Event log: appended AND delivered
    evs = bus.events_of_type(w, "MarketOrderPlaced")
    assert len(evs) == 1 and evs[0].delivered is True
    # Mail: a confirmation email with the FINAL total (109.99 - 11.00, free ship)
    confs = [e for e in w.mail.inbox.values() if e.order_id == r["order_id"]]
    assert len(confs) == 1
    assert abs((confs[0].amount_total or 0) - 98.99) < 1e-9
    assert r["total"] == 98.99
    # Shop completely untouched by the market->mail chain
    assert w.shop.to_json() == shop_before


def test_place_market_order_without_subscriber_records_but_not_delivered():
    w = _market_world()
    market_mut.add_to_cart(w.market, product_id="vm_usb_cable")
    r = market_mut.place_order(w)
    assert r["ok"] is True
    evs = bus.events_of_type(w, "MarketOrderPlaced")
    assert len(evs) == 1 and evs[0].delivered is False
    assert not any(e.order_id == r["order_id"] for e in w.mail.inbox.values())


def test_place_market_order_empty_cart_fails():
    w = _market_world()
    assert market_mut.place_order(w)["ok"] is False
