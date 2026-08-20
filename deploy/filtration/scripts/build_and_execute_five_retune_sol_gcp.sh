#!/usr/bin/env bash
# Five-task retune batch — GCP Sol parallel for unfinished / priority 3-seed confirms.
# Overlay: md_002, food_006, mp_038, mp_remaining, tasks/verifiers (+ Xoogle hub_dist if present).
#
# Default manifest: M142×3 + mp_038 seed2 (local mid-episodes left alone).
# Override with MANIFEST_LOCAL / JOB / GCS_PREFIX / PARALLELISM / TASKS.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-five-retune-sol-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-4}"
TASKS="${TASKS:-4}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-five-retune-sol-${TS}}"
JOB="${JOB:-filtration-five-retune-sol}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/five_retune_sol_remaining_4.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/five_retune_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-five-retune-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/five_retune_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/five_retune_sol_remaining_4.json}"

echo "[five] BASE=$BASE_IMAGE"
echo "[five] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[five] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# --- sync retunes from gym SoT ---
echo "[five] syncing retuned modules from $GYM_ROOT"
for f in md_002.py food_006.py mp_038.py mp_remaining.py tasks.py verifiers.py; do
  cp "$GYM_ROOT/server/$f" "$RUNNER/server/$f"
done
cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py"

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
import copy
from server.tasks import TASKS, make_task
from server.verifiers import Probe, build_suite

need = [
    "md_002/kettle_chase_and_dishrack_reorder",
    "M142/no_monitor_in_stock_high_rating",
    "food_006/design_review_shared_platter",
    "mp_002/ps5_controller_cap_infeasible_ask",
    "mp_038/vireo_q7_cable_and_cheapest_case",
]
for tid in need:
    assert tid in TASKS, tid
    w = make_task(tid, 0)
    init = copy.deepcopy(w)
    suite = build_suite(tid)
    probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
    r = suite.evaluate(probe, current_step=0)
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, r)
print("preflight OK fail-on-initial for", len(need), "tasks")
PY

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/$(basename "$MANIFEST_LOCAL")"
# Optional calendar hub (food_006 Design Review visibility)
if [ -d "$HERE/hub_dist/google_calendar_mock" ]; then
  mkdir -p "$CTX/hub_dist/google_calendar_mock"
  rsync -a "$HERE/hub_dist/google_calendar_mock/" "$CTX/hub_dist/google_calendar_mock/"
fi

MANIFEST_BASENAME="$(basename "$MANIFEST_LOCAL")"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server /app/server
COPY agents/oracle_agent.py /app/agents/oracle_agent.py
COPY deploy/filtration/manifests/${MANIFEST_BASENAME} /app/deploy/filtration/manifests/${MANIFEST_BASENAME}
COPY hub_dist /hub_dist
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  rm -rf "\$DP/server"; \\
  cp -a /app/server "\$DP/server"; \\
  mkdir -p "\$DP/agents"; \\
  cp /app/agents/oracle_agent.py "\$DP/agents/oracle_agent.py"; \\
  python -c "from server.tasks import TASKS; assert 'mp_038/vireo_q7_cable_and_cheapest_case' in TASKS; assert 'M142/no_monitor_in_stock_high_rating' in TASKS; print('five_retune overlay OK', len(TASKS))"
EOF

echo "[five] Cloud Build submit → $IMAGE"
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

echo "[five] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[five] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[five] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[five] execution=$EXEC"

cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{
  "run_id": "$RUN_ID",
  "execution": "$EXEC",
  "job": "$JOB",
  "model": "gpt-5.6-sol",
  "agent": "openai_pixel",
  "n_episodes": $TASKS,
  "parallelism": $PARALLELISM,
  "project": "$PROJECT",
  "region": "$REGION",
  "image": "$IMAGE",
  "gcs_bucket": "$BUCKET",
  "gcs_prefix": "$GCS_PREFIX",
  "manifest": "$MANIFEST",
  "manifest_local": "$MANIFEST_LOCAL",
  "agent_max_steps": 80
}
EOF
echo "[five] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
