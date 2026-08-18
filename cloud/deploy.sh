#!/usr/bin/env bash
# Build the runner image, create/update the Cloud Run Job, and fan the episodes out.
#
#   ./cloud/deploy.sh                 # build + deploy + run whatever is in manifest.json
#   ./cloud/deploy.sh --no-build      # re-run without rebuilding the image
#
# Prereq (interactive, once):  gcloud auth login && gcloud config set project mlproject-501205
set -euo pipefail

PROJECT="${PROJECT:-mlproject-501205}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-runner}"
JOB="${JOB:-gym-eval}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/eval-runner:latest"
BUCKET="${BUCKET:-${PROJECT}-gym-runs}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
MODEL="${OPENAI_MODEL:-gpt-5.6-sol}"
MAX_STEPS="${AGENT_MAX_STEPS:-100}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

N=$(python3 -c "import json;print(len(json.load(open('$HERE/manifest.json'))['runs']))")
echo "project=$PROJECT region=$REGION episodes=$N model=$MODEL cap=$MAX_STEPS run_id=$RUN_ID"

gcloud config set project "$PROJECT" >/dev/null

# --- one-time infra (idempotent) --------------------------------------------
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com secretmanager.googleapis.com storage.googleapis.com \
    --project "$PROJECT" >/dev/null

gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" --repository-format=docker \
    --location "$REGION" --description "browser-gym eval runner"

gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --location "$REGION"

# The API key lives in Secret Manager, never in the job spec or the image.
if ! gcloud secrets describe openai-api-key >/dev/null 2>&1; then
  if [ -f "$ROOT/.env" ] && grep -q '^OPENAI_API_KEY=' "$ROOT/.env"; then
    grep '^OPENAI_API_KEY=' "$ROOT/.env" | head -1 | cut -d= -f2- \
      | gcloud secrets create openai-api-key --data-file=- --replication-policy=automatic
    echo "created secret openai-api-key from .env"
  else
    echo "ERROR: secret 'openai-api-key' missing and no OPENAI_API_KEY in .env" >&2; exit 1
  fi
fi

# --- image -------------------------------------------------------------------
if [ "${1:-}" != "--no-build" ]; then
  echo "building $IMAGE (Cloud Build; the Playwright base is ~2GB, first build is slow)"
  gcloud builds submit "$ROOT" --config=- <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build","-f","cloud/Dockerfile","-t","$IMAGE","."]
images: ["$IMAGE"]
options:
  machineType: E2_HIGHCPU_8
timeout: 3600s
YAML
fi

# --- job ---------------------------------------------------------------------
ARGS=(
  --image "$IMAGE" --region "$REGION" --project "$PROJECT"
  --tasks "$N" --parallelism "$N" --task-timeout 3600s --max-retries 0
  --cpu 2 --memory 4Gi
  --set-env-vars "RUN_ID=$RUN_ID,RESULTS_BUCKET=$BUCKET,OPENAI_MODEL=$MODEL,AGENT_MAX_STEPS=$MAX_STEPS"
  --set-secrets "OPENAI_API_KEY=openai-api-key:latest"
)
if gcloud run jobs describe "$JOB" --region "$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" "${ARGS[@]}"
else
  gcloud run jobs create "$JOB" "${ARGS[@]}"
fi

echo "executing $N episodes in parallel..."
gcloud run jobs execute "$JOB" --region "$REGION" --wait

echo
echo "results:  gs://$BUCKET/runs/$RUN_ID/"
echo "collect:  python3 cloud/collect.py --bucket $BUCKET --run-id $RUN_ID"
echo "logs:     https://console.cloud.google.com/run/jobs/details/$REGION/$JOB/executions?project=$PROJECT"
