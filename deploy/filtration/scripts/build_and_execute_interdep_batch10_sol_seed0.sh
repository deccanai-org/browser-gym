#!/usr/bin/env bash
# Interdep batch10 (mp_039–mp_048) — Sol gpt-5.6-sol seed0 ×10 parallel on GCP.
# Overlay: mp_039..mp_048 + tasks/verifiers/oracle (+ Xoogle hub_dist if present).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-interdep-batch10-sol-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-10}"
TASKS="${TASKS:-10}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-interdep-batch10-sol-${TS}}"
JOB="${JOB:-filtration-interdep-batch10-sol}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/interdep_batch10_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/interdep_batch10_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-interdep-batch10-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/interdep_batch10_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/interdep_batch10_sol_seed0.json}"

echo "[b10] BASE=$BASE_IMAGE"
echo "[b10] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[b10] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# --- sync retunes from gym SoT ---
echo "[b10] syncing retuned modules from $GYM_ROOT"
for f in mp_039.py mp_040.py mp_041.py mp_042.py mp_043.py mp_044.py mp_045.py mp_046.py mp_047.py mp_048.py tasks.py verifiers.py; do
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
    "mp_039/return_unresolved_blocks_blender_reorder",
    "mp_040/couch_pickup_vs_calendar_busy",
    "mp_041/standup_lunch_headcount_shrink",
    "mp_042/support_already_replied_no_followup",
    "mp_043/auction_ends_before_call_check_result",
    "mp_044/cousin_dinner_after_flight_settle",
    "mp_045/desk_lamp_pricematch_not_owed",
    "mp_046/dentist_triple_reschedule_latest_wins",
    "mp_047/lunch_1pm_meeting_may_run_long",
    "mp_048/lamp_warranty_expired_check_first",
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
  python -c "from server.tasks import TASKS; assert 'mp_039/return_unresolved_blocks_blender_reorder' in TASKS; assert 'mp_048/lamp_warranty_expired_check_first' in TASKS; print('interdep_batch10 overlay OK', len(TASKS))"
EOF

echo "[b10] Cloud Build submit → $IMAGE"
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

echo "[b10] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[b10] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[b10] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[b10] execution=$EXEC"

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
echo "[b10] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
