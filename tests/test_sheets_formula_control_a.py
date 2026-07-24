"""Harness-path Control+a on Sheets formula-input — no LLM.

Distinguishes:
  - raw Playwright Control+a (broken select-all on Chromium/macOS)
  - harness-normalized Control+a → ControlOrMeta+a (true select-all)
  - post-type_into_mark / Enter / Control+a / Backspace / type_into_mark chain
    matching M384 postfix seed 0 recovery attempts
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
from harness.runner import BrowserCtx
from server.apps.sheets.exploratory.task_hook import EXPLORATORY_S1_ID

TOKEN = "sheets-ctrl-a-test-token"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fx_state(page) -> dict:
    return page.evaluate(
        """() => {
          const fx = document.querySelector('[data-test-id="formula-input"]');
          const ae = document.activeElement;
          return {
            value: fx ? fx.value : null,
            focused: ae === fx,
            activeTag: ae ? (ae.getAttribute('data-test-id') || ae.tagName) : null,
            selectionStart: fx ? fx.selectionStart : null,
            selectionEnd: fx ? fx.selectionEnd : null,
            selectedLen: fx ? (fx.selectionEnd - fx.selectionStart) : null,
          };
        }"""
    )


def _harness_type_into_mark(page, selector: str, text: str) -> None:
    """Mirror BrowserCtx.type_into_mark: click center, then keyboard.type."""
    box = page.locator(selector).bounding_box()
    assert box is not None
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    page.mouse.click(x, y)
    page.keyboard.type(text)


def _harness_key_press(page, name: str) -> None:
    """Mirror BrowserCtx.key_press including Control+a → ControlOrMeta+a."""
    page.keyboard.press(BrowserCtx._normalize_key_chord(name))


def test_normalize_control_a_maps_to_control_or_meta():
    assert BrowserCtx._normalize_key_chord("Control+a") == "ControlOrMeta+a"
    assert BrowserCtx._normalize_key_chord("Control+A") == "ControlOrMeta+a"
    assert BrowserCtx._normalize_key_chord("Enter") == "Enter"
    assert BrowserCtx._normalize_key_chord("Backspace") == "Backspace"


@pytest.fixture(scope="module")
def live_sheets_base(tmp_path_factory):
    pytest.importorskip("playwright")
    os.environ[HARNESS_TOKEN_ENV] = TOKEN
    from server.main import app as live_app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(live_app, host="127.0.0.1", port=port, log_level="warning")
    )
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
            raise AssertionError("sheets Control+a test server did not start")
        yield base
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _reset_approved_b6(base: str) -> None:
    reset = httpx.post(
        f"{base}/_harness/reset",
        json={"task_id": EXPLORATORY_S1_ID, "seed": 0},
        headers=AUTH,
        timeout=10,
    )
    assert reset.status_code == 200, reset.text
    wb0 = httpx.get(f"{base}/sheets/api/workbook", timeout=10).json()
    rev = wb0["revision"]
    act = httpx.post(
        f"{base}/sheets/api/commands",
        json={
            "command_type": "set_active_sheet",
            "payload": {"sheet_id": "sh_2"},
            "base_revision": rev,
            "idempotency_key": "ctrl-a-activate",
        },
        timeout=10,
    )
    assert act.status_code == 200 and act.json()["ok"]


def _goto_b6_formula_selected(page, base: str) -> None:
    """Name-box Enter → formula shows seeded '1' with select-all (selectCell)."""
    page.goto(f"{base}/sheets", wait_until="load")
    page.wait_for_selector('[data-test-id="formula-input"]')
    page.fill('[data-test-id="name-box"]', "B6")
    page.press('[data-test-id="name-box"]', "Enter")
    page.wait_for_function(
        """() => {
          const fx = document.querySelector('[data-test-id="formula-input"]');
          return fx && fx.value === '1' && document.activeElement === fx
            && fx.selectionStart === 0 && fx.selectionEnd === 1;
        }""",
        timeout=5000,
    )


def test_raw_control_a_is_line_start_not_select_all_on_chromium_macos(
    live_sheets_base,
):
    """Regression pin: raw page.keyboard.press('Control+a') is NOT select-all
    on Chromium/macOS (emacs line-start). This is why pre-fix thrash happened."""
    import sys

    if sys.platform != "darwin":
        pytest.skip("raw Control+a line-start pin is Darwin/Chromium-specific")

    base = live_sheets_base
    _reset_approved_b6(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _goto_b6_formula_selected(page, base)
        page.locator('[data-test-id="formula-input"]').fill("12")
        page.locator('[data-test-id="formula-input"]').click()
        page.keyboard.press("End")
        page.keyboard.press("Control+a")  # raw — no harness normalize
        raw = _fx_state(page)
        assert raw["selectionStart"] == 0 and raw["selectionEnd"] == 0, raw
        page.keyboard.type("X")
        assert _fx_state(page)["value"] == "X12", _fx_state(page)
        browser.close()


def test_standalone_control_a_selects_all_then_type_replaces(live_sheets_base):
    """Harness key('Control+a') on focused formula-input must select-all;
    subsequent keyboard.type (no click) must replace, not append."""
    base = live_sheets_base
    _reset_approved_b6(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _goto_b6_formula_selected(page, base)

        # Collapse selection like a mid-edit caret (end of "1").
        page.locator('[data-test-id="formula-input"]').click()
        page.keyboard.press("End")
        before = _fx_state(page)
        assert before["value"] == "1"
        assert before["focused"] is True
        assert before["selectedLen"] == 0, before

        _harness_key_press(page, "Control+a")
        after_sel = _fx_state(page)
        assert after_sel["focused"] is True, after_sel
        assert after_sel["value"] == "1", after_sel
        assert after_sel["selectionStart"] == 0 and after_sel["selectionEnd"] == 1, (
            f"harness Control+a did not select-all: {after_sel}"
        )

        # Type without click — selected text should be replaced.
        page.keyboard.type("2")
        after_type = _fx_state(page)
        assert after_type["value"] == "2", (
            f"standalone Control+a+type should REPLACE → '2', got {after_type}"
        )
        browser.close()


def test_control_a_backspace_then_type_into_mark_replaces(live_sheets_base):
    """Documented overwrite protocol: Control+a → Backspace → type_into_mark."""
    base = live_sheets_base
    _reset_approved_b6(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _goto_b6_formula_selected(page, base)

        # First append (known type_into_mark semantics).
        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        assert _fx_state(page)["value"] == "12"

        assert _fx_state(page)["focused"] is True
        _harness_key_press(page, "Control+a")
        sel = _fx_state(page)
        assert sel["selectionStart"] == 0 and sel["selectionEnd"] == 2, sel
        _harness_key_press(page, "Backspace")
        cleared = _fx_state(page)
        assert cleared["value"] == "", cleared
        assert cleared["focused"] is True, cleared

        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        final = _fx_state(page)
        assert final["value"] == "2", (
            f"overwrite protocol should yield '2', got {final}"
        )
        browser.close()


def test_seed0_chain_enter_then_harness_control_a_replaces(live_sheets_base):
    """Exact postfix seed-0 recovery order with fixed harness Control+a:
    append → Enter → Control+a → Backspace → type_into_mark → '2'.

    Enter/saveCell keeps formula focused (focusFormula:false only skips
    re-select; it does not blur). Pre-fix thrash was Control+a = line-start,
    not unfocus.
    """
    base = live_sheets_base
    _reset_approved_b6(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _goto_b6_formula_selected(page, base)

        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        assert _fx_state(page)["value"] == "12"

        _harness_key_press(page, "Enter")
        page.wait_for_timeout(200)
        after_enter = _fx_state(page)
        assert after_enter["value"] == "12", after_enter
        assert after_enter["focused"] is True, after_enter

        _harness_key_press(page, "Control+a")
        after_ca = _fx_state(page)
        assert after_ca["selectionStart"] == 0 and after_ca["selectionEnd"] == 2, (
            after_ca
        )

        _harness_key_press(page, "Backspace")
        assert _fx_state(page)["value"] == ""

        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        final = _fx_state(page)
        assert final["value"] == "2", (
            f"seed-0 chain with fixed Control+a should REPLACE → '2', got {final}"
        )
        browser.close()


def test_control_a_then_type_into_mark_without_backspace_appends(live_sheets_base):
    """If agent does Control+a then type_into_mark (no Backspace), the click
    inside type_into_mark collapses selection → append. Document this as
    harness translation hazard (intentional non-clear type), separate from
    the Control+a select-all bug."""
    base = live_sheets_base
    _reset_approved_b6(base)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        _goto_b6_formula_selected(page, base)

        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        assert _fx_state(page)["value"] == "12"

        _harness_key_press(page, "Control+a")
        sel = _fx_state(page)
        assert sel["selectionStart"] == 0 and sel["selectionEnd"] == 2, sel

        # type_into_mark clicks first → collapses selection, then types.
        _harness_type_into_mark(page, '[data-test-id="formula-input"]', "2")
        final = _fx_state(page)
        assert final["value"] == "122", (
            f"Control+a then type_into_mark (click) should APPEND → '122', got {final}"
        )
        browser.close()
