#!/usr/bin/env bash
# Smoke: execute a 5-task Gemini census job (parallelism 5).
#
# Prereq: create a smoke job first, e.g.
#   TASKS=5 PARALLELISM=5 JOB_NAME=gemini-census-smoke \
#     IMAGE=... GCS_BUCKET=... PROJECT_ID=... \
#     ./deploy/gcp_gemini_screen/scripts/create_job.sh
#
# Then override the manifest to the smoke 5-entry file via execute env, OR
# bake MANIFEST_PATH into that job at create time (recommended):
#   (edit create_job or pass below)
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
JOB_NAME="${JOB_NAME:-gemini-census-smoke}"

echo "Executing smoke job ${JOB_NAME} ..."
gcloud run jobs execute "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --wait \
  --update-env-vars="MANIFEST_PATH=/app/deploy/gcp_gemini_screen/manifests/smoke_manifest_5.json"

echo
echo "When complete, merge:"
echo "  .venv/bin/python deploy/gcp_gemini_screen/merge_results.py \\"
echo "    --gcs-bucket gs://\$GCS_BUCKET --expected 5 \\"
echo "    --out trajectories/gemini_smoke_\$(date +%Y%m%d)"
