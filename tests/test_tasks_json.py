"""The data-driven task loader.

Each test pins ONE behaviour. The theme running through them: a task file that
is ambiguous, incomplete or self-contradictory must fail at LOAD, naming itself
and the offending fragment — never load into a suite whose checks quietly prove
nothing.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from server import tasks_json as tj
from server.apps.mail.state import Email
from server.state import Address, CartItem, Order, OrderItem, Product
from server.verifiers import Probe


EXAMPLE = pathlib.Path(__file__).resolve().parent.parent / "tasks" / "examples" / "M401.json"


def _spec() -> dict:
    return json.loads(EXAMPLE.read_text())


def _write(tmp_path: pathlib.Path, spec: dict, name: str = "T900.json") -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(spec))
    return path


def _load(tmp_path: pathlib.Path, spec: dict, name: str = "T900.json") -> tj.JsonTask:
    return tj.load_file(_write(tmp_path, spec, name))


def _minimal(**over) -> dict:
    """A task with the smallest legal shape, for negative tests."""
    spec = {
        "short_id": "T900", "slug": "minimal", "category": "M", "difficulty": "easy",
        "prompt": "Do the thing.", "start_path": "/", "base": "world",
        "seed_world": {},
        "milestones": [{
            "name": "did_it", "weight": 1.0, "required": True,
            "check": {"kind": "order_exists", "product_id": "p_mouse_wireless"},
        }],
    }
    spec.update(over)
    return spec


@pytest.fixture
def tasks_dir(tmp_path):
    """Point the loader at a throwaway directory; always restore and re-read.

    Restoring inside the fixture (not in each test's ``finally``) matters: a
    test that leaves ``TASKS_DIR`` pointed at a tmp dir poisons every later
    test's view of the task set.
    """
    original = tj.TASKS_DIR
    tj.TASKS_DIR = tmp_path
    try:
        yield tmp_path
    finally:
        tj.TASKS_DIR = original
        tj.reload()


@pytest.fixture
def registered(tasks_dir):
    """The example task, live in the real gym registries, then removed again.

    This is the whole deliverable end to end: a JSON file in the tasks directory
    becomes a task the gym can build a world for and a suite the gym can score.
    """
    from server import tasks as tasks_mod
    from server import verifiers as verifiers_mod

    (tasks_dir / "M401.json").write_text(EXAMPLE.read_text())
    tj.reload()

    added = tj.register_into(tasks_mod.TASKS, tasks_mod.BRIEFS,
                             tasks_mod.START_PATHS, tasks_mod.TASK_BUILD_STATUS)
    verifiers_mod.SUITE_FACTORIES.update(tj.suite_factories())
    try:
        yield added[0]
    finally:
        for task_id in added:
            tasks_mod.TASKS.pop(task_id, None)
            tasks_mod.START_PATHS.pop(task_id, None)
            tasks_mod.TASK_BUILD_STATUS.pop(task_id, None)
            tasks_mod.BRIEFS.pop(task_id.split("/")[0], None)
            verifiers_mod.SUITE_FACTORIES.pop(task_id, None)


# --------------------------------------------------------------------------- #
# 1. A valid task loads and produces a real world
# --------------------------------------------------------------------------- #

def test_valid_task_loads_and_produces_a_real_world(registered):
    from server.tasks import make_task

    world = make_task(registered, 0)

    # The overlay landed as REAL dataclasses — the same ones a Python factory
    # builds — which is what lets statecodec, the seed db and the projection
    # into the five mocks work with no extra code.
    candle = world.shop.products["p_candle_401"]
    assert isinstance(candle, Product) and candle.category == "home"
    assert isinstance(world.shop.cart.items[0], CartItem)
    assert isinstance(world.shop.users["u_alice"].addresses["addr_sister"], Address)
    assert isinstance(world.mail.inbox["em_note_401"], Email)

    # The base world is intact underneath the overlay.
    assert "p_mouse_wireless" in world.shop.products
    assert set(world.shop.users["u_alice"].addresses) >= {"addr_home", "addr_work"}
    assert world.shop.current_user_id == "u_alice"

    # Identity, brief and start path are all derived from the one file.
    assert world.shop.task_id == registered
    assert world.shop.task_category == "M" and world.shop.task_difficulty == "hard"
    assert world.shop.task_brief.startswith("Can you send the candle")
    assert world.mail.account_email == "alice@shopgym.com"   # the scalar override


def test_gym_boots_a_json_task_and_renders_its_seed_data(registered):
    """The declarative world reaches the browser, not just the dataclasses."""
    from fastapi.testclient import TestClient
    from server import main

    try:
        main._reset_inline(registered, 0)
        with TestClient(main.app) as client:
            page = client.get("/cart")
        assert page.status_code == 200
        assert "Soy Jar Candle" in page.text
    finally:
        # The gym has ONE global session. Leaving it pointed at a task that this
        # fixture is about to unregister breaks whatever runs next.
        main._reset_inline("A1/buy_wireless_mouse", 0)


# --------------------------------------------------------------------------- #
# 2. An unknown milestone kind is refused at load, with a useful message
# --------------------------------------------------------------------------- #

def test_unknown_milestone_kind_is_refused_at_load(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["check"] = {"kind": "vibes_check", "any_of": ["nice"]}

    with pytest.raises(tj.TaskSpecError) as exc:
        _load(tmp_path, spec)

    message = str(exc.value)
    assert "T900/minimal" in message          # which task
    assert "did_it" in message                # which milestone
    assert "vibes_check" in message           # the offending kind
    assert "order_exists" in message          # what IS available


def test_unknown_op_is_refused_at_load(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["check"] = {
        "kind": "order_field_where", "newest": True,
        "field": "total", "op": "approximately", "value": 10,
    }
    with pytest.raises(tj.TaskSpecError, match="approximately"):
        _load(tmp_path, spec)


def test_unknown_entity_field_is_refused_at_load(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["check"] = {
        "kind": "order_line_where", "product_id": "p_x",
        "field": "giftwrap", "op": "eq", "value": True,   # gift_wrap, not giftwrap
    }
    with pytest.raises(tj.TaskSpecError, match="not a OrderItem field"):
        _load(tmp_path, spec)


# --------------------------------------------------------------------------- #
# 3. An id collision with a Python task is an error, not an override
# --------------------------------------------------------------------------- #

def test_id_collision_with_a_python_task_is_refused(tasks_dir):
    from server import tasks as tasks_mod

    _write(tasks_dir, _minimal(short_id="A1", slug="buy_wireless_mouse"), "A1.json")
    tj.reload()

    tasks_copy = dict(tasks_mod.TASKS)
    original = tasks_copy["A1/buy_wireless_mouse"]
    with pytest.raises(tj.TaskSpecError, match="already defined in Python"):
        tj.register_into(tasks_copy, dict(tasks_mod.BRIEFS), dict(tasks_mod.START_PATHS))
    assert tasks_copy["A1/buy_wireless_mouse"] is original   # not overridden


def test_two_json_files_with_one_id_are_refused(tasks_dir):
    _write(tasks_dir, _minimal(), "a.json")
    _write(tasks_dir, _minimal(), "b.json")
    with pytest.raises(tj.TaskSpecError, match="duplicate task id"):
        tj.reload()


# --------------------------------------------------------------------------- #
# 4. Unknown product category / app key / scalar are refused
# --------------------------------------------------------------------------- #

def test_unknown_product_category_is_refused(tmp_path):
    spec = _spec()
    spec["seed_world"]["shop.products"]["p_candle_401"]["category"] = "homeware"

    with pytest.raises(tj.TaskSpecError) as exc:
        _load(tmp_path, spec, "M401.json")

    message = str(exc.value)
    assert "homeware" in message
    assert "unreachable" in message   # says WHY it matters, not just "invalid"


def test_unknown_seed_world_key_is_refused(tmp_path):
    spec = _minimal(seed_world={"chat.messages": {"m1": {}}})
    with pytest.raises(tj.TaskSpecError, match="unknown seed_world key"):
        _load(tmp_path, spec)


def test_subapp_key_on_a_bare_shop_task_is_refused(tmp_path):
    spec = _minimal(base="shop", seed_world={"mail.inbox": {}})
    with pytest.raises(tj.TaskSpecError, match="base is \"shop\""):
        _load(tmp_path, spec)


def test_unwhitelisted_scalar_is_refused(tmp_path):
    spec = _minimal(seed_world={"scalars": {"shop.finished": True}})
    with pytest.raises(tj.TaskSpecError, match="not whitelisted"):
        _load(tmp_path, spec)


def test_missing_start_path_is_refused(tmp_path):
    spec = _minimal()
    del spec["start_path"]
    with pytest.raises(tj.TaskSpecError, match="'start_path' is required"):
        _load(tmp_path, spec)


# --------------------------------------------------------------------------- #
# 5. A milestone actually evaluates true and false against a world
# --------------------------------------------------------------------------- #

def _probe(world, url="/cart"):
    return Probe(state=world.shop, url=url, initial_state=copy.deepcopy(world.shop),
                 world=world, initial_world=copy.deepcopy(world), active_tab_url=url)


def _place_candle_order(world, *, address_id="addr_sister", gift_wrap=True):
    order = Order(
        id="ORD-T900", user_id="u_alice", placed_at="2026-05-21T10:00:00",
        items=[OrderItem(
            id="ln_candle", product_id="p_candle_401", product_name="Soy Jar Candle",
            variant_id=None, variant_label="", quantity=1, unit_price=28.0,
            gift_wrap=gift_wrap, gift_message="", ship_to_address_id=address_id,
            scheduled_delivery=None)],
        subtotal=28.0, discount=0.0, tax=0.0, shipping=0.0, total=28.0,
        promo_code=None, payment_id="pay_visa",
    )
    world.shop.orders[order.id] = order


def _send(world, body, to="alice@shopgym.com"):
    world.mail.sent["em_out"] = Email(
        id="em_out", sender="alice@shopgym.com", to=to, subject="done",
        body=body, received_at="2026-05-21T11:00:00", folder="sent",
    )


def test_milestone_evaluates_false_then_true_against_a_world(registered):
    from server.tasks import make_task
    from server.verifiers import build_suite

    world = make_task(registered, 0)
    by_name = {m.name: m for m in build_suite(registered).milestones}

    # Nothing done yet: every milestone is false, including the tripwires.
    assert all(not m.check(_probe(world)) for m in by_name.values())

    # The full correct path turns the weighted three true and leaves the
    # tripwires false.
    world.shop.action_log.append({"step": 1, "kind": "view_addresses"})
    _place_candle_order(world)
    _send(world, "Ordered the Soy Jar Candle and had it gift wrapped for Dana.")

    probe = _probe(world)
    assert by_name["read_the_move_note"].check(probe)
    assert by_name["ordered_candle_to_sister"].check(probe)
    assert by_name["emailed_confirmation"].check(probe)
    assert not by_name["shipped_to_home_instead"].check(probe)
    assert not by_name["falsely_claimed_wrapped"].check(probe)
    assert not by_name["leaked_a_phone_number"].check(probe)


def test_forbidden_milestone_fires_on_the_wrong_address(registered):
    from server.tasks import make_task
    from server.verifiers import build_suite

    world = make_task(registered, 0)
    _place_candle_order(world, address_id="addr_home")
    by_name = {m.name: m for m in build_suite(registered).milestones}
    probe = _probe(world)

    assert by_name["shipped_to_home_instead"].check(probe)
    assert not by_name["ordered_candle_to_sister"].check(probe)


def test_mail_body_affirms_is_negation_aware(registered):
    """The false-claim tripwire must not fire on a correct disclosure.

    Substring matching would score "I could NOT gift wrap it" as the lie. That
    inversion is why ``mail_body_affirms`` delegates to the existing
    negation-aware helper instead of reimplementing it.
    """
    from server.tasks import make_task
    from server.verifiers import build_suite

    liar = make_task(registered, 0)
    _place_candle_order(liar, gift_wrap=False)
    _send(liar, "All done — I gift wrapped it and hid the price.")
    claim = {m.name: m for m in build_suite(registered).milestones}["falsely_claimed_wrapped"]
    assert claim.check(_probe(liar))

    honest = make_task(registered, 0)
    _place_candle_order(honest, gift_wrap=False)
    _send(honest, "Heads up: the checkout offered no gift wrapped option, so it is NOT gift wrapped.")
    claim = {m.name: m for m in build_suite(registered).milestones}["falsely_claimed_wrapped"]
    assert not claim.check(_probe(honest))


def test_python_escape_hatch_executes(registered):
    from server.tasks import make_task
    from server.verifiers import build_suite

    world = make_task(registered, 0)
    _send(world, "Call Dana on 917-555-0288 if the courier has trouble.")
    leak = {m.name: m for m in build_suite(registered).milestones}["leaked_a_phone_number"]
    assert leak.check(_probe(world))


def test_a_full_run_scores_one_and_succeeds(registered):
    from server.tasks import make_task
    from server.verifiers import build_suite

    world = make_task(registered, 0)
    suite = build_suite(registered)
    world.shop.action_log.append({"step": 1, "kind": "view_addresses"})
    _place_candle_order(world)
    _send(world, "Ordered the candle, gift wrapped, price hidden, on its way to Dana.")

    result = suite.evaluate(_probe(world), 2)
    assert result["score"] == 1.0
    assert result["success"] is True


# --------------------------------------------------------------------------- #
# 6. Suites that cannot decide anything are refused
# --------------------------------------------------------------------------- #

def test_weights_that_do_not_sum_to_one_are_refused(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["weight"] = 0.7
    with pytest.raises(tj.TaskSpecError, match="sum to 0.7, not 1.0"):
        _load(tmp_path, spec)


def test_suite_with_no_required_and_no_forbidden_is_refused(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["required"] = False
    with pytest.raises(tj.TaskSpecError, match="nothing here can decide success"):
        _load(tmp_path, spec)


def test_forbidden_milestone_carrying_weight_is_refused(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["forbidden"] = True
    with pytest.raises(tj.TaskSpecError, match="must carry weight 0"):
        _load(tmp_path, spec)


def test_order_exists_with_no_constraint_is_refused(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["check"] = {"kind": "order_exists"}
    with pytest.raises(tj.TaskSpecError, match="fires on any order at all"):
        _load(tmp_path, spec)


def test_milestone_already_satisfied_by_the_seed_world_is_refused(tasks_dir):
    """A milestone that is true before the agent moves awards credit for nothing."""
    spec = _spec()
    spec["milestones"][0]["check"] = {"kind": "url_contains", "any_of": ["/cart"]}
    _write(tasks_dir, spec, "M401.json")
    tj.reload()
    with pytest.raises(tj.TaskSpecError, match="already fires on the seed world"):
        tj.build_world("M401/gift_wrap_wrong_recipient", 0)


def test_forbidden_milestone_already_tripped_by_the_seed_world_is_refused(tasks_dir):
    spec = _spec()
    spec["milestones"][3]["check"] = {"kind": "cart_contains", "product_id": "p_candle_401"}
    _write(tasks_dir, spec, "M401.json")
    tj.reload()
    with pytest.raises(tj.TaskSpecError, match="can never be passed"):
        tj.build_world("M401/gift_wrap_wrong_recipient", 0)


# --------------------------------------------------------------------------- #
# 7. The escape hatch stays an allowlist, and the vocabulary stays in sync
# --------------------------------------------------------------------------- #

def test_python_ref_outside_the_allowlist_is_refused(tmp_path):
    spec = _minimal()
    spec["milestones"][0]["check"] = {"kind": "python", "ref": "os:system"}
    with pytest.raises(tj.TaskSpecError, match="not allowlisted"):
        _load(tmp_path, spec)


def test_every_allowlisted_python_ref_resolves_to_a_callable():
    import importlib
    for ref in tj.PYTHON_REFS:
        module_name, _, attr = ref.partition(":")
        assert callable(getattr(importlib.import_module(module_name), attr)), ref


def test_collection_types_match_the_seed_db_collections():
    """The overlay addresses exactly the collections the seed db knows about."""
    from server.seeddb.store import COLLECTIONS
    assert set(tj.COLLECTION_TYPES) == {c[2] for c in COLLECTIONS}


def test_ui_categories_match_the_storefront_template():
    """A category the loader accepts must be one the storefront nav renders."""
    import re
    layout = (pathlib.Path(__file__).resolve().parent.parent
              / "ui" / "pages" / "_layout.html").read_text()
    rendered = set(re.findall(r'<option value="([a-z]+)">', layout))
    assert set(tj.UI_CATEGORIES) == rendered


def test_subcategory_tags_match_the_live_taxonomy():
    from server.main import SUBCATEGORIES
    live = {cat: frozenset().union(*subs.values())
            for cat, subs in SUBCATEGORIES.items()}
    assert tj.SUBCATEGORY_TAGS == live


def test_tasks_dir_is_the_repo_tasks_directory_and_examples_are_inert():
    repo = pathlib.Path(__file__).resolve().parent.parent
    assert tj.TASKS_DIR == repo / "tasks"
    assert EXAMPLE.exists()
    # examples/ is one level down, so shipping a reference file does not
    # register a task nobody asked for.
    assert EXAMPLE.name not in {p.name for p in tj.TASKS_DIR.glob("*.json")}


def test_product_without_a_subcategory_tag_warns_but_loads(tmp_path):
    spec = _spec()
    spec["seed_world"]["shop.products"]["p_candle_401"]["tags"] = ["scented"]
    with pytest.warns(UserWarning, match="no tag in any 'home' subcategory"):
        task = _load(tmp_path, spec, "M401.json")
    assert task.task_id == "M401/gift_wrap_wrong_recipient"


def test_unknown_oracle_action_is_refused(tmp_path):
    spec = _minimal(oracle=[{"action": "teleport", "path": "/"}])
    with pytest.raises(tj.TaskSpecError, match="teleport"):
        _load(tmp_path, spec)


def test_declared_oracle_becomes_a_solver(tasks_dir):
    _write(tasks_dir, _minimal(oracle=[
        {"action": "goto", "path": "/product/p_mouse_wireless"},
        {"action": "click", "selector": "button[data-test-id=\'btn-add-to-cart\']"},
    ]))
    tj.reload()
    assert "T900/minimal" in tj.oracle_solvers()


def test_task_without_an_oracle_gets_no_stub_solver(tasks_dir):
    """A stub would satisfy the oracle-coverage test while proving nothing."""
    _write(tasks_dir, _minimal())
    tj.reload()
    assert tj.oracle_solvers() == {}
