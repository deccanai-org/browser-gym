"""Calendar mutations — touch ONLY CalendarState.

Pure: no access to the shop / mail / food stores. The route handler does
any cross-app flash. Keeping these isolated is what makes the per-app
isolation test meaningful.
"""

from __future__ import annotations

from typing import Any

from server.apps.calendar.state import CalendarEvent, CalendarState


def check_availability(cal: CalendarState, day: str, start: str,
                       end: str) -> dict[str, Any]:
    """Free/busy check for a window. The branch condition for gated tasks."""
    return {"ok": True, "free": cal.is_free(day, start, end),
            "day": day, "window": f"{start}-{end}"}


def _details(location: str = "", description: str = "", calendar_id: str = "",
             all_day: Any = None, recurring: str = "",
             reminder_minutes: Any = None) -> dict[str, Any]:
    """Normalise the optional detail fields the event form collects.

    They arrive as form strings, so coerce here rather than in each caller.
    There is deliberately no guests handling — see CalendarEvent.
    """
    out: dict[str, Any] = {}
    if location:    out["location"] = location.strip()
    if description: out["description"] = description.strip()
    if calendar_id: out["calendar_id"] = calendar_id.strip()
    if recurring:   out["recurring"] = recurring.strip().lower()
    if all_day is not None and all_day != "":
        out["all_day"] = str(all_day).strip().lower() in ("1", "true", "yes", "on")
    if reminder_minutes not in (None, ""):
        try:
            out["reminder_minutes"] = int(reminder_minutes)
        except (TypeError, ValueError):
            pass
    return out


def create_event(cal: CalendarState, *, title: str, day: str,
                 start: str, end: str, day_label: str = "",
                 location: str = "", description: str = "", calendar_id: str = "",
                 all_day: Any = None, recurring: str = "",
                 reminder_minutes: Any = None) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "a title is required"}
    if not day:
        return {"ok": False, "error": "a day is required"}
    s = start or "00:00"
    e = end or "00:00"
    # Reject a booking that OVERLAPS an event already on the calendar — you
    # cannot double-book a slot that's taken. The error names the conflicting
    # event + its window so the agent can read it and pick a free time (the
    # error-recovery path). Half-open overlap, so back-to-back (e.g. 16:00-17:00
    # next to 17:00-19:00) is allowed. NOTE: this guards create_event only;
    # update_event (moving an existing event) is intentionally NOT guarded, so
    # the M22 "move Priya to 2 PM, then delete the cancelled Sync" sequence —
    # which briefly overlaps before the delete — still works.
    for ev in cal.events.values():
        if ev.day != day:
            continue
        if s < ev.end and ev.start < e:        # intervals overlap
            return {"ok": False,
                    "error": (f"Slot already booked — that time overlaps "
                              f"'{ev.title}' ({ev.start} to {ev.end}). "
                              f"Pick a time that's free.")}
    eid = cal.new_id()
    cal.events[eid] = CalendarEvent(
        id=eid, title=title, day=day, day_label=day_label or day,
        start=s, end=e, source="user",
        **_details(location, description, calendar_id, all_day, recurring,
                   reminder_minutes),
    )
    return {"ok": True, "event_id": eid, "title": title, "day": day}


def update_event(cal: CalendarState, event_id: str, *, start: str = "",
                 end: str = "", title: str = "", day: str = "",
                 location: str = "", description: str = "", calendar_id: str = "",
                 all_day: Any = None, recurring: str = "",
                 reminder_minutes: Any = None) -> dict[str, Any]:
    """Move/retitle an existing event IN PLACE — the same event keeps its id.
    This is the path an agent takes to push a reminder to a new time WITHOUT
    leaving the old one behind (the M16 'don't over-keep' negative action).

    ``day`` moves it to another date, which is what dragging a chip onto a
    different cell in the month grid means; without it a drag could only ever
    shift the time."""
    e = cal.events.get(event_id)
    if e is None:
        return {"ok": False, "error": "no such event"}
    if start:
        e.start = start
    if end:
        e.end = end
    if day:
        e.day = day
        # day_label is what the agenda groups on, so it has to move too.
        if hasattr(e, "day_label"):
            e.day_label = day
    if title.strip():
        e.title = title.strip()
    for k, v in _details(location, description, calendar_id, all_day, recurring,
                         reminder_minutes).items():
        setattr(e, k, v)
    return {"ok": True, "event_id": event_id, "day": e.day, "start": e.start, "end": e.end}


def delete_event(cal: CalendarState, event_id: str) -> dict[str, Any]:
    """Remove an event entirely. The other way to avoid an over-kept stale
    reminder: delete the old one and create a fresh one at the new time."""
    if event_id not in cal.events:
        return {"ok": False, "error": "no such event"}
    removed = cal.events.pop(event_id)
    return {"ok": True, "event_id": event_id, "title": removed.title}
