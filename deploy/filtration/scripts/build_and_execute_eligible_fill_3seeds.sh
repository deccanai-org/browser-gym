#!/usr/bin/env bash
# Eligible Suite — fill missing tip-UI Sol seeds 1+2 (16 episodes ∥16).
# Skip tasks already tip-UI 3/3 BREAK: md_002, mp_040, mp_048, mp_056, mp_060.
# Tip-lock seed-to-cua hub_dist wipe + full harness overlay. Headless GCP only.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-eligible-fill-3seeds-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-16}"
TASKS="${TASKS:-16}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-eligible-fill-3seeds-${TS}}"
JOB="${JOB:-filtration-eligible-fill-3seeds}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/eligible_fill_3seeds_missing_16.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/eligible_fill_3seeds_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-eligible-fill-3seeds-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/eligible_fill_3seeds_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/eligible_fill_3seeds_missing_16.json}"

echo "[fill] BASE=$BASE_IMAGE"
echo "[fill] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || { echo "FATAL: HEAD != origin/seed-to-cua-gym tip"; exit 1; }
GIT_HEAD="$(git rev-parse HEAD)"
echo "[fill] tip-lock OK $GIT_HEAD"

# Mirror task modules → gym SoT (bookkeeping)
for f in mail_002.py mp_053.py mp_058.py mp_059.py mp_061.py mp_062.py mp_063.py mp_064.py; do
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
    "mail_002/false_warranty_never_bought",
    "mp_053/cancel_coffee_ambiguous",
    "mp_058/home_nights_dinner_avoid_bad_reviews",
    "mp_059/mom_gift_watch_false_premise",
    "mp_061/coworker_gift_pool_deadline_and_budget",
    "mp_062/return_window_and_replacement_stock",
    "mp_063/subscription_renewal_vs_upcoming_travel",
    "mp_064/split_delivery_two_recipients_one_cart",
]
# dual-beans retune must be present
from server import mp_053 as m53
assert getattr(m53, "ORDER_BEANS_VM", None) == "VM-MP053-BEANS", "mp_053 dual-beans missing"
assert "Andean Peak" in getattr(m53, "NAME_BEANS_VM", ""), m53.NAME_BEANS_VM
for tid in need:
    assert tid in TASKS, tid
    for seed in (1, 2):
        w = make_task(tid, seed)
        init = copy.deepcopy(w)
        suite = build_suite(tid)
        probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
        r = suite.evaluate(probe, current_step=0)
        assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, seed, r)
print("preflight OK fail-on-initial for", len(need), "tasks × seeds 1+2")
PY

# Wipe-rebuild hub_dist from seed-to-cua tip websites
HUB="$RUNNER" REBUILD="${REBUILD:-1}" bash "$HERE/scripts/prepare_hub_dist.sh"
CAL_JS="$(find "$HERE/hub_dist/google_calendar_mock/assets" -name 'index-*.js' -print -quit)"
AMZ_JS="$(find "$HERE/hub_dist/amazon_mock/assets" -name 'index-*.js' -print -quit)"
UBER_JS="$(find "$HERE/hub_dist/uber_eats_mock/assets" -name 'index-*.js' -print -quit)"
MAIL_JS="$(find "$HERE/hub_dist/gmail_mock/assets" -name 'index-*.js' -print -quit)"
EBAY_JS="$(find "$HERE/hub_dist/ebay_mock/assets" -name 'index-*.js' -print -quit)"
test -n "$CAL_JS" && test -n "$AMZ_JS" && test -n "$UBER_JS" && test -n "$MAIL_JS" && test -n "$EBAY_JS"
AMZ_JS_PIN="$(basename "$AMZ_JS")"
CAL_JS_PIN="$(basename "$CAL_JS")"
UBER_JS_PIN="$(basename "$UBER_JS")"
MAIL_JS_PIN="$(basename "$MAIL_JS")"
EBAY_JS_PIN="$(basename "$EBAY_JS")"
python3 - <<PY
from pathlib import Path
cal_p, amz_p, uber_p, mail_p, ebay_p = (Path(p) for p in ("$CAL_JS", "$AMZ_JS", "$UBER_JS", "$MAIL_JS", "$EBAY_JS"))
cal, amz, uber, mail, ebay = (p.read_text(errors="ignore") for p in (cal_p, amz_p, uber_p, mail_p, ebay_p))
assert "/api/" in amz, "FATAL: amazon hub_dist missing /api/"
assert "btn-cancel-order-open" in amz, "amazon missing cancel UI"
assert "btn-schedule-when" in uber and "btn-schedule-slot" in uber, "uber missing schedule-ahead UI"
assert "food.set_schedule" in uber, "uber missing durable food.set_schedule wiring"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[fill] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/tools" "$CTX/harness" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
cp "$RUNNER/tools/bridge.py" "$CTX/tools/bridge.py"
cp "$RUNNER/tools/seed_to_cuagym.py" "$CTX/tools/seed_to_cuagym.py"
cp "$RUNNER/tools/bridge_service.py" "$CTX/tools/bridge_service.py"
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
  python -c "from server.tasks import TASKS; need=['mail_002/false_warranty_never_bought','mp_053/cancel_coffee_ambiguous','mp_058/home_nights_dinner_avoid_bad_reviews','mp_059/mom_gift_watch_false_premise','mp_061/coworker_gift_pool_deadline_and_budget','mp_062/return_window_and_replacement_stock','mp_063/subscription_renewal_vs_upcoming_travel','mp_064/split_delivery_two_recipients_one_cart']; assert all(t in TASKS for t in need); from server import mp_053 as m; assert m.ORDER_BEANS_VM=='VM-MP053-BEANS'; print('eligible fill overlay OK', len(TASKS))"
EOF

echo "[fill] Cloud Build submit → $IMAGE"
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

echo "[fill] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[fill] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[fill] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[fill] execution=$EXEC"

cat >"$META_DIR/run_meta_${RUN_ID}.json" <<EOF
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
    "mail": "$MAIL_JS_PIN",
    "ebay": "$EBAY_JS_PIN"
  },
  "git_head": "$GIT_HEAD",
  "notes": "Eligible fill missing Sol seeds 1+2 (16 eps); tip-lock hub_dist wipe; full harness; headless GCP; skip tip-UI 3/3 BREAK tasks"
}
EOF
echo "[fill] wrote $META_DIR/run_meta_${RUN_ID}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
