#!/usr/bin/env bash
# One Cloud Run Job task == one agent episode, ON THE REALISTIC MOCK UIs.
#
# The whole stack comes up inside this container: gym -> five mock SPAs -> bridge,
# then eval.run drives the agent against the MOCK origins with --app-origins.
# There is no code path here that runs against the gym's own Jinja HTML.
#
# Exit code is deliberately 0 when the agent merely fails the task: a failed
# episode is DATA. A non-zero exit makes Cloud Run retry and pollutes results.
# Only genuine infra faults (a service never came up) exit non-zero.
set -uo pipefail

IDX="${CLOUD_RUN_TASK_INDEX:-0}"
MANIFEST="${MANIFEST_PATH:-/app/cloud/manifest.json}"
RUN_ID="${RUN_ID:-local}"
GYM_PORT=8000
BRIDGE_PORT=8093

export HARNESS_TOKEN="${HARNESS_TOKEN:-cloud-$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
export AGENT_MAX_STEPS="${AGENT_MAX_STEPS:-100}"
# Reward-leakage suppression. The agent default is 0, which makes the harness
# tell the agent its running score and the milestones that fired after every
# action. Benchmark recordings must run with 1 or they are not capability
# evidence. Default to 1 here so a cloud recording cannot leak by omission.
export AGENT_EVAL_MODE="${AGENT_EVAL_MODE:-1}"
export OPENAI_MODEL="${OPENAI_MODEL:-gpt-5.6-sol}"
# Anthropic agents (pixel / pixel_coord / llm) read their model from
# $ANTHROPIC_MODEL (agents/pixel_agent.py) and their key from
# $ANTHROPIC_API_KEY. Left unset the OpenAI path below is byte-identical to
# what it was; set it and this container runs a Claude episode instead.
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-}"
mkdir -p "${TRAJ_DIR:-/tmp/traj}" "${SCREENS_DIR:-/tmp/screens}"

BRIEF_FILE=/tmp/brief_override.txt
read -r TASK_ID SEED AGENT <<<"$(python - "$MANIFEST" "$IDX" "$BRIEF_FILE" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1]))["runs"]
r = rows[int(sys.argv[2]) % len(rows)]
# A hint probe replaces the whole brief. It is written to a file, not printed,
# because a brief carries spaces and newlines that `read -r` would split on.
open(sys.argv[3], "w").write(r.get("brief") or "")
# Pixel/SoM agents only. The DOM agents (openai/llm) drive gym-HTML selectors that
# do not exist in the mocks, and eval.run rejects them in bridged mode anyway.
print(r["task_id"], r.get("seed", 0), r.get("agent", "openai_pixel"))
PY
)"
BRIEF_ARGS=()
if [ -s "$BRIEF_FILE" ]; then
  BRIEF_ARGS=(--brief-override "$(cat "$BRIEF_FILE")")
fi

# eval.run's --model flag is the ANTHROPIC model id; the OpenAI agents ignore it
# and read $OPENAI_MODEL instead. Pass it only for the Anthropic-backed agents so
# the trajectory records pixel[claude-...] rather than pixel[default].
MODEL_ARGS=()
case "$AGENT" in
  pixel|pixel_coord|llm)
    if [ -n "$ANTHROPIC_MODEL" ]; then MODEL_ARGS=(--model "$ANTHROPIC_MODEL"); fi
    SHOW_MODEL="${ANTHROPIC_MODEL:-<pixel_agent default>}" ;;
  *) SHOW_MODEL="$OPENAI_MODEL" ;;
esac

# eval_mode is echoed so every uploaded episode.log carries proof of the value
# the container ACTUALLY ran with. The leak strings are built in an else-branch
# of `if self.eval_mode` inside the agent, so they cannot be grepped for after
# the fact when suppression worked - this banner is the audit trail.
BRIEF_STATE=$([ -s "$BRIEF_FILE" ] && echo "OVERRIDDEN (hint probe)" || echo "stock")
echo "[task $IDX] $TASK_ID seed=$SEED agent=$AGENT model=$SHOW_MODEL cap=$AGENT_MAX_STEPS eval_mode=$AGENT_EVAL_MODE brief=$BRIEF_STATE (REALISTIC UI)"
if [ -s "$BRIEF_FILE" ]; then echo "[task $IDX] brief override: $(cat "$BRIEF_FILE")"; fi

wait_for () {  # url, label, tries
  for _ in $(seq 1 "${3:-60}"); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$1" || true)
    case "$code" in 200|301|302|404) echo "[task $IDX] $2 up"; return 0;; esac
    sleep 1
  done
  echo "[task $IDX] FATAL: $2 never became ready (last=${code:-none})" >&2
  return 1
}

