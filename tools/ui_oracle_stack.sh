#!/usr/bin/env bash
# Bring up a bridged stack serving THIS repo's mock builds, for the new-UI oracle.
#
# Deliberately not reusing the :5201-5205 vite previews: those are served from a
# different checkout (~/Deccan AI/browser-gym), so edits made here never reach
# them. Everything below is served out of this working tree.
#
#   tools/ui_oracle_stack.sh          # gym 8440, bridge 8140, mocks 5231-5235
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
GP="${GP:-8440}"; BP="${BP:-8140}"
export HARNESS_TOKEN="${HARNESS_TOKEN:-oracle-check}"

PIDS=(); cleanup(){ for p in "${PIDS[@]:-}"; do kill -9 "$p" 2>/dev/null; done; }
trap cleanup EXIT INT TERM

for p in "$GP" "$BP" 5231 5232 5233 5234 5235; do
  lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | xargs kill -9 2>/dev/null
done
sleep 1

# Build the 5 mocks from source first. dist/ is gitignored (built, not committed),
# so on a fresh clone it does not exist yet — serving it would hand out an empty
# page. build_hub_mocks.sh runs the vite build for each mock into its own dist/.
echo "==> building the 5 mocks from source (dist/ is not committed)"
"$ROOT/tools/build_hub_mocks.sh" "$ROOT" "" >/tmp/uio_build.log 2>&1 \
  || { echo "mock build failed — see /tmp/uio_build.log"; exit 1; }

# All five from THIS repo's dist. Previously :5201-5205 were served from a
# different checkout, so the agent ran a build without the bridged-fee fix and
# saw a checkout total the engine never charged.
"$PY" cloud/serve_spa.py websites/xmazon_mock/dist            5231 >/tmp/uio_5231.log 2>&1 & PIDS+=($!)
"$PY" cloud/serve_spa.py websites/xbay_mock/dist              5232 >/tmp/uio_5232.log 2>&1 & PIDS+=($!)
"$PY" cloud/serve_spa.py websites/xmail_mock/dist             5233 >/tmp/uio_5233.log 2>&1 & PIDS+=($!)
"$PY" cloud/serve_spa.py websites/xoogle_calendar_mock/dist   5234 >/tmp/uio_5234.log 2>&1 & PIDS+=($!)
"$PY" cloud/serve_spa.py websites/xber_eats_mock/dist         5235 >/tmp/uio_5235.log 2>&1 & PIDS+=($!)

"$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$GP" --log-level warning \
      >/tmp/uio_gym.log 2>&1 & PIDS+=($!)
for _ in $(seq 1 90); do
  [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$GP/")" = "200" ] && break; sleep 1
done

# BRIDGE_NO_HUB=1: the mock tabs poll /bridge/state, so the bridge never needs to
# PUSH state to them. Leaving push on made every action POST to a state endpoint
# the static SPA servers don't have; against a remote hub those POSTs hit the 30s
# default and froze the single worker, so a tab reloaded mid-run got no state and
# fell back to demo data. No hub map -> no push -> no freeze.
GYM_URLS="http://127.0.0.1:$GP" BRIDGE_TICK=0 BRIDGE_AUTOSCALE=0 BRIDGE_DEFAULT_SESSION=1 \
BRIDGE_NO_HUB=1 \
"$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BP" --log-level warning \
      >/tmp/uio_bridge.log 2>&1 & PIDS+=($!)
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$BP/bridge/sessions")" = "200" ] && break; sleep 1
done

for p in 5231 5232 5233 5234 5235; do
  printf "  mock :%s -> %s\n" "$p" "$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:$p/)"
done
echo "  gym :$GP -> $(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:$GP/)"
echo "  bridge :$BP pool $(curl -s -m 4 http://127.0.0.1:$BP/bridge/sessions | "$PY" -c 'import json,sys;print(",".join(json.load(sys.stdin)["pool"]))')"
echo "STACK READY"
echo ""
echo "Run a task in another shell (ports already match ui_oracle.py defaults):"
echo "  UIO_GYM=http://127.0.0.1:$GP UIO_BRIDGE=http://127.0.0.1:$BP \\"
echo "    $PY tools/ui_oracle.py <TASK>     # e.g. FB5, N446, N448, UI041, UI051, mail_002, M430 ..."
sleep 100000
