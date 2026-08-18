#!/usr/bin/env bash
# mp_060 / cousin_dinner_email_calendar_schedule — Sol gpt-5.6-sol seed0 on GCP.
# Newest seed-to-cua hub_dist only (never CUA-Gym-Hub vite / legacy).
# Wipe-rebuilds hub_dist from tip websites; overlays FULL harness package
# (partial runner-only overlay shadows PYTHONPATH and drops api_failure_class).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp060-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-1}"
TASKS="${TASKS:-1}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp060-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp060-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp060_cousin_dinner_schedule_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp060_friday_rewrite_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp060-friday-rewrite-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp060_friday_rewrite_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp060_cousin_dinner_schedule_sol_seed0.json}"

echo "[mp060] BASE=$BASE_IMAGE"
echo "[mp060] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB"

# Mirror task module → gym SoT (bookkeeping)
if [ -f "$RUNNER/server/mp_060.py" ] && [ -d "$GYM_ROOT/server" ]; then
  cp "$RUNNER/server/mp_060.py" "$GYM_ROOT/server/mp_060.py" || true
fi
if [ -f "$RUNNER/harness/runner.py" ] && [ -d "$GYM_ROOT/harness" ]; then
  cp "$RUNNER/harness/runner.py" "$GYM_ROOT/harness/runner.py" || true
fi

cd "$RUNNER"
PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" - <<'PY'
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite
from server.apps.food import mutations as F
from server.mp_060 import FRI, GOLD_DISH, GOLD_REST, BUDGET
import copy

tid = "mp_060/cousin_dinner_email_calendar_schedule"
assert tid in TASKS, tid
assert "mp_060" in BRIEFS
w = make_task(tid, 0)
assert w.food.enable_schedule_ahead is True
assert "vegetarian" in BRIEFS["mp_060"].lower()
assert not any(e.day == FRI for e in w.calendar.events.values()), "Friday must be clear"
init = copy.deepcopy(w)
suite = build_suite(tid)
probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
r = suite.evaluate(probe, current_step=0)
assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, r)
print("preflight OK fail-on-initial for", tid)

# Durable schedule-ahead probe (Friday gold night)
w2 = make_task(tid, 0)
assert F.add_dish(w2.food, dish_id=GOLD_DISH, restaurant_id=GOLD_REST).get("ok")
assert F.set_scheduled_delivery(w2.food, FRI).get("scheduled_delivery") == FRI
placed = F.place_food_order(w2, scheduled_delivery=FRI)
assert placed.get("ok") and placed.get("scheduled_delivery") == FRI
assert w2.food.orders[placed["order_id"]].scheduled_delivery == FRI
assert float(w2.food.orders[placed["order_id"]].total) < BUDGET
print("preflight OK durable scheduled_delivery=", FRI)

from harness.runner import _mock_start_path
assert _mock_start_path("food", f"/food/restaurant/{GOLD_REST}") == f"/store/{GOLD_REST}"
print("preflight OK food restaurant deep-link map")
PY

# Wipe-rebuild hub_dist from seed-to-cua tip websites (same-origin /api/)
HUB="$RUNNER" REBUILD=1 bash "$HERE/scripts/prepare_hub_dist.sh"
CAL_JS="$(find "$HERE/hub_dist/google_calendar_mock/assets" -name 'index-*.js' -print -quit)"
AMZ_JS="$(find "$HERE/hub_dist/amazon_mock/assets" -name 'index-*.js' -print -quit)"
UBER_JS="$(find "$HERE/hub_dist/uber_eats_mock/assets" -name 'index-*.js' -print -quit)"
MAIL_JS="$(find "$HERE/hub_dist/gmail_mock/assets" -name 'index-*.js' -print -quit)"
test -n "$CAL_JS" && test -n "$AMZ_JS" && test -n "$UBER_JS" && test -n "$MAIL_JS"
AMZ_JS_PIN="$(basename "$AMZ_JS")"
CAL_JS_PIN="$(basename "$CAL_JS")"
UBER_JS_PIN="$(basename "$UBER_JS")"
MAIL_JS_PIN="$(basename "$MAIL_JS")"
python3 - <<PY
from pathlib import Path
cal_p, amz_p, uber_p, mail_p = (Path(p) for p in ("$CAL_JS", "$AMZ_JS", "$UBER_JS", "$MAIL_JS"))
cal, amz, uber, mail = (p.read_text(errors="ignore") for p in (cal_p, amz_p, uber_p, mail_p))
assert "/api/" in amz, "FATAL: amazon hub_dist missing /api/"
assert "btn-schedule-when" in uber and "btn-schedule-slot-" in uber, "schedule-ahead affordance missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name)
PY
echo "[mp060] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN"

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
  python -c "from harness.api_failure_class import classify_api_failure; from harness.auth import harness_headers; from harness.runner import _mock_start_path; assert _mock_start_path('food','/food/restaurant/r_x')=='/store/r_x'; print('harness overlay OK')"; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); uber_p=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js')); assert uber_p.name=='${UBER_JS_PIN}', uber_p.name; uber=uber_p.read_text(errors='ignore'); assert 'btn-schedule-when' in uber and 'btn-schedule-slot-' in uber; print('hub overlay OK', uber_p.name)"; \\
  python -c "from server.tasks import TASKS, make_task; assert 'mp_060/cousin_dinner_email_calendar_schedule' in TASKS; w=make_task('mp_060/cousin_dinner_email_calendar_schedule',0); assert w.food.enable_schedule_ahead is True; print('mp060 overlay OK', len(TASKS))"
EOF

echo "[mp060] Cloud Build submit → $IMAGE"
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

echo "[mp060] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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

mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS}
EOF
  echo "[mp060] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp060] execution=$EXEC"

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
    "uber": "$UBER_JS_PIN",
    "mail": "$MAIL_JS_PIN"
  },
  "notes": "mp_060 Friday rewrite: Jamie email pottery 1-8pm, Thu dentist, veg for-two under 30, schedule-ahead Friday; tip-UI hub_dist wipe; enable_schedule_ahead=True"
}
EOF
echo "[mp060] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
