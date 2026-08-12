#!/usr/bin/env bash
# One-time GCP setup for gemini-503300 filtration (APIs, AR, GCS, secret).
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
BUCKET="${BUCKET:-${PROJECT}-filtration-runs}"
SECRET_NAME="${SECRET_NAME:-openai-api-key}"
# Optional: path to env file containing OPENAI_API_KEY=...
ENV_FILE="${ENV_FILE:-/Users/maroonferrari/Deccan/browser-gym-seed-to-cua-gym/.env}"

gcloud config set project "$PROJECT"
gcloud config set run/region "$REGION"

echo "[setup] enabling APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  --project="$PROJECT"

echo "[setup] Artifact Registry repo"
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --project="$PROJECT" \
    --description="Browser gym / filtration worker images"
fi

echo "[setup] GCS bucket gs://$BUCKET"
if ! gcloud storage buckets describe "gs://$BUCKET" --project="$PROJECT" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" \
    --project="$PROJECT" \
    --location="$REGION" \
    --uniform-bucket-level-access
fi

echo "[setup] Secret Manager: $SECRET_NAME"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "WARN: OPENAI_API_KEY not set — skip secret create (set ENV_FILE or export key)" >&2
else
  if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT" >/dev/null 2>&1; then
    echo "[setup] secret exists — adding new version"
    printf '%s' "$OPENAI_API_KEY" | gcloud secrets versions add "$SECRET_NAME" \
      --project="$PROJECT" --data-file=-
  else
    printf '%s' "$OPENAI_API_KEY" | gcloud secrets create "$SECRET_NAME" \
      --project="$PROJECT" --replication-policy=automatic --data-file=-
  fi
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
# Cloud Run default compute SA + Cloud Build SA need secret + storage
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

for SA in "$COMPUTE_SA" "$CLOUDBUILD_SA"; do
  echo "[setup] IAM for $SA"
  gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --project="$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null || true
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectAdmin" \
    --quiet >/dev/null || true
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/artifactregistry.writer" \
    --quiet >/dev/null || true
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/run.developer" \
    --quiet >/dev/null || true
done

# Allow Cloud Build to act as compute SA when deploying (if needed later)
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$CLOUDBUILD_SA" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null || true

echo "[setup] done PROJECT=$PROJECT REGION=$REGION BUCKET=$BUCKET REPO=$REPO SECRET=$SECRET_NAME"
echo "Image tag: ${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:latest"
