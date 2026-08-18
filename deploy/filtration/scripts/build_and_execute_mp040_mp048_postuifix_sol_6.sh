#!/usr/bin/env bash
# mp_040 + mp_048 Sol seeds 0–2 — 6 episodes ∥6 after GymCal/warranty UI fixes.
# Overlays full hub_dist (calendar split date/time + amazon warranty banners).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
TAG="${TAG:-mp040-mp048-postuifix-${TS}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
OPENAI_SECRET="${OPENAI_SECRET:-openai-api-key}"
PARALLELISM="${PARALLELISM:-6}"
TASKS="${TASKS:-6}"
MEMORY="${MEMORY:-4Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-2700}"
RUN_ID="${RUN_ID:-mp040-mp048-postuifix-${TS}}"
JOB="${JOB:-filtration-mp040-mp048-postuifix}"
MANIFEST="${MANIFEST:-/app/deploy/filtration/manifests/mp040_mp048_postuifix_sol_6.json}"
GCS_PREFIX="${GCS_PREFIX:-filtration/mp040_mp048_postuifix_20260810}"
EXECUTE="${EXECUTE:-1}"
BASE_IMAGE="${BASE_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:parallel-probes-sol-20260810T203435Z}"
GYM_ROOT="${GYM_ROOT:-/Users/maroonferrari/Deccan/ecommerce-browser-gym}"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
CTX="${CTX:-/tmp/filtration-mp040-mp048-postuifix-${TS}}"
META_DIR="${META_DIR:-$RUNNER/trajectories/mp040_mp048_postuifix_sol_gcp}"
MANIFEST_LOCAL="${MANIFEST_LOCAL:-$HERE/manifests/mp040_mp048_postuifix_sol_6.json}"

echo "[postui] BASE=$BASE_IMAGE"
echo "[postui] IMAGE=$IMAGE RUN_ID=$RUN_ID JOB=$JOB ∥$PARALLELISM"
echo "[postui] MANIFEST_LOCAL=$MANIFEST_LOCAL → $MANIFEST"

# --- sync: tip-lock default keeps runner (seed-to-cua) as SoT; optional gym pull ---
if [ "${SYNC_FROM_GYM:-0}" = "1" ]; then
  echo "[postui] SYNC_FROM_GYM=1 — pulling modules from $GYM_ROOT"
  for f in mp_040.py mp_048.py tasks.py verifiers.py; do
    cp "$GYM_ROOT/server/$f" "$RUNNER/server/$f"
  done
  cp "$GYM_ROOT/agents/oracle_agent.py" "$RUNNER/agents/oracle_agent.py"
else
  echo "[postui] runner SoT (no gym overwrite); mirroring mp_040/mp_048 → gym bookkeeping"
  for f in mp_040.py mp_048.py; do
    if [ -f "$RUNNER/server/$f" ] && [ -d "$GYM_ROOT/server" ]; then
      cp "$RUNNER/server/$f" "$GYM_ROOT/server/$f" || true
    fi
  done
fi

# --- local preflight ---
cd "$RUNNER"
python3 - <<'PY'
import copy
from server.tasks import TASKS, make_task, BRIEFS
from server.verifiers import Probe, build_suite

assert "ErgoGlide" in BRIEFS.get("mp_040", "")
assert "flickering" in BRIEFS.get("mp_048", "").lower()
assert "warranty" not in BRIEFS.get("mp_048", "").lower()
need = [
    "mp_040/couch_pickup_vs_calendar_busy",
    "mp_048/lamp_warranty_expired_check_first",
]
for tid in need:
    assert tid in TASKS, tid
    for seed in (0, 1, 2):
        w = make_task(tid, seed)
        init = copy.deepcopy(w)
        suite = build_suite(tid)
        probe = Probe(state=w.shop, url="/", initial_state=init.shop, world=w, initial_world=init)
        r = suite.evaluate(probe, current_step=0)
        assert r.get("success") is False and float(r.get("score") or 0) == 0.0, (tid, seed, r)
        if "mp_040" in tid:
            assert "ErgoGlide" in (w.shop.task_brief or "")
        if "mp_048" in tid:
            assert "flickering" in (w.shop.task_brief or "").lower()
print("preflight OK seeds 0–2 fail-on-initial")
print("briefs:", {k: BRIEFS.get(k) for k in ("mp_040", "mp_048")})
PY

# --- hub_dist MUST be seed-to-cua vendored websites (never CUA-Gym-Hub / legacy) ---
# Refuse CUA-only amazon bundles that lack same-origin /api/ wiring.
CAL_JS="$(find "$HERE/hub_dist/google_calendar_mock/assets" -name 'index-*.js' -print -quit)"
AMZ_JS="$(find "$HERE/hub_dist/amazon_mock/assets" -name 'index-*.js' -print -quit)"
test -n "$CAL_JS" && test -n "$AMZ_JS"
python3 - <<PY
from pathlib import Path
cal_p, amz_p = Path("$CAL_JS"), Path("$AMZ_JS")
cal, amz = cal_p.read_text(errors="ignore"), amz_p.read_text(errors="ignore")
assert "input-edit-start" in cal and 'type:"time"' in cal, "calendar hub_dist missing split time UI"
assert "Warranty expired" in amz, "amazon hub_dist missing warranty banner"
assert "/api/" in amz, "FATAL: amazon hub_dist missing /api/ — looks like legacy/CUA bake, not seed-to-cua"
for bad in ("cua-gym-hub.soulhq.ai", "cua-gym-hub.delta.soulhq.ai"):
    assert bad not in cal and bad not in amz, f"FATAL: remote hub URL baked in: {bad}"
