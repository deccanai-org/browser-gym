#!/usr/bin/env bash
# mp_110–mp_119 Eligible e16+ revise batch — Sol seed0 (one job, ten tasks).
# Tip UI wipe-rebuild. Does NOT touch mp_091–108 / e16–e18/e27 already-done IDs.
# Skipped: e16/mp_069→mp_092, e17/mp_070→mp_093, e18/mp_071→mp_094, e27/mp_078→mp_099.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp110-119-sol-seed0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-5}"
TASKS="${TASKS:-10}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp110-119-sol-seed0-${TS}}"
JOB="${JOB:-filtration-mp110-119-sol-seed0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp110_119_e16plus_revise_sol_seed0.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp110_119_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp110-119-sol-seed0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp110_119_sol_seed0_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp110_119_e16plus_revise_sol_seed0.json}"

echo "[mp110-119] BASE=$BASE_IMAGE"
echo "[mp110-119] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp110-119] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp110-119] runner HEAD $GIT_HEAD"

# Mirror task modules gym → runner (do not smash mp_091–108)
for n in 110 111 112 113 114 115 116 117 118 119; do
  cp "$GYM_ROOT/server/mp_${n}.py" "$RUNNER/server/mp_${n}.py"
done
# Keep runner tip tasks.py / verifiers.py (already registered); only ensure modules present
for n in 091 092 093 094 095 096 097 098 099 103 108; do
  test -f "$RUNNER/server/mp_${n}.py" || test -f "$RUNNER/server/mp_${n#0}.py" || true
done
test -f "$RUNNER/server/mp_092.py"
test -f "$RUNNER/server/mp_099.py"
test -f "$RUNNER/server/mp_108.py"

# Copy gates into runner for bookkeeping
mkdir -p "$RUNNER/verification_pipeline_tasks/mp110_119_2026-08-11"
cp "$GYM_ROOT/verification_pipeline_tasks/mp110_119_2026-08-11/run_gates.py" \
  "$RUNNER/verification_pipeline_tasks/mp110_119_2026-08-11/run_gates.py"

PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" "$RUNNER/verification_pipeline_tasks/mp110_119_2026-08-11/run_gates.py"

# Wipe-rebuild hub_dist from seed-to-cua tip websites
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
assert "btn-schedule-when" in uber and "btn-schedule-slot-" in uber, "schedule-ahead affordance missing"
assert "mail.send" in mail or "btn-send" in mail, "mail send affordance missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[mp110-119] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

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
  # Harden gym/bridge health: cold start of tip server can exceed fixed sleep 2
  # (mp110-119 first exec: all 10 tasks "gym health FAIL" with no GCS). Dump log on fail.
  ENTRY_PATCH="$CTX/deploy/filtration/worker_entrypoint.sh"
  python3 - "$ENTRY_PATCH" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
old = """# Health gates
curl -sf -H \"X-Harness-Token: $HARNESS_TOKEN\" \"http://127.0.0.1:$GYM_PORT/_harness/tasks\" >/dev/null \\
  || { echo \"[worker] gym health FAIL\" | tee -a \"$LOG\" >&2; exit 1; }
curl -sf \"http://127.0.0.1:$BRIDGE_PORT/bridge/actions\" >/dev/null \\
  || { echo \"[worker] bridge actions FAIL\" | tee -a \"$LOG\" >&2; exit 1; }"""
new = r'''# Health gates (retry — tip uvicorn cold-start can exceed sleep 2)
gym_ok=0
for _i in $(seq 1 45); do
  if curl -sf -H "X-Harness-Token: $HARNESS_TOKEN" "http://127.0.0.1:$GYM_PORT/_harness/tasks" >/dev/null; then
    gym_ok=1
    echo "[worker] gym health OK after ${_i}s" | tee -a "$LOG"
    break
  fi
  sleep 1
done
if [ "$gym_ok" != "1" ]; then
  echo "[worker] gym health FAIL" | tee -a "$LOG" >&2
  echo "[worker] ---- gym/bridge log tail ----" >&2
  tail -n 120 "$LOG" >&2 || true
  exit 1
fi
bridge_ok=0
for _i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$BRIDGE_PORT/bridge/actions" >/dev/null; then
    bridge_ok=1
    break
  fi
  sleep 1
done
if [ "$bridge_ok" != "1" ]; then
  echo "[worker] bridge actions FAIL" | tee -a "$LOG" >&2
  tail -n 80 "$LOG" >&2 || true
  exit 1
fi'''
if old not in text:
    raise SystemExit("FATAL: health-gate block not found for patch")
p.write_text(text.replace(old, new, 1))
print("patched worker_entrypoint health retries")
PY
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
  python -c "from pathlib import Path; amz=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); uber=next(Path('/hub_dist/uber_eats_mock/assets').glob('index-*.js')); t=uber.read_text(errors='ignore'); assert amz.name=='${AMZ_JS_PIN}', amz.name; assert uber.name=='${UBER_JS_PIN}', uber.name; assert 'btn-schedule-when' in t; print('hub overlay OK', amz.name, uber.name)"; \\
  python -c "from server.tasks import TASKS, make_task; need=['mp_110/valuemart_plus_confirmshame_cancel_email','mp_111/design_review_maya_override_lunch_email','mp_112/kettle_ofd_address_change_email','mp_113/kettle_reason_unlock_address_change_email','mp_114/arcglow_desk_lamp_spend_cap_email','mp_115/five_home_nights_dinner_avoid_sunny_wok_email','mp_116/cancel_subscription_ambiguous_ask_email','mp_117/cancel_subscription_control_email','mp_118/austin_aa1420_trip_prep_email','mp_119/pulseblend_refund_source_anchoring_email']; assert all(t in TASKS for t in need), [t for t in need if t not in TASKS]; w=make_task(need[0],0); assert w.market.enable_membership_cancel; print('mp110-119 overlay OK', len(TASKS))"
EOF

echo "[mp110-119] Cloud Build submit → $IMAGE"
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

echo "[mp110-119] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS parallelism=$PARALLELISM"
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
  echo "[mp110-119] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp110-119] execution=$EXEC"

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
    "mp_110/valuemart_plus_confirmshame_cancel_email",
    "mp_111/design_review_maya_override_lunch_email",
    "mp_112/kettle_ofd_address_change_email",
    "mp_113/kettle_reason_unlock_address_change_email",
    "mp_114/arcglow_desk_lamp_spend_cap_email",
    "mp_115/five_home_nights_dinner_avoid_sunny_wok_email",
    "mp_116/cancel_subscription_ambiguous_ask_email",
    "mp_117/cancel_subscription_control_email",
    "mp_118/austin_aa1420_trip_prep_email",
    "mp_119/pulseblend_refund_source_anchoring_email"
  ],
  "skipped_already_done": ["e16/mp_069→mp_092", "e17/mp_070→mp_093", "e18/mp_071→mp_094", "e27/mp_078→mp_099"],
  "console": "https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
}
EOF
echo "[mp110-119] meta → $META_DIR/run_meta_${RUN_ID}.json"
echo "[mp110-119] GCS gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
echo "[mp110-119] console https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=${PROJECT}"
