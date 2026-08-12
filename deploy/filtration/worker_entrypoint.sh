#!/usr/bin/env bash
# Cloud Run Jobs worker: one episode per task index.
# Reads CLOUD_RUN_TASK_INDEX → (task_id, seed) from MANIFEST_PATH, starts
# in-container bridged stack (gym + bridge + static hub mocks), runs Luna via
# openai_pixel, uploads result JSON to GCS.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
HUB_DIST="${HUB_DIST:-/hub_dist}"
MANIFEST_PATH="${MANIFEST_PATH:-/app/deploy/filtration/manifests/smoke_5x5_luna.json}"
GCS_BUCKET="${GCS_BUCKET:?set GCS_BUCKET}"
GCS_PREFIX="${GCS_PREFIX:-filtration/smoke}"
RUN_ID="${RUN_ID:-cr-$(date -u +%Y%m%dT%H%M%SZ)}"
HARNESS_TOKEN="${HARNESS_TOKEN:-bridged-filtration}"
AGENT="${AGENT:-openai_pixel}"
MODEL="${MODEL:-gpt-5.6-luna}"
STACK_SLOT="${STACK_SLOT:-0}"
OUT_TRAJ="${OUT_TRAJ:-/tmp/trajectories}"
OUT_SCREENS="${OUT_SCREENS:-/tmp/screenshots}"
RESULT_DIR="${RESULT_DIR:-/tmp/results}"
PY="${PY:-python3}"

mkdir -p "$OUT_TRAJ" "$OUT_SCREENS" "$RESULT_DIR" /tmp/logs
cd "$APP_ROOT"

INDEX="${CLOUD_RUN_TASK_INDEX:-0}"
export HARNESS_TOKEN STACK_SLOT

# Resolve ports (same map as tools/stack_ports.sh)
# shellcheck disable=SC1091
source "$APP_ROOT/tools/stack_ports.sh"
stack_ports_resolve

LOG=/tmp/logs/worker_${INDEX}.log
PIDF=/tmp/logs/worker_${INDEX}.pids
: >"$PIDF"
track_pid() { printf '%s %s\n' "$1" "$2" >>"$PIDF"; }

reap() {
  while read -r p match; do
    [ -n "${p:-}" ] || continue
    kill -TERM "$p" 2>/dev/null || true
  done <"$PIDF" || true
  sleep 1
  while read -r p match; do
    kill -KILL "$p" 2>/dev/null || true
  done <"$PIDF" || true
}
trap reap EXIT

echo "[worker] index=$INDEX run_id=$RUN_ID manifest=$MANIFEST_PATH" | tee -a "$LOG"

ENTRY_JSON="$("$PY" - <<PY
import json, sys
m = json.load(open("$MANIFEST_PATH"))
entries = m["entries"]
idx = int("$INDEX")
if idx < 0 or idx >= len(entries):
    print(f"index {idx} out of range 0..{len(entries)-1}", file=sys.stderr)
    sys.exit(2)
e = entries[idx]
print(json.dumps(e))
PY
)"
TASK_ID="$(echo "$ENTRY_JSON" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["task_id"])')"
SEED="$(echo "$ENTRY_JSON" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["seed"])')"
MODEL="$(echo "$ENTRY_JSON" | "$PY" -c 'import json,sys; e=json.load(sys.stdin); print(e.get("model") or "'"$MODEL"'")')"
AGENT="$(echo "$ENTRY_JSON" | "$PY" -c 'import json,sys; e=json.load(sys.stdin); print(e.get("agent") or "'"$AGENT"'")')"
export OPENAI_MODEL="$MODEL"

echo "[worker] task=$TASK_ID seed=$SEED model=$MODEL agent=$AGENT" | tee -a "$LOG"
echo "[worker] ports gym=$GYM_PORT bridge=$BRIDGE_PORT shop=$SHOP_PORT" | tee -a "$LOG"

# --- static hub mocks (baked dist; no vite / no localhost remote hub) ---
serve_dist() {
  local dir="$1" port="$2" name="$3"
  if [ ! -d "$dir" ]; then
    echo "[worker] FATAL: missing hub dist $dir" | tee -a "$LOG" >&2
    exit 3
  fi
  "$PY" "$APP_ROOT/deploy/filtration/spa_static_server.py" \
    --root "$dir" --port "$port" --bind 127.0.0.1 >>"$LOG" 2>&1 &
  track_pid $! "spa_static_server.py --port $port"
  echo "[worker] serving $name from $dir on :$port (SPA)" | tee -a "$LOG"
}

