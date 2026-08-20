"""Ambient (browse-only) calendar events so Xoogle isn't a near-empty week.

Appended in transform_calendar; the gym engine never sees them (verifiers read
p.world.calendar.events, filtered by source=='user'). All ids are amb_cal_*,
source='seed', deterministic. Events never land on the two frozen gym-gate days
(TODAY / TOMORROW) and timed events avoid the 17:00-21:00 evening band, so no
scheduling / evening-free / double-book premise is disturbed. Data lives in
tools/ambient_bulk.json next to the other ambient content.
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import pathlib as _pathlib

from server.apps.calendar.state import TODAY

_BULK = _json.loads((_pathlib.Path(__file__).with_name("ambient_bulk.json")).read_text())
_BASE = _dt.date.fromisoformat(TODAY)

# calendar display-name -> (calendarId in _CAL_DEFAULTS, colour)
_CAL_ID = {
    "Personal": ("c1", "#039BE5"), "Work": ("c2", "#33B679"),
    "Family": ("c3", "#8E24AA"), "Holidays": ("c4", "#F4511E"),
    "Birthdays": ("c5", "#E67C73"),
}


def build_calendar() -> list:
    out = []
    for i, e in enumerate(_BULK.get("calendar", [])):
        off = e.get("day_offset")
        if off in (0, 1) or off is None:      # never touch the frozen gym-gate days
            continue
        cid, color = _CAL_ID.get(e.get("calendar"), ("c1", "#039BE5"))
        day = (_BASE + _dt.timedelta(days=int(off))).isoformat()
        all_day = bool(e.get("all_day"))
        start = (e.get("start_hhmm") or "09:00") if not all_day else "00:00"
        end = (e.get("end_hhmm") or "10:00") if not all_day else "23:59"
        out.append({
            "id": f"amb_cal_{i}", "calendarId": cid, "title": e.get("title") or "(No Title)",
            "start": f"{day}T{start}:00", "end": f"{day}T{end}:00",
            "allDay": all_day, "location": "", "description": "",
            "color": color, "recurring": "none", "reminderMinutes": 10,
            "source": "seed",
        })
    return out
