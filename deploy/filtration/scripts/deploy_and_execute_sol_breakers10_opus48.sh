#!/usr/bin/env bash
# Deploy + execute Sol task-gen breakers n10–n19 × Opus 4.8 (3 seeds = 30 eps).
# Requires: filtration-worker:sol-breakers10 image already built/pushed.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TAG="${TAG:-sol-breakers10}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-anthropic-api-key}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-15}"
TASKS="${TASKS:-30}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_TS="${RUN_TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_ID="${RUN_ID:-sol-breakers10-opus48-${RUN_TS}}"
JOB="${JOB:-filtration-sol-breakers10-opus48}"
MANIFEST="/app/deploy/filtration/manifests/sol_breakers10_opus48_30.json"
EXECUTE="${EXECUTE:-1}"
GCS_PREFIX="${GCS_PREFIX:-filtration/sol_breakers10}"

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

if gcloud run jobs describe "$JOB" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  action=update
else
  action=create
fi

echo "[sol10] $action $JOB model=claude-opus-4-8 agent=pixel run_id=$RUN_ID image=$IMAGE"
gcloud run jobs "$action" "$JOB" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT" \
  --tasks="$TASKS" \
  --parallelism="$PARALLELISM" \
  --task-timeout="${TIMEOUT}s" \
  --max-retries=1 \
  --memory="$MEMORY" \
  --cpu="$CPU" \
  --set-env-vars="MANIFEST_PATH=${MANIFEST},GCS_BUCKET=${BUCKET},GCS_PREFIX=${GCS_PREFIX},RUN_ID=${RUN_ID},MODEL=claude-opus-4-8,AGENT=pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0" \
  --set-secrets="ANTHROPIC_API_KEY=${ANTHROPIC_SECRET}:latest,OPENAI_API_KEY=${OPENAI_SECRET}:latest"

echo "[sol10] RUN_ID=$RUN_ID"

if [ "$EXECUTE" != "1" ]; then
  echo "[sol10] EXECUTE=0 — deploy only. Execute with:"
  echo "  gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[sol10] execution=$EXEC"

META_DIR="${META_DIR:-/Users/maroonferrari/Deccan/browser-gym-seed-to-cua-gym/trajectories/sol_breakers10_opus48}"
mkdir -p "$META_DIR"
cat >"$META_DIR/run_meta.json" <<EOF
{
  "run_id": "$RUN_ID",
  "execution": "$EXEC",
  "job": "$JOB",
  "model": "claude-opus-4-8",
  "agent": "pixel",
  "n_tasks": 10,
  "n_seeds": 3,
  "n_episodes": 30,
  "parallelism": $PARALLELISM,
  "project": "$PROJECT",
  "region": "$REGION",
  "image": "$IMAGE",
  "gcs_bucket": "$BUCKET",
  "gcs_prefix": "$GCS_PREFIX"
}
EOF
echo "[sol10] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
