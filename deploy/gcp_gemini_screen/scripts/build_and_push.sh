#!/usr/bin/env bash
# Build + push the worker image to Artifact Registry.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-browser-gym}"
IMAGE_NAME="${IMAGE_NAME:-gemini-census}"
TAG="${TAG:-$(date +%Y%m%d)}"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}"

echo "Building ${IMAGE} from ${ROOT} ..."
gcloud builds submit "${ROOT}" \
  --project="${PROJECT_ID}" \
  --config=/dev/stdin <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: ['build', '-f', 'deploy/gcp_gemini_screen/Dockerfile', '-t', '${IMAGE}', '.']
images:
  - '${IMAGE}'
timeout: 2400s
EOF

echo
echo "export IMAGE=${IMAGE}"
echo "Then: ./deploy/gcp_gemini_screen/scripts/create_job.sh"
