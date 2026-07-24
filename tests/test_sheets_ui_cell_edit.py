"""UI/API smoke for Sheets scaffold click-to-edit + expanded S3 grid.

Mostly FastAPI TestClient. One Playwright case covers Name-box → Save
(selection via Name box, not grid click) and the empty-selection toast.
"""

from __future__ import annotations

import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from server.apps.sheets.exploratory.seeds import sheet_named
from server.apps.sheets.exploratory.task_hook import EXPLORATORY_S1_ID
from server.main import SESSION, app

TOKEN = "sheets-ui-test-token"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}


def _client() -> TestClient:
    return TestClient(app)


def _reset(client: TestClient, task_id: str, seed: int = 0) -> None:
    r = client.post(
        "/_harness/reset",
        json={"task_id": task_id, "seed": seed},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_workbook_html_has_cell_edit_affordances(monkeypatch):
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = _client()
    _reset(client, EXPLORATORY_S1_ID, 0)
    html = client.get("/sheets").text
    assert 'data-test-id="formula-input"' in html
    assert 'data-test-id="btn-cell-save"' in html
    assert 'data-test-id="name-box"' in html
    assert 'data-test-id="sheets-toast"' in html
    assert 'data-test-id="sheets-grid"' in html
    assert "data-row=" in html
    assert "selectByA1" in html
    assert "Select a cell before saving" in html


def test_set_cell_via_commands_updates_sum_and_workbook_get(monkeypatch):
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = _client()
    _reset(client, EXPLORATORY_S1_ID, 0)
    sheets = SESSION.world.sheets
    approved = sheet_named(sheets.active_workbook(), "Approved Lines")
    # Activate Approved Lines
    r = client.post(
        "/sheets/api/commands",
        json={
            "command_type": "set_active_sheet",
            "payload": {"sheet_id": approved.id},
            "base_revision": sheets.revision,
            "idempotency_key": "t-activate",
        },
    )
    assert r.status_code == 200 and r.json()["ok"]
    rev = r.json()["revision"]
    # B6 row=5 col=1 → 2 so SUM=6
    r2 = client.post(
        "/sheets/api/commands",
        json={
            "command_type": "set_cell",
            "payload": {
                "sheet_id": approved.id, "row": 5, "col": 1, "input": 2,
            },
            "base_revision": rev,
            "idempotency_key": "t-edit-b6",
        },
    )
    body = r2.json()
    assert r2.status_code == 200 and body["ok"]
    assert body["calculation_status"] == "clean"
    cell = body["workbook"]["sheets"][approved.id]["cells"]["9,1"]
    assert cell["value"] == 6 or cell["display"] == "6"
    # Workbook GET reflects same revision/value
    snap = client.get("/sheets/api/workbook").json()
    assert snap["revision"] == body["revision"]
    b10 = snap["workbook"]["sheets"][approved.id]["cells"]["9,1"]
    assert b10["value"] == 6


def test_s3_authority_cells_on_scaffold_grid():
    """Expand grid (24×8) so Final!F21/G21 are present in workbook HTML."""
    from server.apps.sheets.exploratory import seeds as S
    from server.apps.world import WorldState
    from server.state import GymState

    parts = S.seed_s3_world_parts(0)
    shop = GymState(task_id="exploratory/S3_probe", seed=0)
    SESSION.world = WorldState(shop=shop, sheets=parts["sheets"], mail=parts["mail"])
    SESSION.current = shop
    wb = parts["sheets"].active_workbook()
    final = sheet_named(wb, "Final")
    # Activate Final so the scaffold renders its cells
    parts["sheets"].active_workbook().active_sheet_id = final.id
    client = _client()
    html = client.get("/sheets").text
    # row 20 = F21 (0-indexed row 20, col 5); row 20 col 6 = G21
    assert f'cell-{final.id}-r20-c5' in html
    assert f'cell-{final.id}-r20-c6' in html
    assert 'data-grid-rows="24"' in html


def test_harness_snapshot_separates_shop_and_market_orders(monkeypatch):
    """Shop ``orders_count`` stays 0 when only ValueMart has an order."""
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = _client()
    _reset(client, "M384/active_tab_sum_gate", 0)
    snap0 = client.get("/_harness/snapshot", headers=AUTH).json()
    assert snap0["orders_count"] == 0
    assert snap0["market_orders_count"] == 0
    assert "cart_item_count" in snap0

    add = client.post(
        "/market/cart/add",
        data={"product_id": "vm_launch_kit", "quantity": 1},
        follow_redirects=False,
    )
    assert add.status_code == 303
    checkout = client.post("/market/checkout", follow_redirects=False)
    assert checkout.status_code == 303
    assert "/market/order/" in (checkout.headers.get("location") or "")

    snap1 = client.get("/_harness/snapshot", headers=AUTH).json()
    assert snap1["orders_count"] == 0, "Shop orders must stay distinct"
    assert snap1["market_orders_count"] == 1


def test_name_box_select_then_save_persists_and_toast_on_empty(monkeypatch):
    """Name-box → formula → Save posts set_cell; Save with no selection toasts."""
    pytest.importorskip("playwright")
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    from server.main import app as live_app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        live_app, host="127.0.0.1", port=port, log_level="warning",
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(base, timeout=0.2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.05)
        else:
            raise AssertionError("sheets UI test server did not start")

        reset = httpx.post(
            f"{base}/_harness/reset",
            json={"task_id": EXPLORATORY_S1_ID, "seed": 0},
            headers=AUTH,
            timeout=10,
        )
        assert reset.status_code == 200, reset.text

        # Activate Approved Lines (sh_2) so B6 is the Midline qty cell.
        wb0 = httpx.get(f"{base}/sheets/api/workbook", timeout=10).json()
        rev = wb0["revision"]
        act = httpx.post(
            f"{base}/sheets/api/commands",
            json={
                "command_type": "set_active_sheet",
                "payload": {"sheet_id": "sh_2"},
                "base_revision": rev,
                "idempotency_key": "ui-test-activate",
            },
            timeout=10,
        )
        assert act.status_code == 200 and act.json()["ok"]

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{base}/sheets", wait_until="load")
            page.wait_for_selector('[data-test-id="name-box"]')

            # Toast path: clear selection by emptying name + no grid click.
            page.evaluate("""() => {
              const root = document.querySelector('[data-test-id="sheets-workbook"]');
              const name = document.querySelector('[data-test-id="name-box"]');
              const fx = document.querySelector('[data-test-id="formula-input"]');
              if (name) name.value = '';
              if (fx) fx.value = '';
              // Force selected=null by reloading selection state via synthetic save
              // after clearing name — click Save should toast.
            }""")
            # Blur empty name first so blur handler does not re-select A1.
            page.fill('[data-test-id="name-box"]', "")
            page.click('[data-test-id="formula-input"]')
            # Ensure no cell is selected: reload page then clear default A1 without selecting.
            page.goto(f"{base}/sheets", wait_until="load")
            page.fill('[data-test-id="name-box"]', "")
            page.locator('[data-test-id="formula-input"]').click()
            # selected still null until grid/Name selects; Save must toast.
            page.click('[data-test-id="btn-cell-save"]')
            toast = page.locator('[data-test-id="sheets-toast"]')
            page.wait_for_function(
                """() => {
                  const t = document.querySelector('[data-test-id="sheets-toast"]');
                  return t && !t.classList.contains('hidden')
                    && (t.textContent || '').includes('Select a cell');
                }""",
                timeout=5000,
            )
            assert "Select a cell" in (toast.inner_text() or "")
            assert page.get_attribute(
                '[data-test-id="sheets-workbook"]', "data-last-save",
            ) == "noop"

            # Name-box path (no gridcell click): B6 → 2 → Save → B10 becomes 6.
            page.fill('[data-test-id="name-box"]', "B6")
            page.press('[data-test-id="name-box"]', "Enter")
            page.wait_for_function(
                """() => {
                  const td = document.querySelector(
                    'td[data-test-id="cell-sh_2-r5-c1"]');
                  return td && td.classList.contains('ring-emerald-500');
                }""",
                timeout=5000,
            )
            page.fill('[data-test-id="formula-input"]', "2")
            page.click('[data-test-id="btn-cell-save"]')
            page.wait_for_function(
                """() => document.querySelector(
                  '[data-test-id="sheets-workbook"]'
                ).getAttribute('data-last-save') === 'ok'""",
                timeout=5000,
            )
            b10 = page.locator('[data-test-id="cell-sh_2-r9-c1"]')
            assert b10.inner_text().strip() == "6"
            browser.close()

        snap = httpx.get(f"{base}/sheets/api/workbook", timeout=10).json()
        cell = snap["workbook"]["sheets"]["sh_2"]["cells"]["5,1"]
        assert cell.get("value") == 2 or cell.get("display") == "2"
        total = snap["workbook"]["sheets"]["sh_2"]["cells"]["9,1"]
        assert total.get("value") == 6 or total.get("display") == "6"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
