# Deployment handoff — Browser-Gym platform

For whoever hosts this (Ganesh / DevOps). Cloud-agnostic — works for AWS + a
Jenkins pipeline, or any container host. Read **Shared secrets** first: most
deploy failures are one missing secret, or two services that don't agree on one.

## Two repos, 4 deployable units + a database

| # | Service | Repo · path | Port | Ships as | What it is |
|---|---|---|---|---|---|
| 1 | **gym** | this repo · `Dockerfile` | 8000 | Docker image | the ecommerce world; serves `/_harness/*`. seed.db baked in, `SEEDDB_MODE=1` |
| 2 | **live-browser** | this repo · `live_browser/Dockerfile` | 8877 | Docker image | real Chromium (CDP screencast + input) for the live pane |
| 3 | **backend** | annotator · `backend/Dockerfile` | 8090 | Docker image | FastAPI + Alembic; talks to Postgres, the gym, and the live-browser |
| 4 | **frontend** | annotator · `frontend/` | — | **static build** (`make build`) | React SPA → `dist/` for S3/CloudFront (not dockerized) |
| 5 | **postgres** | — | 5432 | managed DB | the backend's own DB (sessions, versions, verifiers) |

Deploy order: **gym + live-browser first**, capture their URLs, then the backend
(pointed at them), then the frontend (built with the live-browser URL).

## Build & run

```bash
# gym  (build context = repo root; seed.db is baked by the build, not copied)
docker build -t browser-gym .
docker run -p 8000:8000 -e HARNESS_TOKEN=$TOKEN browser-gym

# live-browser  (MUST build from repo root, -f the subdir Dockerfile)
docker build -t live-browser -f live_browser/Dockerfile .
docker run -p 8877:8877 -e LIVE_STREAM_SECRET=$SECRET -e LIVE_ALLOWED_ORIGINS=$FRONTEND_ORIGIN live-browser

# backend  (annotator repo)
docker build -t annotator-backend backend/
# frontend  (annotator repo — static, no Docker)
cd frontend && make build VITE_LIVE_BASE=$LIVE_BROWSER_PUBLIC_URL   # → dist/
```

Per-service env is documented in each repo's `.env.example`
(`./.env.example`, `./live_browser/.env.example`, annotator `./.env.example`).
Those files are the authoritative variable lists; this doc covers only what
must be coordinated *across* services.

## Shared secrets — these MUST agree across services

Generate each once with `openssl rand -hex 32`, store in the secret manager.

| Secret | Set on | Must equal | If wrong/unset |
|---|---|---|---|
| `AUTH_SECRET` | backend | — (any strong random) | **prod backend refuses to boot** |
| `HARNESS_TOKEN` (gym) ↔ `GYM_HARNESS_TOKEN` (backend) | gym + backend | **each other** | gym boots healthy but 503s every `/_harness/*` → the 312-task gym review is dead |
| `LIVE_STREAM_SECRET` | live-browser + backend | **each other** | live pane connects then closes 4401 |
| `DB_PASS` | Postgres + backend `DATABASE_URL` | itself | backend can't reach the DB |

> **Trap:** if `LIVE_STREAM_SECRET` is unset it falls back to `HARNESS_TOKEN`, then
> to a hardcoded `dev-live-secret` (a **known** key). Setting only the gym token
> leaves live-browser on the insecure default. Set `LIVE_STREAM_SECRET`
> explicitly on both the backend and live-browser.

## Connection URLs

| Var | Set on | Value |
|---|---|---|
| `GYM_URL` | backend | the gym service URL |
| `LIVE_BROWSER_URL` | backend | the live-browser service URL (used server-side) |
| `VITE_LIVE_BASE` | frontend **build arg** | the live-browser's **public** URL (browser connects here) |
| `LIVE_ALLOWED_ORIGINS` | live-browser | the frontend's public origin(s), comma-separated |

## Per-service must-knows

- **gym** — needs a **writable filesystem** at `/app/screenshots` and
  `/app/trajectories` (mount a volume if the platform's root FS is read-only, e.g.
  Fargate/Cloud Run). Give it **≥2 GiB / 2 vCPU** (headless Chromium). LLM agent
  runs need `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in env; `agent=oracle` is keyless.
- **live-browser** — **run single-instance** (sessions + browsers live in process
  memory; a request routed to another replica 404s). ≥2 GiB / 2 vCPU, and raise the
  platform's request/idle timeout (WS sessions cap at 60 min).
- **backend** — prod must run with `AUTO_CREATE_ALL=false` **and** `RUN_MIGRATIONS=1`
  (the entrypoint runs `alembic upgrade head`). Set `CORS_ORIGINS=[]` — the browser
  only calls `/api` same-origin.
- **frontend** — static `dist/`. Whatever serves it (CloudFront) must route
  **`/api/*` to the backend origin** so the browser sees one origin; the session
  cookie is `SameSite=Lax`, host-only. Do **not** split frontend/backend across
  different public domains without switching the cookie to `SameSite=None; Secure`.
- **workspace isolation** (per-annotator gym container) is **single-host only** — it
  needs the Docker socket, so it can't run on Fargate/Cloud Run. Leave
  `WORKSPACE_ISOLATION=false`; the annotator then shares the one `GYM_URL`.

## Security note

`.env` is gitignored and was never committed, and `.dockerignore` keeps it out of
image build contexts — so git and images are clean. But a **raw folder/zip copy**
of a working tree may carry a local `.env` with live API keys. Provision from these
`.env.example` files + the secret manager; don't ship anyone's `.env`.

## Branches to deploy from

- gym: **`feat/sql-seed-db`**
- annotator: **`fix/dataset-integrity`**

`main` is stale on both and gives an older, different system. Deploy these until
they merge.
