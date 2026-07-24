"""Docs mutations — touch ONLY DocsState.

Pure: no access to shop / mail / food / other stores. Route handlers own
any cross-app flash.
"""

from __future__ import annotations

from typing import Any

from server.apps.docs.state import SEED_DATE, Document, DocsState


def create_document(
    docs: DocsState, *, title: str, body: str = "",
) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "a title is required"}
    did = docs.new_id()
    docs.documents[did] = Document(
        id=did, title=title, body=body or "",
        folder="docs",
        updated_at=f"{SEED_DATE}T12:00:00",
        updated_label="now",
        starred=False,
    )
    return {"ok": True, "doc_id": did, "title": title}


def update_document(
    docs: DocsState, doc_id: str, *, title: str = "", body: str | None = None,
) -> dict[str, Any]:
    doc = docs.documents.get(doc_id)
    if doc is None:
        return {"ok": False, "error": "no such document"}
    if title.strip():
        doc.title = title.strip()
    if body is not None:
        doc.body = body
    doc.updated_at = f"{SEED_DATE}T12:00:00"
    doc.updated_label = "now"
    return {"ok": True, "doc_id": doc_id, "title": doc.title}


def trash_document(docs: DocsState, doc_id: str) -> dict[str, Any]:
    doc = docs.documents.get(doc_id)
    if doc is None:
        return {"ok": False, "error": "no such document"}
    doc.folder = "trash"
    doc.updated_at = f"{SEED_DATE}T12:00:00"
    doc.updated_label = "now"
    return {"ok": True, "doc_id": doc_id, "title": doc.title}


def toggle_star(docs: DocsState, doc_id: str) -> dict[str, Any]:
    doc = docs.documents.get(doc_id)
    if doc is None:
        return {"ok": False, "error": "no such document"}
    doc.starred = not doc.starred
    return {"ok": True, "doc_id": doc_id, "starred": doc.starred}
