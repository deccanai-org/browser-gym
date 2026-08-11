#!/usr/bin/env python3
"""Discoverability + FOI + mutation-oracle + coaching gates for mp_060 Friday rewrite."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.apps.food import mutations as food_mut  # noqa: E402
from server.state import log_action  # noqa: E402
from server.tasks import BRIEFS, make_task  # noqa: E402
from server.verifiers import Probe, build_suite  # noqa: E402
import server.mp_060 as t60  # noqa: E402

TID = t60.TASK_ID


def _probe(world, init, url="/"):
    return Probe(
        state=world.shop,
        url=url,
        initial_state=init.shop,
        world=world,
        initial_world=init,
    )


def _eval(world, init, url="/", step=0):
    return build_suite(TID).evaluate(_probe(world, init, url), current_step=step)


def coaching_clause_check() -> None:
    print("== coaching-clause ==")
    bad = (
        "once it's done", "make sure to verify", "email me at",
        "check the inbox for", "unless you", "will NOT work",
        "dinner saturday night will not",
    )
    brief = (BRIEFS.get("mp_060") or make_task(TID, 0).shop.task_brief or "").lower()
    hits = [b for b in bad if b in brief]
    assert not hits, ("coaching clause", hits, brief)
    # Prompt should mention veg + budget + for two without coaching the night.
    assert "vegetarian" in brief and "30" in brief and "for two" in brief
    assert "jamie" in brief
    print("  coaching OK mp_060")


def veg_and_for_two_scoring_decision() -> None:
    print("== veg / for-two scoring decision ==")
    w = make_task(TID, 0)
    dishes = {d.id: d for d in w.food.restaurants[t60.GOLD_REST].dishes}
    gold = dishes[t60.GOLD_DISH]
    meat = dishes[t60.TRAP_MEAT]
    assert "vegetarian" in (gold.tags or []), gold.tags
    assert "vegetarian" not in (meat.tags or []) and "meat" in (meat.tags or [])
    print("  DECISION: vegetarian scored via Dish.tags ['vegetarian'] (real field)")
    print("  DECISION: for-two scored via qty>=2 OR name/tags for-two (durable cart/order lines)")
    # Named for-two path
    assert food_mut.add_dish(
        w.food, dish_id=t60.GOLD_DISH, restaurant_id=t60.GOLD_REST, quantity=1
    ).get("ok")
    assert food_mut.set_scheduled_delivery(w.food, t60.FRI).get("scheduled_delivery") == t60.FRI
    placed = food_mut.place_food_order(w, scheduled_delivery=t60.FRI)
    assert placed.get("ok"), placed
    oid = placed["order_id"]
    order = w.food.orders[oid]
    assert order.scheduled_delivery == t60.FRI
    assert float(order.total) < t60.BUDGET, order.total
    line = order.items[0]
    assert "for two" in line.name.lower()
    print(f"  gold named-for-two total={order.total} < {t60.BUDGET} OK")

    # qty>=2 alternate path
    w2 = make_task(TID, 0)
    assert food_mut.add_dish(
        w2.food, dish_id=t60.VEG_SINGLE, restaurant_id=t60.GOLD_REST, quantity=2
    ).get("ok")
    food_mut.set_scheduled_delivery(w2.food, t60.FRI)
    placed2 = food_mut.place_food_order(w2, scheduled_delivery=t60.FRI)
    assert placed2.get("ok")
    o2 = w2.food.orders[placed2["order_id"]]
    assert o2.items[0].quantity >= 2
    assert float(o2.total) < t60.BUDGET, o2.total
    print(f"  qty>=2 veg bowls total={o2.total} < {t60.BUDGET} OK")


def discoverability() -> None:
    print("== discoverability ==")
    w = make_task(TID, 0)
    body = w.mail.inbox[t60.COUSIN_EMAIL_ID].body.lower()
    assert "friday" in body and "midday" in body
    assert ("1 to 8pm" in body) or ("1 to 8" in body)
    assert "sunday morning" in body
    assert "pottery" in body
    # No coaching clause dumping "dinner saturday will NOT work"
    assert "will not work" not in body
    print("  email facts: Fri midday / Sat pottery 1–8pm / Sun morning OK")

    cal = w.calendar
    assert t60.DENTIST_EVENT in cal.events
    assert cal.events[t60.DENTIST_EVENT].day == t60.THU
    # Friday has no blocking event
    fri_events = [e for e in cal.events.values() if e.day == t60.FRI]
    assert not fri_events, fri_events
    # Old Team sync must be gone
    assert not any("team sync" in (e.title or "").lower() for e in cal.events.values())
    print("  calendar: Thu dentist + Friday clear (no Team sync) OK")

    assert w.food.enable_schedule_ahead is True
    # Schedule-ahead Friday slot reachable from gym_now Thursday
    assert t60.FRI > t60.THU
    gold = w.food.restaurants[t60.GOLD_REST].dish(t60.GOLD_DISH)
    assert gold and "vegetarian" in gold.tags and gold.price + w.food.restaurants[t60.GOLD_REST].delivery_fee < t60.BUDGET
    print("  schedule-ahead Fri + veg+budget path OK")


def _fired(r: dict, name: str) -> bool:
    for m in r.get("all_milestones") or []:
        if m.get("name") == name and int(m.get("fired_at_step", -1)) >= 0:
            return True
    return name in (r.get("newly_fired") or [])


def foi_check() -> None:
    print("== FOI 0.0 ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    r = _eval(w, init, step=0)
    assert r.get("success") is False, r
    assert float(r.get("score") or 0) == 0.0, r
    fired_forbidden = [
        m["name"] for m in (r.get("all_milestones") or [])
        if m.get("forbidden") and int(m.get("fired_at_step", -1)) >= 0
    ]
    assert not fired_forbidden, ("forbidden at FOI", fired_forbidden)
    print(f"  FOI OK score={r.get('score')}")


def mutation_oracle() -> None:
    print("== mutation-oracle gold path ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    # Read email
    e = w.mail.inbox[t60.COUSIN_EMAIL_ID]
    e.read = True
    if "unread" in (e.labels or []):
        e.labels = [lb for lb in e.labels if lb != "unread"]
    # View calendar
    log_action(w.shop, "viewed_calendar")
    # Order gold Friday
    assert food_mut.add_dish(
        w.food, dish_id=t60.GOLD_DISH, restaurant_id=t60.GOLD_REST
    ).get("ok")
    food_mut.set_scheduled_delivery(w.food, t60.FRI)
    placed = food_mut.place_food_order(w, scheduled_delivery=t60.FRI)
    assert placed.get("ok"), placed
    r = _eval(w, init, url="/food/orders", step=10)
    assert r.get("success") is True, r
    assert abs(float(r.get("score") or 0) - 1.0) < 1e-6, r
    print(f"  gold path OK score={r.get('score')}")

    print("== mutation-oracle Saturday forbidden ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    w.mail.inbox[t60.COUSIN_EMAIL_ID].read = True
    log_action(w.shop, "viewed_calendar")
    food_mut.add_dish(w.food, dish_id=t60.GOLD_DISH, restaurant_id=t60.GOLD_REST)
    food_mut.set_scheduled_delivery(w.food, t60.SAT)
    food_mut.place_food_order(w, scheduled_delivery=t60.SAT)
    r = _eval(w, init, step=10)
    assert r.get("success") is False, r
    assert _fired(r, "ordered_on_saturday_conflict_night"), r
    print("  Saturday conflict forbidden fires OK")

    print("== mutation-oracle non-veg forbidden ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    w.mail.inbox[t60.COUSIN_EMAIL_ID].read = True
    log_action(w.shop, "viewed_calendar")
    food_mut.add_dish(w.food, dish_id=t60.TRAP_MEAT, restaurant_id=t60.GOLD_REST)
    food_mut.set_scheduled_delivery(w.food, t60.FRI)
    food_mut.place_food_order(w, scheduled_delivery=t60.FRI)
    r = _eval(w, init, step=10)
    assert r.get("success") is False, r
    assert _fired(r, "ordered_non_vegetarian_item"), r
    print("  non-veg forbidden fires OK")

    print("== mutation-oracle over-budget forbidden ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    w.mail.inbox[t60.COUSIN_EMAIL_ID].read = True
    log_action(w.shop, "viewed_calendar")
    food_mut.add_dish(w.food, dish_id=t60.TRAP_PRICE, restaurant_id=t60.GOLD_REST)
    food_mut.set_scheduled_delivery(w.food, t60.FRI)
    food_mut.place_food_order(w, scheduled_delivery=t60.FRI)
    r = _eval(w, init, step=10)
    assert r.get("success") is False, r
    assert _fired(r, "order_total_over_30"), r
    print("  over-budget forbidden fires OK")

    print("== mutation-oracle ASAP forbidden ==")
    w = make_task(TID, 0)
    init = copy.deepcopy(w)
    w.mail.inbox[t60.COUSIN_EMAIL_ID].read = True
    log_action(w.shop, "viewed_calendar")
    food_mut.add_dish(w.food, dish_id=t60.GOLD_DISH, restaurant_id=t60.GOLD_REST)
    # place without schedule → ASAP
    food_mut.place_food_order(w)
    r = _eval(w, init, step=10)
    assert r.get("success") is False, r
    assert _fired(r, "order_defaulted_to_asap_despite_future_pick"), r
    print("  ASAP forbidden fires OK")


def pottery_overlap_arithmetic() -> None:
    print("== pottery dinner-hours overlap arithmetic ==")
    # Pottery 13:00–20:00; dinner window ~18:00–21:00 → overlap
    pot_start, pot_end = 13 * 60, 20 * 60
    dinner_start, dinner_end = 18 * 60, 21 * 60
    overlap = max(0, min(pot_end, dinner_end) - max(pot_start, dinner_start))
    assert overlap > 0, overlap
    print(f"  overlap_minutes={overlap} OK")


def main() -> None:
    coaching_clause_check()
    veg_and_for_two_scoring_decision()
    discoverability()
    pottery_overlap_arithmetic()
    foi_check()
    mutation_oracle()
    print("\nALL mp_060 Friday-rewrite gates PASS")


if __name__ == "__main__":
    main()
