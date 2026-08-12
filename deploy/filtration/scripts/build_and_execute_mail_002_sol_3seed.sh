#!/usr/bin/env bash
# Build mail_002 overlay image + Cloud Run Job: Sol seeds 0/1/2 in parallel (∥3).
# Syncs retuned BRIEF from ecommerce-browser-gym onto filtration-worker base.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mail002-sol-3seed-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
TASKS="${TASKS:-3}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mail002-sol-3seed-${TS}}"
JOB="${JOB:-filtration-mail002-sol-3seed}"
MANIFEST="/app/deploy/filtration/manifests/mail_002_sol_3seed_3.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/mail_002}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"
SYNC_FROM_GYM="${SYNC_FROM_GYM:-1}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mail002-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mail_002_sol_3seed_gcp}"

echo "[mail002] BASE=$BASE_IMAGE"
echo "[mail002] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

# --- sync retuned brief from ecommerce-browser-gym ---
if [ "$SYNC_FROM_GYM" = "1" ]; then
  echo "[mail002] syncing mail_002.py from $GYM_ROOT"
  cp "$GYM_ROOT/server/mail_002.py" "$RUNNER/server/mail_002.py"
fi

# Guard: refuse old support@shopgym.com brief wording
if grep -q 'Email support@shopgym.com' "$RUNNER/server/mail_002.py"; then
  echo "FATAL: mail_002 still has old 'Email support@shopgym.com' brief" >&2
  exit 1
fi
if ! grep -q 'motor just suddenly stopped' "$RUNNER/server/mail_002.py"; then
  echo "FATAL: mail_002 missing retuned 'motor just suddenly stopped' brief" >&2
  exit 1
fi
BRIEF_SOURCE="${BRIEF_SOURCE:-LUMOS_MAIL002_BRIEF_RETUNE_2026-08-07}"
echo "[mail002] BRIEF_SOURCE=$BRIEF_SOURCE"

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
from server.mail_002 import BRIEF, TASK_ID, suite_factories
assert TASK_ID == "mail_002/false_warranty_never_bought"
assert "suddenly stopped" in BRIEF
assert "support@shopgym.com" not in BRIEF.split("alice@shopgym.com")[0]
assert "Email support and" in BRIEF
sf = suite_factories()
assert TASK_ID in sf
print("preflight OK:", BRIEF[:80], "...")
PY

# --- stage overlay context ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/deploy/filtration/manifests"
# Minimal overlay: only mail_002 + manifest (base image already has full server)
mkdir -p "$CTX/server"
cp "$RUNNER/server/mail_002.py" "$CTX/server/mail_002.py"
cp "$HERE/manifests/mail_002_tasks.txt" "$CTX/deploy/filtration/manifests/"
cp "$HERE/manifests/mail_002_sol_3seed_3.json" "$CTX/deploy/filtration/manifests/"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server/mail_002.py /app/server/mail_002.py
COPY deploy/filtration/manifests/mail_002_tasks.txt /app/deploy/filtration/manifests/mail_002_tasks.txt
COPY deploy/filtration/manifests/mail_002_sol_3seed_3.json /app/deploy/filtration/manifests/mail_002_sol_3seed_3.json
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  cp /app/server/mail_002.py "\$DP/server/mail_002.py"; \\
  python -c "from server.mail_002 import BRIEF; assert 'suddenly stopped' in BRIEF; assert 'Email support and' in BRIEF; print('mail_002 brief OK')"
EOF

echo "[mail002] Cloud Build submit → $IMAGE"
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

echo "[mail002] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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
  --set-env-vars="MANIFEST_PATH=${MANIFEST},GCS_BUCKET=${BUCKET},GCS_PREFIX=${GCS_PREFIX},RUN_ID=${RUN_ID},MODEL=gpt-5.6-sol,AGENT=openai_pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0,AGENT_MAX_STEPS=80,PYTHONUNBUFFERED=1" \
  --set-secrets="OPENAI_API_KEY=${OPENAI_SECRET}:latest"

echo "[mail002] RUN_ID=$RUN_ID"

mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":3,"parallelism":$PARALLELISM,"brief_source":"$BRIEF_SOURCE"}
EOF
  echo "[mail002] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mail002] execution=$EXEC"

cat >"$META_DIR/run_meta.json" <<EOF
{
  "run_id": "$RUN_ID",
  "execution": "$EXEC",
  "job": "$JOB",
  "model": "gpt-5.6-sol",
  "agent": "openai_pixel",
  "n_tasks": 1,
  "n_seeds": 3,
  "n_episodes": 3,
  "parallelism": $PARALLELISM,
  "project": "$PROJECT",
  "region": "$REGION",
  "image": "$IMAGE",
  "base_image": "$BASE_IMAGE",
  "gcs_bucket": "$BUCKET",
  "gcs_prefix": "$GCS_PREFIX",
  "manifest": "$MANIFEST",
  "agent_max_steps": 80,
  "brief_source": "$BRIEF_SOURCE",
  "task_id": "mail_002/false_warranty_never_bought"
}
EOF
echo "[mail002] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
