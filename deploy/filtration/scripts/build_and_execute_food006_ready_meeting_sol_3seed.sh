#!/usr/bin/env bash
# food_006 ready-when-meeting-starts retune — GCP Sol seeds 0/1/2 in parallel.
# Overlay: food_006 + food Dish.eta_label / place-order ETA + seed_to_cuagym
# dish etaLabel + rebuilt GymEats hub_dist (clock ETA + imageUrl).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-food006-ready-meeting-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
N_CLOUD_TASKS="${N_CLOUD_TASKS:-${CLOUD_RUN_TASKS:-3}}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-food006-ready-meeting-${TS}}"
JOB="${JOB:-filtration-food006-ready-meeting}"
MANIFEST="/app/deploy/filtration/manifests/food006_ready_meeting_sol_3seed.json"
GCS_PREFIX="${GCS_PREFIX:-filtration/food_006_ready_meeting}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"
SYNC_FROM_GYM="${SYNC_FROM_GYM:-1}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-food006-ready-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/food006_ready_meeting_sol_gcp}"
MANIFEST_LOCAL="$HERE/manifests/food006_ready_meeting_sol_3seed.json"

echo "[food006] BASE=$BASE_IMAGE"
echo "[food006] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM n_tasks=$N_CLOUD_TASKS"

if [ "$SYNC_FROM_GYM" = "1" ]; then
  echo "[food006] syncing food_006 from $GYM_ROOT (state/mutations already patched in runner)"
  cp "$GYM_ROOT/server/food_006.py" "$RUNNER/server/food_006.py"
fi

# Guard: new brief + wine/alcohol Sakura decoy (not false halal late platter)
if ! grep -q 'ready when the meeting starts' "$RUNNER/server/food_006.py"; then
  echo "FATAL: food_006 missing ready-when-meeting-starts brief" >&2
  exit 1
fi
if ! grep -q 'd_f006_wine_chicken_platter\|WINE_CHICKEN_PLATTER\|white wine and sake' "$RUNNER/server/food_006.py"; then
  echo "FATAL: food_006 missing wine/sake Sakura dietary decoy" >&2
  exit 1
fi
if grep -q 'Halal Grilled Chicken Platter\|Halal-certified grilled chicken.*no alcohol' "$RUNNER/server/food_006.py"; then
  echo "FATAL: food_006 still has false-halal Sakura copy" >&2
  exit 1
fi
if ! grep -q 'eta_label: str | None' "$RUNNER/server/apps/food/state.py"; then
  echo "FATAL: Dish.eta_label missing" >&2
  exit 1
fi
if ! rg -q 'Arrives by ~|Arrives ~' "$HERE/hub_dist/uber_eats_mock/assets/"*.js; then
  echo "FATAL: hub_dist uber_eats missing clock ETA chrome" >&2
  exit 1
fi
if ! rg -q 'menu-item__photo' "$HERE/hub_dist/uber_eats_mock/assets/"*.js; then
  echo "FATAL: hub_dist uber_eats missing imageUrl photo path" >&2
  exit 1
fi
if ! rg -q 'customizationGroups' "$HERE/hub_dist/uber_eats_mock/assets/"*.js; then
  echo "FATAL: hub_dist uber_eats missing ItemModal customizationGroups safety" >&2
  exit 1
fi
if ! rg -q 'menu-item__add' "$HERE/hub_dist/uber_eats_mock/assets/"*.css; then
  echo "FATAL: hub_dist uber_eats missing styled menu-item__add (clickable +)" >&2
  exit 1
fi

BRIEF_SOURCE="${BRIEF_SOURCE:-FOOD006_READY_WHEN_MEETING_STARTS_2026-08-10}"
echo "[food006] BRIEF_SOURCE=$BRIEF_SOURCE"

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
import copy
from server.food_006 import BRIEF, TASK_ID, WINE_CHICKEN_PLATTER, GOLD_DISH, GYM_NOW
from server.tasks import make_task, TASKS
from server.verifiers import Probe, build_suite
from tools.seed_to_cuagym import transform_food

assert TASK_ID in TASKS
assert "ready when the meeting starts" in BRIEF
w0 = make_task(TASK_ID, 0)
assert w0.shop.task_brief == BRIEF
wine = next(d for d in w0.food.restaurants["r_sushi"].dishes if d.id == WINE_CHICKEN_PLATTER)
assert wine.eta_label == "5:50 PM"
assert "white wine" in wine.description.lower() and "alcohol" in wine.description.lower()
assert "halal-certified" not in wine.description.lower()
proj = transform_food(w0.food.to_json(), TASK_ID)
mi = {m["id"]: m for m in proj["menuItems"]}
assert mi[WINE_CHICKEN_PLATTER]["etaLabel"] == "5:50 PM"
assert mi[GOLD_DISH]["etaLabel"] == "5:40 PM"
assert not any(str(m["id"]).startswith("amb_") for m in proj["menuItems"])
suite = build_suite(TASK_ID)
init = copy.deepcopy(w0)
probe = Probe(state=w0.shop, url="/", initial_state=init.shop, world=w0, initial_world=init)
r = suite.evaluate(probe, current_step=0)
assert r.get("success") is False and float(r.get("score") or 0) == 0.0, r
ms = {m.name: m for m in suite.milestones}
assert ms["ordered_sakura_alcohol_platter"].forbidden is True
print("preflight OK fail-on-initial 0.0; gym_now", GYM_NOW)
print("BRIEF:", BRIEF[:90], "...")
print("wine decoy:", wine.name)
PY

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server/apps/food" "$CTX/tools" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
cp "$RUNNER/server/food_006.py" "$CTX/server/food_006.py"
cp "$RUNNER/server/apps/food/state.py" "$CTX/server/apps/food/state.py"
cp "$RUNNER/server/apps/food/mutations.py" "$CTX/server/apps/food/mutations.py"
cp "$RUNNER/server/apps/food/routes.py" "$CTX/server/apps/food/routes.py"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$RUNNER/tools/bridge.py" "$CTX/tools/bridge.py"
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/food006_ready_meeting_sol_3seed.json"
# Fresh GymEats only (no stale index-*.js leftovers)
rm -rf "$CTX/hub_dist/uber_eats_mock"
rsync -a "$HERE/hub_dist/uber_eats_mock/" "$CTX/hub_dist/uber_eats_mock/"
if [ -d "$HERE/hub_dist/google_calendar_mock" ]; then
  rsync -a "$HERE/hub_dist/google_calendar_mock/" "$CTX/hub_dist/google_calendar_mock/"
