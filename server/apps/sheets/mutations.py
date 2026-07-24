"""Sheets mutations — validation, atomic commands, recalculation, events.

Applies allowlisted commands against a workbook copy conceptually (in-process
commit after validation). Never partially commits: failures leave state
unchanged for that command. Cross-app effects are not emitted generically;
task wiring may subscribe later via the world bus.
"""

from __future__ import annotations

import copy
from typing import Any

from server.apps.sheets.calc import recalculate_workbook
from server.apps.sheets.state import (
    Cell,
    Range,
    SheetEvent,
    SheetsState,
    Worksheet,
    cell_key,
)

ALLOWED_COMMANDS = frozenset({
    "set_cell",
    "clear_cell",
    "set_active_sheet",
    "add_sheet",
    "rename_sheet",
    "hide_rows",
    "unhide_rows",
    "hide_columns",
    "unhide_columns",
    "merge",
    "unmerge",
    "set_selection",
})


def snapshot_workbook(state: SheetsState) -> dict[str, Any]:
    wb = state.active_workbook()
    return {
        "revision": state.revision,
        "workbook": wb.to_json() if wb is not None else None,
        "workbook_hash": state.workbook_hash(),
    }


def a11y_projection(
    state: SheetsState,
    *,
    sheet_id: str | None = None,
    max_rows: int = 20,
    max_cols: int = 10,
) -> dict[str, Any]:
    """Bounded semantic projection — not omniscient, not a hidden answer API."""
    wb = state.active_workbook()
    if wb is None:
        return {"tabs": [], "cells": [], "revision": state.revision}
    sid = sheet_id or wb.active_sheet_id
    ws = wb.sheets.get(sid or "")
    tabs = [
        {
            "sheet_id": s_id,
            "name": wb.sheets[s_id].name,
            "selected": s_id == wb.active_sheet_id,
            "visibility": wb.sheets[s_id].visibility,
        }
        for s_id in wb.sheet_order
    ]
    cells: list[dict[str, Any]] = []
    merges: list[dict[str, Any]] = []
    if ws is not None:
        merges = [m.to_json() for m in ws.merges]
        for r in range(min(ws.row_count, max_rows)):
            if r in ws.hidden_rows:
                continue
            for c in range(min(ws.column_count, max_cols)):
                if c in ws.hidden_columns:
                    continue
                covered = False
                for m in ws.merges:
                    if m.contains(r, c) and not m.is_anchor(r, c):
                        covered = True
                        break
                if covered:
                    continue
                cell = ws.get_cell(r, c)
                cells.append({
                    "sheet_id": ws.id,
                    "row": r,
                    "col": c,
                    "input": cell.input,
                    "display": cell.display,
                    "value": cell.value,
                    "input_type": cell.input_type,
                })
    return {
        "revision": state.revision,
        "calculation_status": wb.calculation_status,
        "tabs": tabs,
        "merges": merges,
        "cells": cells,
        "active_sheet_id": wb.active_sheet_id,
    }


def apply_command(
    state: SheetsState,
    *,
    command_type: str,
    payload: dict[str, Any] | None = None,
    base_revision: int | None = None,
    idempotency_key: str | None = None,
    step: int = 0,
) -> dict[str, Any]:
    payload = dict(payload or {})
    if idempotency_key and idempotency_key in state.idempotency:
        return dict(state.idempotency[idempotency_key])

    if command_type not in ALLOWED_COMMANDS:
        return _reject(
            state, command_type, payload, step,
            reason=f"command not allowlisted: {command_type}",
            idempotency_key=idempotency_key,
        )

    if base_revision is not None and base_revision != state.revision:
        return _reject(
            state, command_type, payload, step,
            reason=(
                f"revision conflict: base={base_revision} "
                f"current={state.revision}"
            ),
            idempotency_key=idempotency_key,
        )

    wb = state.active_workbook()
    if wb is None:
        return _reject(
            state, command_type, payload, step,
            reason="no active workbook",
            idempotency_key=idempotency_key,
        )

    before = state.workbook_hash()
    # Work on a deep copy; commit only on success.
    trial = copy.deepcopy(state)
    trial_wb = trial.active_workbook()
    assert trial_wb is not None

    try:
        _dispatch(trial, trial_wb, command_type, payload)
        recalculate_workbook(trial_wb)
    except Exception as exc:  # noqa: BLE001
        return _reject(
            state, command_type, payload, step,
            reason=str(exc),
            idempotency_key=idempotency_key,
        )

    # Commit trial into live state (replace workbook + counters).
    state.workbooks[trial_wb.id] = trial_wb
    state.revision = trial.revision + 1
    state._next_sheet = trial._next_sheet
    after = state.workbook_hash()
    ev = SheetEvent(
        id=state.new_event_id(),
        step=step,
        workbook_id=trial_wb.id,
        command_type=command_type,
        target=payload,
        before_hash=before,
        after_hash=after,
        revision=state.revision,
        actor="agent",
    )
    state.events.append(ev)
    state.action_log.append({
        "revision": state.revision,
        "command_type": command_type,
        "payload": payload,
    })
    result = {
        "ok": True,
        "revision": state.revision,
        "workbook_hash": after,
        "calculation_status": trial_wb.calculation_status,
        "workbook": trial_wb.to_json(),
        "event_id": ev.id,
    }
    if idempotency_key:
        state.idempotency[idempotency_key] = dict(result)
    return result


