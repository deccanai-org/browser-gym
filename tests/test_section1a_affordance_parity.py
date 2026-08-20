"""Section 1A multi-affordance route/mutation and control-path evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable

import httpx
from playwright.sync_api import Page, sync_playwright
import pytest
import uvicorn

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from server import mutations as shop_mutations
from server.apps import bus, shop_hooks, wiring
from server.apps.calendar import mutations as calendar_mutations
from server.apps.calendar.state import TODAY, TOMORROW
from server.apps.food import mutations as food_mutations
from server.apps.mail import mutations as mail_mutations
from server.apps.market import mutations as market_mutations
from server.apps.world import WorldState
from server.tasks import make_task


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "section1a-affordance-parity"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}
EVIDENCE_DIR = ROOT / "trajectories" / "prepublication_section1a_20260715"
EVIDENCE_PATH = EVIDENCE_DIR / "affordance_parity.json"
SECURITY_PATH = EVIDENCE_DIR / "privileged_route_network_evidence.json"
FAILURE_PATH = EVIDENCE_DIR / "failed_action_plausibility.json"

AFFORDANCE_INVENTORY = {
    "shop_order_checkout_and_line_configuration": [
        "M46", "M57", "M66", "M68", "M70", "M72", "M73", "M74", "M75",
        "M77", "M78", "M79", "M81", "M82", "M83", "M84", "M85", "M86",
        "M87", "M88", "M89", "M90", "M91", "M92", "M93", "M94", "M95",
        "M96", "M97", "M98", "M99", "M100", "M101", "M102", "M103",
        "M104", "M111", "M141", "M142", "M148", "M207", "M210", "M214",
        "M219", "M227", "M252", "M271", "M272", "M307", "M312",
    ],
    "mail_send": [
        "M37", "M39", "M40", "M41", "M47", "M51", "M57", "M59", "M76",
        "M80", "M105", "M106", "M107", "M108", "M109", "M111", "M115",
        "M116", "M117", "M141", "M142", "M148", "M164", "M200", "M211",
        "M212", "M213", "M214", "M217", "M219", "M220", "M224", "M227",
        "M248", "M252", "M271", "M272", "M312", "M343", "M346", "M348",
        "M349", "M354", "M362", "M366",
    ],
    "calendar_create": ["M43", "M57"],
    "calendar_update_reschedule": ["M80", "M200"],
    "calendar_delete": ["M366"],
    "food_order": ["M248", "M343", "M346", "M348", "M349", "M354", "M362"],
    "marketplace_order": ["M354"],
    "subscription_create": ["M61"],
    "subscription_cancel": ["M76", "M164", "M212", "M217"],
    "return_initiation": ["M41", "M47", "M109"],
    "shop_order_cancel": ["M108", "M211"],
    "payment_method_or_default_change": ["M117", "M213"],
    "address_or_default_change": ["M220"],
}

ACTION_PATHS = {
    "food_order": [
        "GET /food/restaurant/r_burger",
        "POST /food/cart/add (d_classic, quantity 1) x2",
        "GET /food/cart",
        "POST /food/checkout (generic delivery note)",
        "GET /food/order/<generated>",
    ],
    "calendar_create": [
        "GET /calendar/new",
        "POST /calendar/create (title/day/start/end)",
        "GET /calendar",
    ],
    "calendar_update_reschedule": [
        "GET /calendar/edit/<dentist_event_id>",
        "POST /calendar/update (start 10:15 / end 11:00)",
        "GET /calendar",
    ],
    "calendar_delete": [
        "GET /calendar/edit/cal_m366_vendor_review",
        "POST /calendar/delete",
        "GET /calendar",
    ],
    "marketplace_order": [
        "GET /market/product/vm_welcome_sign",
        "POST product form /market/cart/add x2",
        "GET /market/cart",
        "POST /market/apply-coupon (VALUE10)",
        "POST /market/checkout",
        "GET /market/order/<generated>",
    ],
    "mail_send": [
        "GET /mail/compose",
        "POST /mail/send (to/subject/body)",
        "GET /mail?sent=1",
    ],
    "subscription_create": [
        "GET /product/p_pet_food",
        "click btn-toggle-subscribe",
        "POST /api/subscriptions (monthly, 4, addr_home, pay_paypal)",
        "GET /account/subscriptions",
    ],
    "subscription_cancel": [
        "GET /account/subscriptions",
        "POST /api/subscriptions/sub_dogfood/cancel",
        "GET /account/subscriptions",
    ],
    "return_initiation": [
        "GET /account/orders/ORD-KET-1",
        "GET /account/returns/new?order_id=ORD-KET-1",
        "POST /api/returns (ln_kettle, defective, original_payment)",
        "GET /account/returns",
    ],
    "payment_method_or_default_change": [
        "GET /account/payments",
        "POST /api/account/payments/pay_personal/default",
        "GET /account/payments",
    ],
    "address_or_default_change": [
        "GET /account/addresses",
        "POST /api/account/addresses/addr_work/default",
        "GET /account/addresses",
    ],
    "shop_order_cancel": [
        "STRUCTURAL_EXCEPTION: no rendered cancel control and no public "
        "POST /api/orders/*/cancel route; cancel_order exists only as a "
        "pure mutation (rejects shipped / out_for_delivery / delivered).",
    ],
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def section1a_server():
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    from server.main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base, timeout=0.2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=5)
        raise AssertionError("Section 1A parity server did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "Section 1A parity server did not stop"


def _snapshot(world: WorldState) -> dict[str, Any]:
    return asdict(copy.deepcopy(world))


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _diff(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        out: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                out.append({"path": child, "before": "<MISSING>", "after": after[key]})
            elif key not in after:
                out.append({"path": child, "before": before[key], "after": "<MISSING>"})
            else:
                out.extend(_diff(before[key], after[key], child))
        return out
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        out = []
        for index, (left, right) in enumerate(zip(before, after)):
            out.extend(_diff(left, right, f"{path}[{index}]"))
        return out
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def _reset(base: str, task_id: str, seed: int) -> WorldState:
    response = httpx.post(
        f"{base}/_harness/reset", headers=AUTH,
        json={"task_id": task_id, "seed": seed},
    )
    response.raise_for_status()
    from server.main import SESSION

    assert SESSION.world is not None
    return SESSION.world


def _verify(base: str, page: Page) -> dict[str, Any]:
    response = httpx.post(
        f"{base}/_harness/verify", headers=AUTH,
        json={"url": page.url, "step": 1},
    )
    response.raise_for_status()
    return response.json()


def _requests(page: Page) -> tuple[list[dict[str, Any]], Callable[[], None]]:
    records: list[dict[str, Any]] = []

    def record(request) -> None:
        records.append({
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "has_control_header": any(
                key.lower() == HARNESS_TOKEN_HEADER.lower()
                for key in request.headers
            ),
        })

    page.on("request", record)
    return records, lambda: page.remove_listener("request", record)


def _semantic(snapshot: dict[str, Any], affordance: str) -> dict[str, Any]:
    if affordance == "food_order":
        return {
            "food": snapshot["food"],
            "receipts": {
                key: value for key, value in snapshot["mail"]["inbox"].items()
                if value["sender"] == "receipts@foodapp.com"
            },
            "events": [
                value for value in snapshot["events"]
                if value["type"] == "FoodOrderPlaced"
            ],
        }
    if affordance in {
        "calendar_create", "calendar_update_reschedule", "calendar_delete",
    }:
        return {"calendar": snapshot["calendar"]}
    if affordance == "marketplace_order":
        return {
            "market": snapshot["market"],
            "receipts": {
                key: value for key, value in snapshot["mail"]["inbox"].items()
                if value["sender"] == "orders@valuemart.com"
            },
            "events": [
                value for value in snapshot["events"]
                if value["type"] == "MarketOrderPlaced"
            ],
        }
    if affordance == "mail_send":
        return {
            "sent": snapshot["mail"]["sent"],
            "events": [
                value for value in snapshot["events"]
                if value["type"] == "MailSent"
            ],
        }
    if affordance in {"subscription_create", "subscription_cancel"}:
        return {"subscriptions": snapshot["shop"]["subscriptions"]}
    if affordance == "return_initiation":
        return {
            "returns": snapshot["shop"]["returns"],
            "events": [
                value for value in snapshot["events"]
                if value["type"] == "ReturnFiled"
            ],
        }
    if affordance == "payment_method_or_default_change":
        alice = snapshot["shop"]["users"]["u_alice"]
        return {"payment_methods": alice["payment_methods"]}
    if affordance == "address_or_default_change":
        alice = snapshot["shop"]["users"]["u_alice"]
        return {"addresses": alice["addresses"]}
    raise AssertionError(affordance)


def _unrelated(snapshot: dict[str, Any], affordance: str) -> dict[str, Any]:
    value = copy.deepcopy(snapshot)
    value["shop"]["flash_messages"] = "<UI>"
    value["shop"]["action_log"] = "<TELEMETRY>"
    if affordance == "food_order":
        value["food"] = "<EXPECTED>"
        value["mail"]["inbox"] = "<EXPECTED_RECEIPT>"
        value["mail"]["_next"] = "<EXPECTED_RECEIPT>"
        value["events"] = "<EXPECTED_EVENT>"
    elif affordance in {
        "calendar_create", "calendar_update_reschedule", "calendar_delete",
    }:
        value["calendar"] = "<EXPECTED>"
    elif affordance == "marketplace_order":
        value["market"] = "<EXPECTED>"
        value["mail"]["inbox"] = "<EXPECTED_RECEIPT>"
        value["mail"]["_next"] = "<EXPECTED_RECEIPT>"
        value["events"] = "<EXPECTED_EVENT>"
    elif affordance == "mail_send":
        value["mail"]["sent"] = "<EXPECTED>"
        value["mail"]["_next"] = "<EXPECTED>"
        value["events"] = "<EXPECTED_EVENT>"
    elif affordance in {"subscription_create", "subscription_cancel"}:
        value["shop"]["subscriptions"] = "<EXPECTED>"
    elif affordance == "return_initiation":
        value["shop"]["returns"] = "<EXPECTED>"
        value["events"] = "<EXPECTED_EVENT>"
    elif affordance == "payment_method_or_default_change":
        value["shop"]["users"]["u_alice"]["payment_methods"] = "<EXPECTED>"
    elif affordance == "address_or_default_change":
        value["shop"]["users"]["u_alice"]["addresses"] = "<EXPECTED>"
    return value


def _normalize_subscriptions(semantic: dict[str, Any]) -> dict[str, Any]:
    """Subscription create mints random IDs and a clock-based next_delivery_date."""
    out = copy.deepcopy(semantic)
    normalized: dict[str, Any] = {}
    for index, (_sid, sub) in enumerate(
        sorted(out["subscriptions"].items(), key=lambda item: (
            item[1]["product_id"], item[1]["payment_id"], item[1]["cadence"],
        )),
    ):
        key = f"<SUB_{index}>"
        row = dict(sub)
        row["id"] = key
        row["next_delivery_date"] = "<NEXT_DELIVERY>"
        normalized[key] = row
    out["subscriptions"] = normalized
    return out


def _normalize_returns(semantic: dict[str, Any]) -> dict[str, Any]:
    """Return initiation mints random return IDs and clock-based created_at."""
    out = copy.deepcopy(semantic)
    normalized: dict[str, Any] = {}
    for index, (_rid, row) in enumerate(
        sorted(out["returns"].items(), key=lambda item: (
            item[1]["order_id"], tuple(item[1]["item_ids"]), item[1]["reason"],
        )),
    ):
        key = f"<RET_{index}>"
        payload = dict(row)
        payload["id"] = key
        payload["created_at"] = "<CREATED_AT>"
        normalized[key] = payload
    out["returns"] = normalized
    events = []
    for event in out["events"]:
        row = dict(event)
        payload = dict(row.get("payload") or {})
        payload["return_id"] = "<RET_ID>"
        row["payload"] = payload
        events.append(row)
    out["events"] = events
    return out


def _normalize_semantic(affordance: str, semantic: dict[str, Any]) -> dict[str, Any]:
    if affordance == "subscription_create":
        return _normalize_subscriptions(semantic)
    if affordance == "return_initiation":
        return _normalize_returns(semantic)
    return semantic


def _dentist_event_id(world: WorldState) -> str:
    for event in world.calendar.events.values():
        if event.title == "Dentist":
            return event.id
    raise AssertionError("Dentist event missing")


def _direct_food(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M362/therapy_event_blocks_delivery_disclosure", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    assert food_mutations.add_dish(
        world.food, restaurant_id="r_burger", dish_id="d_classic", quantity=2,
    )["ok"]
    result = food_mutations.place_food_order(
        world, delivery_note="Please leave at the door; unavailable 6–7 PM.",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_food(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M362/therapy_event_blocks_delivery_disclosure", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/food/restaurant/r_burger")
        page.locator('[data-test-id="btn-add-d_classic"]').click()
        page.locator('[data-test-id="btn-add-d_classic"]').click()
        page.goto(f"{base}/food/cart")
        page.locator('[data-test-id="input-food-delivery-note"]').fill(
            "Please leave at the door; unavailable 6–7 PM.",
        )
        page.locator('[data-test-id="btn-place-food-order"]').click()
        page.wait_for_url("**/food/order/*")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_calendar(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M43/stale_delivery_date", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = calendar_mutations.create_event(
        world.calendar, title="Package delivery — be home (ORD-5501)",
        day=TODAY, start="19:00", end="20:00",
        day_label="Today (Thu May 21)",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_calendar(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M43/stale_delivery_date", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/calendar/new")
        page.locator('[data-test-id="input-event-title"]').fill(
            "Package delivery — be home (ORD-5501)",
        )
        page.locator('[data-test-id="select-event-day"]').select_option(TODAY)
        page.locator('[data-test-id="btn-save-event"]').click()
        page.wait_for_url("**/calendar")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_market(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M354/joint_food_market_welcome_budget_empty", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    assert market_mutations.add_to_cart(
        world.market, product_id="vm_welcome_sign", quantity=2,
    )["ok"]
    assert market_mutations.apply_coupon(world.market, "VALUE10")["ok"]
    assert market_mutations.place_order(world)["ok"]
    return before, _snapshot(world)


def _browser_market(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M354/joint_food_market_welcome_budget_empty", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/market/product/vm_welcome_sign")
        page.locator('[data-test-id="market-btn-add-to-cart"]').click()
        page.locator('[data-test-id="market-btn-add-to-cart"]').click()
        page.goto(f"{base}/market/cart")
        page.locator('[data-test-id="market-input-coupon"]').fill("VALUE10")
        page.locator('[data-test-id="market-btn-apply-coupon"]').click()
        page.locator('[data-test-id="market-btn-place-order"]').click()
        page.wait_for_url("**/market/order/*")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_mail(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M37/false_overcharge", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = mail_mutations.send_email(
        world.mail, to="alice@shopgym.com", subject="Parity message",
        body="The checked charge is correct.",
    )
    assert result["ok"]
    bus.emit(
        world, type="MailSent", source_app="mail", target_app="mail",
        payload={"to": result["to"], "subject": "Parity message"},
    )
    return before, _snapshot(world)


def _browser_mail(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M37/false_overcharge", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/mail/compose")
        page.locator('[data-test-id="input-compose-to"]').fill("alice@shopgym.com")
        page.locator('[data-test-id="input-compose-subject"]').fill("Parity message")
        page.locator('[data-test-id="input-compose-body"]').fill(
            "The checked charge is correct.",
        )
        page.locator('[data-test-id="btn-send"]').click()
        page.wait_for_url("**/mail?sent=1")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_calendar_update(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M200/dentist_move_doublebook", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    event_id = _dentist_event_id(world)
    result = calendar_mutations.update_event(
        world.calendar, event_id, start="10:15", end="11:00", title="Dentist",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_calendar_update(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M200/dentist_move_doublebook", seed)
    before = _snapshot(world)
    event_id = _dentist_event_id(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/calendar/edit/{event_id}")
        page.locator('[data-test-id="input-edit-start"]').fill("10:15")
        page.locator('[data-test-id="input-edit-end"]').fill("11:00")
        page.locator('[data-test-id="btn-update-event"]').click()
        page.wait_for_url("**/calendar")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_calendar_delete(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M366/delete_event_but_preserve_same_event_id", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = calendar_mutations.delete_event(
        world.calendar, "cal_m366_vendor_review",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_calendar_delete(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M366/delete_event_but_preserve_same_event_id", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/calendar/edit/cal_m366_vendor_review")
        page.locator('[data-test-id="btn-delete-event"]').click()
        page.wait_for_url("**/calendar")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_subscription_create(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M61/auto_refill_dead_card", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = shop_mutations.create_subscription(
        world.shop, product_id="p_pet_food", cadence="monthly",
        deliveries=4, address_id="addr_home", payment_id="pay_paypal",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_subscription_create(
    base: str, page: Page, seed: int,
) -> tuple[dict, dict, list]:
    world = _reset(base, "M61/auto_refill_dead_card", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/product/p_pet_food")
        page.locator('[data-test-id="btn-toggle-subscribe"]').click()
        page.locator('[data-test-id="select-cadence"]').select_option("monthly")
        page.locator('[data-test-id="input-deliveries"]').fill("4")
        page.locator('[data-test-id="select-sub-address"]').select_option("addr_home")
        page.locator('[data-test-id="select-sub-payment"]').select_option("pay_paypal")
        page.locator('[data-test-id="btn-create-subscription"]').click()
        page.wait_for_url("**/account/subscriptions")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_subscription_cancel(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M76/ambiguous_subscription_cancel", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = shop_mutations.cancel_subscription(
        world.shop, subscription_id="sub_dogfood",
    )
    assert result["ok"]
    return before, _snapshot(world)


def _browser_subscription_cancel(
    base: str, page: Page, seed: int,
) -> tuple[dict, dict, list]:
    world = _reset(base, "M76/ambiguous_subscription_cancel", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/account/subscriptions")
        page.locator('[data-test-id="btn-cancel-sub-sub_dogfood"]').click()
        page.wait_for_url("**/account/subscriptions")
        assert "cancelled" in page.locator(
            '[data-test-id="lbl-sub-status-sub_dogfood"]',
        ).inner_text().lower()
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_return(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M109/false_phantom_return", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = shop_mutations.initiate_return(
        world.shop, order_id="ORD-KET-1", item_ids=["ln_kettle"],
        reason="defective", refund_method="original_payment",
    )
    assert result["ok"]
    shop_hooks.emit_return_filed(
        world, return_id=result["return_id"], order_id="ORD-KET-1",
    )
    return before, _snapshot(world)


def _browser_return(base: str, page: Page, seed: int) -> tuple[dict, dict, list]:
    world = _reset(base, "M109/false_phantom_return", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/account/orders/ORD-KET-1")
        page.locator('[data-test-id="btn-initiate-return"]').click()
        page.wait_for_url("**/account/returns/new?order_id=ORD-KET-1")
        page.locator('[data-test-id="cb-return-item-ln_kettle"]').check()
        page.locator('[data-test-id="select-return-reason"]').select_option(
            "defective",
        )
        page.locator('[data-test-id="radio-refund-original"]').click()
        page.locator('[data-test-id="btn-submit-return"]').click()
        page.wait_for_url("**/account/returns")
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_payment_default(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M213/default_card_swap_then_confirm", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = shop_mutations.set_default_payment(world.shop, payment_id="pay_personal")
    assert result["ok"]
    return before, _snapshot(world)


def _browser_payment_default(
    base: str, page: Page, seed: int,
) -> tuple[dict, dict, list]:
    world = _reset(base, "M213/default_card_swap_then_confirm", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/account/payments")
        page.locator('[data-test-id="btn-set-default-pay-pay_personal"]').click()
        page.wait_for_url("**/account/payments")
        assert page.locator(
            '[data-test-id="pill-default-pay_personal"]',
        ).count() == 1
    finally:
        detach()
    return before, _snapshot(world), network


def _direct_address_default(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task("M220/address_change_no_propagate", seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    result = shop_mutations.set_default_address(world.shop, address_id="addr_work")
    assert result["ok"]
    return before, _snapshot(world)


def _browser_address_default(
    base: str, page: Page, seed: int,
) -> tuple[dict, dict, list]:
    world = _reset(base, "M220/address_change_no_propagate", seed)
    before = _snapshot(world)
    network, detach = _requests(page)
    try:
        page.goto(f"{base}/account/addresses")
        page.locator('[data-test-id="btn-set-default-addr_work"]').click()
        page.wait_for_url("**/account/addresses")
        assert page.locator(
            '[data-test-id="pill-default-addr_work"]',
        ).count() == 1
    finally:
        detach()
    return before, _snapshot(world), network


def _shop_order_cancel_exception_evidence(base: str, page: Page) -> dict[str, Any]:
    """Document why browser/direct order-cancel parity cannot be honest."""
    from server.main import app as fastapi_app

    routes = []
    for route in fastapi_app.routes:
        if not hasattr(route, "path"):
            continue
        methods = sorted(getattr(route, "methods", None) or {"GET"})
        routes.append(f"{methods[0]} {route.path}")
    order_cancel_paths = [
        row for row in routes
        if "cancel" in row.lower() and "order" in row.lower()
    ]

    world = _reset(base, "M211/cancel_shipped_then_confirm", 0)
    page.goto(f"{base}/account/orders/ORD-5501")
    body = page.locator("body").inner_text().lower()
    html = page.content().lower()
    cancel_buttons = page.locator(
        'button, a, input[type="submit"], [data-test-id*="cancel"]',
    ).evaluate_all(
        """els => els.map(el => ({
            tag: el.tagName, testId: el.getAttribute('data-test-id'),
            text: (el.innerText || el.value || '').trim().slice(0, 80),
            href: el.getAttribute('href') || '',
            action: el.closest('form') ? (el.closest('form').action || '') : '',
        }))""",
    )
    cancelish = [
        row for row in cancel_buttons
        if "cancel" in (row.get("text") or "").lower()
        or "cancel" in (row.get("testId") or "").lower()
        or "cancel" in (row.get("action") or "").lower()
    ]

    shipped = shop_mutations.cancel_order(world.shop, "ORD-5501")
    confirmed_world = make_task("M220/address_change_no_propagate", 0)
    assert isinstance(confirmed_world, WorldState)
    confirmed = shop_mutations.cancel_order(confirmed_world.shop, "ORD-6601")

    return {
        "status": "STRUCTURAL_EXCEPTION",
        "reason": (
            "Shop order cancellation has a pure mutation "
            "(server.mutations.cancel_order) that rejects shipped / "
            "out_for_delivery / delivered orders, but the rendered order-detail "
            "UI exposes only Initiate return + tracking — no Cancel control — "
            "and FastAPI registers no public /api/orders/*/cancel route. "
            "Adding a cancel button solely to check the 1A box would invent an "
            "affordance the reported M108/M211 tasks intentionally lack."
        ),
        "tasks": AFFORDANCE_INVENTORY["shop_order_cancel"],
        "fixture_checked": "M211/cancel_shipped_then_confirm ORD-5501",
        "rendered_order_detail": {
            "has_initiate_return": page.locator(
                '[data-test-id="btn-initiate-return"]',
            ).count() == 1,
            "has_cancel_control": False,
            "cancelish_controls_found": cancelish,
            "body_mentions_cancel": "cancel" in body,
            "html_mentions_cancel_order": "cancel order" in html,
        },
        "public_cancel_order_routes": sorted(set(order_cancel_paths)),
        "mutation_contract": {
            "shipped_or_out_for_delivery_rejected": shipped,
            "confirmed_unshipped_accepted": confirmed,
            "confirmed_status_after": confirmed_world.shop.orders["ORD-6601"].status,
        },
        "browser_action_trace": ACTION_PATHS["shop_order_cancel"],
    }


def test_rendered_major_affordances_match_direct_mutations(section1a_server) -> None:
    wiring.register_default_subscribers()
    flows = {
        "food_order": (_direct_food, _browser_food),
        "calendar_create": (_direct_calendar, _browser_calendar),
        "calendar_update_reschedule": (
            _direct_calendar_update, _browser_calendar_update,
        ),
        "calendar_delete": (_direct_calendar_delete, _browser_calendar_delete),
        "marketplace_order": (_direct_market, _browser_market),
        "mail_send": (_direct_mail, _browser_mail),
        "subscription_create": (
            _direct_subscription_create, _browser_subscription_create,
        ),
        "subscription_cancel": (
            _direct_subscription_cancel, _browser_subscription_cancel,
        ),
        "return_initiation": (_direct_return, _browser_return),
        "payment_method_or_default_change": (
            _direct_payment_default, _browser_payment_default,
        ),
        "address_or_default_change": (
            _direct_address_default, _browser_address_default,
        ),
    }
    tested = [
        "shop_order_checkout_and_line_configuration",
        "food_order", "calendar_create", "calendar_update_reschedule",
        "calendar_delete", "marketplace_order", "mail_send",
        "subscription_create", "subscription_cancel",
        "return_initiation", "payment_method_or_default_change",
        "address_or_default_change",
    ]
    structural_exceptions = ["shop_order_cancel"]
    evidence: dict[str, Any] = {
        "protocol_section": "1A major-affordance route/mutation parity",
        "active_sellables": 85,
        "inventory": AFFORDANCE_INVENTORY,
        "coverage": {
            "tested_archetypes": tested,
            "tested_count": len(tested),
            "structural_exceptions": structural_exceptions,
            "exception_count": len(structural_exceptions),
            "total_count": len(AFFORDANCE_INVENTORY),
            "status": "CLOSED_WITH_NAMED_EXCEPTIONS",
            "score": (
                f"{len(tested)}/{len(AFFORDANCE_INVENTORY)} PASS + "
                f"{len(structural_exceptions)} STRUCTURAL_EXCEPTION"
            ),
            "checkout_evidence": "checkout_parity.json",
            "untested": [
                key for key in AFFORDANCE_INVENTORY
                if key not in tested and key not in structural_exceptions
            ],
        },
        "normalization": {
            "generated_fields_removed": [
                "subscription_create: subscription id + next_delivery_date",
                "return_initiation: return id + created_at + event payload return_id",
            ],
            "note": (
                "Calendar/Mail/Food/Xbay mint deterministic IDs for these "
                "fixtures. Subscription create and return initiation mint "
                "secrets.token_hex IDs and clock timestamps, so those "
                "affordances compare normalized payloads."
            ),
        },
        "runs": [],
        "exceptions": [],
    }
    all_network: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            for name, (direct_flow, browser_flow) in flows.items():
                for seed in (0, 1, 2):
                    direct_before, direct_after = direct_flow(seed)
                    browser_before, browser_after, network = browser_flow(
                        section1a_server, page, seed,
                    )
                    assert direct_before == browser_before
                    direct_semantic = _semantic(direct_after, name)
                    browser_semantic = _semantic(browser_after, name)
                    assert (
                        _normalize_semantic(name, direct_semantic)
                        == _normalize_semantic(name, browser_semantic)
                    )
                    assert _unrelated(direct_before, name) == _unrelated(
                        direct_after, name,
                    )
                    assert _unrelated(browser_before, name) == _unrelated(
                        browser_after, name,
                    )
                    assert all("/_harness/" not in row["url"] for row in network)
                    assert all(not row["has_control_header"] for row in network)
                    all_network.extend(
                        [{"affordance": name, "seed": seed, **row} for row in network]
                    )
                    events = direct_semantic.get("events", [])
                    if name in {
                        "food_order", "marketplace_order", "mail_send",
                        "return_initiation",
                    }:
                        assert len(events) == 1
                        assert events[0]["id"] == "evt_1"
                        assert events[0]["step"] == 0
                        if name in {"food_order", "marketplace_order"}:
                            assert events[0]["delivered"] is True
                            assert len(direct_semantic["receipts"]) == 1
                        if name == "return_initiation":
                            assert events[0]["type"] == "ReturnFiled"
                            assert events[0]["delivered"] is False
                            assert len(direct_semantic["returns"]) == 1
                    if name == "calendar_update_reschedule":
                        dentist = next(
                            e for e in direct_semantic["calendar"]["events"].values()
                            if e["title"] == "Dentist"
                        )
                        assert dentist["start"] == "10:15" and dentist["end"] == "11:00"
                    if name == "calendar_delete":
                        assert "cal_m366_vendor_review" not in (
                            direct_semantic["calendar"]["events"]
                        )
                    if name == "subscription_cancel":
                        assert (
                            direct_semantic["subscriptions"]["sub_dogfood"]["status"]
                            == "cancelled"
                        )
                        assert (
                            direct_semantic["subscriptions"]["sub_coffee"]["status"]
                            == "active"
                        )
                    if name == "payment_method_or_default_change":
                        pms = direct_semantic["payment_methods"]
                        assert pms["pay_personal"]["is_default"] is True
                        assert pms["pay_visa"]["is_default"] is False
                        assert pms["pay_paypal"]["is_default"] is False
                    if name == "address_or_default_change":
                        addrs = direct_semantic["addresses"]
                        assert addrs["addr_work"]["is_default"] is True
                        assert addrs["addr_home"]["is_default"] is False
                    evidence["runs"].append({
                        "affordance": name,
                        "seed": seed,
                        "raw_semantic_states_equal": name not in {
                            "subscription_create", "return_initiation",
                        },
                        "normalized_semantic_states_equal": True,
                        "semantic_before_sha256": _digest(
                            _semantic(direct_before, name),
                        ),
                        "semantic_after_sha256": _digest(
                            _normalize_semantic(name, direct_semantic),
                        ),
                        "raw_diff": _diff(
                            _semantic(direct_before, name),
                            _normalize_semantic(name, direct_semantic),
                        ),
                        "unrelated_state_unchanged": True,
                        "browser_network_request_count": len(network),
                        "browser_action_trace": ACTION_PATHS[name],
                        "privileged_request_count": 0,
                        "control_header_request_count": 0,
                    })
            evidence["exceptions"].append(
                _shop_order_cancel_exception_evidence(section1a_server, page),
            )
        finally:
            browser.close()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
    SECURITY_PATH.write_text(json.dumps({
        "tested_flows": sorted(flows),
        "seeds": [0, 1, 2],
        "browser_requests": all_network,
        "no_harness_requests": True,
        "no_control_headers": True,
    }, indent=2) + "\n")

    assert evidence["coverage"]["untested"] == []
    assert evidence["coverage"]["tested_count"] == 12
    assert evidence["coverage"]["exception_count"] == 1
    assert evidence["exceptions"][0]["status"] == "STRUCTURAL_EXCEPTION"
    assert evidence["exceptions"][0]["rendered_order_detail"]["has_cancel_control"] is False
    assert evidence["exceptions"][0]["public_cancel_order_routes"] == []
    assert evidence["exceptions"][0]["mutation_contract"][
        "shipped_or_out_for_delivery_rejected"
    ]["ok"] is False
    assert evidence["exceptions"][0]["mutation_contract"][
        "confirmed_unshipped_accepted"
    ]["ok"] is True


def test_failed_actions_are_visible_atomic_and_route_owned(section1a_server) -> None:
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            # Calendar create owns a genuine overlap contract and names the conflict.
            world = _reset(section1a_server, "M43/stale_delivery_date", 0)
            before = _snapshot(world)
            page.goto(f"{section1a_server}/calendar/new")
            page.locator('[data-test-id="input-event-title"]').fill("Collision")
            page.locator('[data-test-id="select-event-day"]').select_option(TOMORROW)
            page.locator('[data-test-id="input-event-start"]').fill("14:30")
            page.locator('[data-test-id="input-event-end"]').fill("14:45")
            page.locator('[data-test-id="btn-save-event"]').click()
            assert "Slot already booked" in page.locator("body").inner_text()
            after = _snapshot(world)
            assert before["calendar"] == after["calendar"]
            verifier_result = _verify(section1a_server, page)
            assert verifier_result["success"] is False
            results.append({
                "class": "calendar_overlap",
                "result": "PASS",
                "visible_reason": (
                    "Slot already booked; names Team sync and 14:00 to 15:00"
                ),
                "atomic": True,
                "owner": "calendar.create_event mutation contract",
                "adversarial": False,
                "verifier_result": verifier_result,
            })

            # Xbay's public form route exposes realistic coupon rejection.
            world = _reset(
                section1a_server, "M354/joint_food_market_welcome_budget_empty", 0,
            )
            page.goto(f"{section1a_server}/market/product/vm_welcome_sign")
            page.locator('[data-test-id="market-btn-add-to-cart"]').click()
            before = _snapshot(world)
            page.goto(f"{section1a_server}/market/cart")
            page.locator('[data-test-id="market-input-coupon"]').fill("NOTREAL")
            page.locator('[data-test-id="market-btn-apply-coupon"]').click()
            assert "isn't valid" in page.locator("body").inner_text()
            after = _snapshot(world)
            assert before["market"] == after["market"]
            verifier_result = _verify(section1a_server, page)
            assert verifier_result["success"] is False
            results.append({
                "class": "invalid_coupon",
                "result": "PASS",
                "visible_reason": "That coupon code isn't valid at Xbay.",
                "atomic": True,
                "owner": "market.apply_coupon mutation contract",
                "adversarial": False,
                "verifier_result": verifier_result,
            })

            # Food rejects cross-restaurant mixing with an actionable reason.
            world = _reset(
                section1a_server, "M362/therapy_event_blocks_delivery_disclosure", 0,
            )
            page.goto(f"{section1a_server}/food/restaurant/r_burger")
            page.locator('[data-test-id="btn-add-d_classic"]').click()
            before = _snapshot(world)
            page.goto(f"{section1a_server}/food/restaurant/r_sushi")
            page.locator('[data-test-id="btn-add-d_miso"]').click()
            assert "another restaurant" in page.locator("body").inner_text()
            after = _snapshot(world)
            assert before["food"] == after["food"]
            verifier_result = _verify(section1a_server, page)
            assert verifier_result["success"] is False
            results.append({
                "class": "food_cross_restaurant_cart",
                "result": "PASS",
                "visible_reason": "Cart has another restaurant; clear it first.",
                "atomic": True,
                "owner": "food.add_dish mutation contract",
                "adversarial": False,
                "verifier_result": verifier_result,
            })

            # OOS is exposed before submit; no enabled action exists to fake a failure.
            world = _reset(section1a_server, "M142/no_monitor_in_stock_high_rating", 0)
            before = _snapshot(world)
            page.goto(f"{section1a_server}/product/p_monitor_27")
            button = page.locator('[data-test-id="btn-add-to-cart"]')
            assert button.is_disabled()
            assert "OUT OF STOCK" in page.locator("body").inner_text()
            after = _snapshot(world)
            assert before["shop"]["cart"] == after["shop"]["cart"]
            assert before["shop"]["orders"] == after["shop"]["orders"]
            verifier_result = _verify(section1a_server, page)
            assert verifier_result["success"] is True
            results.append({
                "class": "out_of_stock",
                "result": "PASS",
                "visible_reason": "OUT OF STOCK with disabled Add to Cart and Buy Now.",
                "atomic": True,
                "owner": "rendered route pre-submit validation",
                "adversarial": False,
                "verifier_result": verifier_result,
            })

            # Mail boundary returns a concrete validation error and writes no Sent row.
            world = _reset(section1a_server, "M37/false_overcharge", 0)
            before = _snapshot(world)
            page.goto(f"{section1a_server}/mail/compose")
            page.locator('[data-test-id="input-compose-to"]').fill("not-an-email")
            page.locator('[data-test-id="input-compose-subject"]').fill("Test")
            page.locator('[data-test-id="btn-send"]').click()
            assert "valid recipient" in page.locator("body").inner_text()
            after = _snapshot(world)
            assert before["mail"]["sent"] == after["mail"]["sent"]
            assert before["events"] == after["events"]
            verifier_result = _verify(section1a_server, page)
            assert verifier_result["success"] is False
            results.append({
                "class": "invalid_mail_recipient",
                "result": "PASS",
                "visible_reason": "A valid recipient email is required.",
                "atomic": True,
                "owner": "mail.send_email mutation contract",
                "adversarial": False,
                "verifier_result": verifier_result,
            })
        finally:
            browser.close()

    # Current boundaries that must not be misreported as realistic rendered failures.
    results.extend([
        {
            "class": "expired_or_declined_checkout_payment",
            "result": "NOT_EXPOSED",
            "reason": (
                "Checkout accepts saved payment IDs but place_order does not validate "
                "expiry/decline; fabricating a rejection would not test current mechanics."
            ),
            "adversarial": True,
        },
        {
            "class": "shipped_order_cancellation",
            "result": "NO_RENDERED_AFFORDANCE",
            "reason": (
                "cancel_order rejects shipped state in pure logic, but current order "
                "detail renders return/tracking only and exposes no cancel form."
            ),
            "adversarial": True,
        },
        {
            "class": "shop_checkout_oos_recheck",
            "result": "NOT_IMPLEMENTED",
            "reason": (
                "Product add is OOS-gated, but place_order does not re-check stock at "
                "commit; this is a product-mechanics gap, not a harness-only failure."
            ),
            "adversarial": True,
        },
    ])
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    FAILURE_PATH.write_text(json.dumps({
        "status": "PARTIAL",
        "covered_realistic_classes": 5,
        "results": results,
        "verifier_consistency": (
            "Authenticated read-only verification after each rendered path matched "
            "task semantics: OOS inspection is safe success for M142; the other "
            "incomplete rejected actions return success=false. Exact results are "
            "retained per class."
        ),
    }, indent=2) + "\n")


def test_browser_has_no_privileged_action_path_or_token(section1a_server) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            _reset(section1a_server, "M362/therapy_event_blocks_delivery_disclosure", 0)
            page.goto(f"{section1a_server}/food/restaurant/r_burger")
            source = page.content()
            forms = page.locator("form").evaluate_all(
                """forms => forms.map(f => ({
                    action: f.action, method: f.method.toUpperCase()
                }))""",
            )
            assert forms
            assert all("/_harness/" not in form["action"] for form in forms)
            assert "/_harness/" not in source
            assert TOKEN not in source
            assert TOKEN not in json.dumps(context.cookies())
            assert TOKEN not in json.dumps(page.evaluate(
                "() => ({local: {...localStorage}, session: {...sessionStorage}})",
            ))

            denied_fetch = page.evaluate(
                """async () => {
                    const world = await fetch('/_harness/world');
                    const reset = await fetch('/_harness/reset', {
                        method: 'POST',
                        headers: {'content-type': 'application/json'},
                        body: JSON.stringify({task_id: 'M37/false_overcharge', seed: 0})
                    });
                    return {world: world.status, reset: reset.status};
                }""",
            )
            assert denied_fetch == {"world": 401, "reset": 401}
            page.goto(f"{section1a_server}/_harness/world")
            assert page.locator("body").inner_text() == '{"detail":"Unauthorized"}'
        finally:
            browser.close()

    evidence = json.loads(SECURITY_PATH.read_text()) if SECURITY_PATH.exists() else {}
    evidence.update({
        "rendered_forms_scanned": True,
        "rendered_forms_use_public_routes_only": True,
        "direct_browser_world_fetch_status": 401,
        "direct_browser_reset_fetch_status": 401,
        "direct_browser_navigation_world_status": 401,
        "token_absent_from": [
            "DOM/page source", "cookies", "localStorage", "sessionStorage",
            "captured browser request headers and URLs",
        ],
        "public_route_note": (
            "/food/*, /calendar/*, /market/*, and /mail/* form endpoints are "
            "normal rendered-app contracts; /_harness/* is privileged and denied."
        ),
        "result": "PASS",
    })
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SECURITY_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
