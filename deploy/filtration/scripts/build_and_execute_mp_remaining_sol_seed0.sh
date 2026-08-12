#!/usr/bin/env bash
# Build mp remaining overlay image + Cloud Run Job: 11 tasks x Sol seed 0, parallel 11.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp-remaining-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-11}"
TASKS="${TASKS:-11}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp-remaining-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp-remaining-sol-seed0}"
MANIFEST="/app/deploy/filtration/manifests/mp_remaining_sol_seed0_11.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp_remaining}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp-remaining-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp_remaining_sol_seed0_gcp}"

echo "[mp-rem] BASE=$BASE_IMAGE"
echo "[mp-rem] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

# --- local preflight ---
cd "$RUNNER"
python3 verify_mp_remaining.py

# --- stage overlay context ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/tools" "$CTX/deploy/filtration/manifests"
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$HERE/manifests/mp_remaining_tasks.txt" "$CTX/deploy/filtration/manifests/"
cp "$HERE/manifests/mp_remaining_sol_seed0_11.json" "$CTX/deploy/filtration/manifests/"
cp "$RUNNER/verify_mp_remaining.py" "$CTX/verify_mp_remaining.py"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server /app/server
COPY tools/seed_to_cuagym.py /app/tools/seed_to_cuagym.py
COPY deploy/filtration/manifests/mp_remaining_tasks.txt /app/deploy/filtration/manifests/mp_remaining_tasks.txt
COPY deploy/filtration/manifests/mp_remaining_sol_seed0_11.json /app/deploy/filtration/manifests/mp_remaining_sol_seed0_11.json
COPY verify_mp_remaining.py /tmp/verify_mp_remaining.py
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  rm -rf "\$DP/server"; \\
  cp -a /app/server "\$DP/server"; \\
  mkdir -p "\$DP/tools"; \\
  cp /app/tools/seed_to_cuagym.py "\$DP/tools/seed_to_cuagym.py"; \\
  python /tmp/verify_mp_remaining.py
EOF

echo "[mp-rem] Cloud Build submit → $IMAGE"
gcloud builds submit "$CTX" \
  --project="$PROJECT" \
  --tag="$IMAGE" \
  --timeout=1800s \
  --machine-type=e2-highcpu-8

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

if gcloud run jobs describe "$JOB" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  action=update
else
  action=create
fi

echo "[mp-rem] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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
  --set-env-vars="MANIFEST_PATH=${MANIFEST},GCS_BUCKET=${BUCKET},GCS_PREFIX=${GCS_PREFIX},RUN_ID=${RUN_ID},MODEL=gpt-5.6-sol,AGENT=openai_pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0,AGENT_MAX_STEPS=80" \
  --set-secrets="OPENAI_API_KEY=${OPENAI_SECRET}:latest"

echo "[mp-rem] RUN_ID=$RUN_ID"

mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":11,"parallelism":$PARALLELISM}
EOF
  echo "[mp-rem] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp-rem] execution=$EXEC"

cat >"$META_DIR/run_meta.json" <<EOF
{
  "run_id": "$RUN_ID",
  "execution": "$EXEC",
  "job": "$JOB",
  "model": "gpt-5.6-sol",
  "agent": "openai_pixel",
  "n_tasks": 11,
  "n_seeds": 1,
  "n_episodes": 11,
  "parallelism": $PARALLELISM,
  "project": "$PROJECT",
  "region": "$REGION",
  "image": "$IMAGE",
  "base_image": "$BASE_IMAGE",
  "gcs_bucket": "$BUCKET",
  "gcs_prefix": "$GCS_PREFIX",
  "manifest": "$MANIFEST",
  "agent_max_steps": 80
}
EOF
echo "[mp-rem] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