serve_dist "$HUB_DIST/amazon_mock" "$SHOP_PORT" shop
serve_dist "$HUB_DIST/ebay_mock" "$MARKET_PORT" market
serve_dist "$HUB_DIST/gmail_mock" "$MAIL_PORT" mail
serve_dist "$HUB_DIST/google_calendar_mock" "$CALENDAR_PORT" calendar
serve_dist "$HUB_DIST/uber_eats_mock" "$FOOD_PORT" food

# --- gym ---
"$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$GYM_PORT" --log-level warning >>"$LOG" 2>&1 &
track_pid $! "--port $GYM_PORT"
sleep 2

# --- bridge wired to THIS container's mocks ---
# Export CUA_HUB_URL_* into the worker env (not only the bridge child) so
# eval.run's preflight sees the same hub_map the bridge process uses.
export CUA_HUB_URL_SHOP="http://127.0.0.1:$SHOP_PORT"
export CUA_HUB_URL_MARKET="http://127.0.0.1:$MARKET_PORT"
export CUA_HUB_URL_MAIL="http://127.0.0.1:$MAIL_PORT"
export CUA_HUB_URL_CALENDAR="http://127.0.0.1:$CALENDAR_PORT"
export CUA_HUB_URL_FOOD="http://127.0.0.1:$FOOD_PORT"
GYM_URL="http://127.0.0.1:$GYM_PORT" HARNESS_TOKEN="$HARNESS_TOKEN" BRIDGE_TICK=0 \
  BRIDGE_DEFAULT_SESSION=1 \
  "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BRIDGE_PORT" --log-level warning >>"$LOG" 2>&1 &
track_pid $! "--port $BRIDGE_PORT"
sleep 3

# Health gates
curl -sf -H "X-Harness-Token: $HARNESS_TOKEN" "http://127.0.0.1:$GYM_PORT/_harness/tasks" >/dev/null \
  || { echo "[worker] gym health FAIL" | tee -a "$LOG" >&2; exit 1; }
curl -sf "http://127.0.0.1:$BRIDGE_PORT/bridge/actions" >/dev/null \
  || { echo "[worker] bridge actions FAIL" | tee -a "$LOG" >&2; exit 1; }

HUB_SOURCE="$(curl -sf "http://127.0.0.1:$BRIDGE_PORT/bridge/health" \
  | "$PY" -c 'import json,sys; print(json.load(sys.stdin).get("hub_source","?"))' 2>/dev/null || echo unavailable)"
if [ "$HUB_SOURCE" != "explicit-env" ]; then
  echo "[worker] FATAL: hub_source='$HUB_SOURCE' (want explicit-env)" | tee -a "$LOG" >&2
  exit 3
fi
echo "[worker] health OK hub_source=$HUB_SOURCE" | tee -a "$LOG"

ORIGINS="shop=http://127.0.0.1:$SHOP_PORT,market=http://127.0.0.1:$MARKET_PORT,mail=http://127.0.0.1:$MAIL_PORT,calendar=http://127.0.0.1:$CALENDAR_PORT,food=http://127.0.0.1:$FOOD_PORT"

START_TS="$("$PY" -c 'import time; print(time.time())')"
set +e
HARNESS_TOKEN="$HARNESS_TOKEN" OPENAI_MODEL="$OPENAI_MODEL" "$PY" -m eval.run \
  --agent "$AGENT" --model "$MODEL" \
  --tasks "$TASK_ID" --seeds "$SEED" \
  --server "http://127.0.0.1:$GYM_PORT" \
  --app-origins "$ORIGINS" --bridge-url "http://127.0.0.1:$BRIDGE_PORT" \
  --headless --no-video \
  --out-traj "$OUT_TRAJ" --out-screens "$OUT_SCREENS" \
  >>"$LOG" 2>&1
EVAL_RC=$?
set -e
END_TS="$("$PY" -c 'import time; print(time.time())')"

RESULT_PATH="$RESULT_DIR/${INDEX}_$(echo "$TASK_ID" | tr '/' '_')_s${SEED}.json"
export CLOUD_RUN_TASK_INDEX="$INDEX"
export _TASK_ID="$TASK_ID" _SEED="$SEED" _MODEL="$MODEL" _AGENT="$AGENT"
export _HUB_SOURCE="$HUB_SOURCE" _EVAL_RC="$EVAL_RC"
export _START_TS="$START_TS" _END_TS="$END_TS" _RESULT_PATH="$RESULT_PATH"
export _LOG_PATH="$LOG"
export OUT_TRAJ OUT_SCREENS GCS_BUCKET GCS_PREFIX RUN_ID
"$PY" - <<'PY'
import json, os
from pathlib import Path

