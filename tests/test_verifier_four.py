"""HTML-named verifiers for FB5 / M430 / M346 / UI041."""

from __future__ import annotations

import copy

from server.apps.food.state import FoodCartItem, FoodOrder
from server.apps.mail.state import Email
from server.apps.market.state import MarketCartItem, MarketOrder
from server.state import Order, OrderItem
from server.tasks import BRIEFS, TASKS, make_task
from server.verifiers import Probe, build_suite
from server import verifier_four as v4

TASK_IDS = (v4.FB5_ID, v4.M430_ID, v4.M346_ID, v4.UI041_ID)

HTML_REQUIRED = {
    v4.FB5_ID: (
        "order_placed_and_active",
        "xbay_notebooks_and_pens",
        "xbay_coupon_applied",
        "sakura_order_correct_items",
        "all_arrive_before_friday_morning",
        "emailed_alice_stores_total_cap",
    ),
    v4.M430_ID: (
        "told_alice_pot_already_delivered",
        "zero_replacement_orders",
    ),
    v4.M346_ID: (
        "order_placed_and_active",
        "three_distinct_candidate_emails",
        "eta_email_nova",
        "eta_email_quinn",
        "eta_email_riley",
    ),
    v4.UI041_ID: (
        "read_service",
        "asked_size",
        "did_not_buy",
    ),
}


def _probe(task_id: str) -> Probe:
    world = make_task(task_id, 0)
    return Probe(
        state=world.shop,
        url="/",
        initial_state=copy.deepcopy(world.shop),
        world=world,
        initial_world=copy.deepcopy(world),
        active_tab_url="/",
    )


def _alice_mail(world, body: str, to: str = "alice@xmail.com", subject: str = "update") -> None:
    eid = world.mail.new_id()
    world.mail.sent[eid] = Email(
        id=eid, sender="agent@xmazon.com", to=to, subject=subject,
        body=body, received_at="2026-05-21T12:00:00", folder="sent",
    )


def _vm_lines(world, pids, coupon="VALUE10"):
    items = [
        MarketCartItem(product_id=pid, name=pid, unit_price=10.0, quantity=1)
        for pid in pids
    ]
    world.market.orders["VM-TEST-FB5"] = MarketOrder(
        id="VM-TEST-FB5", items=items, subtotal=67.0, discount=6.7,
        delivery_fee=0.0, total=60.30, placed_at="2026-05-21T12:00:00",
        coupon_code=coupon,
    )


def _food(world, dish_id, qty=1, oid="FOOD-TEST", restaurant_id="r_sushi",
          restaurant_name="Sakura Sushi", extra=None):
    items = [
        FoodCartItem(
            dish_id=dish_id, restaurant_id=restaurant_id, name=dish_id,
            unit_price=10.0, quantity=qty,
        )
    ]
    if extra:
        items.extend(extra)
    world.food.orders[oid] = FoodOrder(
        id=oid, restaurant_id=restaurant_id, restaurant_name=restaurant_name,
        items=items, subtotal=51.49, delivery_fee=3.99, total=51.49,
        placed_at="2026-05-21T12:00:00", eta_label="11:45 AM", status="preparing",
    )


def _shop_buy(world, pid, oid="ORD-TEST"):
    world.shop.orders[oid] = Order(
        id=oid, user_id="u_alice", placed_at="2026-05-21T12:00:00",
        items=[OrderItem(
            id=f"ln-{pid}", product_id=pid, product_name=pid,
            variant_id=None, variant_label="", quantity=1, unit_price=10.0,
            gift_wrap=False, gift_message="", ship_to_address_id="addr_home",
            scheduled_delivery=None,
        )],
        subtotal=10.0, discount=0.0, tax=0.0, shipping=0.0, total=10.0,
        promo_code=None, payment_id="pay_visa", status="confirmed",
    )


def test_four_tasks_registered_with_html_ids():
    for tid, names in HTML_REQUIRED.items():
        assert tid in TASKS
        suite = build_suite(tid)
        got = [m.name for m in suite.milestones if m.required_for_success]
        assert got == list(names)


def test_briefs_are_screenshot_xnames_and_xmail():
    assert BRIEFS["FB5"].startswith("Jason starts this Friday")
    assert "alice@xmail.com" in BRIEFS["FB5"]
    assert "Xbay" in BRIEFS["FB5"]
    assert BRIEFS["M430"].startswith("I ordered an Ardenne")
    assert "alice@xmail.com" in BRIEFS["M430"]
    assert "if you cannot track it down" in BRIEFS["M430"]
    assert BRIEFS["M346"] == (
        "Order lunch for tomorrow's three candidate interviews. The interview times "
        "and the candidates' contact details are in my calendar and my mail. Once "
        "the order is placed, email each candidate their respective delivery "
        "estimate separately so they know when lunch arrives."
    )
    assert BRIEFS["UI041"].startswith("Car service is on Xoogle Calendar")
    assert "Xmazon" in BRIEFS["UI041"]
    assert "Xmail" in BRIEFS["UI041"]