# --- gym --------------------------------------------------------------------
uvicorn server.main:app --host 127.0.0.1 --port "$GYM_PORT" --log-level warning &
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' -H "X-Harness-Token: $HARNESS_TOKEN" \
         "http://127.0.0.1:$GYM_PORT/_harness/tasks" || true)
  [ "$code" = "200" ] && break
  sleep 1
done
[ "${code:-}" = "200" ] || { echo "[task $IDX] FATAL: gym not ready" >&2; exit 1; }
echo "[task $IDX] gym up"

# --- the five mock SPAs -----------------------------------------------------
python /app/cloud/serve_spa.py /app/mocks/shop     5201 &
python /app/cloud/serve_spa.py /app/mocks/market   5202 &
python /app/cloud/serve_spa.py /app/mocks/mail     5203 &
python /app/cloud/serve_spa.py /app/mocks/calendar 5204 &
python /app/cloud/serve_spa.py /app/mocks/food     5205 &
for p in 5201 5202 5203 5204 5205; do
  wait_for "http://127.0.0.1:$p/" "mock :$p" 40 || exit 1
done

# --- bridge -----------------------------------------------------------------
# BRIDGE_TICK=0 because in bridged mode the HARNESS owns the scheduler clock;
# leaving the bridge to tick as well double-advances it and re-fires delivered
# cross-app events.
#
# BRIDGE_DEFAULT_SESSION=1 because eval.run gives each mock tab only
# "?bridge=<url>" with no session id, so the mocks talk to the UNSCOPED
# /bridge/state and /bridge/act routes. Those are opt-in and return 503 by
# default; without this the mock quietly renders its own built-in demo data and
# no action ever reaches the engine — every task scores 0.00 and it reads as a
# model failure rather than a wiring fault. One gym + one episode per container,
# so the unscoped "shared" world is exactly this episode's world.
GYM_URLS="http://127.0.0.1:$GYM_PORT" BRIDGE_TICK=0 BRIDGE_AUTOSCALE=0 \
BRIDGE_DEFAULT_SESSION=1 \
CUA_HUB_URL_SHOP=http://127.0.0.1:5201 CUA_HUB_URL_MARKET=http://127.0.0.1:5202 \
CUA_HUB_URL_MAIL=http://127.0.0.1:5203 CUA_HUB_URL_CALENDAR=http://127.0.0.1:5204 \
CUA_HUB_URL_FOOD=http://127.0.0.1:5205 \
uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BRIDGE_PORT" --log-level warning &
wait_for "http://127.0.0.1:$BRIDGE_PORT/bridge/sessions" "bridge" 40 || exit 1

# --- the episode ------------------------------------------------------------
ORIGINS="shop=http://127.0.0.1:5201,market=http://127.0.0.1:5202,mail=http://127.0.0.1:5203,calendar=http://127.0.0.1:5204,food=http://127.0.0.1:5205"
set +e
python -m eval.run \
  --agent "$AGENT" \
  "${MODEL_ARGS[@]}" \
  --tasks "$TASK_ID" \
  --seeds "$SEED" \
  --server "http://127.0.0.1:$GYM_PORT" \
  --app-origins "$ORIGINS" \
  --bridge-url "http://127.0.0.1:$BRIDGE_PORT" \
  --out-traj "${TRAJ_DIR:-/tmp/traj}" \
  --out-screens "${SCREENS_DIR:-/tmp/screens}" \
  "${BRIEF_ARGS[@]}" \
  --headless 2>&1 | tee /tmp/episode.log
EVAL_RC=$?
set -e
echo "[task $IDX] eval.run rc=$EVAL_RC"

# --- publish ----------------------------------------------------------------
if [ -n "${RESULTS_BUCKET:-}" ]; then
  python /app/cloud/upload.py \
    --bucket "$RESULTS_BUCKET" --prefix "runs/$RUN_ID" \
    --traj-dir "${TRAJ_DIR:-/tmp/traj}" --log /tmp/episode.log \
    --screens-dir "${SCREENS_DIR:-/tmp/screens}" \
    --brief-override "$(cat "$BRIEF_FILE" 2>/dev/null || true)" \
    --task "$TASK_ID" --seed "$SEED" --index "$IDX" || echo "[task $IDX] upload failed" >&2
else
  echo "[task $IDX] RESULTS_BUCKET unset — results stay in the container" >&2
fi

exit 0
