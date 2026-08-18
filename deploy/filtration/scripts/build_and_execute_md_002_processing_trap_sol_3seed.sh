#!/usr/bin/env bash
# Build md_002 processing-trap overlay + Cloud Run Job: Sol seeds 0/1/2 in parallel (∥3).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-md002-proc-trap-sol-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
TASKS="${TASKS:-3}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-md002-proc-trap-sol-${TS}}"
JOB="${JOB:-filtration-md002-proc-trap-sol}"
MANIFEST="/app/deploy/filtration/manifests/md_002_processing_trap_sol_3seed.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/md_002_processing_trap_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"
SYNC_FROM_GYM="${SYNC_FROM_GYM:-1}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-md002-proc-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/md002_proc_trap_sol_3seed_gcp}"
MANIFEST_LOCAL="$HERE/manifests/md_002_processing_trap_sol_3seed.json"
BRIEF_SOURCE="${BRIEF_SOURCE:-MD002_KETTLE_DELIVERED_NOT_PROCESSING_2026-08-10}"

echo "[md002] BASE=$BASE_IMAGE"
echo "[md002] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

if [ "$SYNC_FROM_GYM" = "1" ]; then
  echo "[md002] syncing md_002.py + oracle from $GYM_ROOT"
  cp "$GYM_ROOT/server/md_002.py" "$RUNNER/server/md_002.py"
  cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py"
fi

if ! grep -q "sitting in processing forever" "$RUNNER/server/md_002.py"; then
  echo "FATAL: md_002 missing new processing brief" >&2
  exit 1
fi
if grep -q "was never delivered" "$RUNNER/server/md_002.py"; then
  echo "FATAL: md_002 still has old never-delivered brief" >&2
  exit 1
fi

cd "$RUNNER"
python3 - <<'PY'
from server.md_002 import BRIEF, TASK_ID, ORDER_ID, suite_factories
from server.tasks import make_task
from server.verifiers import Probe, build_suite

assert TASK_ID == "md_002/kettle_chase_and_dishrack_reorder"
assert "sitting in processing forever" in BRIEF
assert "best deal" in BRIEF
sf = suite_factories()
assert TASK_ID in sf
w0 = make_task(TASK_ID, seed=0)
assert w0.shop.orders[ORDER_ID].status == "delivered"
assert w0.shop.orders[ORDER_ID].shipments[0].status == "delivered"
suite = build_suite(TASK_ID)
probe = Probe.__new__(Probe)
probe.world = w0
probe.initial_world = w0
probe.state = w0.shop
probe.initial_state = w0.shop
probe.url = "/"
probe.action_log = []
probe.active_tab_url = "/"
rows = [(m.name, bool(m.check(probe)), m.required_for_success, m.forbidden, m.weight) for m in suite.milestones]
success = all(ok for n,ok,req,forb,wt in rows if req) and not any(ok for n,ok,req,forb,wt in rows if forb)
score = sum(wt for n,ok,req,forb,wt in rows if ok and not forb)
assert success is False and score == 0.0, (success, score, rows)
names = [n for n, *_ in rows]
assert "told_user_kettle_delivered" in names
assert "emailed_support_chase" in names
print("preflight OK fail-on-initial 0.0; delivered kettle + processing brief")
print(BRIEF[:90], "...")
PY

rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/deploy/filtration/manifests"
cp "$RUNNER/server/md_002.py" "$CTX/server/md_002.py"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$HERE/manifests/md_002_tasks.txt" "$CTX/deploy/filtration/manifests/"
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/md_002_processing_trap_sol_3seed.json"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server/md_002.py /app/server/md_002.py
COPY agents/oracle_agent.py /app/agents/oracle_agent.py
COPY deploy/filtration/manifests/md_002_tasks.txt /app/deploy/filtration/manifests/md_002_tasks.txt
COPY deploy/filtration/manifests/md_002_processing_trap_sol_3seed.json /app/deploy/filtration/manifests/md_002_processing_trap_sol_3seed.json
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  cp /app/server/md_002.py "\$DP/server/md_002.py"; \\
  cp /app/agents/oracle_agent.py "\$DP/agents/oracle_agent.py" 2>/dev/null || true; \\
  python -c "from server.md_002 import BRIEF, ORDER_ID; from server.tasks import make_task; w=make_task('md_002/kettle_chase_and_dishrack_reorder',0); assert 'sitting in processing forever' in BRIEF; assert w.shop.orders[ORDER_ID].status=='delivered'; print('md_002 OK', BRIEF[:70])"
EOF

echo "[md002] Cloud Build submit → $IMAGE"
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

echo "[md002] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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

echo "[md002] RUN_ID=$RUN_ID"

mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":3,"parallelism":$PARALLELISM,"brief_source":"$BRIEF_SOURCE"}
EOF
  echo "[md002] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[md002] execution=$EXEC"

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
  "task_id": "md_002/kettle_chase_and_dishrack_reorder",
  "trap": "brief claims processing; ORD-KT-111 delivered"
}
EOF
echo "[md002] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
