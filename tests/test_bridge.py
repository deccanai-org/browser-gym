"""The realistic-UI <-> gym-engine bridge (tools/bridge.py).

Proves the bridge makes the mock UIs a live front-end over the real engine:
a click -> the gym's own action endpoint -> full logic (mutation + cross-app
hook + scheduler) -> re-project the live world -> the mock tabs reflect it,
including a CROSS-APP effect (a shop order's confirmation email showing up in
the Gmail tab) -> the gym's real verifier suite scores it.

Runs fully in-process: bridge HTTP is shimmed onto a FastAPI TestClient for the
gym and an in-memory dict for the mock state-API (the CUA-Gym-Hub /post + /state
contract), so there's no port/token juggling.
"""
from __future__ import annotations

import urllib.parse

import pytest
from fastapi.testclient import TestClient

from harness.auth import HARNESS_TOKEN_ENV
from server.apps import bus, wiring as apps_wiring
from server.main import app
import tools.bridge as bridge
from tools.bridge import Bridge
from tools.cua_env import seed_sid

TOKEN = "test-bridge-token"
GYM = "http://gym"
MOCK = "http://mock"
TASK = "A1/buy_wireless_mouse"


@pytest.fixture(autouse=True)
def _subscribers():
    """The cross-app subscribers, per test, as every other cross-app test does.

    `server.main` registers them once at import, and this file used to lean on
    that. The registry is global, so any test file that clears it on teardown
    (test_apps.py does) left the confirmation email with nobody to deliver it —
    and the failure looked like the bridge, not like import order: the order was
    created and the cart cleared, only the email never arrived.
    """
    bus.clear_subscribers()
    apps_wiring.register_default_subscribers()
    yield
    bus.clear_subscribers()


@pytest.fixture()
def wired(monkeypatch):
    """A Bridge whose HTTP is routed to the TestClient (gym) + a dict (mocks)."""
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = TestClient(app)
    store: dict[str, dict] = {}
    events: list[tuple[str, str]] = []   # (sid, action) — the hub's event journal

    def shim(method, url, *, form=None, json_body=None, headers=None, timeout=30):
        if url.startswith(MOCK):
            q = urllib.parse.urlparse(url).query
            sid = urllib.parse.parse_qs(q).get("sid", [""])[0]
            if url.startswith(MOCK + "/post"):
                # the hub freezes initial_state on `set` and updates current on
                # `set_current`; both write the live state the tab renders.
                act = (json_body or {}).get("action")
                if act in ("set", "set_current"):
                    store[sid] = (json_body or {}).get("state")
                    events.append((sid, act))
                return 200, {"ok": True}
            if url.startswith(MOCK + "/state"):
                return 200, {"stored_state": store.get(sid)}
            return 200, {"ok": True}
        # gym: strip the fake base, drive the TestClient (don't chase 303s)
        path = url[len(GYM):]
        r = client.request(method, path, data=form, json=json_body,
                           headers=headers or {}, follow_redirects=False)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text

    monkeypatch.setattr(bridge, "_http", shim)
    b = Bridge(gym_url=GYM, mock_map={a: MOCK for a in
               ("shop", "mail", "market", "calendar", "food")},
               harness_token=TOKEN)
    b._store = store    # for assertions
    b._events = events
    return b


def _tab(b, app_key):
    sid = b.session.get(app_key) or seed_sid(b.task_id or "", b.seed, app_key)
    return b._store.get(sid) or {}


def test_read_half_projects_live_engine_into_every_tab(wired):
    b = wired
    meta = b.reset(TASK, 0)
    assert meta.get("task_id") == TASK
    pushed = b.push()
    assert set(pushed) >= {"shop", "mail", "market", "calendar", "food"}
    shop = _tab(b, "shop")
    assert shop.get("products"), "amazon tab should carry the live catalog"
    assert len(shop["products"]) > 1


