#!/usr/bin/env bash
# Local Gemini pilot — 20 diverse tasks × seeds {0,1,2} = 60 episodes.
#
# Real Gemini via GOOGLE_API_KEY / GEMINI_API_KEY (source repo .env).
# Does NOT use Cloud Run / GCS. Does NOT touch sellable_breakers_v2.csv.
# Does NOT set GEMINI_MOCK=1.
#
# Usage:
#   ./deploy/gcp_gemini_screen/scripts/local_pilot_20.sh
#   CONCURRENCY=2 ./deploy/gcp_gemini_screen/scripts/local_pilot_20.sh
#   # resume / skip finished indexes (default):
#   SKIP_DONE=1 ./deploy/gcp_gemini_screen/scripts/local_pilot_20.sh
#
# Env of note:
#   CONCURRENCY     default 3 (laptop-safe 2–4)
#   AGENT_MAX_STEPS default 120 (same as Cloud Run worker / README)
#   MANIFEST_PATH   default manifests/local_pilot_20.json
#   LOCAL_RESULTS_DIR default out_pilot_20/results
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PY="${PY:-.venv/bin/python}"

# Load API key without printing secrets.
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${GOOGLE_API_KEY:-}${GEMINI_API_KEY:-}" ]]; then
  echo "ERROR: need GOOGLE_API_KEY or GEMINI_API_KEY (source .env)" >&2
  exit 1
fi

# Ensure generate_manifest --pilot-20 exists; write separate from smoke/full.
"$PY" deploy/gcp_gemini_screen/generate_manifest.py --pilot-20

export MANIFEST_PATH="${MANIFEST_PATH:-$ROOT/deploy/gcp_gemini_screen/manifests/local_pilot_20.json}"
export LOCAL_RESULTS_DIR="${LOCAL_RESULTS_DIR:-$ROOT/deploy/gcp_gemini_screen/out_pilot_20/results}"
export OUT_DIR="${OUT_DIR:-$ROOT/deploy/gcp_gemini_screen/out_pilot_20}"
export STATUS_FILE="${STATUS_FILE:-$OUT_DIR/STATUS.json}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-pro-preview}"
export AGENT_EVAL_MODE=1
export AGENT_MAX_STEPS="${AGENT_MAX_STEPS:-120}"
export LLM_CONTEXT_BUDGET="${LLM_CONTEXT_BUDGET:-900000}"
# Explicitly live — never mock for this pilot.
unset GEMINI_MOCK || true
unset GEMINI_USE_VERTEX || true
unset GCS_BUCKET || true
unset HARNESS_TOKEN || true

CONCURRENCY="${CONCURRENCY:-3}"
SKIP_DONE="${SKIP_DONE:-1}"
EXPECTED=60

mkdir -p "$LOCAL_RESULTS_DIR" "$OUT_DIR/logs" /tmp/gemini_census_pilot20

n_manifest="$("$PY" -c "import json; print(len(json.load(open('$MANIFEST_PATH'))))")"
if [[ "$n_manifest" -ne "$EXPECTED" ]]; then
  echo "ERROR: expected $EXPECTED manifest entries, got $n_manifest" >&2
  exit 1
fi

write_status() {
  local running="$1" done_n="$2" failed_n="$3" msg="$4"
  "$PY" - "$STATUS_FILE" "$running" "$done_n" "$failed_n" "$msg" <<'PY'
import json, sys, time
from pathlib import Path
path, running, done_n, failed_n, msg = sys.argv[1:6]
Path(path).write_text(json.dumps({
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "running": int(running),
    "done": int(done_n),
    "failed_worker_exits": int(failed_n),
    "expected": 60,
    "message": msg,
    "results_dir": "deploy/gcp_gemini_screen/out_pilot_20/results",
}, indent=2) + "\n", encoding="utf-8")
PY
}

count_done() {
  find "$LOCAL_RESULTS_DIR" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l | tr -d ' '
}

run_one() {
  local idx="$1"
  local log="$OUT_DIR/logs/${idx}.log"
  local tmp_base="/tmp/gemini_census_pilot20/${idx}"
  export CLOUD_RUN_TASK_INDEX="$idx"
  export TRAJ_DIR="$tmp_base/traj"
  export SCREENS_DIR="$tmp_base/screens"
  mkdir -p "$TRAJ_DIR" "$SCREENS_DIR"
  echo "[pilot20] start index=$idx $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$log"
  set +e
  "$PY" deploy/gcp_gemini_screen/worker/main.py >>"$log" 2>&1
  local rc=$?
  set -e
  # Free screenshot disk after episode (result JSON already in LOCAL_RESULTS_DIR).
  rm -rf "$tmp_base"
  echo "[pilot20] finish index=$idx rc=$rc $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$log"
  return "$rc"
}

echo "=== Gemini local pilot-20 ==="
echo "manifest=$MANIFEST_PATH"
echo "results=$LOCAL_RESULTS_DIR"
echo "concurrency=$CONCURRENCY AGENT_MAX_STEPS=$AGENT_MAX_STEPS model=$GEMINI_MODEL"
echo "GEMINI_USE_VERTEX=${GEMINI_USE_VERTEX:-unset} (AI Studio expected)"

# Build work queue of missing indexes.
QUEUE=()
for ((i=0; i<EXPECTED; i++)); do
  if [[ "$SKIP_DONE" == "1" && -f "$LOCAL_RESULTS_DIR/${i}.json" ]]; then
    continue
  fi
  QUEUE+=("$i")
done
echo "queued ${#QUEUE[@]} / $EXPECTED (skip_done=$SKIP_DONE, already=$(count_done))"

write_status 0 "$(count_done)" 0 "starting"
FAILED=0
RUNNING_PIDS=()
RUNNING_IDX=()

reap_one() {
  # Wait for any background job; update counters.
  if [[ ${#RUNNING_PIDS[@]} -eq 0 ]]; then
    return 1
  fi
  local pid="${RUNNING_PIDS[0]}"
  local idx="${RUNNING_IDX[0]}"
  set +e
  wait "$pid"
  local rc=$?
  set -e
  RUNNING_PIDS=("${RUNNING_PIDS[@]:1}")
  RUNNING_IDX=("${RUNNING_IDX[@]:1}")
  if [[ $rc -ne 0 ]]; then
    FAILED=$((FAILED + 1))
    echo "[pilot20] worker exit rc=$rc for index=$idx (continuing)" >&2
  fi
  write_status "${#RUNNING_PIDS[@]}" "$(count_done)" "$FAILED" "in_progress"
  return 0
}

for idx in "${QUEUE[@]}"; do
  while [[ ${#RUNNING_PIDS[@]} -ge $CONCURRENCY ]]; do
    reap_one || true
  done
  run_one "$idx" &
  RUNNING_PIDS+=("$!")
  RUNNING_IDX+=("$idx")
  write_status "${#RUNNING_PIDS[@]}" "$(count_done)" "$FAILED" "in_progress"
done

while [[ ${#RUNNING_PIDS[@]} -gt 0 ]]; do
  reap_one || true
done

DONE="$(count_done)"
write_status 0 "$DONE" "$FAILED" "finished_workers"
echo "=== workers done: results=$DONE/$EXPECTED failed_exits=$FAILED ==="

"$PY" deploy/gcp_gemini_screen/merge_results.py \
  --local-dir "$LOCAL_RESULTS_DIR" \
  --expected "$EXPECTED" \
  --out "$OUT_DIR"

write_status 0 "$DONE" "$FAILED" "merged"
echo
echo "Pilot complete → $OUT_DIR/"
ls -la "$OUT_DIR/"
