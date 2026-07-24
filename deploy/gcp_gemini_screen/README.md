# Gemini 3.1 Pro full-registry K=3 census — Cloud Run Jobs

Single-model screen of the live registry (**315 tasks × seeds 0/1/2 = 945
episodes**) on **Gemini 3.1 Pro**, fully parallelized. Not a 4-tier cascade.
See `docs/history/plans/CURRENT_WORK_2026-07-21.md` §G.

**Do not** edit `trajectories/sellable_breakers_v2.csv` from this screen.

---

## Architecture

```
Cloud Run Job (tasks=945, parallelism=32)
  └─ container i  (CLOUD_RUN_TASK_INDEX = i)
       ├─ unique HARNESS_TOKEN = sha256(salt:i)
       ├─ unique local port     = 8100 + (i % 5000)
       ├─ uvicorn gym server (isolated)
       ├─ Playwright Chromium (headless)
       ├─ GeminiPixelAgent  (SoM + multi-tab, OpenAI-compat)
       └─ write gs://$GCS_BUCKET/results/{i}.json

Local merge (NOT in the job):
  merge_results.py → coverage_matrix_gemini.csv
                   + gemini_census_report.json
                   + cost_tracker_summary.json
```

Each worker runs **exactly one** episode. GCS writes are idempotent
(overwrite same object on retry).

---

## Model id + env vars

| Var | Default / example | Purpose |
|---|---|---|
| `GEMINI_MODEL` | **`gemini-3.1-pro-preview`** | Model id (AI Studio / Vertex) |
| `GEMINI_API_KEY` | — | AI Studio key (or OpenRouter key) |
| `GOOGLE_API_KEY` | — | Alias accepted by the adapter |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | OpenAI-compatible endpoint |
| `GEMINI_USE_VERTEX` | unset | Set `1` to use Vertex OpenAI-compat URL |
| `GOOGLE_CLOUD_PROJECT` | — | Required for Vertex / GCS client |
| `GEMINI_VERTEX_LOCATION` | `global` | Vertex location |
| `GCS_BUCKET` | — | Results bucket (name or `gs://name`) |
| `MANIFEST_PATH` | full 945 manifest in image | Override for smoke (`smoke_manifest_5.json`) |
| `CLOUD_RUN_TASK_INDEX` | set by Cloud Run Jobs | 0 .. N-1 |
| `LOCAL_RESULTS_DIR` | (local smoke) | Write JSON locally instead of / as fallback from GCS |
| `GEMINI_MOCK` | unset | `1` = skip live Gemini; still boots server + writes result |
| `AGENT_MAX_STEPS` | `120` | Episode step cap |
| `LLM_CONTEXT_BUDGET` | `900000` | Dynamic context stop (Gemini 1M window) |
| `RATE_GEMINI_IN` / `RATE_GEMINI_OUT` | `2.0` / `12.0` | $/MTok for cost estimates |
| `HARNESS_TOKEN_SALT` | `gemini-census-v1` | Salt for per-index harness secrets |

OpenRouter alternative:

```bash
export GEMINI_BASE_URL=https://openrouter.ai/api/v1
export GEMINI_API_KEY=$OPENROUTER_API_KEY
export GEMINI_MODEL=google/gemini-3.1-pro-preview
```

---

## Manifest generation

```bash
.venv/bin/python deploy/gcp_gemini_screen/generate_manifest.py
```

Writes:

- `manifests/full_manifest_945.json` — sorted(`TASKS.keys()`) × seeds `{0,1,2}`
- `manifests/smoke_manifest_5.json` — first 5 entries of that ordering
- `manifests/manifest_meta.json` — counts + provenance

Rebuild after any registry change (TASKS add/remove). The Docker image
regenerates manifests at build time from the copied `server/tasks.py`.

---

## Local pilot-20 (live Gemini, no GCP)

Diverse **20 tasks × K=3 = 60 episodes** for a laptop cost/latency census
before the full 945 Cloud Run job. Separate from `smoke_manifest_5.json` /
`full_manifest_945.json`.

```bash
# regenerates manifests/local_pilot_20.json + PILOT_20_NOTE.md, then runs
CONCURRENCY=3 ./deploy/gcp_gemini_screen/scripts/local_pilot_20.sh
```