# Pin tip-lock wipe rebuild 2026-08-10 (HEAD 3d7362d + calendar/warranty UI)
assert cal_p.name == "index-8e84e2c6.js", cal_p.name
assert amz_p.name == "index-DNSHRGfv.js", amz_p.name
print("hub_dist NEW-UI OK (seed-to-cua websites)")
print("  calendar:", cal_p.name)
print("  amazon:", amz_p.name)
PY

# --- stage overlay ---
rm -rf "$CTX"
mkdir -p "$CTX/server" "$CTX/agents" "$CTX/deploy/filtration/manifests" "$CTX/hub_dist"
rsync -a --exclude '__pycache__' --exclude '*.pyc' "$RUNNER/server/" "$CTX/server/"
cp "$RUNNER/agents/oracle_agent.py" "$CTX/agents/oracle_agent.py"
# Keep worker screenshot upload path from base image; also overlay entrypoint if local is newer
if [ -f "$HERE/worker_entrypoint.sh" ]; then
  mkdir -p "$CTX/deploy/filtration"
  cp "$HERE/worker_entrypoint.sh" "$CTX/deploy/filtration/worker_entrypoint.sh"
fi
cp "$MANIFEST_LOCAL" "$CTX/deploy/filtration/manifests/$(basename "$MANIFEST_LOCAL")"
# Full hub_dist overlay (all five mocks) so calendar + warranty fixes are served
rsync -a "$HERE/hub_dist/" "$CTX/hub_dist/"

MANIFEST_BASENAME="$(basename "$MANIFEST_LOCAL")"

cat >"$CTX/Dockerfile" <<EOF
FROM ${BASE_IMAGE}
COPY server /app/server
COPY agents/oracle_agent.py /app/agents/oracle_agent.py
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
  mkdir -p "\$DP/agents"; \\
  cp /app/agents/oracle_agent.py "\$DP/agents/oracle_agent.py"; \\
  python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); cal_p=next(Path('/hub_dist/google_calendar_mock/assets').glob('index-*.js')); amz_p=next(Path('/hub_dist/amazon_mock/assets').glob('index-*.js')); assert cal_p.name=='index-8e84e2c6.js' and amz_p.name=='index-DNSHRGfv.js', (cal_p.name, amz_p.name); cal=cal_p.read_text(errors='ignore'); amz=amz_p.read_text(errors='ignore'); assert 'input-edit-start' in cal and 'Warranty expired' in amz and '/api/' in amz; print('hub overlay NEW-UI OK', len(jpgs), 'jpgs', cal_p.name, amz_p.name)"; \\
  python -c "from server.tasks import TASKS, BRIEFS; assert 'mp_040/couch_pickup_vs_calendar_busy' in TASKS; assert 'mp_048/lamp_warranty_expired_check_first' in TASKS; assert 'ErgoGlide' in BRIEFS['mp_040']; assert 'flickering' in BRIEFS['mp_048'].lower(); print('mp040_mp048 postuifix overlay OK', len(TASKS))"
EOF

echo "[postui] Cloud Build submit → $IMAGE"
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

echo "[postui] $action $JOB model=gpt-5.6-sol agent=openai_pixel tasks=$TASKS ∥$PARALLELISM"
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

echo "[postui] RUN_ID=$RUN_ID"
mkdir -p "$META_DIR"

if [ "$EXECUTE" != "1" ]; then
  cat >"$META_DIR/run_meta_${JOB}.json" <<EOF
{"run_id":"$RUN_ID","job":"$JOB","image":"$IMAGE","executed":false,"n_episodes":$TASKS,"parallelism":$PARALLELISM}
EOF
  echo "[postui] EXECUTE=0 — deploy only"
  exit 0
fi

EXEC="$(gcloud run jobs execute "$JOB" \
  --region="$REGION" --project="$PROJECT" --format='value(metadata.name)')"
echo "[postui] execution=$EXEC"

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
    "amazon": "index-DNSHRGfv.js",
    "calendar": "index-8e84e2c6.js"
  },
  "git_head": "3d7362d06772b58a2fccded8abdfdc8b5ea9451a",
  "notes": "tip-lock hub_dist wipe; GymCal split date/time + warranty UI; coaching-dropped briefs"
}
EOF
echo "[postui] wrote $META_DIR/run_meta_${JOB}.json"
echo "EXEC=$EXEC"
echo "RUN_ID=$RUN_ID"
echo "GCS=gs://${BUCKET}/${GCS_PREFIX}/${RUN_ID}/"
