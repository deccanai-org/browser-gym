"""Minimal in-process recalculation for Sheets scaffolding.

TODO (PHASE_E Gate 0 / Phase 1): replace with a localhost Node worker running
pinned Univer OSS headless packages under ``server/apps/sheets/calc/``, with a
strict JSON protocol, network disabled, and browser↔headless golden parity.

This stub supports:
  - literal number / string / blank cells
  - simple arithmetic formulas: =A1+B2, =A1-A2, =A1*A2, =A1/A2
  - =SUM(A1:A3) over a single contiguous column or row range
  - cross-sheet A1 refs: =Sheet1!A1 / ='Name With Spaces'!B2
  - narrow IF: =IF(cond, then, else) with blank/string compares
    (e.g. =IF(F21<>"","Complete","Pending"))

Volatile / network / unsupported formulas become typed errors. Cycles are not
fully solved; a depth cap yields an error cell.

Engine path (S1–S3 exploratory, 2026-07-20): Option 1 — purpose-built Python
stub extensions for cross-sheet + IF. See design note §6.
"""

from __future__ import annotations

import re
from typing import Any

from server.apps.sheets.state import Cell, Workbook, Worksheet, cell_key

_A1 = re.compile(r"^\$?([A-Z]+)\$?(\d+)$", re.I)
_SUM = re.compile(
    r"^=\s*SUM\(\s*\$?([A-Z]+)\$?(\d+)\s*:\s*\$?([A-Z]+)\$?(\d+)\s*\)\s*$",
    re.I,
)
_BIN = re.compile(
    r"^=\s*(\$?[A-Z]+\$?\d+|'(?:[^']+)'![A-Z]+\d+|[A-Za-z0-9_ ]+![A-Z]+\d+)"
    r"\s*([+\-*/])\s*"
    r"(\$?[A-Z]+\$?\d+|'(?:[^']+)'![A-Z]+\d+|[A-Za-z0-9_ ]+![A-Z]+\d+)\s*$",
    re.I,
)
# Sheet!A1 or 'Sheet Name'!A1 (optional leading = handled by caller).
_XSHEET = re.compile(
    r"^(?:'([^']+)'|([A-Za-z0-9][A-Za-z0-9_ ]*))!(\$?[A-Z]+\$?\d+)$",
    re.I,
)
_IF = re.compile(r"^=\s*IF\(\s*(.+)\s*\)\s*$", re.I | re.DOTALL)
_CMP = re.compile(
    r"^(.+?)\s*(<>|=|<=|>=|<|>)\s*(.+)$",
)


def col_letters_to_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def index_to_col_letters(idx: int) -> str:
    n = idx + 1
    out = []
    while n:
        n, rem = divmod(n - 1, 26)
        out.append(chr(ord("A") + rem))
    return "".join(reversed(out))


def parse_a1(ref: str) -> tuple[int, int]:
    m = _A1.match(ref.strip())
    if not m:
        raise ValueError(f"bad A1 ref: {ref}")
    return int(m.group(2)) - 1, col_letters_to_index(m.group(1))


def sheet_by_name(wb: Workbook, name: str) -> Worksheet:
    want = name.strip()
    for ws in wb.sheets.values():
        if ws.name == want:
            return ws
    raise ValueError(f"unknown sheet: {name}")


def _as_number(val: Any) -> float | None:
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return None
    return None


def recalculate_workbook(wb: Workbook) -> None:
    """Synchronous quiescence pass over all sheets' formula cells."""
    status: str = "clean"
    for sid in wb.sheet_order:
        ws = wb.sheets[sid]
        for key, cell in list(ws.cells.items()):
            if cell.input_type != "formula":
                continue
            row_s, col_s = key.split(",", 1)
            row, col = int(row_s), int(col_s)
            try:
                value = _eval_cell(wb, ws, row, col, set())
                num = _as_number(value)
                if num is not None and not isinstance(value, str):
                    cell.value_type = "number"
                    cell.value = num if not float(num).is_integer() else int(num)
                    cell.display = str(cell.value)
                else:
                    cell.value_type = "string" if isinstance(value, str) else "number"
                    cell.value = value
                    cell.display = "" if value is None else str(value)
            except Exception as exc:  # noqa: BLE001 — surface as cell error
                cell.value_type = "error"
                cell.value = f"#ERROR! {exc}"
                cell.display = str(cell.value)
                status = "error"
    wb.calculation_version += 1
    wb.calculation_status = status  # type: ignore[assignment]


def _eval_cell(
    wb: Workbook, ws: Worksheet, row: int, col: int, stack: set[str],
) -> Any:
    key = f"{ws.id}:{cell_key(row, col)}"
    if key in stack:
        raise ValueError("circular reference")
    stack.add(key)
    try:
        cell = ws.get_cell(row, col)
        if cell.input_type == "blank" or cell.input is None:
            return 0
        if cell.input_type == "formula":
            return _eval_formula(wb, ws, str(cell.input), stack)
        if cell.input_type == "number":
            return _as_number(cell.input) if _as_number(cell.input) is not None else cell.input
        return cell.input
    finally:
        stack.discard(key)


def _cell_blank(ws: Worksheet, row: int, col: int) -> bool:
    cell = ws.get_cell(row, col)
    if cell.input_type == "blank" or cell.input is None:
        return True
    if cell.input_type == "string" and str(cell.input).strip() == "":
        return True
    return False


