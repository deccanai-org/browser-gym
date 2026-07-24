"""Sheets app — deterministic self-hosted spreadsheet at ``/sheets``.

Follows ``PHASE_E_SHEETS_SPEC.md``: typed workbook model, revisioned command
protocol, and harness-safe routes. The authoritative calculation engine is
intended to be pinned Apache-2.0 Univer OSS (browser + headless worker).

Scaffolding note: this package lands the Python state/routes/UI shell and a
minimal in-process recalculator so episodes reset and APIs work. Vendored
Univer JS/CSS assets and the Node headless worker under ``calc/`` are deferred
(see ``calc/README.md`` and ``ui/static/sheets/README.md``) per the spec's
phased Gate 0 → Phase 1 → Phase 2 plan.
"""
