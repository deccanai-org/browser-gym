"""Sheets app routes — the ``/sheets`` route family per PHASE_E_SHEETS_SPEC.md.

Injected-deps pattern (no circular import with main). Browser-facing routes
are ordinary HTML/JSON under ``/sheets``; privileged harness control remains
``/_harness/*`` with token auth in ``server.main``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from server.apps.sheets import mutations as S

router = APIRouter(prefix="/sheets", tags=["sheets"])

# Scaffold HTML grid bounds — tall enough that S3 authority cells (F21/G21)
# render on-screen. Univer will own viewporting later.
GRID_ROWS = 24
GRID_COLS = 8

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(
        templates=templates, get_world=get_world,
        build_ctx=build_ctx, flash=flash,
    )


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="sheets", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


class CommandBody(BaseModel):
    command_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    base_revision: int | None = None
    idempotency_key: str | None = None


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def workbook_shell(request: Request):
    world = _deps["get_world"]()
    sheets = world.sheets
    snap = S.snapshot_workbook(sheets)
    a11y = S.a11y_projection(
        sheets, max_rows=GRID_ROWS, max_cols=GRID_COLS,
    )
    # Pre-build a dense display grid for the scaffold HTML table (Jinja-friendly).
    grid: list[list[dict[str, Any]]] = [
        [{"display": "", "input": "", "value": None} for _ in range(GRID_COLS)]
        for _ in range(GRID_ROWS)
    ]
    for item in a11y.get("cells") or []:
        r, c = int(item["row"]), int(item["col"])
        if 0 <= r < GRID_ROWS and 0 <= c < GRID_COLS:
            grid[r][c] = {
                "display": item.get("display") or "",
                "input": item.get("input"),
                "value": item.get("value"),
            }
    return _render(
        request, "sheets/workbook.html",
        sheets=sheets, snapshot=snap, a11y=a11y, grid=grid,
        grid_rows=GRID_ROWS, grid_cols=GRID_COLS,
    )


@router.get("/api/workbook")
async def api_workbook(request: Request):
    sheets = _deps["get_world"]().sheets
    return JSONResponse(S.snapshot_workbook(sheets))


@router.post("/api/commands")
async def api_commands(request: Request, body: CommandBody):
    world = _deps["get_world"]()
    result = S.apply_command(
        world.sheets,
        command_type=body.command_type,
        payload=body.payload,
        base_revision=body.base_revision,
        idempotency_key=body.idempotency_key,
        step=world.step,
    )
    status = 200 if result.get("ok") else 409 if "revision conflict" in (
        result.get("error") or ""
    ) else 400
    return JSONResponse(result, status_code=status)


@router.post("/api/recalculate")
async def api_recalculate(request: Request):
    """Normally internal/testing — recalculation is automatic after commands."""
    sheets = _deps["get_world"]().sheets
    result = S.recalculate(sheets)
    status = 200 if result.get("ok") else 400
    return JSONResponse(result, status_code=status)


@router.get("/api/a11y")
async def api_a11y(
    request: Request,
    sheet_id: str | None = None,
    max_rows: int = 20,
    max_cols: int = 10,
):
    sheets = _deps["get_world"]().sheets
    return JSONResponse(
        S.a11y_projection(
            sheets, sheet_id=sheet_id,
            max_rows=min(max_rows, 50), max_cols=min(max_cols, 26),
        )
    )
