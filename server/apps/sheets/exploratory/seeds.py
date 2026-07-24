"""Seed builders for exploratory Sheets pilots S1–S3.

Cell addresses use Excel A1 (1-indexed rows/cols in labels); storage is
0-indexed via ``parse_a1``.
"""

from __future__ import annotations

from typing import Any

from server.apps.mail.state import MailState, make_mailstate
from server.apps.market.state import MarketProduct, MarketState, make_marketstate
from server.apps.sheets.calc import parse_a1, recalculate_workbook
from server.apps.sheets.state import Cell, SheetsState, Workbook, Worksheet

LAUNCH_KIT_ID = "vm_launch_kit"
WEST_LAUNCH_KIT_ID = "vm_west_launch_kit"
EAST_LAUNCH_KIT_ID = "vm_east_launch_kit"


def _num(n: int | float) -> Cell:
    return Cell(
        input_type="number", input=n, value_type="number",
        value=n, display=str(n),
    )


def _str(s: str) -> Cell:
    return Cell(
        input_type="string", input=s, value_type="string",
        value=s, display=s,
    )


def _formula(text: str) -> Cell:
    return Cell(
        input_type="formula", input=text, value_type="blank",
        value=None, display="",
    )


def _blank() -> Cell:
    return Cell()


def put(ws: Worksheet, a1: str, cell: Cell) -> None:
    row, col = parse_a1(a1)
    ws.set_cell(row, col, cell)


def sheet_named(wb: Workbook, name: str) -> Worksheet:
    for ws in wb.sheets.values():
        if ws.name == name:
            return ws
    raise KeyError(name)


def _new_wb(state: SheetsState, *, title: str) -> Workbook:
    wb = Workbook(id="wb_exploratory", title=title)
    state.workbooks[wb.id] = wb
    state.active_workbook_id = wb.id
    state.revision = 0
    return wb


def _add_sheet(state: SheetsState, wb: Workbook, name: str, *, activate: bool = False) -> Worksheet:
    sid = state.new_sheet_id()
    ws = Worksheet(id=sid, name=name, row_count=40, column_count=12)
    wb.sheets[sid] = ws
    wb.sheet_order.append(sid)
    if activate or wb.active_sheet_id is None:
        wb.active_sheet_id = sid
    return ws


# ---------------------------------------------------------------------------
# S1 — active-tab SUM gate before market order
# ---------------------------------------------------------------------------

def seed_s1_workbook(seed: int = 0) -> SheetsState:
    """Draft (active) + Approved Lines (SUM authority) + Summary (stale)."""
    del seed  # reserved for future light perturbation
    state = SheetsState()
    wb = _new_wb(state, title="Kit Order Workbook")

    draft = _add_sheet(state, wb, "Draft", activate=True)
    put(draft, "A4", _str("Draft qtys (do not use)"))
    for a1, n in (("B5", 3), ("B6", 2), ("B7", 2), ("B8", 1)):
        put(draft, a1, _num(n))
    put(draft, "A10", _str("Cached total (do not use)"))
    put(draft, "B10", _num(8))  # hardcoded — not SUM
    put(draft, "A12", _str("Order ID"))
    put(draft, "D12", _blank())

    approved = _add_sheet(state, wb, "Approved Lines")
    put(approved, "A4", _str("Line"))
    put(approved, "B4", _str("Qty"))
    put(approved, "A5", _str("Base"))
    put(approved, "B5", _num(2))
    put(approved, "A6", _str("Midline"))
    put(approved, "B6", _num(1))
    put(approved, "A7", _str("Add-on"))
    put(approved, "B7", _num(1))
    put(approved, "A8", _str("Spare"))
    put(approved, "B8", _num(1))
    put(approved, "A10", _str("Total Kits"))
    put(approved, "B10", _formula("=SUM(B5:B8)"))
    put(approved, "A11", _str("Raise Midline (B6) if needed"))
    put(approved, "A12", _str("Order ID"))
    put(approved, "D12", _blank())

    summary = _add_sheet(state, wb, "Summary")
    put(summary, "A1", _str("Summary (not live)"))
    put(summary, "A2", _str("last sync"))
    put(summary, "B2", _num(8))

    recalculate_workbook(wb)
    return state


def seed_s1_market() -> MarketState:
    m = make_marketstate(0)
    m.products[LAUNCH_KIT_ID] = MarketProduct(
        id=LAUNCH_KIT_ID, name="Launch Kit", category="kits",
        price=19.99, emoji="📦", description="Standard launch kit.",
        in_stock=True,
    )
    m.cart.items.clear()
    return m


def seed_s1_world_parts(seed: int = 0) -> dict[str, Any]:
    return {
        "sheets": seed_s1_workbook(seed),
        "market": seed_s1_market(),
        "mail": make_mailstate(0),
        "prompt": (
            "On the `Approved Lines` sheet, set the line quantities so "
            "`Total Kits` (`B10`, formula `=SUM(B5:B8)`) equals **6**. "
            "Then order exactly that many `Launch Kit` units from ValueMart. "
            "Do not use the Draft sheet or any cached total. Email me the "
            "order number and the Total Kits value after recalculation."
        ),
    }


