#!/usr/bin/env bash
# Build food_003 overlay image + Cloud Run Job: Sol seeds 0/1/2 in parallel (∥3).
# Syncs third-restaurant gold + Xoogle week-scroll fix onto filtration-worker base.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-food003-sol-3seed-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
TASKS="${TASKS:-3}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-food003-sol-3seed-${TS}}"
JOB="${JOB:-filtration-food003-sol-3seed}"
MANIFEST="/app/deploy/filtration/manifests/food_003_sol_3seed_3.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/food_003}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"
SYNC_FROM_GYM="${SYNC_FROM_GYM:-1}"
REBUILD_CAL="${REBUILD_CAL:-1}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-food003-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/food_003_sol_3seed_gcp}"

echo "[food003] BASE=$BASE_IMAGE"
echo "[food003] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

# --- sync food_003 from ecommerce-browser-gym ---
if [ "$SYNC_FROM_GYM" = "1" ]; then
  echo "[food003] syncing food_003.py from $GYM_ROOT"
  cp "$GYM_ROOT/server/food_003.py" "$RUNNER/server/food_003.py"
fi

# Guard: refuse old abstain / 7pm gold
if grep -q 'place no order\|before-7pm\|emailed_dietary_timing_conflict' "$RUNNER/server/food_003.py"; then
  echo "FATAL: food_003 still has old abstain / 7pm wording" >&2
  exit 1
fi
if ! grep -q 'other places are fine too' "$RUNNER/server/food_003.py"; then
  echo "FATAL: food_003 missing new brief clause" >&2
  exit 1
fi
if ! grep -q 'r_leaf\|Leaf & Grain\|d_f003_garden_bowl' "$RUNNER/server/food_003.py"; then
  echo "FATAL: food_003 missing Leaf & Grain gold" >&2
  exit 1
fi
if ! grep -q '2026-05-21T16:00:00' "$RUNNER/server/food_003.py"; then
  echo "FATAL: food_003 missing gym_now 16:00" >&2
  exit 1
fi
BRIEF_SOURCE="${BRIEF_SOURCE:-FOOD003_THIRD_RESTAURANT_CAL_VISIBLE_2026-08-09}"
echo "[food003] BRIEF_SOURCE=$BRIEF_SOURCE"

# --- rebuild Xoogle week scroll (Team Meeting visible without search) ---
if [ "$REBUILD_CAL" = "1" ]; then
  echo "[food003] building google_calendar_mock (same-origin)"
  CAL="$RUNNER/websites/google_calendar_mock"
  printf 'VITE_API_BASE=\nVITE_MOCK_ID=google_calendar_mock\n' >"$CAL/.env.production"
  ( cd "$CAL"
    [ -d node_modules ] || npm install --silent --no-audit --no-fund
    npx vite build >/dev/null )
  # Prove inverted-min fix landed (preferNow/preferCover → Math.max)
  if ! rg -q 'scrollTop=R\*we|scrollTop = .*Math\.max' "$CAL"/dist/assets/*.js \
    && ! python3 -c "
from pathlib import Path
js=next(Path('$CAL/dist/assets').glob('*.js')).read_text()
assert 'requestAnimationFrame' in js
assert '0.75' in js
assert 'Math.max' in js
# minified: R=Math.max(H,U);N.scrollTop=R*
assert 'scrollTop=' in js
print('calendar scroll markers OK')
"; then
    echo "FATAL: calendar dist missing week-scroll fix" >&2
    exit 1
  fi
  mkdir -p "$HERE/hub_dist/google_calendar_mock"
  rsync -a --delete "$CAL/dist/" "$HERE/hub_dist/google_calendar_mock/"
  echo "[food003] hub_dist/google_calendar_mock refreshed"
fi

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
from server.food_003 import BRIEF, TASK_ID, GOLD_REST, GOLD_DISH, GYM_NOW, suite_factories
from server.tasks import make_task
from server.verifiers import Probe, build_suite

assert TASK_ID == "food_003/team_dinner_named_restaurants"
assert "other places are fine too" in BRIEF
assert GOLD_REST == "r_leaf" and GOLD_DISH == "d_f003_garden_bowl"
assert GYM_NOW.startswith("2026-05-21T16:00")
sf = suite_factories()
assert TASK_ID in sf
w0 = make_task(TASK_ID, seed=0)
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
assert success is False and score == 0.0, (success, score)
assert "r_leaf" in w0.food.restaurants
assert w0.calendar.events["ev_food003_team_meeting"].start == "18:30"
print("preflight OK:", BRIEF[:72], "...")
print("fail-on-initial 0.0; gold rest", GOLD_REST, "gym_now", GYM_NOW)
PY

# --- stage overlay context ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist/google_calendar_mock"
cp "$RUNNER/server/food_003.py" "$CTX/server/food_003.py"
cp "$HERE/manifests/food_003_tasks.txt" "$CTX/deploy/filtration/manifests/"
cp "$HERE/manifests/food_003_sol_3seed_3.json" "$CTX/deploy/filtration/manifests/"
rsync -a "$HERE/hub_dist/google_calendar_mock/" "$CTX/hub_dist/google_calendar_mock/"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server/food_003.py /app/server/food_003.py
COPY deploy/filtration/manifests/food_003_tasks.txt /app/deploy/filtration/manifests/food_003_tasks.txt
COPY deploy/filtration/manifests/food_003_sol_3seed_3.json /app/deploy/filtration/manifests/food_003_sol_3seed_3.json
COPY hub_dist/google_calendar_mock /hub_dist/google_calendar_mock
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
RUN set -e; \\
  DP="\$(python -c "import sys; print([p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')][0])")"; \\
  echo "dist-packages=\$DP"; \\
  cp /app/server/food_003.py "\$DP/server/food_003.py"; \\
  python -c "from server.food_003 import BRIEF, GOLD_REST, GYM_NOW; assert 'other places are fine too' in BRIEF; assert GOLD_REST=='r_leaf'; assert GYM_NOW.startswith('2026-05-21T16:00'); print('food_003 OK', BRIEF[:60])"; \\
  python -c "from pathlib import Path; js=next(Path('/hub_dist/google_calendar_mock/assets').glob('index-*.js')); t=js.read_text(); assert 'requestAnimationFrame' in t and '0.75' in t; print('calendar hub OK', js.name, 'bytes', js.stat().st_size)"
EOF

echo "[food003] Cloud Build submit → $IMAGE"
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

echo "[food003] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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

echo "[food003] RUN_ID=$RUN_ID"

mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":3,"parallelism":$PARALLELISM,"brief_source":"$BRIEF_SOURCE"}
EOF
  echo "[food003] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[food003] execution=$EXEC"

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
  "task_id": "food_003/team_dinner_named_restaurants",
  "gold_restaurant": "Leaf & Grain",
  "gold_dish": "Sesame-Free Garden Bowl",
  "gym_now": "2026-05-21T16:00:00",
  "meeting": "18:30-20:30"
}
EOF
echo "[food003] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