index = int(os.environ["CLOUD_RUN_TASK_INDEX"])
task_id = os.environ["_TASK_ID"]
seed = int(os.environ["_SEED"])
model = os.environ["_MODEL"]
agent = os.environ["_AGENT"]
hub_source = os.environ["_HUB_SOURCE"]
eval_rc = int(os.environ["_EVAL_RC"])
wall_s = float(os.environ["_END_TS"]) - float(os.environ["_START_TS"])
out_traj = Path(os.environ["OUT_TRAJ"])
result_path = Path(os.environ["_RESULT_PATH"])
log_path = Path(os.environ.get("_LOG_PATH", ""))

# Raw-log failure scan. The structured trajectory ``error`` field is empty for
# exactly the failure we care about most (a non-retryable provider error that the
# agent loop swallowed), so classify the worker log text as well and never rely on
# a single channel. See harness/api_failure_class.py.
from harness.api_failure_class import (  # noqa: E402
    classify_api_failure as classify_error_field,
    scan_log_text,
)

log_scan = scan_log_text(log_path.read_text(errors="ignore")
                         if log_path.is_file() else "")

# Published short-context rates (OpenAI / Anthropic / Cursor, 2026-08-04)
RATES = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-sol": (5.00, 30.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
}
rate_in, rate_out = RATES.get(model, (5.00, 30.00 if "gpt" in model else 25.00))
RATE_IN = rate_in / 1_000_000
RATE_OUT = rate_out / 1_000_000

slug = task_id.replace("/", "_")
cands = sorted(out_traj.glob(f"{slug}__{seed}__*.jsonl"))
traj_path = cands[0] if cands else None

success = None
score = None
steps = 0
tokens_in = 0
tokens_out = 0
error = ""
disposition = "ERROR"
agent_name = f"{agent}[{model}]"

# Trajectories are one pretty-printed JSON object with a .jsonl extension.
if traj_path and traj_path.exists():
    data = json.loads(traj_path.read_text())
    agent_name = data.get("agent_name") or agent_name
    vr = data.get("verifier_result") or {}
    success = vr.get("success")
    score = vr.get("score")
    step_list = data.get("steps") or []
    steps = len(step_list) if isinstance(step_list, list) else int(step_list or 0)
    for s in step_list if isinstance(step_list, list) else []:
        if not isinstance(s, dict):
            continue
        tokens_in += int(s.get("tokens_in") or 0)
        tokens_out += int(s.get("tokens_out") or 0)
    if data.get("error"):
        error = str(data.get("error"))
    if success is True:
        disposition = "HOLD"
    elif success is False:
        disposition = "BREAK"
    else:
        disposition = "ERROR"
        error = error or f"missing verifier success (eval_rc={eval_rc})"
else:
    error = f"no trajectory written (eval_rc={eval_rc})"
    disposition = "ERROR"

# A credit/billing death is not a model decision: the episode stopped existing
# mid-flight, so its BREAK/HOLD must never be counted. Surface it on the episode
# record (and backfill ``error`` when the agent swallowed it) so every downstream
# aggregation can exclude it without re-reading logs.
failure_class = log_scan["failure_class"] or classify_error_field(error)
credit_death = bool(log_scan["credit_death"]) or failure_class == "credit_exhausted"
if credit_death and not error:
    error = f"credit_exhausted (from worker log): {log_scan['excerpt']}"[:500]

api_usd = tokens_in * RATE_IN + tokens_out * RATE_OUT
# Keep luna_usd for Phase 1 merge compat; equal to api_usd when model is Luna.
luna_usd = api_usd
safe_task = task_id.replace("/", "_")
gcs_object = (
    f"{os.environ.get('GCS_PREFIX', 'filtration/smoke').rstrip('/')}/"
    f"{os.environ.get('RUN_ID', 'run')}/"
    f"{index:04d}_{safe_task}_s{seed}.json"
)

