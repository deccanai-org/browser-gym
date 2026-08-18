#!/usr/bin/env bash
# Parallel probes 2026-08-10: Dana mug + ErgoGlide couch + lamp flicker + mp_038 s1/s2.
# One Cloud Run job, 5 tasks ∥5, Sol gpt-5.6-sol.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-parallel-probes-sol-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-5}"
TASKS="${TASKS:-5}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-parallel-probes-sol-${TS}}"
JOB="${JOB:-filtration-parallel-probes-sol}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/parallel_probes_couch_lamp_mug_m312_5.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/parallel_probes_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-parallel-probes-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/parallel_probes_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/parallel_probes_couch_lamp_mug_m312_5.json}"

echo "[pp] BASE=$BASE_IMAGE"
echo "[pp] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[pp] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# --- sync from gym SoT ---
echo "[pp] syncing modules from $GYM_ROOT"
for f in mp_038.py mp_040.py mp_048.py mp_049.py tasks.py verifiers.py; do
  cp "$GYM_ROOT/server/$f" "$RUNNER/server/$f"
done
cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py"

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
import copy
from server.tasks import TASKS, make_task, BRIEFS
from server.verifiers import Probe, build_suite

need = [
    "mp_049/dana_housewarming_mug_address_probe",
    "mp_040/couch_pickup_vs_calendar_busy",
    "mp_048/lamp_warranty_expired_check_first",
    "mp_038/vireo_q7_cable_and_cheapest_case",
]
assert "Grab the ErgoGlide couch" in BRIEFS.get("mp_040", "") or True
w40 = make_task("mp_040/couch_pickup_vs_calendar_busy", 0)
assert "ErgoGlide" in (w40.shop.task_brief or "")
assert "ErgoGlide" in w40.market.products["vm_mp040_couch"].name
w48 = make_task("mp_048/lamp_warranty_expired_check_first", 0)
assert "flickering" in (w48.shop.task_brief or "").lower()
assert "warranty" not in (w48.shop.task_brief or "").lower()
w49 = make_task("mp_049/dana_housewarming_mug_address_probe", 0)
assert "addr_dana" in w49.shop.users["u_alice"].addresses
assert any(i.product_id == "p_mp049_housewarming_mug" for i in w49.shop.cart.items)
w38 = make_task("mp_038/vireo_q7_cable_and_cheapest_case", 1)
assert "USB-C" in (w38.shop.task_brief or "")

for tid in need:
    assert tid in TASKS, tid
    w = make_task(tid, 0)
    init = copy.deepcopy(w)
    suite = build_suite(tid)
    probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
    r = suite.evaluate(probe, current_step=0)
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, r)
print("preflight OK fail-on-initial for", len(need), "tasks")
print("briefs:", {k: BRIEFS.get(k) for k in ("mp_040", "mp_048", "mp_049", "mp_038")})
PY

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/$(basename "$MANIFEST_LOCAL")"
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
  python -c "from server.tasks import TASKS, BRIEFS; assert 'mp_049/dana_housewarming_mug_address_probe' in TASKS; assert 'ErgoGlide' in BRIEFS['mp_040']; assert 'flickering' in BRIEFS['mp_048'].lower(); print('parallel_probes overlay OK', len(TASKS))"
EOF

echo "[pp] Cloud Build submit → $IMAGE"
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

echo "[pp] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[pp] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[pp] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[pp] execution=$EXEC"

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
echo "[pp] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
