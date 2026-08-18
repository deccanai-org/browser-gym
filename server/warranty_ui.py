"""Shared warranty status helpers for ShopGym order / return pages.

Infers a limited-warranty window from product copy (e.g. "12 months from
purchase date" or "90-day replace policy") plus the order's placed_at,
compared to the gym clock.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any


_MONTHS_RE = re.compile(r"(\d+)\s*[- ]?\s*months?\b", re.I)
_DAYS_RE = re.compile(r"(\d+)\s*[- ]?\s*days?\b", re.I)
_WARRANTY_RE = re.compile(r"warranty|replace\s+polic", re.I)


def _parse_day(raw: str | None) -> date | None:
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if "T" in s or s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # Clamp day for shorter months.
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    return date(y, m, 1)


def warranty_summary(
    product: Any,
    placed_at: str | None,
    gym_today: str,
) -> dict[str, Any] | None:
    """Return a display dict or None when no warranty window can be inferred."""
    if product is None:
        return None
    text = " ".join(
        str(x)
        for x in (
            getattr(product, "short_description", None),
            getattr(product, "long_description", None),
            getattr(product, "name", None),
        )
        if x
    )
    if not _WARRANTY_RE.search(text):
        return None
    purchased = _parse_day(placed_at)
    today = _parse_day(gym_today)
    if purchased is None or today is None:
        return None

    # Prefer an explicit day window ("90-day") when present; else months.
    dm = _DAYS_RE.search(text)
    mm = _MONTHS_RE.search(text)
    months: int | None = None
    days: int | None = None
    if dm:
        days = int(dm.group(1))
        if days <= 0 or days > 3660:
            return None
        ends = purchased + timedelta(days=days)
        window_label = f"{days}-day"
    elif mm:
        months = int(mm.group(1))
        if months <= 0 or months > 120:
            return None
        ends = _add_months(purchased, months)
        window_label = f"{months}-month"
    else:
        return None

    expired = today >= ends
    purchase_label = f"{purchased.strftime('%B')} {purchased.day}, {purchased.year}"
    ends_label = f"{ends.strftime('%B')} {ends.day}, {ends.year}"
    return {
        "months": months,
        "days": days,
        "window_label": window_label,
        "purchase_label": purchase_label,
        "ends_label": ends_label,
        "expired": expired,
        "status_label": (
            f"Warranty expired (ended {ends_label})"
            if expired
            else f"Warranty active until {ends_label}"
        ),
        "product_name": getattr(product, "name", "") or "",
        "product_id": getattr(product, "id", "") or "",
    }


def warranties_for_order(order: Any, products: dict, gym_today: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in getattr(order, "items", []) or []:
        p = products.get(it.product_id)
        info = warranty_summary(p, getattr(order, "placed_at", None), gym_today)
        if info:
            out.append(info)
    return out
