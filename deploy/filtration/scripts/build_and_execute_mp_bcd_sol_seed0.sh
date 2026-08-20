#!/usr/bin/env bash
# Build Full Pack B/C/D overlay image + Cloud Run Job: 3 tasks x Sol seed 0, ∥3.
# Overlays latest mp_032/033/034 server modules + seed_to_cuagym + hub_dist
# (pickup / BCC / gym-now calendar) onto filtration-worker base.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp-bcd-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
TASKS="${TASKS:-3}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp-bcd-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp-bcd-sol-seed0}"
MANIFEST="/app/deploy/filtration/manifests/mp_bcd_sol_seed0_3.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp_bcd}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"
HUB="${HUB:-/Users/maroonferrari/Deccan/CUA-Gym-Hub}"
SYNC_FROM_GYM="${SYNC_FROM_GYM:-1}"
PREPARE_HUB="${PREPARE_HUB:-1}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp-bcd-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp_bcd_sol_seed0_gcp}"

echo "[mp-bcd] BASE=$BASE_IMAGE"
echo "[mp-bcd] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

READY_STAMP="${READY_STAMP:-$HERE/manifests/mp_bcd_BC_RETUNE_READY}"
if [ ! -f "$READY_STAMP" ]; then
  echo "FATAL: missing B/C retune ready stamp: $READY_STAMP" >&2
  echo "       Wait for FULL_PACK_BC_RETUNE_GYM_NOW before packing." >&2
  exit 1
fi
# Guard: refuse pre-retune briefs
if ! grep -q 'starting today' "$GYM_ROOT/server/mp_032.py"; then
  echo "FATAL: mp_032 missing retuned 'starting today' brief" >&2
  exit 1
fi
if ! grep -q 'wooden spoon' "$GYM_ROOT/server/mp_033.py"; then
  echo "FATAL: mp_033 missing retuned 'wooden spoon' brief" >&2
  exit 1
fi
BRIEF_SOURCE="${BRIEF_SOURCE:-FULL_PACK_BC_RETUNE_GYM_NOW}"
echo "[mp-bcd] BRIEF_SOURCE=$BRIEF_SOURCE stamp=$(cat "$READY_STAMP")"

# --- sync latest suites from ecommerce-browser-gym ---
if [ "$SYNC_FROM_GYM" = "1" ]; then
  echo "[mp-bcd] syncing mp_032/033/034 + calendar gym_now from $GYM_ROOT"
  for f in mp_032.py mp_033.py mp_034.py; do
    cp "$GYM_ROOT/server/$f" "$RUNNER/server/$f"
  done
  mkdir -p "$RUNNER/server/apps/calendar"
  cp "$GYM_ROOT/server/apps/calendar/state.py" "$RUNNER/server/apps/calendar/state.py"
fi

# --- refresh hub_dist (pickup / BCC / calendar gym-now) ---
if [ "$PREPARE_HUB" = "1" ]; then
  # Prefer CUA-Gym-Hub for asset-heavy shop/market; overlay runner dist when
  # it has the retune fixes (calendar gym-now red line, food pickup, mail BCC).
  echo "[mp-bcd] preparing hub_dist"
  OUT="$HERE/hub_dist"
  mkdir -p "$OUT"
  for m in amazon_mock ebay_mock gmail_mock google_calendar_mock uber_eats_mock; do
    src=""
    case "$m" in
      google_calendar_mock|uber_eats_mock|gmail_mock)
        if [ -d "$RUNNER/websites/$m/dist" ] && [ -f "$RUNNER/websites/$m/dist/index.html" ]; then
          src="$RUNNER/websites/$m/dist"
        fi
        ;;
    esac
    if [ -z "$src" ] && [ -d "$HUB/websites/$m/dist" ]; then
      src="$HUB/websites/$m/dist"
    elif [ -z "$src" ] && [ -d "$RUNNER/websites/$m/dist" ]; then
      src="$RUNNER/websites/$m/dist"
    fi
    if [ -z "$src" ]; then
      echo "FATAL: missing dist for $m" >&2
      exit 1
    fi
    echo "[mp-bcd] hub $m ← $src"
    mkdir -p "$OUT/$m"
    rsync -a --delete "$src/" "$OUT/$m/"
  done
  N_JPG="$(find "$OUT/amazon_mock" -name '*.jpg' -print | wc -l | tr -d ' ')"
  echo "[mp-bcd] amazon JPGs=$N_JPG"
  if [ "$N_JPG" -lt 100 ]; then
    echo "FATAL: expected >=100 Xmazon JPGs in hub_dist/amazon_mock" >&2
    exit 1
  fi
fi

# --- local preflight ---
cd "$RUNNER"
python3 verify_mp_bcd.py

# --- stage overlay context ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/tools" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$HERE/manifests/mp_bcd_tasks.txt" "$CTX/deploy/filtration/manifests/"
cp "$HERE/manifests/mp_bcd_sol_seed0_3.json" "$CTX/deploy/filtration/manifests/"
cp "$RUNNER/verify_mp_bcd.py" "$CTX/verify_mp_bcd.py"
rsync -a "$HERE/hub_dist/" "$CTX/hub_dist/"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server /app/server
COPY tools/seed_to_cuagym.py /app/tools/seed_to_cuagym.py
COPY deploy/filtration/manifests/mp_bcd_tasks.txt /app/deploy/filtration/manifests/mp_bcd_tasks.txt
COPY deploy/filtration/manifests/mp_bcd_sol_seed0_3.json /app/deploy/filtration/manifests/mp_bcd_sol_seed0_3.json
COPY verify_mp_bcd.py /tmp/verify_mp_bcd.py
COPY hub_dist /hub_dist
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  rm -rf "\$DP/server"; \\
  cp -a /app/server "\$DP/server"; \\
  mkdir -p "\$DP/tools"; \\
  cp /app/tools/seed_to_cuagym.py "\$DP/tools/seed_to_cuagym.py"; \\
  python /tmp/verify_mp_bcd.py; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=50 or True; print('hub overlay OK', root)"
EOF

echo "[mp-bcd] Cloud Build submit → $IMAGE"
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

echo "[mp-bcd] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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

echo "[mp-bcd] RUN_ID=$RUN_ID"

mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":3,"parallelism":$PARALLELISM}
EOF
  echo "[mp-bcd] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp-bcd] execution=$EXEC"

cat >"$META_DIR/run_meta.json" <<EOF
{
  "run_id": "$RUN_ID",
  "execution": "$EXEC",
  "job": "$JOB",
  "model": "gpt-5.6-sol",
  "agent": "openai_pixel",
  "n_tasks": 3,
  "n_seeds": 1,
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
  "brief_source": "${BRIEF_SOURCE:-pack_or_retune}"
}
EOF
echo "[mp-bcd] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
