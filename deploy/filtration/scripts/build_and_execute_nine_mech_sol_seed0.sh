#!/usr/bin/env bash
# Nine-mech batch (mp_051–mp_058) — Sol gpt-5.6-sol seed0 ×8 parallel on GCP.
# Newest seed-to-cua hub_dist only (never CUA-Gym-Hub vite / legacy).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-nine-mech-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-8}"
TASKS="${TASKS:-8}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-nine-mech-sol-seed0-${TS}}"
JOB="${JOB:-filtration-nine-mech-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/nine_mech_sol_seed0_8.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/nine_mech_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-nine-mech-sol-seed0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/nine_mech_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/nine_mech_sol_seed0_8.json}"

echo "[nine] BASE=$BASE_IMAGE"
echo "[nine] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[nine] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# --- use runner tree (seed-to-cua) which already holds mp_051–mp_058 + env affordances ---
# Optionally mirror task modules back to gym SoT for bookkeeping (non-fatal).
echo "[nine] mirroring mp_051–mp_058 → $GYM_ROOT (bookkeeping)"
for f in mp_051.py mp_052.py mp_053.py mp_054.py mp_055.py mp_056.py mp_057.py mp_058.py; do
  if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
    cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
  fi
done
cd "$RUNNER"
python3 - <<'PY'
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite
import copy

