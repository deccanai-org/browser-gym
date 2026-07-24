#!/usr/bin/env bash
# Gemini step-60 subsample — same tasks/seeds as pilot indexes, AGENT_MAX_STEPS=60.
#
# Real Gemini via GOOGLE_API_KEY / GEMINI_API_KEY (source repo .env).
# Does NOT use Cloud Run / GCS. Does NOT touch sellable_breakers_v2.csv.
#
# Default INDEXES (8): thrash M226×2, M249×2, M142×2 + cheap M73, M200.
# Override: INDEXES="36 48 12 9" ./deploy/gcp_gemini_screen/scripts/local_pilot_step60.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PY="${PY:-.venv/bin/python}"

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

export MANIFEST_PATH="${MANIFEST_PATH:-$ROOT/deploy/gcp_gemini_screen/manifests/local_pilot_20.json}"
export LOCAL_RESULTS_DIR="${LOCAL_RESULTS_DIR:-$ROOT/deploy/gcp_gemini_screen/out_pilot_step60/results}"
export OUT_DIR="${OUT_DIR:-$ROOT/deploy/gcp_gemini_screen/out_pilot_step60}"
export STATUS_FILE="${STATUS_FILE:-$OUT_DIR/STATUS.json}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.1-pro-preview}"
export AGENT_EVAL_MODE=1
export AGENT_MAX_STEPS="${AGENT_MAX_STEPS:-60}"
export LLM_CONTEXT_BUDGET="${LLM_CONTEXT_BUDGET:-900000}"
unset GEMINI_MOCK || true
unset GEMINI_USE_VERTEX || true
unset GCS_BUCKET || true
unset HARNESS_TOKEN || true

CONCURRENCY="${CONCURRENCY:-3}"
SKIP_DONE="${SKIP_DONE:-1}"
# shellcheck disable=SC2206
INDEXES=(${INDEXES:-36 37 48 49 12 14 9 21})

mkdir -p "$LOCAL_RESULTS_DIR" "$OUT_DIR/logs" "$OUT_DIR/traj" /tmp/gemini_census_step60

write_status() {
  local running="$1" done_n="$2" failed_n="$3" msg="$4"
  "$PY" - "$STATUS_FILE" "$running" "$done_n" "$failed_n" "$msg" "$OUT_DIR" <<'PY'
import json, sys, time
from pathlib import Path
path, running, done_n, failed_n, msg, out_dir = sys.argv[1:7]
Path(path).write_text(json.dumps({
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "running": int(running),
    "done": int(done_n),
    "failed_worker_exits": int(failed_n),
    "expected": None,
    "message": msg,
    "results_dir": f"{out_dir}/results",
    "agent_max_steps": 60,
}, indent=2) + "\n", encoding="utf-8")
PY
}

count_done() {
  local n=0
  for i in "${INDEXES[@]}"; do
    if [[ -f "$LOCAL_RESULTS_DIR/${i}.json" ]]; then
      n=$((n + 1))
    fi
  done
  echo "$n"
}

run_one() {
  local idx="$1"
  local log="$OUT_DIR/logs/${idx}.log"
  local tmp_base="/tmp/gemini_census_step60/${idx}"
  export CLOUD_RUN_TASK_INDEX="$idx"
  export TRAJ_DIR="$OUT_DIR/traj/${idx}"
  export SCREENS_DIR="$tmp_base/screens"
  mkdir -p "$TRAJ_DIR" "$SCREENS_DIR"
  echo "[step60] start index=$idx AGENT_MAX_STEPS=$AGENT_MAX_STEPS $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$log"
  set +e
  "$PY" deploy/gcp_gemini_screen/worker/main.py >>"$log" 2>&1
  local rc=$?
  set -e
  # Drop screenshots (heavy); keep traj JSON for per-step tokens_in.
  rm -rf "$tmp_base"
  echo "[step60] finish index=$idx rc=$rc $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$log"
  return "$rc"
}

echo "=== Gemini local pilot step-60 subsample ==="
echo "manifest=$MANIFEST_PATH"
echo "results=$LOCAL_RESULTS_DIR"
echo "indexes=${INDEXES[*]}"
echo "concurrency=$CONCURRENCY AGENT_MAX_STEPS=$AGENT_MAX_STEPS model=$GEMINI_MODEL"

QUEUE=()
for i in "${INDEXES[@]}"; do
  if [[ "$SKIP_DONE" == "1" && -f "$LOCAL_RESULTS_DIR/${i}.json" ]]; then
    continue
  fi
  QUEUE+=("$i")
done
echo "queued ${#QUEUE[@]} / ${#INDEXES[@]} (skip_done=$SKIP_DONE, already=$(count_done))"

write_status 0 "$(count_done)" 0 "starting"
FAILED=0
RUNNING_PIDS=()
RUNNING_IDX=()

reap_one() {
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
    echo "[step60] worker exit rc=$rc for index=$idx (continuing)" >&2
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
echo "=== workers done: results=$DONE/${#INDEXES[@]} failed_exits=$FAILED ==="

# Lightweight merge for this subsample (no full 60-expected merge).
"$PY" - "$LOCAL_RESULTS_DIR" "$OUT_DIR" "${INDEXES[@]}" <<'PY'
import json, sys
from pathlib import Path
from collections import defaultdict

results_dir = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
indexes = [int(x) for x in sys.argv[3:]]
rows = []
for i in indexes:
    p = results_dir / f"{i}.json"
    if p.exists():
        rows.append(json.loads(p.read_text()))
summary = {
    "n_expected": len(indexes),
    "n_result_files": len(rows),
    "indexes": indexes,
    "agent_max_steps": 60,
    "total_tokens_in": sum(int(r.get("tokens_in") or 0) for r in rows),
    "total_tokens_out": sum(int(r.get("tokens_out") or 0) for r in rows),
    "total_cost_usd_est": round(sum(float(r.get("cost_usd_est") or 0) for r in rows), 6),
    "episodes": [
        {
            "task_index": r["task_index"],
            "task_id": r["task_id"],
            "seed": r["seed"],
            "outcome": r["outcome"],
            "n_steps": r["n_steps"],
            "tokens_in": r["tokens_in"],
            "tokens_out": r["tokens_out"],
            "cost_usd_est": r["cost_usd_est"],
            "wall_s": r["wall_s"],
        }
        for r in rows
    ],
}
(out_dir / "cost_tracker_summary.json").write_text(
    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({
    "n": summary["n_result_files"],
    "cost": summary["total_cost_usd_est"],
    "tokens_in": summary["total_tokens_in"],
}, indent=2))
PY

write_status 0 "$DONE" "$FAILED" "merged"
echo
echo "Step-60 subsample complete → $OUT_DIR/"
ls -la "$OUT_DIR/"
