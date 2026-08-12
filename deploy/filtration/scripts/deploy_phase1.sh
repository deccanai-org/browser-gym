#!/usr/bin/env bash
# Deploy filtration-phase1-luna job (315 tasks). DOES NOT EXECUTE.
# Execute only after explicit go-ahead:
#   gcloud run jobs execute filtration-phase1-luna --region=us-central1 --project=gemini-503300
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TAG="${TAG:-latest}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
SECRET_NAME="${SECRET_NAME:-openai-api-key}"
JOB="${JOB:-filtration-phase1-luna}"
# Quota ceiling @ 2CPU/4GiB ≈ 100 (mem 400GiB / CPU ~200 vCPU). Plan's 150 exceeds CPU.
PARALLELISM="${PARALLELISM:-100}"
TASKS="${TASKS:-315}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

if gcloud run jobs describe "$JOB" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  ACTION=update
else
  ACTION=create
fi

echo "[phase1-deploy] $ACTION $JOB tasks=$TASKS parallelism=$PARALLELISM (NO EXECUTE)"
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
  --set-env-vars="MANIFEST_PATH=/app/deploy/filtration/manifests/phase1_luna_315.json,GCS_BUCKET=${BUCKET},GCS_PREFIX=filtration/phase1,MODEL=gpt-5.6-luna,AGENT=openai_pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0" \
  --set-secrets="OPENAI_API_KEY=${SECRET_NAME}:latest"

echo "[phase1-deploy] job ready. Do NOT execute until go-ahead."
echo "  gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT"
