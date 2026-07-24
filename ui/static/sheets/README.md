# Sheets static assets (deferred)

Per `PHASE_E_SHEETS_SPEC.md`:

- Serve all JS/CSS/fonts/workers **locally** under `/static/sheets`
- Pin exact Apache-2.0 `@univerjs/*` OSS packages (no Pro, no CDN, no telemetry)
- Fingerprint bundles; keep SBOM + NOTICE

**Scaffold status:** directory reserved. The workbook shell at
`ui/pages/sheets/workbook.html` mounts `#univer-root` and currently renders a
server-side HTML grid with stable `data-test-id` selectors. Drop the pinned
Univer build here after Gate 0 approval, then wire the shell to hydrate from
`GET /sheets/api/workbook` and commit via `POST /sheets/api/commands`.
