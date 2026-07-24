"""Docs app routes — the ``/docs`` route family.

Same injected-deps pattern as Mail/Calendar (no circular import).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from server.apps.docs import mutations as D

router = APIRouter(prefix="/docs", tags=["docs"])

_deps: dict[str, Any] = {}


def configure(*, templates, get_world, build_ctx, flash) -> None:
    _deps.update(
        templates=templates, get_world=get_world,
        build_ctx=build_ctx, flash=flash,
    )


def _render(request: Request, name: str, **extra):
    ctx = _deps["build_ctx"](request, active_app="docs", **extra)
    return _deps["templates"].TemplateResponse(request, name, ctx)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def document_list(request: Request, folder: str = "docs"):
    docs = _deps["get_world"]().docs
    folder = "trash" if folder == "trash" else "docs"
    rows = docs.ordered(folder=folder)
    return _render(
        request, "docs/list.html",
        docs=docs, documents=rows, folder=folder,
    )


@router.get("/new", response_class=HTMLResponse)
async def new_document(request: Request):
    docs = _deps["get_world"]().docs
    return _render(request, "docs/new.html", docs=docs)


@router.post("/create")
async def create(
    request: Request,
    title: str = Form(""),
    body: str = Form(""),
):
    world = _deps["get_world"]()
    r = D.create_document(world.docs, title=title, body=body)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", f"Created '{r['title']}'.")
        return RedirectResponse(f"/docs/{r['doc_id']}", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not create."))
    return RedirectResponse("/docs/new", 303)


@router.get("/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: str):
    world = _deps["get_world"]()
    docs = world.docs
    doc = docs.get(doc_id)
    if doc is None:
        _deps["flash"](world.shop, "error", "That document could not be found.")
        return RedirectResponse("/docs", 303)
    return _render(request, "docs/view.html", docs=docs, doc=doc)


@router.get("/{doc_id}/edit", response_class=HTMLResponse)
async def edit_document(request: Request, doc_id: str):
    world = _deps["get_world"]()
    docs = world.docs
    doc = docs.get(doc_id)
    if doc is None:
        _deps["flash"](world.shop, "error", "That document could not be found.")
        return RedirectResponse("/docs", 303)
    return _render(request, "docs/edit.html", docs=docs, doc=doc)


@router.post("/{doc_id}/update")
async def update(
    request: Request,
    doc_id: str,
    title: str = Form(""),
    body: str = Form(""),
):
    world = _deps["get_world"]()
    r = D.update_document(world.docs, doc_id, title=title, body=body)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", "Document saved.")
        return RedirectResponse(f"/docs/{doc_id}", 303)
    _deps["flash"](world.shop, "error", r.get("error", "Could not save."))
    return RedirectResponse(f"/docs/{doc_id}/edit", 303)


@router.post("/{doc_id}/trash")
async def trash(request: Request, doc_id: str):
    world = _deps["get_world"]()
    r = D.trash_document(world.docs, doc_id)
    if r.get("ok"):
        _deps["flash"](world.shop, "success", f"Moved '{r['title']}' to Trash.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not trash."))
    return RedirectResponse("/docs", 303)


@router.post("/{doc_id}/star")
async def star(request: Request, doc_id: str):
    world = _deps["get_world"]()
    r = D.toggle_star(world.docs, doc_id)
    if r.get("ok"):
        label = "Starred" if r["starred"] else "Unstarred"
        _deps["flash"](world.shop, "success", f"{label} document.")
    else:
        _deps["flash"](world.shop, "error", r.get("error", "Could not update star."))
    return RedirectResponse(f"/docs/{doc_id}", 303)
