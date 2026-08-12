#!/usr/bin/env bash
# mp_092 + mp_093 + mp_094 + mp_099 — Sol seed0 (one job, four tasks).
# Tip-lock hub_dist + full harness overlay. Does NOT touch Eligible Suite.
# Does NOT smash in-flight mp_121–129 (job filtration-mp121-129-sol-seed0).
# Does NOT push GitHub Pages.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp092-094-099-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-4}"
TASKS="${TASKS:-4}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp092-094-099-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp092-094-099-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp092_093_094_099_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp092_094_099_20260812}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp092-094-099-sol-seed0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp092_094_099_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp092_093_094_099_sol_seed0.json}"

echo "[mp092-094-099] BASE=$BASE_IMAGE"
echo "[mp092-094-099] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB"
test "$JOB" != "filtration-mp121-129-sol-seed0"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp092-094-099] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp092-094-099] runner HEAD $GIT_HEAD"

# Mirror task modules gym SoT → runner. Do NOT copy mp_121–129.
for id in 092 093 094 099; do
  if [ -f "$GYM_ROOT/server/mp_${id}.py" ]; then
    cp "$GYM_ROOT/server/mp_${id}.py" "$RUNNER/server/mp_${id}.py"
  fi
done
if [ -f "$GYM_ROOT/agents/oracle_agent.py" ]; then
  cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py"
fi

PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" - <<'PY'
import copy
from dataclasses import asdict
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite
from tools.seed_to_cuagym import transform_calendar, transform_market
import server.mp_092 as t092
import server.mp_093 as t093
import server.mp_094 as t094
import server.mp_099 as t099

for mod, key in ((t092, "mp_092"), (t093, "mp_093"), (t094, "mp_094"), (t099, "mp_099")):
    assert mod.TASK_ID in TASKS, mod.TASK_ID
    assert key in BRIEFS
    w = make_task(mod.TASK_ID, 0)
    init = copy.deepcopy(w)
    r = build_suite(mod.TASK_ID).evaluate(
        Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init),
        current_step=0,
    )
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (mod.TASK_ID, r)

w92 = make_task(t092.TASK_ID, 0)
assert "helmet" not in (w92.market.products[t092.STAND_ID].description or "").lower()
mj = transform_market(asdict(w92.market))
listing = next(x for x in mj["listings"] if x["id"] == t092.STAND_ID)
assert listing["sellerId"] == t092.SELLER_ID

w93 = make_task(t093.TASK_ID, 0)
assert w93.calendar.events[t093.INSTANCE_ID].status == "cancelled"
assert w93.calendar.gym_now == t093.GYM_NOW
cj = transform_calendar(asdict(w93.calendar))
this = next(e for e in cj["events"] if e.get("id") == t093.INSTANCE_ID)
assert this.get("status") == "cancelled"
assert "Order lunch for the team meeting on Thursday" in (BRIEFS.get("mp_093") or "")

w94 = make_task(t094.TASK_ID, 0)
assert w94.shop.promotions[t094.EXPIRED].expired is True
assert t094.EXPIRY_LABEL in w94.mail.inbox[t094.PROMO_MAIL].body

w99 = make_task(t099.TASK_ID, 0)
assert w99.market.silent_noop_first_listing is True
print("preflight OK mp_092/093/094/099 FOI + seed facts")
PY

# Tip-lock existing hub_dist (no GitHub Pages push; no smash of in-flight jobs).
HUB_REBUILD="${HUB_REBUILD:-0}"
if [ "$HUB_REBUILD" = "1" ]; then
  HUB="$RUNNER" REBUILD=1 bash "$HERE/scripts/prepare_hub_dist.sh"
else
  echo "[mp092-094-099] HUB_REBUILD=0 — using existing deploy/filtration/hub_dist (tip-lock)"
  test -d "$HERE/hub_dist/ebay_mock/assets"
  test -d "$HERE/hub_dist/gmail_mock/assets"
  test -d "$HERE/hub_dist/google_calendar_mock/assets"
fi
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
assert "mail.send" in mail or "btn-send" in mail, "mail send affordance missing"
assert "cancelled" in cal.lower() or "Canceled" in cal, "calendar cancelled-instance UI missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[mp092-094-099] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

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
  python -c "from pathlib import Path; cal_p=next(Path('/hub_dist/google_calendar_mock/assets').glob('index-*.js')); assert cal_p.name=='${CAL_JS_PIN}', cal_p.name; print('hub overlay OK', cal_p.name)"; \\
  python -c "from server.tasks import TASKS, make_task; tids=['mp_092/valuemart_leroy_bike_stand_helmet_absence_email','mp_093/thursday_team_meeting_cancelled_lunch_email','mp_094/shopgym_razer_expired_promo_email','mp_099/silent_noop_valuemart_monitor_comps']; assert all(t in TASKS for t in tids); w=make_task(tids[1],0); assert w.calendar.events['ev_mp093_team_this'].status=='cancelled'; print('mp092-094-099 overlay OK', len(TASKS))"
EOF

echo "[mp092-094-099] Cloud Build submit → $IMAGE"
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

echo "[mp092-094-099] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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
  cat >"$META_DIR/run_meta_${RUN_ID}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS}
EOF
  echo "[mp092-094-099] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp092-094-099] execution=$EXEC"

cat >"$META_DIR/run_meta_${RUN_ID}.json" <<EOF
{
  "run_id": "$RUN_ID",
  "job": "$JOB",
  "execution": "$EXEC",
  "image": "$IMAGE",
  "manifest": "$MANIFEST_LOCAL",
  "gcs": "gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/",
  "hub_pins": {
    "amazon": "$AMZ_JS_PIN",
    "calendar": "$CAL_JS_PIN",
    "uber": "$UBER_JS_PIN",
    "mail": "$MAIL_JS_PIN",
    "ebay": "$EBAY_JS_PIN"
  },
  "runner_head": "$GIT_HEAD",
  "task_ids": [
    "mp_092/valuemart_leroy_bike_stand_helmet_absence_email",
    "mp_093/thursday_team_meeting_cancelled_lunch_email",
    "mp_094/shopgym_razer_expired_promo_email",
    "mp_099/silent_noop_valuemart_monitor_comps"
  ],
  "console": "https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
}
EOF
echo "[mp092-094-099] meta → $META_DIR/run_meta_${RUN_ID}.json"
echo "[mp092-094-099] GCS gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
echo "[mp092-094-099] console https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