need = [
    "mp_051/false_premise_two_lamp_orders",
    "mp_052/water_filter_deadline_unit_price",
    "mp_053/cancel_coffee_ambiguous",
    "mp_054/cancel_coffee_control",
    "mp_055/toaster_protection_under_budget",
    "mp_056/desk_address_change_ofd_infeasible",
    "mp_057/lamp_address_change_reason_unlock",
    "mp_058/home_nights_dinner_avoid_bad_reviews",
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
# world_full + schedule/cancel actions present
from pathlib import Path
main = Path("server/main.py").read_text()
assert "/_harness/world_full" in main
bridge = Path("tools/bridge.py").read_text()
for a in ("food.set_schedule", "shop.cancel_order", "shop.change_order_address"):
    assert a in bridge, a
print("bridge actions + world_full OK")
PY

# --- hub_dist MUST be seed-to-cua vendored websites (never CUA-Gym-Hub / legacy) ---
HUB="$RUNNER" REBUILD=0 bash "$HERE/scripts/prepare_hub_dist.sh"
CAL_JS="$(find "$HERE/hub_dist/google_calendar_mock/assets" -name 'index-*.js' -print -quit)"
AMZ_JS="$(find "$HERE/hub_dist/amazon_mock/assets" -name 'index-*.js' -print -quit)"
UBER_JS="$(find "$HERE/hub_dist/uber_eats_mock/assets" -name 'index-*.js' -print -quit)"
test -n "$CAL_JS" && test -n "$AMZ_JS" && test -n "$UBER_JS"
python3 - <<PY
from pathlib import Path
cal_p, amz_p, uber_p = Path("$CAL_JS"), Path("$AMZ_JS"), Path("$UBER_JS")
cal, amz, uber = (p.read_text(errors="ignore") for p in (cal_p, amz_p, uber_p))
assert "input-edit-start" in cal and 'type:"time"' in cal, "calendar hub_dist missing split time UI"
assert "Warranty expired" in amz, "amazon hub_dist missing warranty banner"
assert "/api/" in amz, "FATAL: amazon hub_dist missing /api/ — looks like legacy/CUA bake"
assert "btn-cancel-order-open" in amz, "amazon missing cancel UI"
assert "order-address-change" in amz or "change_order_address" in amz or "changeOrderAddress" in amz
assert "btn-schedule-when" in uber and "btn-schedule-slot" in uber, "uber missing schedule-ahead UI"
assert "food.set_schedule" in uber, "uber missing durable food.set_schedule wiring"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber, f"FATAL: remote hub URL baked in: {bad}"
# Pin tip-lock wipe rebuild 2026-08-10 (HEAD 3d7362d + mp_040/048 UI fixes)
assert cal_p.name == "index-8e84e2c6.js", cal_p.name
assert amz_p.name == "index-DNSHRGfv.js", amz_p.name
assert uber_p.name == "index-DXWw629n.js", uber_p.name
print("hub_dist NEW-UI OK (seed-to-cua websites)")
print("  calendar:", cal_p.name)
print("  amazon:", amz_p.name)
print("  uber:", uber_p.name)
PY

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/tools" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$RUNNER/tools/bridge.py" "$CTX/tools/bridge.py"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$RUNNER/tools/bridge_service.py" "$CTX/tools/bridge_service.py"
if [ -f "$HERE/worker_entrypoint.sh" ]; then
  mkdir -p "$CTX/deploy/filtration"
  cp "$HERE/worker_entrypoint.sh" "$CTX/deploy/filtration/worker_entrypoint.sh"
fi
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/$(basename "$MANIFEST_LOCAL")"
rsync -a "$HERE/hub_dist/" "$CTX/hub_dist/"

MANIFEST_BASENAME="$(basename "$MANIFEST_LOCAL")"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server /app/server
COPY agents/oracle_agent.py /app/agents/oracle_agent.py
COPY tools/bridge.py /app/tools/bridge.py
COPY tools/seed_to_cuagym.py /app/tools/seed_to_cuagym.py
COPY tools/bridge_service.py /app/tools/bridge_service.py
COPY deploy/filtration/manifests/${MANIFEST_BASENAME} /app/deploy/filtration/manifests/${MANIFEST_BASENAME}
COPY deploy/filtration/worker_entrypoint.sh /app/deploy/filtration/worker_entrypoint.sh
RUN rm -rf /hub_dist
COPY hub_dist /hub_dist
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
ENV HUB_DIST=/hub_dist
RUN set -e; \\
  chmod +x /app/deploy/filtration/worker_entrypoint.sh; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  rm -rf "\$DP/server"; \\
  cp -a /app/server "\$DP/server"; \\
  mkdir -p "\$DP/agents" "\$DP/tools"; \\
  cp /app/agents/oracle_agent.py "\$DP/agents/oracle_agent.py"; \\
  cp /app/tools/bridge.py "\$DP/tools/bridge.py"; \\
  cp /app/tools/seed_to_cuagym.py "\$DP/tools/seed_to_cuagym.py"; \\
  cp /app/tools/bridge_service.py "\$DP/tools/bridge_service.py"; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); cal_p=next(Path('/hub_dist/google_calendar_mock/assets').glob('index-*.js')); amz_p=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); uber_p=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js')); assert cal_p.name=='index-8e84e2c6.js' and amz_p.name=='index-DNSHRGfv.js' and uber_p.name=='index-DXWw629n.js', (cal_p.name, amz_p.name, uber_p.name); amz=amz_p.read_text(errors='ignore'); uber=uber_p.read_text(errors='ignore'); assert '/api/' in amz and 'btn-cancel-order-open' in amz and 'btn-schedule-when' in uber and 'food.set_schedule' in uber; print('hub overlay NEW-UI OK', len(jpgs), 'jpgs', cal_p.name, amz_p.name, uber_p.name)"; \\
  python -c "from server.tasks import TASKS; assert 'mp_051/false_premise_two_lamp_orders' in TASKS; assert 'mp_058/home_nights_dinner_avoid_bad_reviews' in TASKS; from tools.bridge import ACTIONS; assert 'food.set_schedule' in ACTIONS and 'shop.cancel_order' in ACTIONS; print('nine_mech overlay OK', len(TASKS))"
EOF

echo "[nine] Cloud Build submit → $IMAGE"
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

echo "[nine] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[nine] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[nine] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[nine] execution=$EXEC"

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
  "agent_max_steps": 80,
  "hub_dist": {
    "amazon": "index-DNSHRGfv.js",
    "calendar": "index-8e84e2c6.js",
    "uber": "index-DXWw629n.js"
  },
  "git_head": "3d7362d06772b58a2fccded8abdfdc8b5ea9451a",
  "notes": "nine-mech mp_051-058 seed0; tip-lock hub_dist wipe; schedule/cancel/address overlays"
}
EOF
echo "[nine] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