def _resolve_ref(
    wb: Workbook, ws: Worksheet, ref: str, stack: set[str],
) -> Any:
    text = ref.strip()
    m = _XSHEET.match(text)
    if m:
        name = m.group(1) if m.group(1) is not None else m.group(2)
        target = sheet_by_name(wb, name)
        return _eval_cell(wb, target, *parse_a1(m.group(3)), stack)
    return _eval_cell(wb, ws, *parse_a1(text), stack)


def _resolve_ref_coords(
    wb: Workbook, ws: Worksheet, ref: str,
) -> tuple[Worksheet, int, int]:
    text = ref.strip()
    m = _XSHEET.match(text)
    if m:
        name = m.group(1) if m.group(1) is not None else m.group(2)
        target = sheet_by_name(wb, name)
        return target, *parse_a1(m.group(3))
    return ws, *parse_a1(text)


def _split_csv_args(inner: str) -> list[str]:
    """Split IF args on top-level commas (respect quoted strings)."""
    args: list[str] = []
    buf: list[str] = []
    in_str = False
    depth = 0
    for ch in inner:
        if ch == '"' and depth == 0:
            in_str = not in_str
            buf.append(ch)
            continue
        if not in_str:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                args.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    if buf or args:
        args.append("".join(buf).strip())
    return args


def _eval_literal_or_ref(
    wb: Workbook, ws: Worksheet, expr: str, stack: set[str],
) -> Any:
    text = expr.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    if text.upper() in ("TRUE", "FALSE"):
        return text.upper() == "TRUE"
    num = _as_number(text)
    if num is not None and _A1.match(text) is None and "!" not in text:
        return int(num) if float(num).is_integer() else num
    return _resolve_ref(wb, ws, text, stack)


def _eval_condition(
    wb: Workbook, ws: Worksheet, cond: str, stack: set[str],
) -> bool:
    text = cond.strip()
    m = _CMP.match(text)
    if not m:
        # bare truthiness
        val = _eval_literal_or_ref(wb, ws, text, stack)
        if isinstance(val, str):
            return bool(val)
        n = _as_number(val)
        return bool(n) if n is not None else bool(val)

    left_s, op, right_s = m.group(1).strip(), m.group(2), m.group(3).strip()

    # Blank checks against "" use cell emptiness, not numeric 0 coercion.
    if right_s == '""' or left_s == '""':
        ref = left_s if right_s == '""' else right_s
        target, row, col = _resolve_ref_coords(wb, ws, ref)
        blank = _cell_blank(target, row, col)
        if op == "<>":
            return not blank
        if op == "=":
            return blank
        raise ValueError(f"unsupported blank compare op: {op}")

    left = _eval_literal_or_ref(wb, ws, left_s, stack)
    right = _eval_literal_or_ref(wb, ws, right_s, stack)
    ln, rn = _as_number(left), _as_number(right)
    if ln is not None and rn is not None:
        a, b = ln, rn
    else:
        a, b = left, right
    if op == "=":
        return a == b
    if op == "<>":
        return a != b
    if op == "<":
        return a < b  # type: ignore[operator]
    if op == ">":
        return a > b  # type: ignore[operator]
    if op == "<=":
        return a <= b  # type: ignore[operator]
    if op == ">=":
        return a >= b  # type: ignore[operator]
    raise ValueError(f"bad compare op: {op}")


def _eval_formula(
    wb: Workbook, ws: Worksheet, formula: str, stack: set[str],
) -> Any:
    text = formula.strip()
    # Reject volatiles / network-ish names early.
    upper = text.upper()
    for banned in ("NOW(", "TODAY(", "RAND(", "RANDBETWEEN(", "WEBSERVICE(", "IMPORT"):
        if banned in upper:
            raise ValueError(f"unsupported volatile/external function: {banned}")

    m = _IF.match(text)
    if m:
        parts = _split_csv_args(m.group(1))
        if len(parts) != 3:
            raise ValueError("IF requires exactly 3 arguments")
        if _eval_condition(wb, ws, parts[0], stack):
            return _eval_literal_or_ref(wb, ws, parts[1], stack)
        return _eval_literal_or_ref(wb, ws, parts[2], stack)

    m = _SUM.match(text)
    if m:
        r1, c1 = int(m.group(2)) - 1, col_letters_to_index(m.group(1))
        r2, c2 = int(m.group(4)) - 1, col_letters_to_index(m.group(3))
        total = 0.0
        for r in range(min(r1, r2), max(r1, r2) + 1):
            for c in range(min(c1, c2), max(c1, c2) + 1):
                if r in ws.hidden_rows or c in ws.hidden_columns:
                    # Hidden cells still contribute (matches Excel SUM default).
                    pass
                v = _eval_cell(wb, ws, r, c, stack)
                n = _as_number(v)
                if n is not None:
                    total += n
        return int(total) if total == int(total) else total

    m = _BIN.match(text)
    if m:
        left = _resolve_ref(wb, ws, m.group(1), stack)
        right = _resolve_ref(wb, ws, m.group(3), stack)
        a, b = _as_number(left), _as_number(right)
        if a is None or b is None:
            raise ValueError("non-numeric operand")
        op = m.group(2)
        if op == "+":
            out = a + b
        elif op == "-":
            out = a - b
        elif op == "*":
            out = a * b
        elif op == "/":
            if b == 0:
                raise ValueError("division by zero")
            out = a / b
        else:
            raise ValueError("bad operator")
        return int(out) if out == int(out) else out

    # Bare reference: =A1 or =Sheet!A1
    if text.startswith("="):
        ref = text[1:].strip()
        if _A1.match(ref) or _XSHEET.match(ref):
            return _resolve_ref(wb, ws, ref, stack)

    raise ValueError(f"unsupported formula: {formula}")
