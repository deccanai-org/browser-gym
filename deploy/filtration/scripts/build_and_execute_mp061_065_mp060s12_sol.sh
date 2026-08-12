#!/usr/bin/env bash
# mp_061–065 Sol seed0 + mp_060 seeds 1+2 — 7 episodes ∥7 on GCP.
# Tip-lock seed-to-cua hub_dist wipe + full harness overlay.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp061-065-mp060s12-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-7}"
TASKS="${TASKS:-7}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp061-065-mp060s12-${TS}}"
JOB="${JOB:-filtration-mp061-065-mp060s12}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp061_065_s0_and_mp060_s12_sol.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp061_065_mp060s12_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp061-065-mp060s12-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp061_065_mp060s12_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp061_065_s0_and_mp060_s12_sol.json}"

echo "[mp061+] BASE=$BASE_IMAGE"
echo "[mp061+] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp061+] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp061+] runner HEAD $GIT_HEAD"

# Mirror task modules → gym SoT (bookkeeping)
for f in mp_060.py mp_061.py mp_062.py mp_063.py mp_064.py mp_065.py; do
  if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
    cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
  fi
done
cp "$RUNNER/agents/oracle_agent.py" "$GYM_ROOT/agents/oracle_agent.py" || true

cd "$RUNNER"
PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" - <<'PY'
import copy
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite

need = [
    ("mp_061/coworker_gift_pool_deadline_and_budget", 0),
    ("mp_062/return_window_and_replacement_stock", 0),
    ("mp_063/subscription_renewal_vs_upcoming_travel", 0),
    ("mp_064/split_delivery_two_recipients_one_cart", 0),
    ("mp_065/price_drop_reorder_after_original_ships", 0),
    ("mp_060/cousin_dinner_email_calendar_schedule", 1),
    ("mp_060/cousin_dinner_email_calendar_schedule", 2),
]
for tid, seed in need:
    assert tid in TASKS, tid
    w = make_task(tid, seed)
    init = copy.deepcopy(w)
    suite = build_suite(tid)
    probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
    r = suite.evaluate(probe, current_step=0)
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, seed, r)
assert "mp_061" in BRIEFS and "Priya" in BRIEFS["mp_061"]
assert "mp_064" in BRIEFS and "cart" in BRIEFS["mp_064"].lower()
w60 = make_task("mp_060/cousin_dinner_email_calendar_schedule", 1)
assert w60.food.enable_schedule_ahead is True
print("preflight OK FOI for 7 episodes")
PY

# Wipe-rebuild hub_dist from seed-to-cua tip websites
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
echo "[mp061+] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN"

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
  python -c "from harness.api_failure_class import classify_api_failure; from harness.auth import harness_headers; from harness.runner import _mock_start_path; assert _mock_start_path('food','/food/restaurant/r_x')=='/store/r_x'; print('harness overlay OK')"; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); uber_p=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js')); assert uber_p.name=='${UBER_JS_PIN}', uber_p.name; uber=uber_p.read_text(errors='ignore'); assert 'btn-schedule-when' in uber and 'btn-schedule-slot-' in uber; print('hub overlay OK', uber_p.name)"; \\
  python -c "from server.tasks import TASKS, make_task; need=['mp_061/coworker_gift_pool_deadline_and_budget','mp_062/return_window_and_replacement_stock','mp_063/subscription_renewal_vs_upcoming_travel','mp_064/split_delivery_two_recipients_one_cart','mp_065/price_drop_reorder_after_original_ships','mp_060/cousin_dinner_email_calendar_schedule']; assert all(t in TASKS for t in need); w=make_task('mp_060/cousin_dinner_email_calendar_schedule',1); assert w.food.enable_schedule_ahead is True; print('mp061+ overlay OK', len(TASKS))"
EOF

echo "[mp061+] Cloud Build submit → $IMAGE"
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

echo "[mp061+] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[mp061+] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp061+] execution=$EXEC"

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
  "notes": "mp_061-065 seed0 + mp_060 seeds1/2; full harness overlay + wipe-rebuild hub_dist; no CUA-Gym-Hub"
}
EOF
echo "[mp061+] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
