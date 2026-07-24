"""Focused calc stub tests: cross-sheet refs + IF (engine slice for S2/S3)."""

from __future__ import annotations

from server.apps.sheets.calc import recalculate_workbook
from server.apps.sheets.mutations import apply_command
from server.apps.sheets.state import Cell, SheetsState, Workbook, Worksheet


def _wb_two_sheets() -> tuple[SheetsState, Workbook, str, str]:
    state = SheetsState()
    a = Worksheet(id="sh_a", name="Inputs", row_count=20, column_count=10)
    b = Worksheet(id="sh_b", name="Approval", row_count=20, column_count=10)
    a.set_cell(4, 3, Cell(  # D5
        input_type="number", input=4, value_type="number", value=4, display="4",
    ))
    a.set_cell(3, 3, Cell(  # D4 decoy
        input_type="number", input=3, value_type="number", value=3, display="3",
    ))
    b.set_cell(3, 1, Cell(  # B4
        input_type="formula", input="=Inputs!D5", value_type="blank",
        value=None, display="",
    ))
    wb = Workbook(
        id="wb1", title="t",
        sheet_order=["sh_a", "sh_b"],
        sheets={"sh_a": a, "sh_b": b},
        active_sheet_id="sh_b",
    )
    state.workbooks["wb1"] = wb
    state.active_workbook_id = "wb1"
    recalculate_workbook(wb)
    return state, wb, "sh_a", "sh_b"


def test_cross_sheet_ref_resolves():
    _, wb, _, sh_b = _wb_two_sheets()
    assert wb.sheets[sh_b].get_cell(3, 1).value == 4
    assert wb.calculation_status == "clean"


def test_cross_sheet_updates_on_source_edit():
    state, wb, sh_a, sh_b = _wb_two_sheets()
    r = apply_command(
        state,
        command_type="set_cell",
        payload={"sheet_id": sh_a, "row": 4, "col": 3, "input": 7},
        base_revision=0,
    )
    assert r["ok"]
    assert state.active_workbook().sheets[sh_b].get_cell(3, 1).value == 7


def test_cross_sheet_quoted_name_with_spaces():
    state = SheetsState()
    src = Worksheet(id="sh1", name="Approved Lines", row_count=20, column_count=10)
    dst = Worksheet(id="sh2", name="Gate", row_count=20, column_count=10)
    src.set_cell(0, 0, Cell(
        input_type="number", input=9, value_type="number", value=9, display="9",
    ))
    dst.set_cell(0, 0, Cell(
        input_type="formula", input="='Approved Lines'!A1",
        value_type="blank", value=None, display="",
    ))
    wb = Workbook(
        id="wb", title="t", sheet_order=["sh1", "sh2"],
        sheets={"sh1": src, "sh2": dst}, active_sheet_id="sh2",
    )
    state.workbooks["wb"] = wb
    state.active_workbook_id = "wb"
    recalculate_workbook(wb)
    assert dst.get_cell(0, 0).value == 9


def test_if_blank_gate_flips_on_write():
    state = SheetsState()
    ws = Worksheet(id="sh_f", name="Final", row_count=30, column_count=10)
    ws.set_cell(20, 5, Cell())  # F21 blank
    ws.set_cell(20, 6, Cell(  # G21
        input_type="formula", input='=IF(F21<>"","Complete","Pending")',
        value_type="blank", value=None, display="",
    ))
    wb = Workbook(
        id="wb", title="t", sheet_order=["sh_f"],
        sheets={"sh_f": ws}, active_sheet_id="sh_f",
    )
    state.workbooks["wb"] = wb
    state.active_workbook_id = "wb"
    recalculate_workbook(wb)
    assert ws.get_cell(20, 6).value == "Pending"

    r = apply_command(
        state,
        command_type="set_cell",
        payload={"sheet_id": "sh_f", "row": 20, "col": 5, "input": "cal_vendor_review"},
        base_revision=0,
    )
    assert r["ok"]
    assert state.active_workbook().sheets["sh_f"].get_cell(20, 6).value == "Complete"


def test_sum_still_works_after_extensions():
    state = SheetsState()
    ws = Worksheet(id="sh", name="S", row_count=20, column_count=5)
    for i, n in enumerate((2, 1, 1, 1)):
        ws.set_cell(4 + i, 1, Cell(
            input_type="number", input=n, value_type="number", value=n, display=str(n),
        ))
    ws.set_cell(9, 1, Cell(
        input_type="formula", input="=SUM(B5:B8)",
        value_type="blank", value=None, display="",
    ))
    wb = Workbook(
        id="wb", title="t", sheet_order=["sh"], sheets={"sh": ws}, active_sheet_id="sh",
    )
    state.workbooks["wb"] = wb
    state.active_workbook_id = "wb"
    recalculate_workbook(wb)
    assert ws.get_cell(9, 1).value == 5
