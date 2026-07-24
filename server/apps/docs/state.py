"""Docs app store — DocsState + Document.

Wholly separate from the other apps. Fixed timestamps so a reset for a given
seed reproduces an identical document list (the environment-correctness gate
requires deterministic episodes).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEED_DATE = "2026-05-21"


@dataclass
class Document:
    id: str
    title: str
    body: str
    folder: str = "docs"              # docs | trash
    updated_at: str = f"{SEED_DATE}T09:00:00"
    updated_label: str = "9:00 AM"
    starred: bool = False


@dataclass
class DocsState:
    documents: dict[str, Document] = field(default_factory=dict)
    account_name: str = "Alice Anderson"
    _next: int = 1

    def new_id(self) -> str:
        did = f"doc_{self._next}"
        self._next += 1
        return did

    def get(self, doc_id: str) -> Document | None:
        return self.documents.get(doc_id)

    def ordered(self, *, folder: str = "docs") -> list[Document]:
        rows = [d for d in self.documents.values() if d.folder == folder]
        return sorted(rows, key=lambda d: d.updated_at, reverse=True)

    def to_json(self) -> dict[str, Any]:
        return {
            "account_name": self.account_name,
            "documents": {k: asdict(v) for k, v in self.documents.items()},
        }


def make_docsstate(seed: int = 0) -> DocsState:
    """Default document list so /docs is non-empty in any episode.

    Cross-app tasks may replace or extend these fixtures in their factories.
    Seed currently only varies a decoy title so resets remain deterministic
    per seed without changing the core shape.
    """
    d = DocsState()
    decoy = "Weekend shopping notes" if seed % 2 == 0 else "Weekend errands draft"
    seeds = [
        (
            "Workspace welcome",
            (
                "Welcome to ShopGym Docs.\n\n"
                "Use this app for notes and instructions that other apps "
                "may reference in multi-app tasks."
            ),
            f"{SEED_DATE}T08:00:00",
            "8:00 AM",
            False,
        ),
        (
            "Authoritative meeting brief",
            (
                "Team sync brief (canonical):\n"
                "- Prefer calendar confirmation over informal chat notes.\n"
                "- Do not treat drafts in Trash as current policy."
            ),
            f"{SEED_DATE}T09:15:00",
            "9:15 AM",
            True,
        ),
        (
            decoy,
            "Scratch list — not authoritative for ordering decisions.",
            f"{SEED_DATE}T10:00:00",
            "10:00 AM",
            False,
        ),
    ]
    for title, body, updated_at, label, starred in seeds:
        did = d.new_id()
        d.documents[did] = Document(
            id=did, title=title, body=body, folder="docs",
            updated_at=updated_at, updated_label=label, starred=starred,
        )
    return d
