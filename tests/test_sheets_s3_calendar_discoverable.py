"""M386/S3 Vendor Review Calendar discoverability + oracle non-hardcode guard."""

from __future__ import annotations

import inspect
import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from agents import oracle_agent
from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from server.apps.sheets.exploratory.seeds import (
    S3_VENDOR_REVIEW_EVENT_ID,
    seed_s3_calendar,
    seed_s3_world_parts,
)
from server.main import app as live_app
from server.sheets_s3_task import task_m386_writeback_if_complete

TOKEN = "sheets-s3-cal-discover-token"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}
TASK_ID = "M386/writeback_if_complete"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_s3_seed_includes_vendor_review_calendar_event():
    parts = seed_s3_world_parts(0)
    cal = parts["calendar"]
    assert cal is not None
    ev = cal.events.get(S3_VENDOR_REVIEW_EVENT_ID)
    assert ev is not None
    assert ev.title == "Vendor Review"
    assert ev.start == "15:30"

    world = task_m386_writeback_if_complete(0)
    assert world.calendar is not None
    assert S3_VENDOR_REVIEW_EVENT_ID in world.calendar.events
    assert world.calendar.events[S3_VENDOR_REVIEW_EVENT_ID].title == "Vendor Review"


def test_s3_oracle_solver_does_not_hardcode_event_id():
    """UI-only gold must discover the id; source must not embed the seed literal."""
    src = inspect.getsource(
        oracle_agent.solve_exploratory_s3_writeback_if_complete,
    )
    assert "cal_vendor_review" not in src
    assert "event-id-display" in src or "event_id" in src
    assert "/calendar" in src


def test_vendor_review_event_id_visible_in_calendar_ui(monkeypatch):
    """Agenda → Edit surfaces Event ID text (no harness/world poke)."""
    pytest.importorskip("playwright")
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    os.environ[HARNESS_TOKEN_ENV] = TOKEN

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
            raise AssertionError("calendar discoverability server did not start")

        reset = httpx.post(
            f"{base}/_harness/reset",
            json={"task_id": TASK_ID, "seed": 0},
            headers=AUTH,
            timeout=10,
        )
        assert reset.status_code == 200, reset.text

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{base}/calendar", wait_until="load")
            page.wait_for_selector("[data-test-id='agenda']")
            title = page.locator(
                "[data-test-id^='event-title-']", has_text="Vendor Review",
            )
            assert title.count() >= 1
            row = title.first.locator("xpath=ancestor::li[1]")
            row.locator("a[data-test-id^='link-edit-']").click()
            page.wait_for_selector("[data-test-id='event-id-display']")
            label = page.locator(
                "[data-test-id='event-id-display']",
            ).inner_text().strip()
            assert label == f"Event ID: {S3_VENDOR_REVIEW_EVENT_ID}"
            form_id = page.locator(
                "input[data-test-id='input-edit-event-id']",
            ).input_value()
            assert form_id == S3_VENDOR_REVIEW_EVENT_ID
            # URL path also carries the id (secondary UI signal).
            assert f"/calendar/edit/{S3_VENDOR_REVIEW_EVENT_ID}" in page.url
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_seed_s3_calendar_keeps_default_events():
    cal = seed_s3_calendar(0)
    assert "Gym session" in {e.title for e in cal.events.values()}
    assert S3_VENDOR_REVIEW_EVENT_ID in cal.events