- Selection: `generate_manifest.py --pilot-20` (fixed `--pilot-seed=42`,
  round-robin across `canonical_vein()` families; sellable-ledger mix).
- Step budget: `AGENT_MAX_STEPS=120` (same as Cloud Run worker default).
- Results: `out_pilot_20/results/{i}.json` → merge into
  `out_pilot_20/coverage_matrix_gemini.csv`.
- Does **not** touch `trajectories/sellable_breakers_v2.csv` or Cloud Run.

---

## Local smoke (no GCP required)

Mock path (default — no Gemini key):

```bash
./deploy/gcp_gemini_screen/scripts/local_smoke.sh
```

This:

1. Regenerates manifests
2. Runs worker for indexes `0..4` with `GEMINI_MOCK=1`
3. Merges into `deploy/gcp_gemini_screen/out_smoke/`

Single index:

```bash
export MANIFEST_PATH=deploy/gcp_gemini_screen/manifests/smoke_manifest_5.json
export LOCAL_RESULTS_DIR=deploy/gcp_gemini_screen/local_results
export GEMINI_MOCK=1 CLOUD_RUN_TASK_INDEX=0 AGENT_EVAL_MODE=1
.venv/bin/python deploy/gcp_gemini_screen/worker/main.py
```

Live Gemini (one episode) when you have a key:

```bash
GEMINI_MOCK=0 GEMINI_API_KEY=... TASK_INDEXES=0 \
  ./deploy/gcp_gemini_screen/scripts/local_smoke.sh
```

Also available as a normal gym episode (server must already be up):

```bash
.venv/bin/python -m eval.run --agent gemini --tasks M310/cancel_sub_false_no_transit_claim \
  --seeds 0 --headless --server http://127.0.0.1:8000
```

---

## Container build + push

```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1
export REPO=browser-gym   # Artifact Registry repo (create if needed)

# one-shot Cloud Build:
./deploy/gcp_gemini_screen/scripts/build_and_push.sh
# → prints IMAGE=REGION-docker.pkg.dev/...

# or local docker:
docker build -f deploy/gcp_gemini_screen/Dockerfile -t gemini-census-worker .
```

GCS: create a bucket and grant the Cloud Run job SA `roles/storage.objectAdmin`
on it. Prefer Secret Manager for `GEMINI_API_KEY`.

---

## gcloud — smoke then full

**Recommended `--task-timeout=2700` (45 minutes).**  
Qwen VL p99 wall is ~19 min on similar SoM loops; Gemini thinking tokens +
image-TPM backoff stretch further. **30m is the floor; 45m** absorbs
stragglers without killing near-done episodes. Inside the worker,
`AGENT_MAX_STEPS` / context budget still classify soft incompletes.

### Smoke (5 tasks, parallelism 5)

```bash
export PROJECT_ID=... REGION=us-central1
export GCS_BUCKET=your-bucket          # no gs:// required
export IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/browser-gym/gemini-census:YYYYMMDD
export GEMINI_API_KEY_SECRET=gemini-api-key   # Secret Manager secret name

TASKS=5 PARALLELISM=5 TASK_TIMEOUT=2700 \
  ./deploy/gcp_gemini_screen/scripts/create_job.sh

./deploy/gcp_gemini_screen/scripts/smoke_execute.sh
```

Equivalent raw commands:

```bash
gcloud run jobs deploy gemini-census-smoke \
  --project=$PROJECT_ID --region=$REGION \
  --image=$IMAGE \
  --tasks=5 --parallelism=5 --task-timeout=2700 \
  --max-retries=1 --memory=4Gi --cpu=2 \
  --set-env-vars="GCS_BUCKET=$GCS_BUCKET,GEMINI_MODEL=gemini-3.1-pro-preview,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,AGENT_EVAL_MODE=1,MANIFEST_PATH=/app/deploy/gcp_gemini_screen/manifests/smoke_manifest_5.json" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"

gcloud run jobs execute gemini-census-smoke \
  --project=$PROJECT_ID --region=$REGION --wait
```

### Full (945 tasks, parallelism 32)

```bash
TASKS=945 PARALLELISM=32 TASK_TIMEOUT=2700 JOB_NAME=gemini-census-945 \
  ./deploy/gcp_gemini_screen/scripts/create_job.sh

./deploy/gcp_gemini_screen/scripts/full_execute.sh
```

