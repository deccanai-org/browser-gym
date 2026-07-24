# Sheets calculation worker (deferred)

Per `PHASE_E_SHEETS_SPEC.md` Gate 0 / Phase 1, the production calculation
engine is a **pinned Apache-2.0 Univer OSS** headless Node worker with:

- local-only assets (no CDN / telemetry / Pro packages)
- strict JSON request/response protocol
- network disabled, memory/CPU/time limits
- browser ↔ headless golden parity for the documented formula allowlist

**Scaffold status:** Python in-process stub in `recalculate_workbook`
(`server/apps/sheets/calc/__init__.py` exports via mutations importing the
module). Drop a Node worker here (e.g. `worker.mjs` + `package.json` with
exact pinned `@univerjs/*` versions + SBOM) when Gate 0 is approved.

Until then, `/sheets/api/recalculate` and post-command recalculation use the
Python stub only.

**Exploratory slice (2026-07-20, Option 1):** stub also evaluates cross-sheet
`Sheet!A1` / `'Name'!A1` and narrow `IF` (blank/string compares) so S2/S3
fixtures can prove mechanisms without Univer. See design note §6.
