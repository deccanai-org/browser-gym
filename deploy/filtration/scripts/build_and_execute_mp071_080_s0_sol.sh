#!/usr/bin/env bash
# mp_071–080 Sol seed0 — 12 episodes ∥5 on GCP.
# Tip-lock seed-to-cua hub_dist wipe + full harness overlay.
# Does NOT touch Eligible Suite.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp071-080-s0-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-6}"
TASKS="${TASKS:-12}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp071-080-s0-${TS}}"
JOB="${JOB:-filtration-mp071-080-s0}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp071_080_s0_sol.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp071_080_s0_20260811}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp071-080-s0-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp071_080_s0_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp071_080_s0_sol.json}"

echo "[mp071+] BASE=$BASE_IMAGE"
echo "[mp071+] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"

cd "$RUNNER"
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/seed-to-cua-gym)" \
  || echo "[mp071+] WARN: HEAD != origin/seed-to-cua-gym tip (continuing with local tip)"
GIT_HEAD="$(git rev-parse HEAD)"
echo "[mp071+] runner HEAD $GIT_HEAD"

# Mirror task modules → gym SoT (bookkeeping)
for f in mp_071.py mp_072.py mp_073.py mp_074.py mp_074b.py mp_075.py mp_076.py mp_077.py mp_077b.py mp_078.py mp_079.py mp_080.py; do
  if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
    cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
  fi
done
# Mechanism support used by mp_072 / mp_078
for f in apps/market/state.py apps/market/mutations.py apps/market/routes.py; do
  if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
    mkdir -p "$(dirname "$GYM_ROOT/server/$f")"
    cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
  fi
done
cp "$RUNNER/tools/bridge.py" "$GYM_ROOT/tools/bridge.py" 2>/dev/null || true
cp "$RUNNER/tools/seed_to_cuagym.py" "$GYM_ROOT/tools/seed_to_cuagym.py" 2>/dev/null || true
cp "$RUNNER/agents/oracle_agent.py" "$GYM_ROOT/agents/oracle_agent.py" || true

cd "$RUNNER"
PY="${PY:-$RUNNER/.venv/bin/python}"
"$PY" verification_pipeline_tasks/mp071_080_2026-08-11/run_gates.py

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
assert "btn-buy-it-now" in ebay, "ebay buy-it-now missing"
assert "enableSellerCreate" in ebay or "nav-sell" in ebay or "/membership" in ebay, "ebay sell/membership hooks missing"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz and bad not in uber and bad not in mail and bad not in ebay, bad
print("hub_dist NEW-UI OK", amz_p.name, cal_p.name, uber_p.name, mail_p.name, ebay_p.name)
PY
echo "[mp071+] hub pins amazon=$AMZ_JS_PIN calendar=$CAL_JS_PIN uber=$UBER_JS_PIN mail=$MAIL_JS_PIN ebay=$EBAY_JS_PIN"

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
  python -c "from server.tasks import TASKS, make_task; need=['mp_071/expired_promo_code_vs_stated_budget','mp_072/valuemart_confirmshame_cancel_flow','mp_073/gymcal_recurring_series_vs_single_override','mp_074/kettle_address_change_ofd_infeasible','mp_074b/kettle_address_change_reason_unlock','mp_075/spend_cap_late_binding_valuemart','mp_076/five_dinners_negative_constraint_gymeats','mp_077/matched_pair_cancel_the_subscription_ambiguous','mp_077b/matched_pair_cancel_the_subscription_control','mp_078/silent_noop_valuemart_listing','mp_079/long_horizon_trip_prep_four_app_chain','mp_080/shopmail_source_anchoring_reversed']; assert all(t in TASKS for t in need), [t for t in need if t not in TASKS]; w72=make_task(need[1],0); assert w72.market.enable_membership_cancel; w78=make_task(need[9],0); assert w78.market.silent_noop_first_listing and w78.market.enable_seller_create; print('mp071+ overlay OK', len(TASKS))"
EOF

echo "[mp071+] Cloud Build submit → $IMAGE"
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

echo "[mp071+] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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
  echo "[mp071+] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[mp071+] execution=$EXEC"

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
  "n_episodes": $TASKS,
  "parallelism": $PARALLELISM,
  "model": "gpt-5.6-sol",
  "agent": "openai_pixel"
}
EOF

echo "[mp071+] meta → $META_DIR/run_meta_${RUN_ID}.json"
echo "[mp071+] console: https://console.cloud.google.com/run/jobs/executions/details/${REGION}/${EXEC}?project=$(gcloud projects describe $PROJECT --format='value(projectNumber)')"
echo "[mp071+] GCS: gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
