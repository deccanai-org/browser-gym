#!/usr/bin/env bash
# Create (or update) the Cloud Run Job for the Gemini K=3 full-registry census.
#
# Required env before running:
#   PROJECT_ID, REGION, GCS_BUCKET, IMAGE
# Optional:
#   JOB_NAME (default: gemini-census-945)
#   GEMINI_API_KEY (or use Secret Manager — see README)
#   PARALLELISM (default 32), TASK_TIMEOUT (default 2700s = 45m)
#
# Rationale for --task-timeout=2700 (45m):
#   Qwen VL p99 wall ~19 min on similar SoM episodes; Gemini thinking + image
#   TPM backoff can stretch further. 30m is the floor; 45m absorbs stragglers
#   without silently killing a nearly-done episode. Soft incomplete classification
#   still applies inside the worker via AGENT_MAX_STEPS / context budget.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
GCS_BUCKET="${GCS_BUCKET:?set GCS_BUCKET (bucket name, no gs://)}"
IMAGE="${IMAGE:?set IMAGE (e.g. REGION-docker.pkg.dev/PROJECT/REPO/gemini-census:tag)}"
JOB_NAME="${JOB_NAME:-gemini-census-945}"
PARALLELISM="${PARALLELISM:-32}"
# 45 minutes — see header comment.
TASK_TIMEOUT="${TASK_TIMEOUT:-2700}"
TASKS="${TASKS:-945}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
SA="${SERVICE_ACCOUNT:-}"

GCS_BUCKET="${GCS_BUCKET#gs://}"

if [[ "${TASKS}" == "5" ]]; then
  MANIFEST_PATH="${MANIFEST_PATH:-/app/deploy/gcp_gemini_screen/manifests/smoke_manifest_5.json}"
  JOB_NAME="${JOB_NAME:-gemini-census-smoke}"
else
  MANIFEST_PATH="${MANIFEST_PATH:-/app/deploy/gcp_gemini_screen/manifests/full_manifest_945.json}"
fi

ARGS=(
  run jobs deploy "${JOB_NAME}"
  --project="${PROJECT_ID}"
  --region="${REGION}"
  --image="${IMAGE}"
  --tasks="${TASKS}"
  --parallelism="${PARALLELISM}"
  --task-timeout="${TASK_TIMEOUT}"
  --max-retries=1
  --memory="${MEMORY}"
  --cpu="${CPU}"
  --set-env-vars="GCS_BUCKET=${GCS_BUCKET},GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.1-pro-preview},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},AGENT_EVAL_MODE=1,MANIFEST_PATH=${MANIFEST_PATH}"
)

if [[ -n "${SA}" ]]; then
  ARGS+=(--service-account="${SA}")
fi

# Prefer Secret Manager for the API key when GEMINI_API_KEY_SECRET is set.
if [[ -n "${GEMINI_API_KEY_SECRET:-}" ]]; then
  ARGS+=(--set-secrets="GEMINI_API_KEY=${GEMINI_API_KEY_SECRET}:latest")
elif [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ARGS+=(--update-env-vars="GEMINI_API_KEY=${GEMINI_API_KEY}")
  echo "WARNING: passing GEMINI_API_KEY as plaintext env — prefer GEMINI_API_KEY_SECRET" >&2
fi

echo "gcloud ${ARGS[*]}"
gcloud "${ARGS[@]}"

echo
echo "Created/updated job ${JOB_NAME} (tasks=${TASKS}, parallelism=${PARALLELISM}, timeout=${TASK_TIMEOUT}s)"
echo "Smoke next:  TASKS=5 PARALLELISM=5 JOB_NAME=gemini-census-smoke ./deploy/gcp_gemini_screen/scripts/create_job.sh"
echo "             then ./deploy/gcp_gemini_screen/scripts/smoke_execute.sh"
