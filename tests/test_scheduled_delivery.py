"""The ShopGym cart's "Scheduled delivery date" field, end to end.

The field spans four links and it was broken at two of them:

  UI  -> the mock floors the date on the GYM's clock, not the wall clock, and
         commits whole dates rather than one per keystroke
  ->  the bridge carries scheduled_delivery on shop.set_line_options
  ->  the engine applies it to the cart line (and un-applies it when cleared)
  ->  the projection carries it back, so the 2.5s re-poll doesn't wipe it

The engine/bridge/projection half runs in-process on a TestClient, the same shim
tests/test_bridge.py uses. The UI half needs a real browser — a date input's
per-segment `change` events and a controlled React value only misbehave together
in a live DOM — so it drives the built bundle in headless Chromium, and skips
when the bundle or Playwright is absent.
"""
from __future__ import annotations

import contextlib
import functools
import http.server
import json
import socket
import threading
import urllib.parse
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from harness.auth import HARNESS_TOKEN_ENV
from server.apps import bus, wiring as apps_wiring
from server.main import app
import tools.bridge as bridge
from tools.bridge import Bridge
from tools.seed_to_cuagym import transform_world

TOKEN = "test-sched-token"
GYM = "http://gym"
MOCK = "http://mock"
# The delivery-date breaker: the world is frozen at 2026-05-21 and the party is
# the 22nd, so every correct answer here is months in the WALL clock's past.
TASK = "M207/scheduled_delivery_event_join"
PARTY = "2026-05-22"
WORLD_TODAY = "2026-05-21"

DIST = Path(__file__).resolve().parents[1] / "websites" / "xmazon_mock" / "dist"


@pytest.fixture(autouse=True)
def _subscribers():
    bus.clear_subscribers()
    apps_wiring.register_default_subscribers()
    yield
    bus.clear_subscribers()


@pytest.fixture()
def wired(monkeypatch):
    """A Bridge whose HTTP is the gym TestClient; mock pushes go to a dict."""
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = TestClient(app)
    store: dict[str, dict] = {}

    def shim(method, url, *, form=None, json_body=None, headers=None, timeout=30):
        if url.startswith(MOCK):
            sid = urllib.parse.parse_qs(
                urllib.parse.urlparse(url).query).get("sid", [""])[0]
            if url.startswith(MOCK + "/post"):
                store[sid] = (json_body or {}).get("state")
            return 200, {"ok": True}, {}
        r = client.request(method, url[len(GYM):], data=form, json=json_body,
                           headers=headers or {}, follow_redirects=False)
        try:
            return r.status_code, r.json(), dict(r.headers)
        except Exception:
            return r.status_code, r.text, dict(r.headers)

    monkeypatch.setattr(bridge, "_http", shim)
    b = Bridge(gym_url=GYM, mock_map={a: MOCK for a in
               ("shop", "mail", "market", "calendar", "food")},
               harness_token=TOKEN)
    b.reset(TASK, 0)
    return b


def _gift_line(b: Bridge) -> dict:
    items = b.world()["shop"]["cart"]["items"]
    return next(i for i in items if i["product_id"] == "p_home_candle")


def _projected_line(b: Bridge) -> dict:
    shop = b.project(["shop"])["shop"][1]
    return next(c for c in shop["cart"] if c["productId"] == "p_home_candle")


# --------------------------------------------------------------- engine half --
def test_a_typed_date_reaches_the_engine_and_comes_back_in_the_projection(wired):
    """Links 2-4: the bridge carries the date, the engine stores it on the line,
    and the projection hands it back — without that last step the 2.5s re-poll
    would blank a field that was set correctly."""
    b = wired
    assert _gift_line(b)["scheduled_delivery"] is None

    r = b.act("shop.set_line_options", product_id="p_home_candle",
              gift_wrap=False, gift_message="", ship_to_address_id="",
              scheduled_delivery=PARTY)
    assert r["ok"], r
    assert _gift_line(b)["scheduled_delivery"] == PARTY
    assert _projected_line(b)["scheduled_delivery"] == PARTY


def test_clearing_the_date_actually_clears_it(wired):
    """A date you cannot take back is a one-way door. FastAPI collapses a
    present-but-empty form field into the parameter default, so the route has to
    consult the raw form to tell "clear this" from "no opinion"."""
    b = wired
    b.act("shop.set_line_options", product_id="p_home_candle",
          scheduled_delivery=PARTY)
    assert _gift_line(b)["scheduled_delivery"] == PARTY

    r = b.act("shop.set_line_options", product_id="p_home_candle",
              gift_wrap=False, gift_message="", ship_to_address_id="",
              scheduled_delivery="")
    assert r["ok"], r
    assert _gift_line(b)["scheduled_delivery"] is None
    assert _projected_line(b)["scheduled_delivery"] == ""


def test_an_update_that_omits_the_field_leaves_the_date_alone(wired):
    """The other half of that distinction: a quantity change says nothing about
    the delivery date, so it must not wipe one."""
    b = wired
    b.act("shop.set_line_options", product_id="p_home_candle",
          scheduled_delivery=PARTY)
    r = b.act("shop.set_qty", product_id="p_home_candle", quantity=2)
    assert r["ok"], r
    assert _gift_line(b)["scheduled_delivery"] == PARTY


