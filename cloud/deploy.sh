#!/usr/bin/env bash
# Build the runner image, create/update the Cloud Run Job, and fan the episodes out.
#
#   ./cloud/deploy.sh                 # build + deploy + run whatever is in manifest.json
#   ./cloud/deploy.sh --no-build      # re-run without rebuilding the image
#
# Prereq (interactive, once):  gcloud auth login && gcloud config set project mlproject-501205
set -euo pipefail

PROJECT="${PROJECT:-mlproject-501205}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-runner}"
JOB="${JOB:-gym-eval}"
# One image can carry several batches; MANIFEST_FILE picks which one this
# job runs. The episode count is read from that file, not from a fixed name.
MANIFEST_FILE="${MANIFEST_FILE:-manifest.json}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/eval-runner:latest"
BUCKET="${BUCKET:-${PROJECT}-gym-runs}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
# PROVIDER picks which vendor's key + model env the job gets. Default "openai"
# keeps every existing invocation of this script byte-identical; PROVIDER=anthropic
# swaps in ANTHROPIC_API_KEY/ANTHROPIC_MODEL for the `pixel` (Claude SoM) agent.
PROVIDER="${PROVIDER:-openai}"
MODEL="${OPENAI_MODEL:-gpt-5.6-sol}"
ANTHROPIC_MODEL_ID="${ANTHROPIC_MODEL:-claude-opus-5}"
MAX_STEPS="${AGENT_MAX_STEPS:-100}"
# Reward-leakage suppression. With AGENT_EVAL_MODE=0 (the agent default) the
# harness tells the agent its running score and which milestones fired after
# every action, which contaminates the episode as capability evidence.
# Benchmark recordings must set 1.
EVAL_MODE="${AGENT_EVAL_MODE:-1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

case "$PROVIDER" in
  openai)    SHOW_MODEL="$MODEL" ;;
  anthropic) SHOW_MODEL="$ANTHROPIC_MODEL_ID" ;;
  *) echo "ERROR: PROVIDER must be openai|anthropic (got '$PROVIDER')" >&2; exit 2 ;;
esac

N=$(python3 -c "import json;print(len(json.load(open('$HERE/$MANIFEST_FILE'))['runs']))")
echo "project=$PROJECT region=$REGION job=$JOB manifest=$MANIFEST_FILE episodes=$N provider=$PROVIDER model=$SHOW_MODEL cap=$MAX_STEPS run_id=$RUN_ID"

gcloud config set project "$PROJECT" >/dev/null

# --- one-time infra (idempotent) --------------------------------------------
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com secretmanager.googleapis.com storage.googleapis.com \
    --project "$PROJECT" >/dev/null

gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" --repository-format=docker \
    --location "$REGION" --description "browser-gym eval runner"

gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --location "$REGION"

# The API key lives in Secret Manager, never in the job spec or the image.
# Seeded from the exported env var if present, else from .env. Never echoed.
if [ "$PROVIDER" = "anthropic" ]; then
  KEY_SECRET="anthropic-api-key"; KEY_VAR="ANTHROPIC_API_KEY"
else
  KEY_SECRET="openai-api-key";    KEY_VAR="OPENAI_API_KEY"
fi
if ! gcloud secrets describe "$KEY_SECRET" >/dev/null 2>&1; then
  if [ -n "${!KEY_VAR:-}" ]; then
    printf '%s' "${!KEY_VAR}" \
      | gcloud secrets create "$KEY_SECRET" --data-file=- --replication-policy=automatic
    echo "created secret $KEY_SECRET from \$$KEY_VAR"
  elif [ -f "$ROOT/.env" ] && grep -q "^$KEY_VAR=" "$ROOT/.env"; then
    grep "^$KEY_VAR=" "$ROOT/.env" | head -1 | cut -d= -f2- \
      | gcloud secrets create "$KEY_SECRET" --data-file=- --replication-policy=automatic
    echo "created secret $KEY_SECRET from .env"
  else
    echo "ERROR: secret '$KEY_SECRET' missing and no $KEY_VAR in env or .env" >&2; exit 1
  fi
fi

