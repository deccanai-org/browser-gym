#!/usr/bin/env bash
# One self-contained lane: start a gym + bridge, run a task list through them,
# tear them down. Everything is a CHILD of this script.
#
# Why not start the servers separately and point episodes at them: a gym or
# bridge detached from a short-lived shell kept dying mid-batch — sometimes all
# four gyms at once, sometimes one bridge. The episodes then ran on against a
# dead bridge, the mock silently fell back to its own demo data, and the run
# scored 0.00 while looking exactly like a genuine model failure. Owning the
# processes for the lifetime of the batch removes that whole class of ghost.
#
#   ./cloud/lane.sh 8401 8093 "M434/foo M436/bar" [per_episode_seconds]
set -uo pipefail

GP="${1:?gym port}"; BP="${2:?bridge port}"; TASKS="${3:?task list}"; LIMIT="${4:-2100}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export HARNESS_TOKEN="${HARNESS_TOKEN:-oracle-check}"
# Shared between this script's supervisor and run_batch.sh: either can raise the
# fault, and run_batch.sh is what discards the tainted output and retries.
export FAULT_FLAG="/tmp/lane_fault_${GP}"
cd "$ROOT"

cleanup () { [ -n "${SUPPID:-}" ] && kill -9 "$SUPPID" 2>/dev/null
             [ -n "${BPID:-}" ] && kill -9 "$BPID" 2>/dev/null
             [ -n "${GPID:-}" ] && kill -9 "$GPID" 2>/dev/null; }
trap cleanup EXIT INT TERM

start_bridge () {
  GYM_URLS="http://127.0.0.1:$GP" BRIDGE_TICK=0 BRIDGE_AUTOSCALE=0 BRIDGE_DEFAULT_SESSION=1 \
  CUA_HUB_URL_SHOP=http://127.0.0.1:5201 CUA_HUB_URL_MARKET=http://127.0.0.1:5202 \
  CUA_HUB_URL_MAIL=http://127.0.0.1:5203 CUA_HUB_URL_CALENDAR=http://127.0.0.1:5204 \
  CUA_HUB_URL_FOOD=http://127.0.0.1:5205 \
  "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BP" --log-level warning \
        >>"/tmp/bridge_$BP.log" 2>&1 & BPID=$!
  for _ in $(seq 1 60); do
    [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$BP/bridge/sessions")" = "200" ] && return 0
    sleep 1
  done
  return 1
}

start_gym () {
  "$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$GP" --log-level warning \
        >>"/tmp/gym_$GP.log" 2>&1 & GPID=$!
  for _ in $(seq 1 90); do
    [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$GP/")" = "200" ] && return 0
    sleep 1
  done
  return 1
}

for p in "$GP" "$BP"; do lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | xargs kill -9 2>/dev/null; done
sleep 1

start_gym    || { echo "FATAL lane $GP: gym never came up" >&2; exit 1; }
start_bridge || { echo "FATAL lane $GP: bridge never came up" >&2; exit 1; }

# Supervisor. Both the gym and the bridge have been killed from outside
# mid-batch — empty logs, no traceback, just gone. Whatever is doing it, an
# episode that keeps running against a dead bridge is the dangerous outcome:
# the mock silently serves its own demo data and the run scores 0.00 looking
# like a real model failure. So respawn them, and record every respawn so a
# lane that flapped can be distrusted afterwards.
#
# Respawning is NOT enough on its own. The gym keeps the episode's world in a
# module global, so a fresh process comes up on the default task with an empty
# world: the episode carries on driving a world that is not the task's, and the
# suite then scores THAT. It looks like a model failure and is nothing of the
# kind — a respawn silently manufactures exactly the fake evidence this
# supervisor exists to prevent. So a respawn kills the in-flight episode too and
# drops a marker; run_batch.sh discards the partial output and retries the task
# against the rebuilt gym.
rm -f "$FAULT_FLAG"
( while true; do
    sleep 20
    down=""
    if [ "$(curl -s -o /dev/null -m 4 -w '%{http_code}' "http://127.0.0.1:$GP/")" != "200" ]; then
      echo "[supervisor] gym :$GP died — respawning" ; start_gym ; down="gym"
    fi
    if [ "$(curl -s -o /dev/null -m 4 -w '%{http_code}' "http://127.0.0.1:$BP/bridge/sessions")" != "200" ]; then
      echo "[supervisor] bridge :$BP died — respawning" ; start_bridge ; down="${down:+$down+}bridge"
    fi
    if [ -n "$down" ]; then
      echo "[supervisor] $down respawned with a fresh world — aborting the in-flight episode"
      echo "$down" > "$FAULT_FLAG"
      pkill -f "eval.run.*--server http://127.0.0.1:$GP" 2>/dev/null || true
    fi
  done ) & SUPPID=$!

POOL=$(curl -s -m 4 "http://127.0.0.1:$BP/bridge/sessions" | "$PY" -c \
  'import json,sys
try: print(",".join(json.load(sys.stdin)["pool"]))
except Exception: print("")')
if [ "$POOL" != "http://127.0.0.1:$GP" ]; then
  echo "FATAL lane $GP/$BP: bridge pools '$POOL', expected gym :$GP" >&2
  exit 1
fi
echo "lane up: gym :$GP  bridge :$BP  (pool $POOL)"

SERVER="http://127.0.0.1:$GP" BRIDGE="http://127.0.0.1:$BP" OUT="${OUT:-/tmp/sol10}" \
  "$ROOT/cloud/run_batch.sh" "$TASKS" "$LIMIT"
