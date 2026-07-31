"""Calendar app routes — the ``/calendar`` route family.

Same injected-deps pattern as Mail/Food (no circular import).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from server.apps.calendar import mutations as C
from server.apps.calendar.state import TODAY, TOMORROW

router = APIRouter(prefix="/calendar", tags=["calendar"])

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(templates=templates, get_world=get_world,
                 build_ctx=build_ctx, flash=flash)


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="calendar", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def agenda(request: Request):
    world = _deps["get_world"]()
    # Log the agenda view so verifiers can confirm (state-based, robust to where the
    # agent ends up) that the agent actually checked the calendar — mirrors the shop's
    # view_orders log.
    from server.state import log_action
    log_action(world.shop, "viewed_calendar")
    cal = world.calendar
    # Group events by day_label, in day/time order.
    days: dict[str, list] = {}
    for e in cal.ordered():
        days.setdefault(e.day_label, []).append(e)
    return _render(request, "calendar/agenda.html", calendar=cal, days=days)


@router.get("/new", response_class=HTMLResponse)
async def new_event(request: Request, day: str = "", title: str = ""):
    cal = _deps["get_world"]().calendar
    return _render(request, "calendar/new_event.html", calendar=cal,
                   day_prefill=day, title_prefill=title,
                   today=TODAY, tomorrow=TOMORROW)


@router.post("/create")
async def create(
    request: Request,
    title: str = Form(""),
    day: str = Form(""),
    start: str = Form("19:00"),
    end: str = Form("20:00"),
):
    world = _deps["get_world"]()
    day_label = ("Tomorrow (Fri May 22)" if day == TOMORROW
                 else ("Today (Thu May 21)" if day == TODAY else day))
    r = C.create_event(world.calendar, title=title, day=day,
                       start=start, end=end, day_label=day_label)
    if r.get("ok"):
        _deps["flash"](world.shop, "success",
                       f"Added '{r['title']}' to your calendar.")
        return RedirectResponse("/calendar", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not add event."))
    return RedirectResponse("/calendar/new", 303)


@router.get("/edit/{event_id}", response_class=HTMLResponse)
async def edit_event(request: Request, event_id: str):
    from server.state import log_action
    world = _deps["get_world"]()
    cal = world.calendar
    event = cal.events.get(event_id)
    # Log the view so a verifier can distinguish a genuine inert-decoy break
    # (opened edit, saved, day unchanged) from a do-nothing (M69 inert-edit-day).
    log_action(world.shop, "viewed_event_edit", event_id=event_id)
    return _render(request, "calendar/edit_event.html", calendar=cal,
                   event=event, today=TODAY, tomorrow=TOMORROW)


@router.post("/update")
async def update(
    request: Request,
    event_id: str = Form(""),
    title: str = Form(""),
    start: str = Form(""),
    end: str = Form(""),
    day: str = Form(""),
):
    world = _deps["get_world"]()
    r = C.update_event(world.calendar, event_id, start=start, end=end,
                       title=title, day=day)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Updated your calendar event.")
        return RedirectResponse("/calendar", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not update."))
    return RedirectResponse(f"/calendar/edit/{event_id}", 303)


@router.post("/delete")
async def delete(request: Request, event_id: str = Form("")):
    world = _deps["get_world"]()
    r = C.delete_event(world.calendar, event_id)
    if r.get("ok"):
        _deps["flash"](world.shop, "success",
                       f"Removed '{r['title']}' from your calendar.")
    else:
        _deps["flash"](world.shop, "error",
                       r.get("error", "Could not remove event."))
    return RedirectResponse("/calendar", 303)
