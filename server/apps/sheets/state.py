"""Sheets app store — canonical workbook model per PHASE_E_SHEETS_SPEC.md.

Stable IDs independent of display names. Dates/timestamps are fixed so a reset
for a given seed reproduces an identical workbook. No network import on seed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SEED_DATE = "2026-05-21"

InputType = Literal[
    "blank", "string", "number", "boolean", "date", "error", "formula",
]
CalcStatus = Literal["clean", "error"]
Visibility = Literal["visible", "hidden"]


def cell_key(row: int, col: int) -> str:
    return f"{row},{col}"


@dataclass
class Cell:
    input_type: InputType = "blank"
    input: Any = None                 # exact user-entered scalar or formula text
    value_type: str = "blank"         # normalized calculated type
    value: Any = None                 # normalized calculated value
    display: str = ""                 # deterministic formatted string
    style_id: str | None = None


@dataclass
class Range:
    start_row: int
    start_col: int
    end_row: int
    end_col: int

    def contains(self, row: int, col: int) -> bool:
        return (
            self.start_row <= row <= self.end_row
            and self.start_col <= col <= self.end_col
        )

    def is_anchor(self, row: int, col: int) -> bool:
        return row == self.start_row and col == self.start_col

    def to_json(self) -> dict[str, int]:
        return {
            "start_row": self.start_row, "start_col": self.start_col,
            "end_row": self.end_row, "end_col": self.end_col,
        }


@dataclass
class DefinedName:
    id: str
    name: str
    scope: str                        # workbook | sheet:{sheet_id}
    ref: str                          # absolute A1 or constant/formula


@dataclass
class Worksheet:
    id: str
    name: str
    row_count: int = 50
    column_count: int = 26
    cells: dict[str, Cell] = field(default_factory=dict)
    merges: list[Range] = field(default_factory=list)
    hidden_rows: set[int] = field(default_factory=set)
    hidden_columns: set[int] = field(default_factory=set)
    row_sizes: dict[int, float] = field(default_factory=dict)
    column_sizes: dict[int, float] = field(default_factory=dict)
    default_style_id: str | None = None
    visibility: Visibility = "visible"

    def get_cell(self, row: int, col: int) -> Cell:
        return self.cells.get(cell_key(row, col), Cell())

    def set_cell(self, row: int, col: int, cell: Cell) -> None:
        key = cell_key(row, col)
        if cell.input_type == "blank" and cell.input is None and not cell.display:
            self.cells.pop(key, None)
        else:
            self.cells[key] = cell

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "cells": {k: asdict(v) for k, v in self.cells.items()},
            "merges": [m.to_json() for m in self.merges],
            "hidden_rows": sorted(self.hidden_rows),
            "hidden_columns": sorted(self.hidden_columns),
            "row_sizes": {str(k): v for k, v in self.row_sizes.items()},
            "column_sizes": {str(k): v for k, v in self.column_sizes.items()},
            "default_style_id": self.default_style_id,
            "visibility": self.visibility,
        }


@dataclass
class Workbook:
    id: str
    title: str
    sheet_order: list[str] = field(default_factory=list)
    sheets: dict[str, Worksheet] = field(default_factory=dict)
    defined_names: dict[str, DefinedName] = field(default_factory=dict)
    active_sheet_id: str | None = None
    active_selection: dict[str, Any] | None = None
    calculation_version: int = 0
    calculation_status: CalcStatus = "clean"

    def active_sheet(self) -> Worksheet | None:
        if not self.active_sheet_id:
            return None
        return self.sheets.get(self.active_sheet_id)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "sheet_order": list(self.sheet_order),
            "sheets": {k: v.to_json() for k, v in self.sheets.items()},
            "defined_names": {k: asdict(v) for k, v in self.defined_names.items()},
            "active_sheet_id": self.active_sheet_id,
            "active_selection": self.active_selection,
            "calculation_version": self.calculation_version,
            "calculation_status": self.calculation_status,
        }


@dataclass
class SheetEvent:
    id: str
    step: int
    workbook_id: str
    command_type: str
    target: dict[str, Any]
    before_hash: str
    after_hash: str
    revision: int
    actor: str = "agent"
    rejected: bool = False
    reason: str | None = None


@dataclass
class SheetsState:
    workbooks: dict[str, Workbook] = field(default_factory=dict)
    active_workbook_id: str | None = None
    revision: int = 0
    action_log: list[dict[str, Any]] = field(default_factory=list)
    events: list[SheetEvent] = field(default_factory=list)
    # Idempotency: key -> committed response payload
    idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)
    _next_sheet: int = 1
    _next_event: int = 1
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)

    def new_sheet_id(self) -> str:
        sid = f"sh_{self._next_sheet}"
        self._next_sheet += 1
        return sid

    def new_event_id(self) -> str:
        eid = f"sev_{self._next_event}"
        self._next_event += 1
        return eid

    def active_workbook(self) -> Workbook | None:
        if not self.active_workbook_id:
            return None
        return self.workbooks.get(self.active_workbook_id)

    def workbook_hash(self, workbook_id: str | None = None) -> str:
        wb = self.workbooks.get(workbook_id or (self.active_workbook_id or ""))
        if wb is None:
            return ""
        payload = json.dumps(wb.to_json(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_json(self) -> dict[str, Any]:
        return {
            "active_workbook_id": self.active_workbook_id,
            "revision": self.revision,
            "workbooks": {k: v.to_json() for k, v in self.workbooks.items()},
            "action_log": list(self.action_log),
            "events": [asdict(e) for e in self.events],
            "styles": dict(self.styles),
        }


def make_sheetsstate(seed: int = 0) -> SheetsState:
    """Default single-workbook seed with a small demo grid.

    Task factories replace this with declarative fixtures. Seed only perturbs
    a label cell so reset stays deterministic per seed.
    """
    state = SheetsState()
    wb_id = "wb_default"
    sheet_id = state.new_sheet_id()
    ws = Worksheet(id=sheet_id, name="Sheet1", row_count=30, column_count=10)
    label = "Seed A" if seed % 2 == 0 else "Seed B"
    ws.set_cell(0, 0, Cell(
        input_type="string", input=label, value_type="string",
        value=label, display=label,
    ))
    ws.set_cell(1, 0, Cell(
        input_type="number", input=10, value_type="number",
        value=10, display="10",
    ))
    ws.set_cell(2, 0, Cell(
        input_type="number", input=5, value_type="number",
        value=5, display="5",
    ))
    ws.set_cell(3, 0, Cell(
        input_type="formula", input="=A2+A3", value_type="number",
        value=15, display="15",
    ))
    wb = Workbook(
        id=wb_id,
        title="Workbook",
        sheet_order=[sheet_id],
        sheets={sheet_id: ws},
        active_sheet_id=sheet_id,
        calculation_version=1,
        calculation_status="clean",
    )
    state.workbooks[wb_id] = wb
    state.active_workbook_id = wb_id
    state.revision = 0
    return state