def test_write_half_runs_full_logic_and_cross_app_reaches_gmail(wired):
    b = wired
    b.reset(TASK, 0)
    b.push()

    w = b.world()
    sh = w["shop"]
    uid = sh["current_user_id"]
    user = sh["users"][uid]
    prod_id = next(iter(sh["products"]))
    pay_id = next(iter(user["payment_methods"]))
    inbox0 = len((_tab(b, "mail") or {}).get("emails", []))

    # add-to-cart through the gym's REAL endpoint -> amazon tab reflects it
    r1 = b.act("shop.add_to_cart", product_id=prod_id, quantity=1)
    assert r1["ok"], r1
    assert len(_tab(b, "shop").get("cart") or []) >= 1

    # place-order -> engine creates the order, clears the cart, and the
    # cross-app hook delivers a confirmation email into the Gmail tab
    r2 = b.act("shop.place_order", payment_id=pay_id)
    assert r2["ok"], r2
    assert b.world()["shop"]["orders"], "engine should have created an order"
    assert len(_tab(b, "shop").get("cart") or []) == 0, "cart should clear"

    emails = _tab(b, "mail").get("emails", [])
    assert len(emails) > inbox0, "a new email should reach the Gmail tab"
    subjects = " ".join(e.get("subject", "").lower() for e in emails)
    assert "order" in subjects or "confirm" in subjects, subjects


def test_verifier_suite_scores_the_live_world(wired):
    b = wired
    b.reset(TASK, 0)
    v = b.verify(url="/")
    assert isinstance(v, dict)
    assert "all_milestones" in v and "success" in v


def test_product_keyed_cart_edits_resolve_to_line_ids(wired):
    """The mocks know product ids, not gym line ids — the bridge resolves them."""
    b = wired
    b.reset(TASK, 0)
    sh = b.world()["shop"]
    pids = list(sh["products"])[:2]
    for p in pids:
        assert b.act("shop.add_to_cart", product_id=p, quantity=1)["ok"]
    assert len(b.world()["shop"]["cart"]["items"]) == 2

    # set_qty by product_id (not line_id) -> bridge resolves + updates
    r = b.act("shop.set_qty", product_id=pids[0], quantity=3)
    assert r["ok"], r
    line = next(i for i in b.world()["shop"]["cart"]["items"] if i["product_id"] == pids[0])
    assert line["quantity"] == 3

    # remove_product by product_id -> bridge resolves + removes
    assert b.act("shop.remove_product", product_id=pids[1])["ok"]
    remaining = [i["product_id"] for i in b.world()["shop"]["cart"]["items"]]
    assert pids[1] not in remaining and pids[0] in remaining

    # removing something not in the cart fails cleanly (no crash)
    assert b.act("shop.remove_product", product_id=pids[1])["ok"] is False


def test_add_address_runs_through_engine(wired):
    b = wired
    b.reset(TASK, 0)
    uid = b.world()["shop"]["current_user_id"]
    before = len(b.world()["shop"]["users"][uid]["addresses"])
    r = b.act("shop.add_address", label="Work", full_name="Alice A", line1="1 Main St",
              city="Austin", state="TX", zip="78701", set_default=True)
    assert r["ok"], r
    assert len(b.world()["shop"]["users"][uid]["addresses"]) == before + 1


def test_line_options_reach_the_engine(wired):
    """gift message / gift wrap / per-line ship-to must not be dropped."""
    b = wired
    b.reset(TASK, 0)
    sh = b.world()["shop"]
    pid = next(iter(sh["products"]))
    uid = sh["current_user_id"]
    addr_id = next(iter(sh["users"][uid]["addresses"]))
    assert b.act("shop.add_to_cart", product_id=pid, quantity=1)["ok"]
    r = b.act("shop.set_line_options", product_id=pid, gift_wrap=True,
              gift_message="Happy birthday", ship_to_address_id=addr_id)
    assert r["ok"], r
    line = b.world()["shop"]["cart"]["items"][0]
    assert line.get("gift_wrap") is True
    assert line.get("gift_message") == "Happy birthday"
    assert line.get("ship_to_address_id") == addr_id


