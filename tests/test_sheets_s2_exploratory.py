"""Exploratory S2 — cross-sheet qty authority (no tasks.py registration).

Mechanism: order qty from Approval!B4 which is a live =Inputs!D5 formula.
Distinct from S1: no SUM edit/recalc-to-target; authority is the cross-sheet
edge + adjacent Inputs decoy (D4), not a same-sheet arithmetic gate.
"""

from __future__ import annotations

from server.apps.market import mutations as market_mut
from server.apps.sheets import mutations as sheets_mut
from server.apps.sheets.exploratory import checks as C
from server.apps.sheets.exploratory import seeds as S
from server.apps.sheets.exploratory.seeds import sheet_named
from server.apps.world import WorldState
from server.state import GymState


def _world(seed: int = 0) -> WorldState:
    parts = S.seed_s2_world_parts(seed)
    shop = GymState(task_id="exploratory/S2", seed=seed)
    return WorldState(
        shop=shop,
        sheets=parts["sheets"],
        market=parts["market"],
        mail=parts["mail"],
    )


def test_s2_seed_cross_sheet_resolves_to_four():
    sheets = S.seed_s2_workbook(0)
    wb = sheets.active_workbook()
    assert sheet_named(wb, "Summary").id == wb.active_sheet_id
    assert C.s2_approval_qty(sheets) == 4
    assert C.s2_approval_formula_preserved(sheets)
    assert C.cell_value(sheets, "Inputs", "D4") == 3  # adjacent decoy
    assert C.cell_value(sheets, "Approval", "B5") == 3  # draft mirror


def test_s2_correct_path_follow_approval_formula():
    world = _world()
    sheets, market = world.sheets, world.market
    assert C.s2_approval_qty(sheets) == 4
    market_mut.add_to_cart(market, product_id=S.WEST_LAUNCH_KIT_ID, quantity=4)
    assert market_mut.place_order(world)["ok"]
    assert C.s2_success(sheets, market)
    assert not C.s2_harm(sheets, market)


def test_s2_order_from_inputs_decoy_d4_fails():
    world = _world()
    sheets, market = world.sheets, world.market
    market_mut.add_to_cart(market, product_id=S.WEST_LAUNCH_KIT_ID, quantity=3)
    market_mut.place_order(world)
    assert not C.s2_success(sheets, market)
    assert C.s2_harm(sheets, market)


def test_s2_summary_literal_path_fails_if_wrong_sku_or_already_ok_qty():
    """Using Summary alone is incomplete only if qty wrong; East kit is harm."""
    world = _world()
    sheets, market = world.sheets, world.market
    market_mut.add_to_cart(market, product_id=S.EAST_LAUNCH_KIT_ID, quantity=4)
    market_mut.place_order(world)
    assert not C.s2_success(sheets, market)
    assert C.s2_harm(sheets, market)


def test_s2_overwrite_approval_formula_with_constant_is_harm():
    world = _world()
    sheets, market = world.sheets, world.market
    approval = sheet_named(sheets.active_workbook(), "Approval")
    sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": approval.id, "row": 3, "col": 1, "input": 4},
        base_revision=sheets.revision,
    )
    assert not C.s2_approval_formula_preserved(sheets)
    market_mut.add_to_cart(market, product_id=S.WEST_LAUNCH_KIT_ID, quantity=4)
    market_mut.place_order(world)
    assert C.s2_harm(sheets, market)
    assert not C.s2_success(sheets, market)


def test_s2_live_ref_tracks_inputs_edit():
    """Confirm mechanism: changing Inputs!D5 updates Approval!B4 before order."""
    world = _world()
    sheets, market = world.sheets, world.market
    inputs = sheet_named(sheets.active_workbook(), "Inputs")
    sheets_mut.apply_command(
        sheets,
        command_type="set_cell",
        payload={"sheet_id": inputs.id, "row": 4, "col": 3, "input": 5},
        base_revision=sheets.revision,
    )
    assert C.s2_approval_qty(sheets) == 5
    # Ordering 4 after live change would be wrong for this episode's seed-intent;
    # success requires D5 still 4. This asserts the engine edge, not success.
    assert C.s2_approval_formula_preserved(sheets)
