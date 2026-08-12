#!/usr/bin/env bash
# mp_114 + mp_115 fairness retune — Sol seed0 (one job, two tasks).
# Tip-lock hub_dist + full harness overlay. Does NOT touch Eligible Suite.
# mp_114: $60 cap now in the user-facing prompt (pref mail corroborates).
# mp_115: named home/out ShopMail + prompt pointer (calendar corroborates).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp114-115-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-2}"
TASKS="${TASKS:-2}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp114-115-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp114-115-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp114_115_fairness_retune_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp114_115_20260812}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp114-115-sol-seed0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp114_115_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp114_115_fairness_retune_sol_seed0.json}"

echo "[mp114-115] BASE=$BASE_IMAGE"
echo "[mp114-115] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp114-115] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp114-115] runner HEAD $GIT_HEAD"

# Mirror task modules gym SoT → runner
for id in 114 115; do
  if [ -f "$GYM_ROOT/server/mp_${id}.py" ]; then
    cp "$GYM_ROOT/server/mp_${id}.py" "$RUNNER/server/mp_${id}.py"
  fi
done

PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" - <<'PY'
import copy
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite
import server.mp_114 as t114
import server.mp_115 as t115

assert t114.TASK_ID in TASKS and t115.TASK_ID in TASKS
assert "don't spend more than $60" in (BRIEFS.get("mp_114") or "").lower()
assert "emailed you" in (BRIEFS.get("mp_115") or "").lower()
for mod in (t114, t115):
    w = make_task(mod.TASK_ID, 0)
    init = copy.deepcopy(w)
    r = build_suite(mod.TASK_ID).evaluate(
        Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init),
        current_step=0,
    )
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (mod.TASK_ID, r)

w114 = make_task(t114.TASK_ID, 0)
assert float(w114.market.products[t114.LAMP].price) == 74.0
assert "$60" in w114.mail.inbox[t114.PREF_MAIL].body
w115 = make_task(t115.TASK_ID, 0)
assert t115.HOME_MAIL in w115.mail.inbox
assert "may 21" in w115.mail.inbox[t115.HOME_MAIL].body.lower()
print("preflight OK mp_114 $60-in-brief + mp_115 named home-nights mail")
PY

# Tip-lock: keep pinned hub_dist (prompt/seed retune; no UI change).
HUB_REBUILD="${HUB_REBUILD:-0}"
if [ "$HUB_REBUILD" = "1" ]; then
  HUB="$RUNNER" REBUILD=1 bash "$HERE/scripts/prepare_hub_dist.sh"
else
  echo "[mp114-115] HUB_REBUILD=0 — using existing deploy/filtration/hub_dist (tip-lock)"
  test -d "$HERE/hub_dist/ebay_mock/assets"
  test -d "$HERE/hub_dist/gmail_mock/assets"
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
assert "/store/" in uber or "restaurant" in uber.lower(), "food store affordance missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[mp114-115] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

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
  python -c "from pathlib import Path; amz_p=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); mail_p=next(Path('/hub_dist/gmail_mock/assets').glob('index-*.js')); assert amz_p.name=='${AMZ_JS_PIN}', amz_p.name; assert 'btn-send' in mail_p.read_text(errors='ignore') or 'mail.send' in mail_p.read_text(errors='ignore'); print('hub overlay OK', amz_p.name, mail_p.name)"; \\
  python -c "from server.tasks import TASKS, BRIEFS, make_task; t114='mp_114/arcglow_desk_lamp_spend_cap_email'; t115='mp_115/five_home_nights_dinner_avoid_sunny_wok_email'; assert t114 in TASKS and t115 in TASKS; assert '60' in (BRIEFS.get('mp_114') or ''); w=make_task(t114,0); assert float(w.market.products['vm_mp114_desk_lamp'].price)==74.0; w=make_task(t115,0); assert 'em_mp115_home_nights' in w.mail.inbox; print('mp114/115 overlay OK', len(TASKS))"
EOF

echo "[mp114-115] Cloud Build submit → $IMAGE"
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

echo "[mp114-115] $action $JOB model=gpt-5.6-sol agent=openai_pixel"
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
  echo "[mp114-115] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp114-115] execution=$EXEC"

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
    "mp_114/arcglow_desk_lamp_spend_cap_email",
    "mp_115/five_home_nights_dinner_avoid_sunny_wok_email"
  ],
  "console": "https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
}
EOF
echo "[mp114-115] meta → $META_DIR/run_meta_${RUN_ID}.json"
echo "[mp114-115] GCS gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
echo "[mp114-115] console https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
