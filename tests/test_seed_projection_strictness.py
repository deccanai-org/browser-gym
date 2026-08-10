"""Task setup must fail loudly, not guess.

Four places used to answer a question they could not answer with a plausible
default. Each default was reproducible, none of them showed up in a run's
output, and every one of them produced a task that looked set up correctly and
was not:

  * an unmapped product category became Electronics, so Premium Dog Food was
    filed as a gadget in the live storefront;
  * a task with a factory but no verifier suite 500'd the gym on reset;
  * a task missing from the sid map was dropped from the exported catalog and
    the exporter still exited 0;
  * an unrecognised start-path segment resolved to shop, so a task with no
    resolvable primary app ran as a shop task.

Two of these tests are completeness checks rather than examples: they re-derive
the real vocabulary (every category the engine emits, every top-level route the
gym serves) and fail when something new appears that the maps do not name. That
is what keeps the maps honest as tasks are added.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from harness.auth import HARNESS_TOKEN_ENV, HARNESS_TOKEN_HEADER
from harness.runner import (
    UnknownStartPath, _SEG_TO_APP, _seg_to_app, _seg_to_app_or_none,
)
from server.apps.world import WorldState
from server.seeddb.runtime import seed_source
from server.tasks import TASKS, START_PATHS
from tools.seed_to_cuagym import (
    UnmappedCategory, _AMAZON_CAT, _EBAY_CAT, _amazon_category, _ebay_category,
    transformed_states,
)

TOKEN = "deterministic-test-token"
AUTH = {HARNESS_TOKEN_HEADER: TOKEN}


# --------------------------------------------------------------------------- #
# 1. product categories
# --------------------------------------------------------------------------- #

def _emitted_categories() -> tuple[set[str], set[str]]:
    """Every distinct (shop, market) product category across the whole registry."""
    shop_cats: set[str] = set()
    market_cats: set[str] = set()
    for task_id in TASKS:
        base = seed_source(task_id, 0)
        shop = base.shop if isinstance(base, WorldState) else base
        for p in (shop.products or {}).values():
            shop_cats.add((p.category or "").strip().lower())
        market = getattr(base, "market", None) if isinstance(base, WorldState) else None
        if market is not None:
            for p in (market.products or {}).values():
                market_cats.add((p.category or "").strip().lower())
    return shop_cats, market_cats


def test_every_category_the_engine_emits_has_a_storefront_mapping() -> None:
    shop_cats, market_cats = _emitted_categories()
    assert shop_cats, "no shop products found — the enumeration itself is broken"
    assert not (shop_cats - set(_AMAZON_CAT)), (
        f"shop categories with no _AMAZON_CAT entry: {sorted(shop_cats - set(_AMAZON_CAT))}"
    )
    assert not (market_cats - set(_EBAY_CAT)), (
        f"market categories with no _EBAY_CAT entry: {sorted(market_cats - set(_EBAY_CAT))}"
    )


def test_unmapped_shop_category_raises_naming_the_product() -> None:
    with pytest.raises(UnmappedCategory) as exc:
        _amazon_category({"id": "p_yoga_1", "name": "Yoga Mat", "category": "sports"})
    msg = str(exc.value)
    assert "p_yoga_1" in msg and "Yoga Mat" in msg and "sports" in msg


def test_unmapped_market_category_raises_naming_the_listing() -> None:
    with pytest.raises(UnmappedCategory) as exc:
        _ebay_category("vm_yoga_1", {"name": "Yoga Mat", "category": "sports"})
    msg = str(exc.value)
    assert "vm_yoga_1" in msg and "Yoga Mat" in msg and "sports" in msg


def test_pet_and_office_products_ship_under_their_own_category() -> None:
    """The concrete regression: dog food reached the live UI as Electronics."""
    _, shop = transformed_states("M310/cancel_sub_false_no_transit_claim", 0, ["shop"])["shop"]
    by_id = {p["id"]: p for p in shop["products"]}
    assert by_id["p_pet_food"]["category"] == "Pet Supplies"
    assert by_id["p_office_display"]["category"] == "Office Products"


def test_every_task_projects_without_an_unmapped_category() -> None:
    for task_id in TASKS:
        transformed_states(task_id, 0, ["shop", "market"])


# --------------------------------------------------------------------------- #
# 2. a task with a factory but no verifier suite
# --------------------------------------------------------------------------- #

@pytest.fixture
def unsuited_task():
    """Register a task that builds but cannot be graded, exactly as a new
    JSON-defined task with a forgotten suite would land."""
    task_id = "ZZ9/task_with_no_verifier_suite"
    TASKS[task_id] = TASKS["A1/buy_wireless_mouse"]
    try:
        yield task_id
    finally:
        TASKS.pop(task_id, None)


def test_registry_has_a_suite_for_every_task() -> None:
    from server.main import _registry_gaps

    unsuited, _ = _registry_gaps()
    assert not unsuited, f"tasks with no verifier suite: {unsuited}"


@pytest.mark.parametrize("route", ["/_harness/reset", "/_harness/load_state"])
def test_task_without_a_suite_is_a_422_naming_it_not_a_500(
    monkeypatch, unsuited_task: str, route: str,
) -> None:
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    from server.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(route, json={"task_id": unsuited_task, "seed": 0, "state": {}},
                       headers=AUTH)
    assert resp.status_code == 422, resp.text
    assert unsuited_task in resp.json()["detail"]


def test_startup_refuses_a_registry_with_an_ungradeable_task(
    monkeypatch, unsuited_task: str,
) -> None:
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    from server.main import app

    with pytest.raises(RuntimeError) as exc:
        with TestClient(app):
            pass
    assert unsuited_task in str(exc.value)


def test_startup_succeeds_on_a_consistent_registry(monkeypatch) -> None:
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    from server.main import app

    with TestClient(app) as client:
        resp = client.post("/_harness/reset",
                           json={"task_id": "A1/buy_wireless_mouse", "seed": 0},
                           headers=AUTH)
        assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 3. the exported catalog must cover every task
# --------------------------------------------------------------------------- #

def test_exporter_refuses_when_a_task_is_missing_from_the_sid_map(monkeypatch, capsys) -> None:
    import tools.export_cua_catalog as ex

    sid_map = json.loads(ex.SID_MAP.read_text())
    dropped = sid_map["tasks"][0]["task_id"]
    sid_map["tasks"] = [t for t in sid_map["tasks"] if t["task_id"] != dropped]

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "sid_map.json").write_text(json.dumps(sid_map))
    monkeypatch.setattr(ex, "SID_MAP", tmp / "sid_map.json")
    out = tmp / "catalog.json"
    monkeypatch.setattr("sys.argv", ["export_cua_catalog", "-o", str(out)])

    with pytest.raises(SystemExit) as exc:
        ex.main()
    assert exc.value.code != 0
    assert dropped in capsys.readouterr().err
    assert not out.exists(), "refused, but still wrote a short catalog"


def test_exporter_covers_every_task_today() -> None:
    import tools.export_cua_catalog as ex

    sid_map = json.loads(ex.SID_MAP.read_text())
    mapped = {t["task_id"] for t in sid_map["tasks"]}
    assert not (set(TASKS) - mapped), f"tasks absent from the sid map: {sorted(set(TASKS) - mapped)}"


# --------------------------------------------------------------------------- #
# 4. start-path -> primary app
# --------------------------------------------------------------------------- #

def _gym_route_segments() -> set[str]:
    """Every top-level path segment the running gym serves a page on.

    Walks the live route table (including the four sub-app routers) so the map
    cannot drift behind a newly added route.
    """
    from server.main import app

    segs: set[str] = set()

    def walk(routes, prefix: str = "") -> None:
        for route in routes:
            path = getattr(route, "path", None)
            if path is not None:
                segs.add((prefix + path).lstrip("/").split("/")[0].lower())
            sub = getattr(route, "routes", None)
            router = getattr(route, "router", None)
            if sub is None and router is not None:
                sub, prefix = router.routes, prefix + (router.prefix or "")
            if sub:
                walk(sub, prefix)

    walk(app.routes)
    # Not pages an agent navigates to: the control plane, the JSON API, the
    # asset mount and FastAPI's own docs.
    return segs - {"_harness", "api", "static", "docs", "redoc", "openapi.json"}


def test_seg_map_names_every_top_level_route_the_gym_serves(monkeypatch) -> None:
    monkeypatch.setenv(HARNESS_TOKEN_ENV, TOKEN)
    unnamed = _gym_route_segments() - set(_SEG_TO_APP)
    assert not unnamed, (
        f"top-level gym route(s) with no _SEG_TO_APP entry: {sorted(unnamed)} — "
        f"they would raise UnknownStartPath if a task started there"
    )


def test_unknown_start_path_segment_raises_instead_of_becoming_shop() -> None:
    with pytest.raises(UnknownStartPath) as exc:
        _seg_to_app("/frobnicate/42")
    assert "frobnicate" in str(exc.value)
    assert _seg_to_app_or_none("/frobnicate/42") is None


@pytest.mark.parametrize(("path", "app_key"), [
    ("/", "shop"), ("/cart", "shop"), ("/account/security", "shop"),
    ("/product/p_mouse_wireless", "shop"), ("/search?q=mouse", "shop"),
    ("/mail", "mail"), ("/food", "food"), ("/calendar/day", "calendar"),
    ("/market/listing", "market"), ("/valuemart", "market"),
])
def test_known_segments_still_resolve(path: str, app_key: str) -> None:
    assert _seg_to_app(path) == app_key


def test_every_registered_task_has_a_resolvable_primary_app() -> None:
    unresolvable = []
    for task_id in TASKS:
        try:
            _seg_to_app(START_PATHS.get(task_id, "/"))
        except UnknownStartPath:
            unresolvable.append((task_id, START_PATHS.get(task_id)))
    assert not unresolvable, f"tasks with no resolvable primary app: {unresolvable[:5]}"


def test_shop_start_paths_are_named_not_defaulted() -> None:
    """The shop segments carry 70-odd tasks; they must be listed, not inferred."""
    shop_segments = {
        urlsplit(START_PATHS.get(t, "/")).path.lstrip("/").split("/")[0].lower()
        for t in TASKS
    }
    assert {"cart", "account", "product", "search", "bulk"} <= set(_SEG_TO_APP)
    assert not (shop_segments - set(_SEG_TO_APP))


def test_mid_run_navigation_stays_lenient_for_an_unknown_path() -> None:
    """_abs serves the agent, not task setup: a hallucinated URL must not raise."""
    from harness.runner import BrowserCtx

    ctx = object.__new__(BrowserCtx)
    ctx.server_url = "http://gym.test"
    ctx.app_sids = {}
    ctx.app_origins = {"shop": "http://shop.test"}
    ctx.bridge_url = "http://bridge.test"
    assert ctx._abs("/frobnicate") == "http://gym.test/frobnicate"
    assert ctx._abs("/cart").startswith("http://shop.test")
