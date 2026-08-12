#!/usr/bin/env bash
# Deploy + execute Phase 2 sample20: 20 tasks × 5 seeds × Sol and Opus (200 eps).
# Two Cloud Run Jobs (Sol batch + Opus batch), parallelism ≤100.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TAG="${TAG:-latest}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-anthropic-api-key}"
PARALLELISM="${PARALLELISM:-100}"
TASKS="${TASKS:-100}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_TS="${RUN_TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
SOL_RUN_ID="${SOL_RUN_ID:-phase2-sample20-sol-${RUN_TS}}"
OPUS_RUN_ID="${OPUS_RUN_ID:-phase2-sample20-opus-${RUN_TS}}"
EXECUTE="${EXECUTE:-1}"  # set 0 to deploy-only

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

deploy_job() {
  local job="$1" manifest="$2" run_id="$3" model="$4" agent="$5" secrets="$6"
  local action
  if gcloud run jobs describe "$job" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
    action=update
  else
    action=create
  fi
  echo "[phase2] $action $job model=$model agent=$agent run_id=$run_id"
  gcloud run jobs "$action" "$job" \
    --image="$IMAGE" \
    --region="$REGION" \
    --project="$PROJECT" \
    --tasks="$TASKS" \
    --parallelism="$PARALLELISM" \
    --task-timeout="${TIMEOUT}s" \
    --max-retries=1 \
    --memory="$MEMORY" \
    --cpu="$CPU" \
    --set-env-vars="MANIFEST_PATH=${manifest},GCS_BUCKET=${BUCKET},GCS_PREFIX=filtration/phase2_sample20,RUN_ID=${run_id},MODEL=${model},AGENT=${agent},HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0" \
    --set-secrets="$secrets"
}

deploy_job \
  "filtration-phase2-sample20-sol" \
  "/app/deploy/filtration/manifests/phase2_sample20_sol_100.json" \
  "$SOL_RUN_ID" \
  "gpt-5.6-sol" \
  "openai_pixel" \
  "OPENAI_API_KEY=${OPENAI_SECRET}:latest"

deploy_job \
  "filtration-phase2-sample20-opus" \
  "/app/deploy/filtration/manifests/phase2_sample20_opus_100.json" \
  "$OPUS_RUN_ID" \
  "claude-opus-5" \
  "pixel" \
  "ANTHROPIC_API_KEY=${ANTHROPIC_SECRET}:latest,OPENAI_API_KEY=${OPENAI_SECRET}:latest"

echo "[phase2] SOL_RUN_ID=$SOL_RUN_ID"
echo "[phase2] OPUS_RUN_ID=$OPUS_RUN_ID"

if [ "$EXECUTE" != "1" ]; then
  echo "[phase2] EXECUTE=0 — deploy only. Execute with:"
  echo "  gcloud run jobs execute filtration-phase2-sample20-sol --region=$REGION --project=$PROJECT"
  echo "  gcloud run jobs execute filtration-phase2-sample20-opus --region=$REGION --project=$PROJECT"
  exit 0
fi

echo "[phase2] executing Sol…"
SOL_EXEC="$(gcloud run jobs execute filtration-phase2-sample20-sol \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[phase2] Sol execution=$SOL_EXEC"

echo "[phase2] executing Opus…"
OPUS_EXEC="$(gcloud run jobs execute filtration-phase2-sample20-opus \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[phase2] Opus execution=$OPUS_EXEC"

# Persist run metadata for the report / merge step
META_DIR="${META_DIR:-/Users/maroonferrari/Deccan/browser-gym-seed-to-cua-gym/trajectories/tencent_filtration_phase2_sample20}"
mkdir -p "$META_DIR"
cat >"$META_DIR/run_meta.json" <<EOF
{
  "sol_run_id": "$SOL_RUN_ID",
  "opus_run_id": "$OPUS_RUN_ID",
  "sol_execution": "$SOL_EXEC",
  "opus_execution": "$OPUS_EXEC",
  "sol_model": "gpt-5.6-sol",
  "opus_model": "claude-opus-5",
  "n_tasks": 20,
  "n_seeds": 5,
  "n_episodes_per_model": 100,
  "project": "$PROJECT",
  "region": "$REGION",
  "gcs_bucket": "$BUCKET",
  "gcs_prefix": "filtration/phase2_sample20"
}
EOF
echo "[phase2] wrote $META_DIR/run_meta.json"
echo "SOL_EXEC=$SOL_EXEC"
echo "OPUS_EXEC=$OPUS_EXEC"
