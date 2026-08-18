#!/usr/bin/env bash
# Run a list of episodes sequentially with a HARD per-episode wall-clock kill.
#
# Why a watchdog and not just the SDK timeout: the retry layer already bounds each
# API call with asyncio.wait_for(asyncio.to_thread(...)), but a to_thread worker
# cannot be cancelled. When a call wedges, wait_for gives up and the episode
# finishes — then ThreadPoolExecutor's atexit handler JOINS the still-blocked
# worker and the process hangs at shutdown, forever, holding the whole batch
# behind it. Observed: M430 wrote 41 frames, then sat at 0% CPU with an
# ESTABLISHED socket for 15+ minutes.
#
# macOS ships no coreutils `timeout`, hence the explicit watchdog.
#
#   ./cloud/run_batch.sh "M430/foo M431/bar" [seconds]
set -uo pipefail

TASK_LIST="${1:?usage: run_batch.sh \"task1 task2 ...\" [per_episode_seconds]}"

# Nothing in the agent loads .env, so a batch launched from a bare shell dies at
# step 0 with "Missing credentials" — 1.9s per episode, score 0.00, which reads
# exactly like ten task failures rather than one missing variable. Load it here,
# but let an explicitly-exported OPENAI_MODEL win over the file's.
_MODEL_OVERRIDE="${OPENAI_MODEL:-}"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
[ -n "$_MODEL_OVERRIDE" ] && export OPENAI_MODEL="$_MODEL_OVERRIDE"
[ -n "${OPENAI_API_KEY:-}" ] || { echo "FATAL: no OPENAI_API_KEY after loading .env" >&2; exit 1; }
echo "model=$OPENAI_MODEL  cap=${AGENT_MAX_STEPS:-unset}  key=loaded"
LIMIT="${2:-1500}"
SERVER="${SERVER:-http://127.0.0.1:8401}"
BRIDGE="${BRIDGE:-http://127.0.0.1:8093}"
OUT="${OUT:-/tmp/sol10}"
# Overridable so a rerun can point at a SEPARATE set of mock servers. Rebuilding
# websites/*/dist in place would swap the bundle under episodes already running
# against :5201-5205; a second build served on other ports keeps the two apart.
ORIGINS="${ORIGINS:-shop=http://127.0.0.1:5201,market=http://127.0.0.1:5202,mail=http://127.0.0.1:5203,calendar=http://127.0.0.1:5204,food=http://127.0.0.1:5205}"
MOCK_PORTS="${MOCK_PORTS:-5201 5202 5203 5204 5205}"

# Surface a wedged call faster than the default 3 x 120s.
export LLM_CALL_TIMEOUT="${LLM_CALL_TIMEOUT:-90}"
export LLM_MAX_ATTEMPTS="${LLM_MAX_ATTEMPTS:-2}"

# Per-lane, so two lanes on one box cannot read each other's faults. lane.sh
# exports the same path for its supervisor.
FAULT_FILE="${FAULT_FLAG:-/tmp/lane_fault_${SERVER##*:}}"
RETRY_LIST=""
rm -f "$FAULT_FILE"