fi

# Quoted heredoc so host bash does not eat Dockerfile \`\\\` line continuations.
{
  echo "FROM ${BASE_IMAGE}"
  cat <<'EOS'
COPY server/food_006.py /app/server/food_006.py
COPY server/apps/food/state.py /app/server/apps/food/state.py
COPY server/apps/food/mutations.py /app/server/apps/food/mutations.py
COPY server/apps/food/routes.py /app/server/apps/food/routes.py
COPY tools/seed_to_cuagym.py /app/tools/seed_to_cuagym.py
COPY tools/bridge.py /app/tools/bridge.py
COPY deploy/filtration/manifests/food006_ready_meeting_sol_3seed.json /app/deploy/filtration/manifests/food006_ready_meeting_sol_3seed.json
COPY hub_dist /hub_dist
ENV PYTHONPATH=/app
ENV AGENT_MAX_STEPS=80
ENV PYTHONUNBUFFERED=1
RUN python -c "import sys,shutil,pathlib; dp=next(p for p in sys.path if p.endswith('dist-packages') or p.endswith('site-packages')); print('dist-packages',dp); shutil.copy('/app/server/food_006.py', dp+'/server/food_006.py'); pathlib.Path(dp+'/server/apps/food').mkdir(parents=True, exist_ok=True); pathlib.Path(dp+'/tools').mkdir(parents=True, exist_ok=True); shutil.copy('/app/server/apps/food/state.py', dp+'/server/apps/food/state.py'); shutil.copy('/app/server/apps/food/mutations.py', dp+'/server/apps/food/mutations.py'); shutil.copy('/app/server/apps/food/routes.py', dp+'/server/apps/food/routes.py'); shutil.copy('/app/tools/seed_to_cuagym.py', dp+'/tools/seed_to_cuagym.py'); shutil.copy('/app/tools/bridge.py', dp+'/tools/bridge.py')" \
 && python -c "from server.food_006 import BRIEF, WINE_CHICKEN_PLATTER; assert 'ready when the meeting starts' in BRIEF; assert WINE_CHICKEN_PLATTER=='d_f006_wine_chicken_platter'; print('food_006 OK', BRIEF[:70])" \
 && python -c "from server.apps.food.state import Dish; from server.apps.food import mutations as F; assert hasattr(F,'set_dish_qty') and hasattr(F,'remove_dish'); print('Dish.eta_label OK', 'eta_label' in Dish.__dataclass_fields__)" \
 && python -c "from pathlib import Path; js=max(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js'), key=lambda p: p.stat().st_size); t=js.read_text(); assert 'Arrives' in t and 'etaLabel' in t and 'menu-item__photo' in t and 'customizationGroups' in t, (js.name, len(t)); css=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.css')); assert 'menu-item__add' in css.read_text(); print('uber_eats hub OK', js.name, js.stat().st_size, css.name)"
EOS
} >"$CTX/Dockerfile"

echo "[food006] Cloud Build submit → $IMAGE"
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

echo "[food006] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
gcloud run jobs "$action" "$JOB" \
  --image="$IMAGE" \
  --region="$REGION" \
  --project="$PROJECT" \
  --tasks="$N_CLOUD_TASKS" \
  --parallelism="$PARALLELISM" \
  --task-timeout="${TIMEOUT}s" \
  --max-retries=1 \
  --memory="$MEMORY" \
  --cpu="$CPU" \
  --set-env-vars="MANIFEST_PATH=${MANIFEST},GCS_BUCKET=${BUCKET},GCS_PREFIX=${GCS_PREFIX},RUN_ID=${RUN_ID},MODEL=gpt-5.6-sol,AGENT=openai_pixel,HARNESS_TOKEN=bridged-filtration,FAIL_ON_ERROR=0,AGENT_MAX_STEPS=80,PYTHONUNBUFFERED=1" \
  --set-secrets="OPENAI_API_KEY=${OPENAI_SECRET}:latest"

echo "[food006] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"
if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":3,"parallelism":$PARALLELISM,"brief_source":"$BRIEF_SOURCE"}
EOF
  echo "[food006] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[food006] execution=$EXEC"

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
  "task_id": "food_006/design_review_shared_platter",
  "clock_eta_ui": true,
  "dish_level_late_eta": "6:15 PM",
  "meeting_start": "18:00"
}
EOF
echo "[food006] wrote $META_DIR/run_meta.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
