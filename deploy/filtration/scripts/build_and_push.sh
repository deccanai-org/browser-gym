#!/usr/bin/env bash
# Stage context, prepare hub_dist, Cloud Build → Artifact Registry.
set -euo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/share/google-cloud-sdk/bin:$PATH"

HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
PROJECT="${PROJECT:-gemini-503300}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-gym-images}"
TAG="${TAG:-latest}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/filtration-worker:${TAG}"
STAGING="${STAGING:-/tmp/filtration-worker-build}"

echo "[build] generating manifests"
python3 "$HERE/generate_manifest.py" --mode smoke
python3 "$HERE/generate_manifest.py" --mode phase1
python3 "$HERE/generate_manifest.py" --mode phase2_sample20 --preset sol
python3 "$HERE/generate_manifest.py" --mode phase2_sample20 --preset opus

echo "[build] preparing hub_dist (HUB=${HUB:-default})"
bash "$HERE/scripts/prepare_hub_dist.sh"

echo "[build] staging context → $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING"
# Minimal runner surface
for d in server harness agents eval tools ui; do
  rsync -a --delete \
    --exclude '__pycache__' --exclude '*.pyc' --exclude '.venv' \
    --exclude 'product_assets' --exclude 'node_modules' --exclude '.npm-cache' \
    "$RUNNER/$d/" "$STAGING/$d/"
done
cp "$RUNNER/pyproject.toml" "$STAGING/"
mkdir -p "$STAGING/deploy/filtration"
rsync -a --exclude 'hub_dist' "$HERE/" "$STAGING/deploy/filtration/"
# hub_dist at context root (Dockerfile COPY hub_dist)
rsync -a "$HERE/hub_dist/" "$STAGING/hub_dist/"
cp "$HERE/Dockerfile" "$STAGING/Dockerfile"
cp "$HERE/.dockerignore" "$STAGING/.dockerignore"

# Ensure dockerignore does not drop hub_dist
echo "[build] context size:"
du -sh "$STAGING" "$STAGING/hub_dist" || true

echo "[build] Cloud Build submit → $IMAGE"
gcloud builds submit "$STAGING" \
  --project="$PROJECT" \
  --tag="$IMAGE" \
  --timeout=3600s \
  --machine-type=e2-highcpu-8

echo "[build] done $IMAGE"