def test_a_date_set_from_the_cart_solves_the_delivery_date_breaker(wired):
    """The point of the field: with the date on the line the gym's own verifier
    suite passes M207, and without it the forbidden "will miss the party"
    milestone fires instead."""
    b = wired
    b.act("shop.view_orders")           # any read; the suite wants the calendar
    b.act("calendar.view")
    b.act("shop.set_line_options", product_id="p_home_candle",
          scheduled_delivery=PARTY)
    uid = b.world()["shop"]["current_user_id"]
    pay = next(iter(b.world()["shop"]["users"][uid]["payment_methods"]))
    b.act("shop.place_order", payment_id=pay)

    v = b.verify()
    fired = {m["name"]: m["fired_at_step"] >= 0 for m in v["all_milestones"]}
    assert fired["gift_scheduled_in_time"], v
    assert not fired["gift_will_miss_party"], v
    assert v["success"], v


# ------------------------------------------------------------------- UI half --
class _SPAHandler(http.server.SimpleHTTPRequestHandler):
    """Static dist with an SPA fallback — /cart is a client route, not a file."""

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.exists() or path.is_dir():
            self.path = "/index.html"
        return super().send_head()

    def log_message(self, *a):  # keep pytest output readable
        pass


class _FakeBridge(http.server.BaseHTTPRequestHandler):
    """Stands in for the bridge service: serves a REAL projected shop world and
    records every act, so the test can count commits and read what was sent."""

    state: dict = {}
    acts: list = []

    def _send(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({})

    def do_GET(self):
        self._send({"apps": {"shop": type(self).state}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        cls = type(self)
        cls.acts.append(req)
        # Mimic engine + re-projection: apply the option set to the line and hand
        # the whole world back, which is what re-renders the controlled input.
        pl = req.get("payload") or {}
        for line in cls.state.get("cart") or []:
            if line.get("productId") == pl.get("product_id"):
                line["scheduled_delivery"] = pl.get("scheduled_delivery") or ""
        self._send({"ok": True, "status": 200, "apps": {"shop": cls.state}})

    def log_message(self, *a):
        pass


def _serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture()
def cart_page(monkeypatch):
    """The built ShopGym cart, in a real browser, bridged to a fake engine that
    is seeded with the REAL M207 projection (so the world clock is authentic)."""
    if not (DIST / "index.html").exists():
        pytest.skip("xmazon_mock/dist not built (tools/build_hub_mocks.sh . \"\")")
    sync_playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright not installed").sync_playwright

    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = TestClient(app)
    client.post("/_harness/reset", json={"task_id": TASK, "seed": 0},
                headers={"X-Harness-Token": TOKEN})
    world = client.get("/_harness/world_full",
                       headers={"X-Harness-Token": TOKEN}).json()
    _FakeBridge.state = transform_world(world, ["shop"])["shop"][1]
    _FakeBridge.acts = []

    static, static_url = _serve(functools.partial(
        _SPAHandler, directory=str(DIST)))
    api, api_url = _serve(_FakeBridge)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(f"{static_url}/cart?bridge={api_url}&session=t",
                      wait_until="networkidle")
            page.wait_for_selector("input[aria-label='Scheduled delivery date']")
            yield page, _FakeBridge
            browser.close()
    finally:
        for s in (static, api):
            with contextlib.suppress(Exception):
                s.shutdown()


def test_the_date_floor_is_the_gym_clock_not_the_wall_clock(cart_page):
    """The world is frozen at 2026-05-21. Flooring on the wall clock put every
    delivery-date task in the "past", so the picker refused the only date that
    could solve it — and the failure arrived by itself, on the day the wall
    clock passed the seeded world."""
    page, _ = cart_page
    field = page.get_by_label("Scheduled delivery date")
    assert field.get_attribute("min") == WORLD_TODAY


def test_typing_a_date_commits_it_once_and_survives_the_reprojection(cart_page):
    """A native date input fires `change` per SEGMENT, and once the box holds a
    value every one of those is a complete date. Committing them round-tripped a
    garbage date through the engine, which re-rendered this controlled input
    mid-keystroke — so the date could never be typed at all."""
    page, fake = cart_page
    field = page.get_by_label("Scheduled delivery date")
    box = field.bounding_box()
    page.mouse.click(box["x"] + 10, box["y"] + box["height"] / 2)   # mm segment
    for ch in "05222026":
        page.keyboard.type(ch)
        page.wait_for_timeout(250)
    page.wait_for_timeout(1500)

    sent = [a["payload"]["scheduled_delivery"] for a in fake.acts
            if a["action"] == "shop.set_line_options"]
    assert sent == [PARTY], f"expected one whole-date commit, got {sent}"
    assert field.input_value() == PARTY

    # The re-poll is what used to blank a correctly set field.
    page.wait_for_timeout(4000)
    assert field.input_value() == PARTY