def test_enable_two_fa_reaches_engine(wired):
    b = wired
    b.reset(TASK, 0)
    r = b.act("shop.enable_two_fa", code="123456")
    assert r["ok"], r
    uid = b.world()["shop"]["current_user_id"]
    user = b.world()["shop"]["users"][uid]
    # engine records 2FA on the user (field name may vary; just assert a truthy flag)
    assert any(("two" in k.lower() and "fa" in k.lower()) and user[k] for k in user) or \
           user.get("two_fa_enabled") is True, user


def test_view_actions_log_for_verifiers(wired):
    """A GET view action must produce the log entry milestones look for."""
    b = wired
    b.reset(TASK, 0)
    sh = b.world()["shop"]
    pid = next(iter(sh["products"]))
    pay = next(iter(sh["users"][sh["current_user_id"]]["payment_methods"]))
    b.act("shop.add_to_cart", product_id=pid, quantity=1)
    b.act("shop.place_order", payment_id=pay)
    order_id = list(b.world()["shop"]["orders"])[-1]
    r = b.act("shop.view_tracking", order_id=order_id)
    assert r["ok"], r
    log = [a.get("kind") for a in b.world()["shop"].get("action_log", [])]
    assert "viewed_tracking" in log, log


def test_tracking_number_is_projected(wired):
    """The mock order must carry the real shipment tracking # (was hardcoded None)."""
    b = wired
    b.reset(TASK, 0)
    sh = b.world()["shop"]
    pid = next(iter(sh["products"]))
    pay = next(iter(sh["users"][sh["current_user_id"]]["payment_methods"]))
    b.act("shop.add_to_cart", product_id=pid, quantity=1)
    b.act("shop.place_order", payment_id=pay)
    b.push()
    order = _tab(b, "shop")["orders"][-1]
    assert order.get("trackingNumber"), "projected order should carry a tracking number"
    assert order["trackingNumber"].startswith("1Z")


def test_harness_bridged_nav_urls():
    """The harness builds mock-origin URLs carrying ?bridge=, query before hash."""
    from harness.runner import bridged_app_url, _seg_to_app
    ao = {"shop": "http://h:5203", "mail": "http://h:5401", "food": "http://h:5403"}
    bu = "http://h:8090"
    shop = bridged_app_url(ao, bu, "shop")
    assert shop.startswith("http://h:5203/?bridge=")
    mail = bridged_app_url(ao, bu, "mail")
    # hash-routed Gmail: ?bridge must come BEFORE the #, so location.search sees it
    assert "?bridge=" in mail and mail.index("?bridge=") < mail.index("#/inbox")
    assert _seg_to_app("/") == "shop" and _seg_to_app("/mail") == "mail"
    assert _seg_to_app("/market/x") == "market" and _seg_to_app("/food") == "food"


def test_deep_link_start_path_mapping():
    """Bridged mode honors a task's deep-link start-path where the mock has a
    matching route; unknown paths fall back safely to the app root."""
    from harness.runner import _mock_start_path
    assert _mock_start_path("shop", "/cart") == "/cart"
    assert _mock_start_path("shop", "/product/p_x") == "/product/p_x"
    assert _mock_start_path("shop", "/search?q=abc&category=electronics") == "/search?q=abc&category=electronics"
    assert _mock_start_path("shop", "/account/orders") == "/orders"
    assert _mock_start_path("market", "/market/product/vm_mouse") == "/item/vm_mouse"
    assert _mock_start_path("market", "/market/cart") == "/cart"
    assert _mock_start_path("food", "/food/cart") == "/cart"
    # A deep link to ONE order lands on the orders list. The mock has `/orders`
    # but no order-detail route (see websites/amazon_mock/src/App.jsx), so the
    # nearest real page is the list the order is on — which is where the
    # annotator finds it. This used to return None and drop them on the
    # homepage instead, which is strictly further from the task.
    assert _mock_start_path("shop", "/account/orders/ORD-1") == "/orders"
    # genuinely unknown / app-root -> None (falls back to the app start page)
    assert _mock_start_path("shop", "/") is None
    assert _mock_start_path("shop", None) is None


