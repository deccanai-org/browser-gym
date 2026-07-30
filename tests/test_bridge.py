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
from server.main import app
import tools.bridge as bridge
from tools.bridge import Bridge

TOKEN = "test-bridge-token"
GYM = "http://gym"
MOCK = "http://mock"
TASK = "A1/buy_wireless_mouse"


@pytest.fixture()
def wired(monkeypatch):
    """A Bridge whose HTTP is routed to the TestClient (gym) + a dict (mocks)."""
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    client = TestClient(app)
    store: dict[str, dict] = {}

    def shim(method, url, *, form=None, json_body=None, headers=None, timeout=30):
        if url.startswith(MOCK):
            q = urllib.parse.urlparse(url).query
            sid = urllib.parse.parse_qs(q).get("sid", [""])[0]
            if url.startswith(MOCK + "/post"):
                if (json_body or {}).get("action") == "set":
                    store[sid] = (json_body or {}).get("state")
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
    b._store = store  # for assertions
    return b


def _tab(b, app_key):
    sid = b.session.get(app_key) or f"seed-{b.task_id}-{b.seed}-{app_key}"
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


def test_actions_cover_every_app(wired):
    apps = {a.split(".")[0] for a in bridge.ACTIONS}
    assert apps == {"shop", "mail", "market", "food", "calendar"}
    # every action's path template only references fields it declares or a
    # payload key the bridge resolves (address_id / payment_id / subscription_id)
    import re
    for name, (_m, path, _f) in bridge.ACTIONS.items():
        for tok in re.findall(r"\{(\w+)\}", path):
            assert tok in ("address_id", "payment_id", "subscription_id"), (name, tok)