# Cloud Run Jobs run as the default compute SA. That SA usually has project
# Editor (enough for the results bucket) but Editor does NOT include
# secretmanager.secretAccessor, so without this every task dies at startup with
# "Permission denied on secret". Idempotent; a failure here is a warning, not
# fatal, because an org may have granted it at a higher level already.
PROJNUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null || true)"
if [ -n "$PROJNUM" ]; then
  RUN_SA="${RUN_SA:-${PROJNUM}-compute@developer.gserviceaccount.com}"
  gcloud secrets add-iam-policy-binding "$KEY_SECRET" \
    --member "serviceAccount:$RUN_SA" --role roles/secretmanager.secretAccessor \
    --project "$PROJECT" >/dev/null 2>&1 \
    && echo "granted secretAccessor on $KEY_SECRET to $RUN_SA" \
    || echo "WARN: could not grant secretAccessor on $KEY_SECRET to $RUN_SA" >&2
fi

# --- image -------------------------------------------------------------------
if [ "${1:-}" != "--no-build" ]; then
  echo "building $IMAGE (Cloud Build; the Playwright base is ~2GB, first build is slow)"
  # --ignore-file is REQUIRED: with no .gcloudignore, gcloud falls back to
  # .gitignore, which carries `websites/*/dist/` — the five mock bundles the
  # image is built around would silently never reach Cloud Build.
  # gcloud cannot read --config from stdin ("Unable to read file [-]"), so the
  # build config is materialised to a temp file outside the repo (keeping it out
  # of the build context and out of the working tree) and removed on exit.
  BUILD_CFG="$(mktemp -t gymbuild)"
  trap 'rm -f "$BUILD_CFG"' EXIT
  cat > "$BUILD_CFG" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build","-f","cloud/Dockerfile","-t","$IMAGE","."]
images: ["$IMAGE"]
options:
  machineType: E2_HIGHCPU_8
timeout: 3600s
YAML
  gcloud builds submit "$ROOT" --ignore-file="cloud/.gcloudignore" --config="$BUILD_CFG"
fi

# --- job ---------------------------------------------------------------------
ARGS=(
  --image "$IMAGE" --region "$REGION" --project "$PROJECT"
  --tasks "$N" --parallelism "$N" --task-timeout 3600s --max-retries 0
  --cpu 2 --memory 4Gi
)
if [ "$PROVIDER" = "anthropic" ]; then
  # agents/pixel_agent.py ends an episode when the MEASURED prompt size crosses
  # LLM_CONTEXT_BUDGET (default 190000, sized for a 200K window). Claude Opus 5
  # has a 1M window, so leaving the default means the context guard — not the
  # step cap — usually ends the episode. Export LLM_CONTEXT_BUDGET to move it;
  # note the agent resends every screenshot each turn, so input cost is O(steps^2).
  EXTRA=""
  if [ -n "${LLM_CONTEXT_BUDGET:-}" ]; then EXTRA=",LLM_CONTEXT_BUDGET=$LLM_CONTEXT_BUDGET"; fi
  ARGS+=(
    --set-env-vars "RUN_ID=$RUN_ID,RESULTS_BUCKET=$BUCKET,MANIFEST_PATH=/app/cloud/$MANIFEST_FILE,ANTHROPIC_MODEL=$ANTHROPIC_MODEL_ID,AGENT_MAX_STEPS=$MAX_STEPS,AGENT_EVAL_MODE=$EVAL_MODE$EXTRA"
    --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest"
  )
else
  ARGS+=(
    --set-env-vars "RUN_ID=$RUN_ID,RESULTS_BUCKET=$BUCKET,MANIFEST_PATH=/app/cloud/$MANIFEST_FILE,OPENAI_MODEL=$MODEL,AGENT_MAX_STEPS=$MAX_STEPS,AGENT_EVAL_MODE=$EVAL_MODE"
    --set-secrets "OPENAI_API_KEY=openai-api-key:latest"
  )
fi
if gcloud run jobs describe "$JOB" --region "$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" "${ARGS[@]}"
else
  gcloud run jobs create "$JOB" "${ARGS[@]}"
fi

echo "executing $N episodes in parallel..."
gcloud run jobs execute "$JOB" --region "$REGION" --wait

echo
echo "results:  gs://$BUCKET/runs/$RUN_ID/"
echo "collect:  python3 cloud/collect.py --bucket $BUCKET --run-id $RUN_ID"
echo "logs:     https://console.cloud.google.com/run/jobs/details/$REGION/$JOB/executions?project=$PROJECT"