def test_bridge_tick_disable(monkeypatch):
    """With tick disabled (harness owns the clock), act() must not tick."""
    import tools.bridge as bridge
    calls = {"tick": 0, "act": 0}

    def fake_http(method, url, *, form=None, json_body=None, headers=None, timeout=30):
        if url.endswith("/_harness/tick"):
            calls["tick"] += 1
        if "/api/" in url:
            calls["act"] += 1
        if url.endswith("/_harness/world_full"):
            return 200, {"shop": {"cart": {"items": []}}}
        return 200, {}
    monkeypatch.setattr(bridge, "_http", fake_http)
    b = bridge.Bridge(gym_url="http://g", mock_map={}, tick_enabled=False)
    b.reset("A1/buy_wireless_mouse", 0)
    b.act("shop.apply_promo", code="X")
    assert calls["act"] == 1 and calls["tick"] == 0, calls


def test_create_subscription_autofills_address_and_payment(wired):
    """create_subscription used to 422 (missing address_id/payment_id) — the
    bridge now fills them from the user's defaults so subscribe clicks succeed."""
    from server.main import TASKS
    b = wired
    c3 = next((t for t in TASKS if t.startswith("C3/")), None)
    b.reset(c3, 0)
    sh = b.world()["shop"]
    subable = [p for p, v in sh["products"].items() if v.get("is_subscribable")]
    assert subable, "expected a subscribable product on C3"
    before = len(b.world()["shop"].get("subscriptions") or {})
    r = b.act("shop.create_subscription", product_id=subable[0], cadence="weekly", deliveries=4)
    assert r["ok"], r
    assert len(b.world()["shop"].get("subscriptions") or {}) == before + 1


def test_view_and_search_actions_log(wired):
    """The nav/view GET actions must log the signal view-gated milestones need."""
    b = wired
    b.reset(TASK, 0)
    pid = next(iter(b.world()["shop"]["products"]))
    b.act("shop.view_product", product_id=pid)
    b.act("shop.search", q="mouse")
    b.act("shop.view_orders")
    log = [a.get("kind") for a in b.world()["shop"].get("action_log", [])]
    for k in ("view_product", "search", "view_orders"):
        assert k in log, (k, log[-6:])


def test_actions_cover_every_app(wired):
    apps = {a.split(".")[0] for a in bridge.ACTIONS}
    assert apps == {"shop", "mail", "market", "food", "calendar"}
    # every action's path template only references fields it declares or a
    # payload key the bridge resolves (address_id / payment_id / subscription_id)
    import re
    for name, (_m, path, _f) in bridge.ACTIONS.items():
        for tok in re.findall(r"\{(\w+)\}", path):
            assert tok in ("address_id", "payment_id", "subscription_id", "order_id",
                           "product_id", "email_id", "event_id"), (name, tok)


def test_actions_are_journalled_to_the_hub(wired):
    """The hub write pattern IS the trajectory: one `set` baseline at reset, then
    one `set_current` per app per action. If a later push wrote `set` again it
    would overwrite the frozen initial_state and every diff-based verifier would
    go blind."""
    b = wired
    b.reset(TASK, 0)
    b.push(baseline=True)
    assert {a for _sid, a in b._events} == {"set"}, "reset must freeze the baseline"

    b._events.clear()
    pid = next(iter(b.world()["shop"]["products"]))
    b.act("shop.add_to_cart", product_id=pid, quantity=1)
    actions = {a for _sid, a in b._events}
    assert actions == {"set_current"}, f"actions must append, not re-baseline: {actions}"
    # and it lands under a real UUID sid — the hub's Postgres store rejects others
    import uuid
    for sid, _a in b._events:
        assert str(uuid.UUID(sid)) == sid, sid
