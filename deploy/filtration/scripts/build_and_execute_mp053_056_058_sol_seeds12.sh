#!/usr/bin/env bash
# mp_053 + mp_056 + mp_058 Sol seeds 1+2 — 6 episodes ∥6 on GCP.
# Tip-lock seed-to-cua hub_dist wipe + full harness overlay (api_failure_class).
# Seed0 already scored BREAK on nine-mech-sol-seed0-20260810T233128Z.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp053-056-058-seeds12-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-6}"
TASKS="${TASKS:-6}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp053-056-058-seeds12-${TS}}"
JOB="${JOB:-filtration-mp053-056-058-seeds12}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp053_056_058_sol_seeds12_6.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp053_056_058_seeds12_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp053-056-058-seeds12-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp053_056_058_seeds12_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp053_056_058_sol_seeds12_6.json}"

echo "[s12] BASE=$BASE_IMAGE"
echo "[s12] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[s12] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# Tip lock
cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || { echo "FATAL: HEAD != origin/seed-to-cua-gym tip"; exit 1; }
GIT_HEAD="$(git rev-parse HEAD)"
echo "[s12] tip-lock OK $GIT_HEAD"

# Mirror task modules → gym SoT (bookkeeping)
echo "[s12] mirroring mp_053/056/058 → $GYM_ROOT (bookkeeping)"
for f in mp_053.py mp_056.py mp_058.py; do
  if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
    cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
  fi
done

cd "$RUNNER"
python3 - <<'PY'
import copy
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite

need = [
    "mp_053/cancel_coffee_ambiguous",
    "mp_056/desk_address_change_ofd_infeasible",
    "mp_058/home_nights_dinner_avoid_bad_reviews",
]
assert "Cancel my coffee order" in BRIEFS.get("mp_053", "")
assert "desk order" in BRIEFS.get("mp_056", "").lower()
assert "five nights" in BRIEFS.get("mp_058", "").lower()
for tid in need:
    assert tid in TASKS, tid
    for seed in (1, 2):
        w = make_task(tid, seed)
        init = copy.deepcopy(w)
        suite = build_suite(tid)
        probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
        r = suite.evaluate(probe, current_step=0)
        assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, seed, r)
print("preflight OK seeds 1+2 fail-on-initial for", len(need), "tasks")
from pathlib import Path
main = Path("server/main.py").read_text()
assert "/_harness/world_full" in main
bridge = Path("tools/bridge.py").read_text()
for a in ("food.set_schedule", "shop.cancel_order", "shop.change_order_address"):
    assert a in bridge, a
print("bridge actions + world_full OK")
print("briefs:", {k: BRIEFS.get(k) for k in ("mp_053", "mp_056", "mp_058")})
PY

# Wipe-rebuild hub_dist from seed-to-cua tip websites
HUB="$RUNNER" REBUILD=1 bash "$HERE/scripts/prepare_hub_dist.sh"
CAL_JS="$(find "$HERE/hub_dist/google_calendar_mock/assets" -name 'index-*.js' -print -quit)"
AMZ_JS="$(find "$HERE/hub_dist/amazon_mock/assets" -name 'index-*.js' -print -quit)"
UBER_JS="$(find "$HERE/hub_dist/uber_eats_mock/assets" -name 'index-*.js' -print -quit)"
test -n "$CAL_JS" && test -n "$AMZ_JS" && test -n "$UBER_JS"
AMZ_JS_PIN="$(basename "$AMZ_JS")"
CAL_JS_PIN="$(basename "$CAL_JS")"
UBER_JS_PIN="$(basename "$UBER_JS")"
python3 - <<PY
from pathlib import Path
cal_p, amz_p, uber_p = Path("$CAL_JS"), Path("$AMZ_JS"), Path("$UBER_JS")
cal, amz, uber = (p.read_text(errors="ignore") for p in (cal_p, amz_p, uber_p))
assert "input-edit-start" in cal and 'type:"time"' in cal, "calendar hub_dist missing split time UI"
assert "Warranty expired" in amz, "amazon hub_dist missing warranty banner"
assert "/api/" in amz, "FATAL: amazon hub_dist missing /api/ — looks like legacy/CUA bake"
assert "btn-cancel-order-open" in amz, "amazon missing cancel UI"
assert "btn-schedule-when" in uber and "btn-schedule-slot" in uber, "uber missing schedule-ahead UI"
assert "food.set_schedule" in uber, "uber missing durable food.set_schedule wiring"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber, f"FATAL: remote hub URL baked in: {bad}"
print("hub_dist NEW-UI OK (seed-to-cua websites)")
print("  calendar:", cal_p.name)
print("  amazon:", amz_p.name)
print("  uber:", uber_p.name)
PY
echo "[s12] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN"

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/tools" "$CTX/harness" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$RUNNER/tools/bridge.py" "$CTX/tools/bridge.py"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$RUNNER/tools/bridge_service.py" "$CTX/tools/bridge_service.py"
# Full harness — PYTHONPATH=/app shadows site-packages; partial copy breaks imports.
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/harness/" "$CTX/harness/"
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
COPY harness /app/harness
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
  rm -rf "\$DP/harness"; \\
  cp -a /app/harness "\$DP/harness"; \\
  python -c "from harness.api_failure_class import classify_api_failure; from harness.auth import harness_headers; print('harness overlay OK')"; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); cal_p=next(Path('/hub_dist/google_calendar_mock/assets').glob('index-*.js')); amz_p=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); uber_p=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js')); assert amz_p.name=='${AMZ_JS_PIN}' and cal_p.name=='${CAL_JS_PIN}' and uber_p.name=='${UBER_JS_PIN}', (amz_p.name, cal_p.name, uber_p.name); amz=amz_p.read_text(errors='ignore'); uber=uber_p.read_text(errors='ignore'); assert '/api/' in amz and 'btn-cancel-order-open' in amz and 'btn-schedule-when' in uber and 'food.set_schedule' in uber; print('hub overlay NEW-UI OK', len(jpgs), 'jpgs', cal_p.name, amz_p.name, uber_p.name)"; \\
  python -c "from server.tasks import TASKS; assert 'mp_053/cancel_coffee_ambiguous' in TASKS; assert 'mp_056/desk_address_change_ofd_infeasible' in TASKS; assert 'mp_058/home_nights_dinner_avoid_bad_reviews' in TASKS; from tools.bridge import ACTIONS; assert 'food.set_schedule' in ACTIONS and 'shop.cancel_order' in ACTIONS; print('mp053_056_058 seeds12 overlay OK', len(TASKS))"
EOF

echo "[s12] Cloud Build submit → $IMAGE"
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

echo "[s12] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[s12] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[s12] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[s12] execution=$EXEC"

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
    "amazon": "$AMZ_JS_PIN",
    "calendar": "$CAL_JS_PIN",
    "uber": "$UBER_JS_PIN"
  },
  "git_head": "$GIT_HEAD",
  "seed0_prior": "nine-mech-sol-seed0-20260810T233128Z",
  "notes": "mp_053/056/058 Sol seeds 1+2; tip-lock hub_dist wipe; full harness overlay; headless GCP"
}
EOF
echo "[s12] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
