"""M385/S2 ValueMart West Launch Kit reachability (no LLM).

Proves the authority SKU is above the fold on the pinned viewport while the
East decoy remains present. Also confirms scroll can reveal a deliberately
offscreen product (scroll affordance works).
"""

from __future__ import annotations

import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from harness.runner import PINNED_VIEWPORT
from server.apps.sheets.exploratory.seeds import (
    EAST_LAUNCH_KIT_ID,
    WEST_LAUNCH_KIT_ID,
    seed_s2_market,
)
from server.main import app as live_app

TOKEN = "sheets-s2-vm-reach-token"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}
TASK_ID = "M385/cross_sheet_qty_authority"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server() -> tuple[uvicorn.Server, threading.Thread, str]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        live_app, host="127.0.0.1", port=port, log_level="warning",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(base, timeout=0.2).status_code == 200:
                return server, thread, base
        except httpx.HTTPError:
            time.sleep(0.05)
    raise AssertionError("ValueMart reachability test server did not start")


def test_s2_market_seed_is_kits_only():
    m = seed_s2_market()
    assert set(m.products) == {WEST_LAUNCH_KIT_ID, EAST_LAUNCH_KIT_ID}
    rows = sorted(m.products.values(), key=lambda p: (p.category, p.name))
    assert [p.name for p in rows] == ["East Launch Kit", "West Launch Kit"]


def test_west_launch_kit_above_fold_and_clickable(monkeypatch):
    """Pinned viewport: West is in view without scroll; Add + works."""
    pytest.importorskip("playwright")
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    server, thread, base = _start_server()
    try:
        reset = httpx.post(
            f"{base}/_harness/reset",
            json={"task_id": TASK_ID, "seed": 0},
            headers=AUTH,
            timeout=10,
        )
        assert reset.status_code == 200, reset.text

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport=dict(PINNED_VIEWPORT),
                device_scale_factor=1.0,
            )
            page.goto(f"{base}/market", wait_until="load")
            page.wait_for_selector("[data-test-id='market-product-list']")

            west = page.locator(
                f"[data-test-id='market-product-{WEST_LAUNCH_KIT_ID}']",
            )
            east = page.locator(
                f"[data-test-id='market-product-{EAST_LAUNCH_KIT_ID}']",
            )
            assert west.count() == 1
            assert east.count() == 1
            assert west.is_visible()
            assert east.is_visible()

            # Geometry: both cards intersect the pinned viewport (above fold).
            west_box = west.bounding_box()
            east_box = east.bounding_box()
            assert west_box is not None and east_box is not None
            vh = PINNED_VIEWPORT["height"]
            assert 0 <= west_box["y"] < vh
            assert west_box["y"] + west_box["height"] > 0
            assert 0 <= east_box["y"] < vh

            # Legitimate UI path: click West's Add + without scrolling.
            page.click(
                f"button[data-test-id='market-btn-add-{WEST_LAUNCH_KIT_ID}']",
            )
            page.wait_for_url("**/market/**")
            # Cart badge or cart page should reflect West, not East.
            snap = httpx.get(
                f"{base}/_harness/world", headers=AUTH, timeout=10,
            ).json()
            cart = snap.get("market", {}).get("cart", {}).get("items", [])
            assert len(cart) == 1
            assert cart[0]["product_id"] == WEST_LAUNCH_KIT_ID
            assert cart[0]["name"] == "West Launch Kit"
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_scroll_moves_viewport_content(monkeypatch):
    """Scroll affordance works: an offscreen marker can be brought into view."""
    pytest.importorskip("playwright")
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    server, thread, base = _start_server()
    try:
        reset = httpx.post(
            f"{base}/_harness/reset",
            json={"task_id": TASK_ID, "seed": 0},
            headers=AUTH,
            timeout=10,
        )
        assert reset.status_code == 200, reset.text

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport=dict(PINNED_VIEWPORT),
                device_scale_factor=1.0,
            )
            page.goto(f"{base}/market", wait_until="load")
            page.wait_for_selector("[data-test-id='market-product-list']")
            # Inject a tall spacer + marker below the fold.
            page.evaluate(
                """() => {
                  const marker = document.createElement('div');
                  marker.setAttribute('data-test-id', 'below-fold-marker');
                  marker.textContent = 'BELOW_FOLD_MARKER';
                  marker.style.marginTop = '2000px';
                  marker.style.padding = '8px';
                  document.querySelector('main')?.appendChild(marker);
                }""",
            )
            marker = page.locator("[data-test-id='below-fold-marker']")
            box0 = marker.bounding_box()
            assert box0 is not None
            assert box0["y"] >= PINNED_VIEWPORT["height"]
            page.mouse.wheel(0, 1800)
            page.wait_for_timeout(200)
            box1 = marker.bounding_box()
            assert box1 is not None
            assert box1["y"] < box0["y"]
            assert box1["y"] < PINNED_VIEWPORT["height"]
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