# ---------------------------------------------------------------------------
# S2 — cross-sheet qty authority (not Summary)
# ---------------------------------------------------------------------------

def seed_s2_workbook(seed: int = 0) -> SheetsState:
    del seed
    state = SheetsState()
    wb = _new_wb(state, title="West Qty Approval")

    summary = _add_sheet(state, wb, "Summary", activate=True)
    put(summary, "A2", _str("planned West kits (cached)"))
    put(summary, "B2", _num(4))

    inputs = _add_sheet(state, wb, "Inputs")
    put(inputs, "C4", _str("early estimate"))
    put(inputs, "D4", _num(3))
    put(inputs, "C5", _str("approved West qty"))
    put(inputs, "D5", _num(4))
    put(inputs, "A6", _str("Approval binds to D5"))

    approval = _add_sheet(state, wb, "Approval")
    put(approval, "A4", _str("West"))
    put(approval, "B4", _formula("=Inputs!D5"))
    put(approval, "C4", _str("APPROVED"))
    put(approval, "A5", _str("draft mirror"))
    put(approval, "B5", _num(3))

    recalculate_workbook(wb)
    return state


def seed_s2_market() -> MarketState:
    """Authority-vs-decoy kits only — no long default catalog.

    The full ``make_marketstate`` catalog sorts kits last (East then West).
    On the pinned 1280×800 viewport that left West below the fold while East
    stayed visible, so models that never scroll could only click the decoy.
    Keep both kits (East remains the wrong-SKU trap); drop unrelated SKUs so
    both are above the fold without changing catalog sort globally.
    """
    m = make_marketstate(0)
    m.products.clear()
    m.products[WEST_LAUNCH_KIT_ID] = MarketProduct(
        id=WEST_LAUNCH_KIT_ID, name="West Launch Kit", category="kits",
        price=19.99, emoji="📦", description="West region launch kit.",
        in_stock=True,
    )
    m.products[EAST_LAUNCH_KIT_ID] = MarketProduct(
        id=EAST_LAUNCH_KIT_ID, name="East Launch Kit", category="kits",
        price=19.99, emoji="📦", description="East region decoy kit.",
        in_stock=True,
    )
    m.cart.items.clear()
    return m


def seed_s2_world_parts(seed: int = 0) -> dict[str, Any]:
    return {
        "sheets": seed_s2_workbook(seed),
        "market": seed_s2_market(),
        "mail": make_mailstate(0),
        "prompt": (
            "Order `West Launch Kit` from ValueMart using the quantity shown "
            "on the `Approval` sheet in `B4`. That cell is a live formula from "
            "`Inputs`. Do not use the Summary sheet. Place exactly one order."
        ),
    }


# ---------------------------------------------------------------------------
# S3 — IF Status writeback before mail
# ---------------------------------------------------------------------------

def seed_s3_workbook(seed: int = 0) -> SheetsState:
    del seed
    state = SheetsState()
    wb = _new_wb(state, title="Vendor Review Writeback")

    draft = _add_sheet(state, wb, "Draft", activate=True)
    put(draft, "A12", _str("Vendor Review"))
    put(draft, "C12", _str("14:00"))
    put(draft, "F12", _blank())
    put(draft, "G12", _formula('=IF(F12<>"","Complete","Pending")'))

    final = _add_sheet(state, wb, "Final")
    put(final, "A20", _str("Vendor Renewal"))
    put(final, "C20", _str("15:00"))
    put(final, "F20", _blank())
    put(final, "G20", _formula('=IF(F20<>"","Complete","Pending")'))
    put(final, "A21", _str("Vendor Review"))
    put(final, "C21", _str("15:30"))
    put(final, "F21", _blank())
    put(final, "G21", _formula('=IF(F21<>"","Complete","Pending")'))

    recalculate_workbook(wb)
    return state


S3_VENDOR_REVIEW_EVENT_ID = "cal_vendor_review"


def seed_s3_calendar(seed: int = 0):
    """Default calendar plus a discoverable Vendor Review event.

    Event id is stable (``cal_vendor_review``) so the verifier can check
    equality; agents must still read it from the Calendar UI (agenda Edit
    link / edit-page Event ID), not from this constant.
    """
    from server.apps.calendar.state import (
        TODAY,
        CalendarEvent,
        make_calendarstate,
    )

    cal = make_calendarstate(seed)
    cal.events[S3_VENDOR_REVIEW_EVENT_ID] = CalendarEvent(
        id=S3_VENDOR_REVIEW_EVENT_ID,
        title="Vendor Review",
        day=TODAY,
        day_label="Today (Thu May 21)",
        start="15:30",
        end="16:30",
        source="seed",
    )
    return cal


def seed_s3_world_parts(seed: int = 0) -> dict[str, Any]:
    return {
        "sheets": seed_s3_workbook(seed),
        "mail": make_mailstate(0),
        "calendar": seed_s3_calendar(seed),
        "prompt": (
            "On the `Final` sheet, write the Calendar event ID for "
            "`Vendor Review` into `F21`, wait until `G21` shows `Complete`, "
            "then email me the start time in `C21`. Do not edit the Draft sheet."
        ),
        "event_id": S3_VENDOR_REVIEW_EVENT_ID,
    }
