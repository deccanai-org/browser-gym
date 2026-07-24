#!/usr/bin/env bash
# Local smoke — validate worker logic for N indexes without Cloud Run.
#
# Default: GEMINI_MOCK=1 (no live Gemini call). Set GEMINI_MOCK=0 + GEMINI_API_KEY
# for a real 1-episode smoke.
#
# Usage:
#   ./deploy/gcp_gemini_screen/scripts/local_smoke.sh
#   TASK_INDEXES=0,1,2 ./deploy/gcp_gemini_screen/scripts/local_smoke.sh
#   GEMINI_MOCK=0 GEMINI_API_KEY=... TASK_INDEXES=0 ./deploy/gcp_gemini_screen/scripts/local_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PY="${PY:-.venv/bin/python}"

"$PY" deploy/gcp_gemini_screen/generate_manifest.py

export MANIFEST_PATH="${MANIFEST_PATH:-$ROOT/deploy/gcp_gemini_screen/manifests/smoke_manifest_5.json}"
export LOCAL_RESULTS_DIR="${LOCAL_RESULTS_DIR:-$ROOT/deploy/gcp_gemini_screen/local_results}"
export GEMINI_MOCK="${GEMINI_MOCK:-1}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-pro-preview}"
export AGENT_EVAL_MODE=1
# Avoid clobbering a shared gym — each index gets its own token+port.
unset HARNESS_TOKEN || true

mkdir -p "$LOCAL_RESULTS_DIR"
INDEXES="${TASK_INDEXES:-0,1,2,3,4}"
IFS=',' read -r -a ARR <<< "$INDEXES"

for idx in "${ARR[@]}"; do
  echo "=== local smoke task_index=${idx} mock=${GEMINI_MOCK} ==="
  CLOUD_RUN_TASK_INDEX="${idx}" "$PY" deploy/gcp_gemini_screen/worker/main.py
done

"$PY" deploy/gcp_gemini_screen/merge_results.py \
  --local-dir "$LOCAL_RESULTS_DIR" \
  --expected "${#ARR[@]}" \
  --out "$ROOT/deploy/gcp_gemini_screen/out_smoke"

echo
echo "Local smoke complete → deploy/gcp_gemini_screen/out_smoke/"
ls -la "$ROOT/deploy/gcp_gemini_screen/out_smoke/"
