#!/usr/bin/env bash
# Deploy filtration-smoke Cloud Run Job and execute 25 tasks (5×5).
# Does NOT launch Phase 1 (315).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TAG="${TAG:-latest}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
SECRET_NAME="${SECRET_NAME:-openai-api-key}"
JOB="${JOB:-filtration-smoke}"
# Quota-safe: us-central1 MemAlloc=400GiB, CPU≈200 vCPU → ~100 @ 2CPU/4GiB.
# Smoke only needs 25.
PARALLELISM="${PARALLELISM:-25}"
TASKS="${TASKS:-25}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-smoke-$(date -u +%Y%m%dT%H%M%SZ)}"
GCS_PREFIX="${GCS_PREFIX:-filtration/smoke/${RUN_ID}}"

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

echo "[deploy] job=$JOB image=$IMAGE parallelism=$PARALLELISM tasks=$TASKS run_id=$RUN_ID"

if gcloud run jobs describe "$JOB" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

gcloud run jobs "$ACTION" "$JOB" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT" \
  --tasks="$TASKS" \
  --parallelism="$PARALLELISM" \
  --task-timeout="${TIMEOUT}s" \
  --max-retries=1 \
  --memory="$MEMORY" \
  --cpu="$CPU" \
  --set-env-vars="MANIFEST_PATH=/app/deploy/filtration/manifests/smoke_5x5_luna.json,GCS_BUCKET=${BUCKET},GCS_PREFIX=${GCS_PREFIX},RUN_ID=${RUN_ID},MODEL=gpt-5.6-luna,AGENT=openai_pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0" \
  --set-secrets="OPENAI_API_KEY=${SECRET_NAME}:latest"

echo "[execute] starting smoke"
EXEC_OUT="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" \
  --project="$PROJECT" \
  --format='value(metadata.name)')"
echo "[execute] execution=$EXEC_OUT"
echo "$EXEC_OUT" > /tmp/filtration_smoke_execution.txt
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/"
echo "Monitor: gcloud run jobs executions describe $EXEC_OUT --region=$REGION --project=$PROJECT"
