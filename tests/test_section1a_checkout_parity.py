"""Section 1A rendered-checkout versus direct-mutation parity evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
import re
import socket
import threading
import time
from typing import Any

import httpx
from playwright.sync_api import sync_playwright
import pytest
import uvicorn

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from server import mutations
from server.apps import shop_hooks, wiring
from server.apps.world import WorldState
from server.state import Cart, log_action
from server.tasks import make_task


ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "M73/expired_card_checkout"
TOKEN = "section1a-checkout-parity"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}
EVIDENCE_PATH = (
    ROOT / "trajectories" / "prepublication_section1a_20260715"
    / "checkout_parity.json"
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def checkout_server():
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
        raise AssertionError("checkout parity server did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "checkout parity server did not stop"


def _snapshot(world: WorldState) -> dict[str, Any]:
    """Capture complete in-memory state; this never performs the browser action."""
    return asdict(copy.deepcopy(world))


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


def _normalization_map(after: dict[str, Any]) -> dict[str, str]:
    orders = after["shop"]["orders"]
    order = next(iter(orders.values()))
    shipment = order["shipments"][0]
    return {
        next(iter(orders)): "<ORDER_ID>",
        order["id"]: "<ORDER_ID>",
        order["placed_at"]: "<TIMESTAMP>",
        shipment["id"]: "<SHIPMENT_ID>",
        shipment["tracking_number"]: "<TRACKING_NUMBER>",
        shipment["events"][0]["timestamp"]: "<TIMESTAMP>",
    }


def _normalize(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            replacements.get(str(k), str(k)): _normalize(v, replacements)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_normalize(v, replacements) for v in value]
    if isinstance(value, str):
        result = value
        for actual, placeholder in sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True,
        ):
            result = result.replace(actual, placeholder)
        return result
    return value


def _semantic_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    shop = snapshot["shop"]
    orders = list(shop["orders"].values())
    order = orders[-1] if orders else None
    receipts = [
        email for email in snapshot["mail"]["inbox"].values()
        if "orders" in email["labels"] and email["order_id"]
    ]
    return {
        "order": order,
        "inventory": {
            "p_coffee_maker": shop["products"]["p_coffee_maker"]["stock"],
        },
        "payment_default_flags": {
            key: value["is_default"]
            for key, value in shop["users"]["u_alice"]["payment_methods"].items()
        },
        "addresses": shop["users"]["u_alice"]["addresses"],
        "cart": shop["cart"],
        "receipt": receipts[-1] if receipts else None,
        "events": snapshot["events"],
    }


def _unrelated_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(snapshot)
    shop = value["shop"]
    shop["cart"] = "<EXPECTED_MUTATION>"
    shop["orders"] = "<EXPECTED_MUTATION>"
    shop["products"]["p_coffee_maker"]["stock"] = "<EXPECTED_MUTATION>"
    shop["action_log"] = "<ROUTE_TELEMETRY>"
    shop["flash_messages"] = "<EPHEMERAL_UI>"
    value["mail"]["inbox"] = "<EXPECTED_RECEIPT>"
    value["mail"]["_next"] = "<EXPECTED_RECEIPT>"
    value["events"] = "<EXPECTED_EVENT>"
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _direct_checkout(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    world = make_task(TASK_ID, seed)
    assert isinstance(world, WorldState)
    before = _snapshot(world)
    # Reproduce the normal checkout route's navigation telemetry/trigger, then
    # call the exact mutation used by pure-logic tests and dispatch its event.
    log_action(world.shop, "checkout_step", step="address")
    shop_hooks.emit_shop_checkout_reached(world)
    log_action(world.shop, "checkout_step", step="payment")
    log_action(world.shop, "checkout_step", step="review")
    result = mutations.place_order(world.shop, payment_id="pay_paypal")
    assert result["ok"] is True
    shop_hooks.emit_shop_order_placed(world, result["order_id"])
    # The rendered confirmation page consumes flash messages through _ctx.
    world.shop.flash_messages.clear()
    return before, _snapshot(world)


def _browser_checkout(
    base: str, page, seed: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    reset = httpx.post(
        f"{base}/_harness/reset", headers=AUTH,
        json={"task_id": TASK_ID, "seed": seed},
    )
    reset.raise_for_status()
    from server.main import SESSION

    assert SESSION.world is not None
    authenticated_before = httpx.get(
        f"{base}/_harness/world", headers=AUTH,
    )
    authenticated_before.raise_for_status()
    assert authenticated_before.json() == SESSION.world.to_json()
    before = _snapshot(SESSION.world)
    page.goto(f"{base}/cart")
    page.locator('[data-test-id="btn-proceed-checkout"]').click()
    page.locator('[data-test-id="btn-continue-payment"]').click()
    page.locator('[data-test-id="btn-continue-review"]').click()
    page.locator('[data-test-id="select-final-payment"]').select_option("pay_paypal")
    page.locator('[data-test-id="btn-place-order"]').click()
    page.wait_for_url(re.compile(r"/order/ORD_[A-F0-9]+$"))
    assert SESSION.world is not None
    authenticated_after = httpx.get(
        f"{base}/_harness/world", headers=AUTH,
    )
    authenticated_after.raise_for_status()
    assert authenticated_after.json() == SESSION.world.to_json()
    return before, _snapshot(SESSION.world), page.url


def _assert_required_fields(state: dict[str, Any]) -> None:
    order = state["order"]
    assert order is not None
    assert len(order["items"]) == 1
    item = order["items"][0]
    assert item["product_id"] == "p_coffee_maker"
    assert item["quantity"] == 1
    assert item["unit_price"] == 59.99
    assert item["ship_to_address_id"] == "addr_home"
    assert order["subtotal"] == 59.99
    assert order["discount"] == 0.0
    assert order["tax"] == 5.10
    assert order["shipping"] == 5.99
    assert order["total"] == 71.08
    assert order["payment_id"] == "pay_paypal"
    assert state["inventory"]["p_coffee_maker"] == 63
    assert state["cart"]["items"] == []
    assert state["receipt"]["order_id"] == order["id"]
    assert state["receipt"]["to"] == "alice@shopmail.com"
    assert state["receipt"]["amount_total"] == order["total"]
    assert order["id"] in state["receipt"]["subject"]
    placed = [e for e in state["events"] if e["type"] == "ShopOrderPlaced"]
    assert len(placed) == 1 and placed[0]["delivered"] is True
    assert placed[0]["payload"]["order_id"] == order["id"]


def test_rendered_checkout_matches_direct_mutation(checkout_server) -> None:
    wiring.register_default_subscribers()
    runs = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            for seed in (0, 1, 2):
                direct_before, direct_after = _direct_checkout(seed)
                browser_before, browser_after, final_url = _browser_checkout(
                    checkout_server, page, seed,
                )
                assert direct_before == browser_before
                direct_semantic = _semantic_state(direct_after)
                browser_semantic = _semantic_state(browser_after)
                _assert_required_fields(direct_semantic)
                _assert_required_fields(browser_semantic)

                direct_map = _normalization_map(direct_after)
                browser_map = _normalization_map(browser_after)
                normalized_direct = _normalize(direct_semantic, direct_map)
                normalized_browser = _normalize(browser_semantic, browser_map)
                assert normalized_browser == normalized_direct
                assert _unrelated_projection(direct_before) == _unrelated_projection(
                    direct_after,
                )
                assert _unrelated_projection(browser_before) == _unrelated_projection(
                    browser_after,
                )

                runs.append({
                    "seed": seed,
                    "browser_final_url": final_url,
                    "browser_action_path": [
                        "/cart", "/checkout/address", "/checkout/payment",
                        "/checkout/review", "POST /api/checkout/place",
                    ],
                    "direct_action_path": [
                        "mutations.place_order(payment_id='pay_paypal')",
                        "shop_hooks.emit_shop_order_placed(order_id)",
                    ],
                    "raw_diff": {
                        "browser": _diff(browser_before, browser_after),
                        "direct": _diff(direct_before, direct_after),
                    },
                    "normalized_diff": {
                        "browser": _diff(
                            _normalize(_semantic_state(browser_before), browser_map),
                            normalized_browser,
                        ),
                        "direct": _diff(
                            _normalize(_semantic_state(direct_before), direct_map),
                            normalized_direct,
                        ),
                    },
                    "normalized_semantic_states_equal": True,
                    "unrelated_state": {
                        "browser_before_sha256": _digest(
                            _unrelated_projection(browser_before),
                        ),
                        "browser_after_sha256": _digest(
                            _unrelated_projection(browser_after),
                        ),
                        "direct_before_sha256": _digest(
                            _unrelated_projection(direct_before),
                        ),
                        "direct_after_sha256": _digest(
                            _unrelated_projection(direct_after),
                        ),
                        "unchanged": True,
                    },
                    "field_results": {
                        "order_line_quantity_total": "PASS",
                        "inventory_exact_decrement": "PASS",
                        "payment_instrument": "PASS",
                        "ship_to_address_and_line_routing": "PASS",
                        "cart_cleared": "PASS",
                        "receipt_reference_and_recipient": "PASS",
                        "event_and_subscriber_delivery": "PASS",
                        "no_unrelated_mutation": "PASS",
                    },
                })
        finally:
            browser.close()

    evidence = {
        "protocol_section": "1A checkout route/mutation parity",
        "task_id": TASK_ID,
        "seeds": [0, 1, 2],
        "result": "PASS",
        "browser_action_used_harness_control": False,
        "harness_control_usage": [
            "authenticated reset",
            "authenticated /_harness/world before/after snapshots",
        ],
        "inventory_snapshot_note": (
            "The authenticated world snapshot was cross-checked byte-for-byte "
            "against the same live WorldState; the test additionally captured "
            "the in-process product catalog because GymState.to_json exposes "
            "only products_count, not per-product stock."
        ),
        "normalization": {
            "only": [
                "generated order id", "placed timestamp", "generated shipment id",
                "generated tracking number", "shipment-event timestamp",
            ],
            "substantive_fields_removed": False,
        },
        "failure_path_boundary": {
            "comparable_browser_checkout_rejection_available": False,
            "reason": (
                "The rendered review select can submit only saved payment IDs. "
                "place_order rejects login/cart/payment/address shape errors but "
                "does not validate card expiry or re-check inventory at commit, "
                "so declined-card/OOS checkout rejection parity cannot be tested "
                "without fabricating a path the current UI does not expose."
            ),
            "direct_empty_cart_atomicity_test": (
                "test_place_order_empty_cart_rejects_without_partial_mutation"
            ),
        },
        "runs": runs,
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n")


def test_place_order_empty_cart_rejects_without_partial_mutation() -> None:
    world = make_task(TASK_ID, 0)
    assert isinstance(world, WorldState)
    world.shop.cart = Cart()
    before = _snapshot(world)
    result = mutations.place_order(world.shop, payment_id="pay_paypal")
    assert result == {"ok": False, "error": "cart empty"}
    after = _snapshot(world)
    before["shop"]["flash_messages"] = []
    after["shop"]["flash_messages"] = []
    assert after == before