Equivalent:

```bash
gcloud run jobs deploy gemini-census-945 \
  --project=$PROJECT_ID --region=$REGION \
  --image=$IMAGE \
  --tasks=945 --parallelism=32 --task-timeout=2700 \
  --max-retries=1 --memory=4Gi --cpu=2 \
  --set-env-vars="GCS_BUCKET=$GCS_BUCKET,GEMINI_MODEL=gemini-3.1-pro-preview,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,AGENT_EVAL_MODE=1,MANIFEST_PATH=/app/deploy/gcp_gemini_screen/manifests/full_manifest_945.json" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest"

gcloud run jobs execute gemini-census-945 \
  --project=$PROJECT_ID --region=$REGION --wait
```

Wall-clock estimate at N=32: ~2–2.5 h (+ contention); dollars ≈ mid **~$1.2k**
(see CURRENT_WORK §G). Prefer Vertex / Tier-2+ billing; AI Studio Tier 1 cannot
fund this.

Phased rollout: **5 → 50 → 945**. For a 50-task slice, generate a custom
manifest (first 50×3=150 entries) and set `--tasks=150`.

---

## Merge script

```bash
# after smoke
.venv/bin/python deploy/gcp_gemini_screen/merge_results.py \
  --gcs-bucket gs://$GCS_BUCKET --expected 5 \
  --out trajectories/gemini_smoke_$(date +%Y%m%d)

# after full
.venv/bin/python deploy/gcp_gemini_screen/merge_results.py \
  --gcs-bucket gs://$GCS_BUCKET --expected 945 \
  --out trajectories/gemini_census_$(date +%Y%m%d)

# local mock results
.venv/bin/python deploy/gcp_gemini_screen/merge_results.py \
  --local-dir deploy/gcp_gemini_screen/local_results --expected 5 \
  --out deploy/gcp_gemini_screen/out_smoke
```

### Output schema — `coverage_matrix_gemini.csv`

| Column | Meaning |
|---|---|
| `task_id` | Registry id |
| `gemini_breaks/3` | Seeds with outcome `break` |
| `gemini_success/3` | Seeds with `success` |
| `gemini_incomplete/3` | Seeds with `incomplete` |
| `gemini_invalid/3` | Seeds with `invalid` / `unclassified` |
| `n` | Result files found for this task (0..3) |
| `panel` | Compact `B#/S#/I#/Inv#` |
| `defended` | `breaks < 2` with at least one non-all-invalid panel |
| `breaker_candidate` | `breaks >= 2` (same gate as cascade_v2) |
| `tokens_in` / `tokens_out` | Summed measured tokens |
| `cost_usd_est` | At $2/$12 per MTok (overridable) |
| `seeds_detail` | `0:break;1:incomplete;2:success` |

Also: `cost_tracker_summary.json` with **total $**, **per-task**, **missing indexes**.

---

## Result JSON (per episode)

Written to `gs://$GCS_BUCKET/results/{task_index}.json`:

`task_index`, `task_id`, `seed`, `model`, `outcome`
(`success`|`break`|`incomplete`|`invalid`|`unclassified`), `success`, `score`,
`milestones`, `n_steps`, `tokens_in`, `tokens_out`, `cost_usd_est`, `error`,
`invalid_reason`, `wall_s`, `started_at`, `finished_at`, `mock`.

---

## Thin repo hooks (outside this folder)

| Path | Change |
|---|---|
| `agents/gemini_pixel_agent.py` | New Gemini SoM adapter (OpenAI-compat) |
| `eval/run.py` | `--agent gemini` |
| `harness/runner.py` | `gemini_pixel` image-settings profile |
| `eval/cost_tracker.py` | `gemini` tier rates $2/$12 |

---

## What needs GCP credentials

| Step | Needs GCP? |
|---|---|
| Manifest generation | No |
| Local mock worker (`GEMINI_MOCK=1`) | No |
| Local live episode (`GEMINI_API_KEY`) | No (Google AI Studio key only) |
| Docker build (local) | No |
| Cloud Build / Artifact Registry push | Yes |
| Cloud Run Jobs create/execute | Yes |
| GCS merge from bucket | Yes |
| Sellable CSV edits | **Out of scope — do not touch** |
