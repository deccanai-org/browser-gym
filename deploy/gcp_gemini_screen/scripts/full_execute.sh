#!/usr/bin/env bash
# Full 945-episode Gemini census execute.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
JOB_NAME="${JOB_NAME:-gemini-census-945}"

echo "Executing full job ${JOB_NAME} (945 tasks, check parallelism on the job) ..."
gcloud run jobs execute "${JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --wait

echo
echo "Merge when complete:"
echo "  .venv/bin/python deploy/gcp_gemini_screen/merge_results.py \\"
echo "    --gcs-bucket gs://\$GCS_BUCKET --expected 945 \\"
echo "    --out trajectories/gemini_census_\$(date +%Y%m%d)"
