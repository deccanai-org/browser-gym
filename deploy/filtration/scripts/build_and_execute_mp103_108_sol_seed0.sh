#!/usr/bin/env bash
# mp_103–mp_108 multi-step batch — Sol seed0 (one job, six tasks).
# Tip UI: pause subscription, change_order_shipping, gift registry.
# Does NOT clobber mp_095–099. Does NOT touch mp_098 desk re-run.
# User originally labeled these mp_097–102; those IDs are taken — mapped to 103–108.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp103-108-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-3}"
TASKS="${TASKS:-6}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp103-108-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp103-108-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp103_108_multistep_batch_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp103_108_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp103-108-sol-seed0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp103_108_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp103_108_multistep_batch_sol_seed0.json}"

echo "[mp103-108] BASE=$BASE_IMAGE"
echo "[mp103-108] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp103-108] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp103-108] runner HEAD $GIT_HEAD"

# Mirror task modules gym → runner (do not touch mp_095–099).
# Do NOT overwrite runner state/mutations/main from gym (runner has refused() + catalog helpers).
for n in 103 104 105 106 107 108; do
  cp "$GYM_ROOT/server/mp_${n}.py" "$RUNNER/server/mp_${n}.py"
done
cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py" 2>/dev/null || true
# Leave existing mp_095–099 alone
test -f "$RUNNER/server/mp_095.py"
test -f "$RUNNER/server/mp_098.py"
test -f "$RUNNER/server/mp_099.py"

PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" - <<'PY'
from server import mutations
from server.state import refused, GiftRegistry, SupportTicket
assert hasattr(mutations, "pause_subscription")
assert hasattr(mutations, "change_order_shipping")
assert hasattr(mutations, "create_support_ticket")
assert hasattr(mutations, "view_registry")
print("runner engine tip APIs OK")
PY

# Tip UI pause / shipping / registry markers
AMZ_SUBS="$RUNNER/websites/amazon_mock/src/pages/Subscriptions.jsx"
AMZ_ORD="$RUNNER/websites/amazon_mock/src/pages/Orders.jsx"
AMZ_REG="$RUNNER/websites/amazon_mock/src/pages/Registry.jsx"
grep -q 'pauseSubscription\|Pause subscription' "$AMZ_SUBS" \
  || { echo "FATAL: Subscriptions.jsx missing Pause"; exit 1; }
grep -q 'changeOrderShipping\|Upgrade to Express' "$AMZ_ORD" \
  || { echo "FATAL: Orders.jsx missing shipping upgrade"; exit 1; }
test -f "$AMZ_REG" || { echo "FATAL: Registry.jsx missing"; exit 1; }
grep -q 'pause_subscription' "$RUNNER/tools/bridge.py"
grep -q 'change_order_shipping' "$RUNNER/tools/bridge.py"
grep -q 'view_registry' "$RUNNER/tools/bridge.py"

"$PY" - <<'PY'
import copy
from server.tasks import TASKS, BRIEFS, make_task
from server.verifiers import Probe, build_suite
from tools.seed_to_cuagym import transform_shop
import server.mp_103 as a
import server.mp_104 as b
import server.mp_105 as c
import server.mp_106 as d
import server.mp_107 as e
import server.mp_108 as f
import server.mp_097 as old097
import server.mp_098 as old098
import server.mp_099 as old099

assert old097.TASK_ID in TASKS and "coffee" in old097.TASK_ID
assert old098.TASK_ID in TASKS and "desk" in old098.TASK_ID
assert old099.TASK_ID in TASKS

for mod, key in ((a,"mp_103"),(b,"mp_104"),(c,"mp_105"),(d,"mp_106"),(e,"mp_107"),(f,"mp_108")):
    tid = mod.TASK_ID
    assert tid in TASKS, tid
    assert key in BRIEFS
    w = make_task(tid, 0)
    init = copy.deepcopy(w)
    r = build_suite(tid).evaluate(
        Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init),
        current_step=0,
    )
    assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, r)
    ts = transform_shop(w.shop.to_json())
    assert isinstance(ts.get("orders"), list)
print("preflight OK mp_103–108 FOI + no clobber of 097–099")
# Affordance seeds
w107 = make_task(e.TASK_ID, 0)
assert w107.shop.subscriptions[e.SUB_CONFLICT].next_delivery_date == "2026-07-25"
w108 = make_task(f.TASK_ID, 0)
assert w108.shop.registries[f.REG_ID].items[0].quantity_purchased == 1
w103 = make_task(a.TASK_ID, 0)
o = w103.shop.orders[a.ORDER_ID]
assert o.shipping_speed == "standard" and o.express_eta
print("seed affordances OK")
PY

# Wipe-rebuild hub_dist from seed-to-cua tip websites (includes pause/registry/shipping)
HUB="$RUNNER" REBUILD=1 bash "$HERE/scripts/prepare_hub_dist.sh"
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
assert "Pause subscription" in amz or "pauseSubscription" in amz or "pause_subscription" in amz, "pause missing from amazon hub"
assert "Upgrade to Express" in amz or "changeOrderShipping" in amz or "change_order_shipping" in amz, "shipping upgrade missing"
assert "Gift Registry" in amz or "registry-title" in amz or "/registry" in amz, "registry missing"
assert "mail.send" in mail or "btn-send" in mail, "mail send affordance missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[mp103-108] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

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
  python -c "from pathlib import Path; amz=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); t=amz.read_text(errors='ignore'); assert amz.name=='${AMZ_JS_PIN}', amz.name; assert 'Pause' in t or 'pause' in t; print('hub overlay OK', amz.name)"; \\
  python -c "from server.tasks import TASKS, make_task; tid='mp_103/annual_checkup_reschedule_and_prescription_refill'; assert tid in TASKS; assert 'mp_108/gift_registry_duplicate_purchase_check' in TASKS; w=make_task(tid,0); assert w.shop.orders['ORD-MP103-VERTANE'].express_eta; print('mp103-108 overlay OK', len(TASKS))"
EOF

echo "[mp103-108] Cloud Build submit → $IMAGE"
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

echo "[mp103-108] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS parallelism=$PARALLELISM"
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
  echo "[mp103-108] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp103-108] execution=$EXEC"

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
    "mp_103/annual_checkup_reschedule_and_prescription_refill",
    "mp_104/return_wrong_size_reorder_correct_with_price_match",
    "mp_105/dinner_party_headcount_venue_and_grocery_run",
    "mp_106/insurance_claim_photo_evidence_deadline",
    "mp_107/vacation_hold_mail_and_recurring_delivery_pause",
    "mp_108/gift_registry_duplicate_purchase_check"
  ],
  "id_mapping_note": "User labeled mp_097-102; those IDs taken — shipped as mp_103-108",
  "console": "https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
}
EOF
echo "[mp103-108] meta → $META_DIR/run_meta_${RUN_ID}.json"
echo "[mp103-108] GCS gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
echo "[mp103-108] console https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