def recalculate(state: SheetsState) -> dict[str, Any]:
    wb = state.active_workbook()
    if wb is None:
        return {"ok": False, "error": "no active workbook"}
    recalculate_workbook(wb)
    return {
        "ok": True,
        "revision": state.revision,
        "calculation_status": wb.calculation_status,
        "calculation_version": wb.calculation_version,
        "workbook_hash": state.workbook_hash(),
        "workbook": wb.to_json(),
    }


def _reject(
    state: SheetsState,
    command_type: str,
    payload: dict[str, Any],
    step: int,
    *,
    reason: str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    wb = state.active_workbook()
    ev = SheetEvent(
        id=state.new_event_id(),
        step=step,
        workbook_id=wb.id if wb else "",
        command_type=command_type,
        target=payload,
        before_hash=state.workbook_hash(),
        after_hash=state.workbook_hash(),
        revision=state.revision,
        actor="agent",
        rejected=True,
        reason=reason,
    )
    state.events.append(ev)
    result = {
        "ok": False,
        "error": reason,
        "revision": state.revision,
        "rejected": True,
        "event_id": ev.id,
    }
    if idempotency_key:
        state.idempotency[idempotency_key] = dict(result)
    return result


def _dispatch(
    state: SheetsState, wb, command_type: str, payload: dict[str, Any],
) -> None:
    if command_type == "set_cell":
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        row, col = int(payload["row"]), int(payload["col"])
        _ensure_in_bounds(ws, row, col)
        for m in ws.merges:
            if m.contains(row, col) and not m.is_anchor(row, col):
                raise ValueError("cannot write covered merge cell; use anchor")
        raw = payload.get("input")
        cell = _cell_from_input(raw)
        ws.set_cell(row, col, cell)
        return

    if command_type == "clear_cell":
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        row, col = int(payload["row"]), int(payload["col"])
        ws.cells.pop(cell_key(row, col), None)
        return

    if command_type == "set_active_sheet":
        sid = payload.get("sheet_id")
        if sid not in wb.sheets:
            raise ValueError("unknown sheet_id")
        wb.active_sheet_id = sid
        return

    if command_type == "add_sheet":
        name = (payload.get("name") or f"Sheet{len(wb.sheets) + 1}").strip()
        sid = state.new_sheet_id()
        ws = Worksheet(id=sid, name=name)
        wb.sheets[sid] = ws
        wb.sheet_order.append(sid)
        if payload.get("activate", True):
            wb.active_sheet_id = sid
        return

    if command_type == "rename_sheet":
        ws = _require_sheet(wb, payload.get("sheet_id"))
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValueError("name required")
        ws.name = name
        return

    if command_type in ("hide_rows", "unhide_rows"):
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        rows = [int(r) for r in payload.get("rows") or []]
        for r in rows:
            if command_type == "hide_rows":
                ws.hidden_rows.add(r)
            else:
                ws.hidden_rows.discard(r)
        return

    if command_type in ("hide_columns", "unhide_columns"):
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        cols = [int(c) for c in payload.get("columns") or []]
        for c in cols:
            if command_type == "hide_columns":
                ws.hidden_columns.add(c)
            else:
                ws.hidden_columns.discard(c)
        return

    if command_type == "merge":
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        rng = Range(
            start_row=int(payload["start_row"]),
            start_col=int(payload["start_col"]),
            end_row=int(payload["end_row"]),
            end_col=int(payload["end_col"]),
        )
        for existing in ws.merges:
            # reject overlap
            if not (
                rng.end_row < existing.start_row
                or rng.start_row > existing.end_row
                or rng.end_col < existing.start_col
                or rng.start_col > existing.end_col
            ):
                raise ValueError("merge overlaps existing merge")
        ws.merges.append(rng)
        return

    if command_type == "unmerge":
        ws = _require_sheet(wb, payload.get("sheet_id") or wb.active_sheet_id)
        row, col = int(payload["row"]), int(payload["col"])
        ws.merges = [m for m in ws.merges if not m.contains(row, col)]
        return

    if command_type == "set_selection":
        # Canonical only when task-consequential; still recorded in state.
        wb.active_selection = {
            "sheet_id": payload.get("sheet_id") or wb.active_sheet_id,
            "row": payload.get("row"),
            "col": payload.get("col"),
        }
        return

    raise ValueError(f"unhandled command: {command_type}")


def _require_sheet(wb, sheet_id: str | None) -> Worksheet:
    if not sheet_id or sheet_id not in wb.sheets:
        raise ValueError("unknown sheet_id")
    return wb.sheets[sheet_id]


def _ensure_in_bounds(ws: Worksheet, row: int, col: int) -> None:
    if row < 0 or col < 0 or row >= ws.row_count or col >= ws.column_count:
        raise ValueError("cell out of bounds")


def _cell_from_input(raw: Any) -> Cell:
    if raw is None or raw == "":
        return Cell()
    if isinstance(raw, bool):
        return Cell(
            input_type="boolean", input=raw, value_type="boolean",
            value=raw, display=str(raw).upper(),
        )
    if isinstance(raw, (int, float)):
        return Cell(
            input_type="number", input=raw, value_type="number",
            value=raw, display=str(raw),
        )
    text = str(raw)
    if text.startswith("="):
        return Cell(
            input_type="formula", input=text, value_type="blank",
            value=None, display="",
        )
    # numeric string?
    try:
        if "." in text:
            num: Any = float(text)
        else:
            num = int(text)
        return Cell(
            input_type="number", input=num, value_type="number",
            value=num, display=str(num),
        )
    except ValueError:
        return Cell(
            input_type="string", input=text, value_type="string",
            value=text, display=text,
        )
