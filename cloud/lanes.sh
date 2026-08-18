#!/usr/bin/env bash
# Bring up N independent gym+bridge LANES that share the five vite-preview mocks.
#
# A gym holds ONE world in a module-global SESSION, so concurrency is bounded by
# the number of gym processes. The mocks are lane-agnostic because the harness
# passes the bridge as a per-tab query param (?bridge=…), so all lanes can share
# one set of static servers on :5201-5205 — only the gym+bridge pair is per-lane.
#
#   ./cloud/lanes.sh 4        # lane 0 = 8401/8093, lane i = 840i+1 / 809i+3
set -uo pipefail
N="${1:-4}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export HARNESS_TOKEN="${HARNESS_TOKEN:-oracle-check}"

up () { curl -s -o /dev/null -w '%{http_code}' -m 4 "$1"; }

for i in $(seq 0 $((N-1))); do
  GP=$((8401+i)); BP=$((8093+i))
  if [ "$(up http://127.0.0.1:$GP/)" = "200" ]; then
    echo "lane $i: gym :$GP already up"
  else
    ( cd "$ROOT" && nohup "$PY" -m uvicorn server.main:app --host 127.0.0.1 \
        --port "$GP" --log-level warning >"/tmp/gym_$GP.log" 2>&1 & disown )
  fi
  # A live bridge is NOT good enough: this port may be a leftover whose pool
  # points at some older gym. That is how a batch silently runs against a stale
  # registry and every task 404s or gets a default world. Reuse only if the pool
  # is EXACTLY this lane's gym; otherwise take the port over.
  POOL=$(curl -s -m 4 "http://127.0.0.1:$BP/bridge/sessions" | "$PY" -c \
    'import json,sys
try: print(",".join(json.load(sys.stdin)["pool"]))
except Exception: print("")' 2>/dev/null)
  if [ "$POOL" = "http://127.0.0.1:$GP" ]; then
    echo "lane $i: bridge :$BP already up on the right gym"
  else
    if [ -n "$POOL" ]; then
      echo "lane $i: bridge :$BP was pooling '$POOL' — replacing it"
      lsof -nP -iTCP:$BP -sTCP:LISTEN -t 2>/dev/null | xargs -r kill -9
      sleep 1
    fi
    # BRIDGE_TICK=0: in bridged mode the HARNESS owns the scheduler clock. Letting
    # the bridge tick too double-advances it and re-fires delivered cross-app events.
    # BRIDGE_DEFAULT_SESSION=1 is REQUIRED for eval.run. The harness hands each
    # mock tab only "?bridge=<url>" with no session id, so the mocks use the
    # UNSCOPED /bridge/state and /bridge/act routes — which are opt-in and 503 by
    # default. Without this the mock silently falls back to its own built-in demo
    # data and every action dies at the bridge: the agent reads a fake world, the
    # engine records nothing, and all ten tasks score 0.00 while looking like
    # genuine model failures. Safe here because each lane owns one gym and runs
    # one episode at a time, so "the shared world" is exactly that episode's.
    ( cd "$ROOT" && GYM_URLS="http://127.0.0.1:$GP" BRIDGE_TICK=0 BRIDGE_AUTOSCALE=0 \
      BRIDGE_DEFAULT_SESSION=1 \
      CUA_HUB_URL_SHOP=http://127.0.0.1:5201 CUA_HUB_URL_MARKET=http://127.0.0.1:5202 \
      CUA_HUB_URL_MAIL=http://127.0.0.1:5203 CUA_HUB_URL_CALENDAR=http://127.0.0.1:5204 \
      CUA_HUB_URL_FOOD=http://127.0.0.1:5205 \
      nohup "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BP" \
        --log-level warning >"/tmp/bridge_$BP.log" 2>&1 & disown )
  fi
done

sleep 8
echo
for i in $(seq 0 $((N-1))); do
  GP=$((8401+i)); BP=$((8093+i))
  POOL=$(curl -s -m 4 "http://127.0.0.1:$BP/bridge/sessions" | "$PY" -c \
    'import json,sys
try: print(",".join(json.load(sys.stdin)["pool"]))
except Exception: print("UNREACHABLE")')
  printf "lane %s  gym :%s -> %s   bridge :%s -> pool %s\n" \
    "$i" "$GP" "$(up http://127.0.0.1:$GP/)" "$BP" "$POOL"
done
