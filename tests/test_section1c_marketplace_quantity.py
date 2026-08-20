"""Section 1C construct-validity checks for Xbay quantity actions."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any

import httpx
from playwright.async_api import async_playwright
import pytest
import uvicorn

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from harness.som import annotate_image, extract_marks


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "section1c-marketplace-quantity"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}
TASK_ID = "M358/approval_level_selects_market_quantity"
EVIDENCE_DIR = ROOT / "trajectories" / "prepublication_section1c_20260715"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def section1c_server():
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
        raise AssertionError("Section 1C server did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "Section 1C server did not stop"


def _reset(base: str, seed: int) -> None:
    response = httpx.post(
        f"{base}/_harness/reset",
        headers=AUTH,
        json={"task_id": TASK_ID, "seed": seed},
    )
    response.raise_for_status()


def _world(base: str) -> dict[str, Any]:
    response = httpx.get(f"{base}/_harness/world", headers=AUTH)
    response.raise_for_status()
    return response.json()


def _verify(base: str, url: str, step: int) -> dict[str, Any]:
    response = httpx.post(
        f"{base}/_harness/verify",
        headers=AUTH,
        json={"url": url, "step": step},
    )
    response.raise_for_status()
    return response.json()


def test_marketplace_quantity_via_visible_marked_add_button_is_reliable(
    section1c_server: str,
) -> None:
    async def run() -> None:
        runs: list[dict[str, Any]] = []
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                for run_index in range(12):
                    seed = run_index % 3
                    _reset(section1c_server, seed)
                    await page.goto(
                        f"{section1c_server}/market/product/vm_chair",
                        wait_until="load",
                    )

                    quantity = page.locator('input[name="quantity"]')
                    dom = await quantity.evaluate(
                        """el => ({
                            tag: el.tagName,
                            type: el.type,
                            name: el.name,
                            value: el.value,
                            disabled: el.disabled,
                            hidden: el.hidden,
                            display: getComputedStyle(el).display,
                            visibility: getComputedStyle(el).visibility,
                            rect: {
                                x: el.getBoundingClientRect().x,
                                y: el.getBoundingClientRect().y,
                                width: el.getBoundingClientRect().width,
                                height: el.getBoundingClientRect().height,
                            },
                        })"""
                    )
                    assert dom == {
                        "tag": "INPUT",
                        "type": "hidden",
                        "name": "quantity",
                        "value": "1",
                        "disabled": False,
                        "hidden": False,
                        "display": "none",
                        "visibility": "visible",
                        "rect": {"x": 0, "y": 0, "width": 0, "height": 0},
                    }
                    assert not await quantity.is_visible()
                    assert await quantity.is_enabled()

                    marks = await extract_marks(page)
                    add_mark = next(
                        mark for mark in marks
                        if mark.role == "button" and mark.name == "Add to cart"
                    )
                    assert not any(mark.role == "spinbutton" for mark in marks)
                    initial_marks = [mark.to_dict() for mark in marks]

                    if run_index < 3:
                        raw = await page.screenshot()
                        (EVIDENCE_DIR / f"market_product_seed{seed}_raw.png").write_bytes(raw)
                        (EVIDENCE_DIR / f"market_product_seed{seed}_som.png").write_bytes(
                            annotate_image(raw, marks)
                        )

                    click_latencies: list[int] = []
                    for _ in range(3):
                        marks = await extract_marks(page)
                        add_mark = next(
                            mark for mark in marks
                            if mark.role == "button" and mark.name == "Add to cart"
                        )
                        started = time.monotonic()
                        async with page.expect_navigation(wait_until="load"):
                            await page.mouse.click(*add_mark.center)
                        click_latencies.append(
                            round((time.monotonic() - started) * 1000)
                        )

                    await page.goto(f"{section1c_server}/market/cart", wait_until="load")
                    assert "× 3" in await page.locator(
                        '[data-test-id="market-cart-line-vm_chair"]'
                    ).inner_text()
                    cart_marks = await extract_marks(page)
                    place_mark = next(
                        mark for mark in cart_marks
                        if mark.role == "button" and mark.name == "Place order"
                    )
                    async with page.expect_navigation(wait_until="load"):
                        await page.mouse.click(*place_mark.center)
                    assert "/market/order/VM-2201" in page.url

                    world = _world(section1c_server)
                    order = world["market"]["orders"]["VM-2201"]
                    assert len(order["items"]) == 1
                    assert order["items"][0]["product_id"] == "vm_chair"
                    assert order["items"][0]["name"] == "Office Chair"
                    assert order["items"][0]["quantity"] == 3
                    verifier = _verify(section1c_server, page.url, run_index + 1)
                    assert verifier["success"] is False
                    assert not any(
                        row["name"] == "wrong_chair_quantity"
                        and row["fired_at_step"] >= 0
                        for row in verifier["all_milestones"]
                    )
                    runs.append({
                        "run": run_index + 1,
                        "seed": seed,
                        "product_dom": dom,
                        "product_marks": initial_marks,
                        "add_button_mark": add_mark.to_dict(),
                        "click_latencies_ms": click_latencies,
                        "cart_rendered_quantity": 3,
                        "order_id": order["id"],
                        "order_quantity": order["items"][0]["quantity"],
                        "verifier_success_before_required_email": verifier["success"],
                        "wrong_quantity_forbidden_fired": False,
                    })
            finally:
                await browser.close()

        (EVIDENCE_DIR / "interaction_probe.json").write_text(
            json.dumps({
                "task_id": TASK_ID,
                "sellable": False,
                "runs": runs,
                "successful_mark_clicks": sum(
                    len(row["click_latencies_ms"]) for row in runs
                ),
                "successful_orders": len(runs),
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    asyncio.run(run())
