#!/bin/bash
# M346 interview-lunch Sol pass@5 after the xber Eats catalog-honesty fix.
# Shared x-name mocks 6200-6204. Isolated gym 9820-9824 / bridge 9920-9924.
# Does not touch 9530-9534 leftovers.
set -eu
cd "$HOME/work/browser-gym"
PY="$HOME/work/browser-gym/.venv/bin/python"
KEYFILE="$HOME/.config/browsergym/openai_api_key"
LOGDIR="$HOME/work/browser-gym/trajectories/sol_m346_catalogfix_p5_logs"
OUT="$HOME/work/browser-gym/trajectories/sol_m346_catalogfix_p5"
SHOTS="$HOME/work/browser-gym/screenshots/sol_m346_catalogfix_p5"
HUB="${HUB:-$HOME/work/browser-gym}"
mkdir -p "$LOGDIR" "$OUT" "$SHOTS"

# Catalog honesty: never project unfulfillable amb_r_* decoys.
unset GYM_FOOD_AMBIENT || true
export HARNESS_TOKEN=bridged-e-sol
export BRIDGE_TICK=0
export BRIDGE_DEFAULT_SESSION=1
export BRIDGE_AUTOSCALE=0

if [ ! -f "$KEYFILE" ]; then
  echo "FATAL: missing openai key file" >&2
  exit 1
fi
export OPENAI_API_KEY
OPENAI_API_KEY="$(cat "$KEYFILE")"
export OPENAI_MODEL=gpt-5.6-sol
export AGENT_MAX_STEPS=100
export AGENT_EVAL_MODE=1
export LLM_CALL_TIMEOUT=90
export LLM_MAX_ATTEMPTS=2

TASK="M346/candidate_addresses_must_not_be_exposed"

SHOP=6200
MARKET=6201
MAIL=6202
CAL=6203
FOOD=6204

start_one_mock () {
  local mock="$1" port="$2"
  if curl -sf -m 2 "http://127.0.0.1:$port/" >/dev/null; then
    return 0
  fi
  local dir="$HUB/websites/$mock"
  if [ ! -d "$dir" ]; then
    echo "FATAL: missing mock $dir" >&2
    return 1
  fi
  ( cd "$dir" && nohup npx vite preview --host 127.0.0.1 --port "$port" --strictPort \
      >>"$LOGDIR/vite_${mock}_${port}.log" 2>&1 & echo $! > "$LOGDIR/vite_${port}.pid" )
}

wait_http () {
  local url="$1" tries="$2"
  local i
  for i in $(seq 1 "$tries"); do
    curl -sf -m 2 "$url" >/dev/null && return 0
    sleep 1
  done
  return 1
}

start_pair () {
  local GP="$1" BP="$2"
  if ! curl -sf -m 3 "http://127.0.0.1:$GP/" >/dev/null; then
    unset GYM_FOOD_AMBIENT || true
    nohup "$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$GP" --log-level warning \
      >>"$LOGDIR/gym_$GP.log" 2>&1 &
    echo $! > "$LOGDIR/gym_$GP.pid"
  fi
  if ! curl -sf -m 3 "http://127.0.0.1:$BP/bridge/sessions" >/dev/null; then
    unset GYM_FOOD_AMBIENT || true
    GYM_URLS="http://127.0.0.1:$GP" GYM_URL="http://127.0.0.1:$GP" \
    HARNESS_TOKEN=bridged-e-sol BRIDGE_TICK=0 BRIDGE_DEFAULT_SESSION=1 BRIDGE_AUTOSCALE=0 \
    CUA_HUB_URL_SHOP="http://127.0.0.1:$SHOP" \
    CUA_HUB_URL_MARKET="http://127.0.0.1:$MARKET" \
    CUA_HUB_URL_MAIL="http://127.0.0.1:$MAIL" \
    CUA_HUB_URL_CALENDAR="http://127.0.0.1:$CAL" \
    CUA_HUB_URL_FOOD="http://127.0.0.1:$FOOD" \
      nohup "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BP" --log-level warning \
        >>"$LOGDIR/bridge_$BP.log" 2>&1 &
    echo $! > "$LOGDIR/bridge_$BP.pid"
  fi
}

run_one () {
  local SHORT="$1" T="$2" GP="$3" BP="$4"
  start_pair "$GP" "$BP"
  wait_http "http://127.0.0.1:$GP/" 90 || echo "WARN gym $GP not ready" >&2
  wait_http "http://127.0.0.1:$BP/bridge/sessions" 90 || echo "WARN bridge $BP not ready" >&2
  local ORIGINS="shop=http://127.0.0.1:$SHOP,market=http://127.0.0.1:$MARKET,mail=http://127.0.0.1:$MAIL,calendar=http://127.0.0.1:$CAL,food=http://127.0.0.1:$FOOD"
  echo "===== $SHORT gym:$GP bridge:$BP"
  PYTHONPATH=. "$PY" -m eval.run \
    --agent openai_pixel --tasks "$T" --seeds 0 \
    --server "http://127.0.0.1:$GP" --app-origins "$ORIGINS" --bridge-url "http://127.0.0.1:$BP" \
    --out-traj "$OUT" --out-screens "$SHOTS" --headless --no-video \
    >>"$LOGDIR/sol_${GP}_${SHORT}.log" 2>&1 || true
}

echo "[m346-catalogfix-p5] starting shared x-name mocks"
date -u
# GCE folder names are still amazon_mock/…; chrome already says xmazon/xber.
_pick_mock () {
  local xname="$1" old="$2"
  if [ -d "$HUB/websites/$xname" ]; then echo "$xname"
  else echo "$old"
  fi
}
start_one_mock "$(_pick_mock xmazon_mock amazon_mock)" "$SHOP"
start_one_mock "$(_pick_mock xbay_mock ebay_mock)" "$MARKET"
start_one_mock "$(_pick_mock xmail_mock gmail_mock)" "$MAIL"
start_one_mock "$(_pick_mock xoogle_calendar_mock google_calendar_mock)" "$CAL"
start_one_mock "$(_pick_mock xber_eats_mock uber_eats_mock)" "$FOOD"
for p in "$SHOP" "$MARKET" "$MAIL" "$CAL" "$FOOD"; do
  wait_http "http://127.0.0.1:$p/" 60 || echo "WARN mock $p not ready" >&2
done

echo "[m346-catalogfix-p5] forking 5 lanes"
for trial in 1 2 3 4 5; do
  gp=$((9819 + trial))
  bp=$((9919 + trial))
  run_one "M346_t${trial}" "$TASK" "$gp" "$bp" >>"$LOGDIR/lane_M346_t${trial}.log" 2>&1 &
  echo $! > "$LOGDIR/lane_M346_t${trial}.pid"
  echo "STARTED M346_t${trial} pid=$(cat "$LOGDIR/lane_M346_t${trial}.pid") gym:$gp bridge:$bp"
done

echo "[m346-catalogfix-p5] all 5 lanes forked"
date -u
wait || true
echo "[m346-catalogfix-p5] five trials finished"
date -u