for T in $TASK_LIST; do
  SHORT="${T%%/*}"

  # Resume. Background tasks in this environment get SIGTERMed wholesale — all
  # three lanes died at the same instant mid-batch, twice. Rather than fight it,
  # make a relaunch idempotent: an episode that already produced a trajectory is
  # skipped, so re-running the same command picks up exactly where it stopped.
  if ls "$OUT/${SHORT}_"*.jsonl >/dev/null 2>&1; then
    echo "===== $SHORT  already scored — skipping"
    continue
  fi

  echo "===== $SHORT  (limit ${LIMIT}s)"

  # Pre-flight. Four parallel Chromiums (five app tabs each) plus four gyms was
  # enough for the OS to reap every gym mid-batch; the episodes then died with
  # rc=137 and no result. Check the stack is actually alive FIRST, so a dead gym
  # is a loud skip instead of a silent zero that enters the ledger as a breaker.
  DEAD=""
  [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$SERVER/")" = "200" ] || DEAD="gym($SERVER)"
  [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BRIDGE/bridge/sessions")" = "200" ] || DEAD="$DEAD bridge($BRIDGE)"
  for p in $MOCK_PORTS; do
    [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1:$p/")" = "200" ] || DEAD="$DEAD mock:$p"
  done
  if [ -n "$DEAD" ]; then
    echo "  FATAL: stack down before $SHORT -> $DEAD  (SKIPPED, not a task result)"
    continue
  fi

  PYTHONPATH=. .venv/bin/python -m eval.run \
      --agent openai_pixel --tasks "$T" --seeds 0 \
      --server "$SERVER" --app-origins "$ORIGINS" --bridge-url "$BRIDGE" \
      --out-traj "$OUT" --headless --no-video > "/tmp/ep_${SHORT}.log" 2>&1 &
  PID=$!

  ( sleep "$LIMIT"
    if kill -0 "$PID" 2>/dev/null; then
      echo "  [watchdog] $SHORT exceeded ${LIMIT}s — killing (infra fault, not a task result)"
      kill -9 "$PID" 2>/dev/null
    fi ) & WD=$!

  # Mid-episode health. The pre-flight above only proves the stack was alive at
  # the START; bridges have died PART-WAY through an episode, and the agent then
  # carries on against the mock's own demo data and produces a scored 0.00 that
  # is indistinguishable from a real failure. Kill the episode instead, so it
  # lands as "NO RESULT" and is excluded from the ledger rather than poisoning it.
  #
  # Watching the bridge alone is not enough, and this cost a whole M444 run: the
  # GYM died, the bridge stayed up, and the supervisor respawned the gym on the
  # DEFAULT task with an empty world. Liveness said healthy the entire time. The
  # episode kept driving a world that was not the task's and produced a scored
  # trajectory that was pure noise. So the check is identity, not liveness: the
  # gym must still be serving THIS task. A respawn changes task_id, which is the
  # one signal that distinguishes a fresh process from a healthy one.
  rm -f "$FAULT_FILE"
  ( while kill -0 "$PID" 2>/dev/null; do
      sleep 15
      if [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BRIDGE/bridge/sessions")" != "200" ]; then
        sleep 10   # one retry — the supervisor may be respawning it right now
        if [ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BRIDGE/bridge/sessions")" != "200" ] \
           && kill -0 "$PID" 2>/dev/null; then
          echo "  [health] bridge died during $SHORT — killing episode (fault, NOT a task result)"
          echo "bridge died" > "$FAULT_FILE"
          kill -9 "$PID" 2>/dev/null; exit 0
        fi
      fi
      LIVE=$(curl -s -m 5 -H "X-Harness-Token: ${HARNESS_TOKEN:-oracle-check}" \
               "$SERVER/_harness/world" 2>/dev/null \
             | .venv/bin/python -c 'import json,sys
try: print(json.load(sys.stdin).get("task_id") or "")
except Exception: print("")' 2>/dev/null)
      if [ -n "$LIVE" ] && [ "$LIVE" != "$T" ] && kill -0 "$PID" 2>/dev/null; then
        echo "  [health] gym is serving '$LIVE', not '$T' — world was reset under the episode"
        echo "gym world reset ($LIVE)" > "$FAULT_FILE"
        kill -9 "$PID" 2>/dev/null; exit 0
      fi
    done ) & HW=$!

  wait "$PID" 2>/dev/null
  RC=$?
  kill -9 "$WD" 2>/dev/null; wait "$WD" 2>/dev/null
  kill -9 "$HW" 2>/dev/null; wait "$HW" 2>/dev/null

  # A faulted episode must never leave a scored file behind. Whatever it wrote
  # describes a world that was not the task's, and on a relaunch the resume check
  # above would treat it as "already scored" and skip the task for good.
  if [ -s "$FAULT_FILE" ]; then
    rm -f "$OUT/${SHORT}_"*.jsonl
    echo "  FAULT: $(cat "$FAULT_FILE") — output discarded, retrying $SHORT once"
    rm -f "$FAULT_FILE"
    RETRY_LIST="$RETRY_LIST $T"
    continue
  fi

  LINE=$(grep -E "^M4[0-9]{2}" "/tmp/ep_${SHORT}.log" | tail -1)
  if [ -n "$LINE" ]; then
    echo "  $LINE"
  else
    echo "  NO RESULT (rc=$RC) — see /tmp/ep_${SHORT}.log"
  fi
  # A wedged worker thread can survive its parent; clear it before the next episode.
  pkill -9 -f "eval\.run --agent openai_pixel --tasks $T" 2>/dev/null
done

# One retry pass for episodes killed by an infra fault. A task that faults twice
# is reported as having no result rather than being quietly dropped, because a
# missing row in the ledger reads as "not run" while a zero reads as a breaker.
if [ -n "${RETRY_LIST// /}" ]; then
  echo "===== retrying faulted episodes:$RETRY_LIST"
  for T in $RETRY_LIST; do
    SHORT="${T%%/*}"
    ls "$OUT/${SHORT}_"*.jsonl >/dev/null 2>&1 && continue
    echo "===== $SHORT (retry)"
    rm -f "$FAULT_FILE"
    PYTHONPATH=. .venv/bin/python -m eval.run \
        --agent openai_pixel --tasks "$T" --seeds 0 \
        --server "$SERVER" --app-origins "$ORIGINS" --bridge-url "$BRIDGE" \
        --out-traj "$OUT" --headless --no-video > "/tmp/ep_${SHORT}.log" 2>&1
    LINE=$(grep -E "^M4[0-9]{2}" "/tmp/ep_${SHORT}.log" | tail -1)
    [ -n "$LINE" ] && echo "  $LINE" || echo "  NO RESULT on retry — see /tmp/ep_${SHORT}.log"
  done
fi
echo "===== batch done"