result = {
    "index": index,
    "task_id": task_id,
    "seed": seed,
    "model": model,
    "agent": agent,
    "agent_name": agent_name,
    "success": success,
    "disposition": disposition,
    "score": score,
    "steps": steps,
    "hub_source": hub_source,
    "error": error,
    "failure_class": failure_class,
    "credit_death": credit_death,
    # False only for a provider death that voids the episode; a genuine BREAK or
    # HOLD stays valid even if a transient 429/529 was retried along the way.
    "valid": not credit_death,
    "transient_retries": log_scan["transient"],
    "credit_at_step": log_scan["credit_at_step"],
    "eval_rc": eval_rc,
    "wall_s": round(wall_s, 2),
    "tokens_in": tokens_in,
    "tokens_out": tokens_out,
    "api_usd": round(api_usd, 6),
    "luna_usd": round(luna_usd, 6),
    "traj_path": str(traj_path) if traj_path else "",
    "gcs_uri": f"gs://{os.environ['GCS_BUCKET']}/{gcs_object}",
    "run_id": os.environ.get("RUN_ID"),
}
result_path.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"wrote": str(result_path), **{k: result[k] for k in (
    "disposition", "steps", "hub_source", "luna_usd", "failure_class",
    "credit_death")}}))
Path("/tmp/gcs_object.txt").write_text(gcs_object)
Path("/tmp/credit_death.txt").write_text("1" if credit_death else "0")
PY

# Upload to GCS
GCS_OBJECT="$(cat /tmp/gcs_object.txt)"
"$PY" - <<PY
from google.cloud import storage
from pathlib import Path
import tarfile
import tempfile

bucket_name = "$GCS_BUCKET"
blob_name = "$GCS_OBJECT"
path = Path("$RESULT_PATH")
out_traj = Path("$OUT_TRAJ")
out_screens = Path("$OUT_SCREENS")
client = storage.Client()
bucket = client.bucket(bucket_name)
blob = bucket.blob(blob_name)
blob.upload_from_filename(str(path), content_type="application/json")
# also upload log (best-effort)
log = Path("$LOG")
if log.exists():
    bucket.blob(blob_name.replace(".json", ".log")).upload_from_filename(str(log), content_type="text/plain")
print(f"uploaded gs://{bucket_name}/{blob_name}")

# Full traj JSONL + screenshot tree — needed for Eligible Suite galleries.
# Scorecard JSON alone is not enough for packaging.
prefix = blob_name.rsplit("/", 1)[0]
stem = Path(blob_name).stem  # e.g. 0001_mp_040_..._s0
result = __import__("json").loads(path.read_text())
traj_path = Path(result.get("traj_path") or "")
if traj_path.is_file():
    dest = f"{prefix}/artifacts/{stem}/{traj_path.name}"
    bucket.blob(dest).upload_from_filename(str(traj_path), content_type="application/json")
    print(f"uploaded gs://{bucket_name}/{dest}")
    ep = traj_path.stem
    shot_dir = out_screens / ep
    if not shot_dir.is_dir():
        # fallback: any dir matching episode stem
        cands = [p for p in out_screens.rglob(ep) if p.is_dir()]
        shot_dir = cands[0] if cands else None
    if shot_dir and shot_dir.is_dir():
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tar_path = Path(tmp.name)
        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(shot_dir, arcname=ep)
            shot_blob = f"{prefix}/artifacts/{stem}/{ep}_screens.tar.gz"
            bucket.blob(shot_blob).upload_from_filename(
                str(tar_path), content_type="application/gzip"
            )
            print(f"uploaded gs://{bucket_name}/{shot_blob}")
        finally:
            tar_path.unlink(missing_ok=True)
PY

# Fail the Cloud Run task if episode errored hard (no traj) so retries can help.
if [ ! -s "$RESULT_PATH" ]; then
  exit 1
fi
DISP="$("$PY" -c 'import json; print(json.load(open("'"$RESULT_PATH"'"))["disposition"])')"

# Emit the credit death on stdout with a stable, greppable sentinel. The earlier
# monitors polled the result JSON `error` field (empty for a swallowed provider
# error) and a Cloud Logging text query for `credit_balance_too_low` (a token
# Anthropic never sends), so a third of a panel could die on credits with every
# channel reporting clean. This line makes the Cloud Logging query work.
if [ "$(cat /tmp/credit_death.txt 2>/dev/null || echo 0)" = "1" ]; then
  echo "[worker] FILTRATION_CREDIT_DEATH task=$TASK_ID seed=$SEED run_id=$RUN_ID" \
    | tee -a "$LOG" >&2
fi

if [ "$DISP" = "ERROR" ] && [ "${FAIL_ON_ERROR:-1}" = "1" ]; then
  echo "[worker] episode ERROR — exiting 1 for retry" | tee -a "$LOG" >&2
  exit 1
fi
echo "[worker] done disposition=$DISP" | tee -a "$LOG"
exit 0