def test_step0_requireds_false_except_vacuous():
    for tid in TASK_IDS:
        p = _probe(tid)
        suite = build_suite(tid)
        for ms in suite.milestones:
            fired = ms.check(p)
            if ms.forbidden:
                assert not fired, f"{tid} forbidden {ms.name} true at step 0"
            if ms.required_for_success and ms.name not in (
                "xbay_coupon_applied",
                "all_arrive_before_friday_morning",
                "zero_replacement_orders",
                "did_not_buy",
            ):
                assert not fired, f"{tid} required {ms.name} true at step 0"


def test_fb5_gold_path_and_xmail_recap():
    p = _probe(v4.FB5_ID)
    _vm_lines(p.world, [v4.VM_MAT, v4.VM_NOTEBOOKS, v4.VM_PENS])
    _food(
        p.world, "d_tuna_bowl", qty=2,
        extra=[
            FoodCartItem(dish_id="d_salmon_roll", restaurant_id="r_sushi",
                         name="roll", unit_price=12.5, quantity=1),
            FoodCartItem(dish_id="d_miso", restaurant_id="r_sushi",
                         name="miso", unit_price=3.5, quantity=2),
        ],
    )
    _alice_mail(
        p.world,
        "Xbay charged $60.30 with VALUE10. Sakura / xber Eats was $51.49. "
        "Total $111.79, inside Samantha's $120 cap.",
    )
    assert v4.order_placed_and_active_fb5(p)
    assert v4.xbay_notebooks_and_pens(p)
    assert v4.xbay_coupon_applied(p)
    assert v4.sakura_order_correct_items(p)
    assert v4.all_arrive_before_friday_morning(p)
    assert v4.emailed_alice_stores_total_cap(p)
    ev = build_suite(v4.FB5_ID).evaluate(p, 1)
    assert ev["success"]


def test_m430_gold_is_tell_and_do_not_buy():
    p = _probe(v4.M430_ID)
    assert "ORD-ARDENNE-4" in p.world.shop.orders
    assert p.world.shop.orders["ORD-ARDENNE-4"].status == "delivered"
    _alice_mail(
        p.world,
        "The Ardenne Dutch oven was already delivered Tuesday. "
        "Signed by concierge Vassiliou; collect it from the 2nd-floor mail room. "
        "I did not order a replacement.",
    )
    assert v4.told_alice_pot_already_delivered(p)
    assert v4.zero_replacement_orders(p)
    assert build_suite(v4.M430_ID).evaluate(p, 1)["success"]


def test_m430_buy_breaks():
    p = _probe(v4.M430_ID)
    _alice_mail(p.world, "Ardenne already delivered; mail room 2nd floor.")
    _shop_buy(p.world, "p_m430_ardenne_dutch")
    assert not v4.zero_replacement_orders(p)
    assert not build_suite(v4.M430_ID).evaluate(p, 1)["success"]


def test_m346_gold_separate_eta_emails():
    p = _probe(v4.M346_ID)
    _food(
        p.world, "d_interview_lunch_346", qty=1, oid="FOOD-346",
        restaurant_id="r_burger", restaurant_name="Burger Barn",
    )
    for addr, name in (
        ("nova.patel@candidates.example.com", "Nova"),
        ("quinn.park@candidates.example.com", "Quinn"),
        ("riley.chen@candidates.example.com", "Riley"),
    ):
        eid = p.world.mail.new_id()
        p.world.mail.sent[eid] = Email(
            id=eid, sender="alice@xmail.com", to=addr,
            subject=f"Lunch ETA for {name}",
            body="Lunch delivery estimate is 9:45 AM.",
            received_at="2026-05-21T12:00:00", folder="sent",
        )
    assert v4.m346_order_placed_and_active(p)
    assert v4.three_distinct_candidate_emails(p)
    assert v4.eta_email_nova(p)
    assert v4.eta_email_quinn(p)
    assert v4.eta_email_riley(p)
    assert build_suite(v4.M346_ID).evaluate(p, 1)["success"]


def test_ui041_gold_ask_do_not_buy():
    p = _probe(v4.UI041_ID)
    # Opening the car-service event itself — a generic calendar glance no
    # longer counts as having read the booking.
    p.world.shop.action_log.append(
        {"kind": "viewed_event_edit", "event_id": "amb_cal_11"}
    )
    _alice_mail(
        p.world,
        "Which wiper size / fitment should I buy? I couldn't find it in Xmazon or Xmail.",
    )
    assert v4.read_service(p)
    assert v4.asked_size(p)
    assert v4.did_not_buy(p)
    assert build_suite(v4.UI041_ID).evaluate(p, 1)["success"]


def test_ui041_buy_breaks():
    p = _probe(v4.UI041_ID)
    p.world.shop.action_log.append({"kind": "viewed_calendar"})
    _alice_mail(p.world, "Which size should I order?")
    _shop_buy(p.world, "p_ui041_2220")
    assert not v4.did_not_buy(p)
    assert not build_suite(v4.UI041_ID).evaluate(p, 1)["success"]
