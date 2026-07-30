#!/usr/bin/env bash
# Run a model on the REALISTIC UIs (bridged) and capture scored trajectories —
# the same agents/models as the breaker sweep, just driving the CUA-Gym-Hub mock
# SPAs instead of the gym's own HTML. Browser navigation goes to the mocks
# (+ ?bridge=); scoring stays on the gym /_harness/*.
#
# Prereqs (one-time): clone CUA-Gym-Hub next to the gym, apply the *_bridged.patch,
# npm build each mock (see PILOT_SETUP.md). API key in env for the chosen model.
#
# Usage:
#   HUB=/path/to/CUA-Gym-Hub AGENT=pixel MODEL=claude-opus-4-8 \
#     TASKS=M301/stale_tracking_forward_sycophancy SEEDS=0 tools/run_newui_eval.sh
#
# AGENT: pixel (Anthropic SoM) | openai_pixel (GPT SoM) | qwen  — same as breakers.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${HUB:?set HUB=/path/to/CUA-Gym-Hub}"
AGENT="${AGENT:-pixel}"; MODEL="${MODEL:-claude-opus-4-8}"
TASKS="${TASKS:-A1/buy_wireless_mouse}"; SEEDS="${SEEDS:-0}"
TOKEN="${HARNESS_TOKEN:-newui-$RANDOM}"
GYM_PORT="${GYM_PORT:-8078}"; BRIDGE_PORT="${BRIDGE_PORT:-8091}"
PY="${PY:-$HERE/.venv/bin/python}"
# app:port:mock-dir — indexed strings, not associative arrays (works on macOS bash 3.2)
APPS="shop:5203:amazon_mock market:5301:ebay_mock mail:5401:gmail_mock calendar:5402:google_calendar_mock food:5403:uber_eats_mock"

pids=()
cleanup(){ for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

echo "[newui] gym :$GYM_PORT"
HARNESS_TOKEN="$TOKEN" "$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$GYM_PORT" --log-level warning & pids+=($!)
sleep 3
echo "[newui] bridge :$BRIDGE_PORT (BRIDGE_TICK=0 — harness owns the clock)"
GYM_URL="http://127.0.0.1:$GYM_PORT" HARNESS_TOKEN="$TOKEN" BRIDGE_TICK=0 \
  "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BRIDGE_PORT" --log-level warning & pids+=($!)
sleep 3

origins=""
for entry in $APPS; do
  app="${entry%%:*}"; rest="${entry#*:}"; p="${rest%%:*}"; dir="${rest##*:}"
  d="$HUB/websites/$dir"
  if [ -d "$d/dist" ]; then
    ( cd "$d" && ./node_modules/.bin/vite preview --host 127.0.0.1 --port "$p" --strictPort >/dev/null 2>&1 & )
    pids+=($!)
    origins="${origins:+$origins,}$app=http://127.0.0.1:$p"
  else
    echo "[newui] WARN: $d/dist missing (npm run build it) — skipping $app"
  fi
done
sleep 4

echo "[newui] origins: $origins"
echo "[newui] running $AGENT ($MODEL) on $TASKS seeds=$SEEDS"
# HEADLESS=0 opens a REAL Chromium window you can watch (with the ghost cursor) +
# records a video; default headless for unattended sweeps.
if [ "${HEADLESS:-1}" = "0" ]; then MODE_FLAGS=""; else MODE_FLAGS="--headless --no-video"; fi
HARNESS_TOKEN="$TOKEN" "$PY" -m eval.run \
  --agent "$AGENT" --model "$MODEL" \
  --tasks "$TASKS" --seeds "$SEEDS" \
  --server "http://127.0.0.1:$GYM_PORT" \
  --app-origins "$origins" --bridge-url "http://127.0.0.1:$BRIDGE_PORT" \
  $MODE_FLAGS \
  --out-traj "trajectories/newui_$AGENT" --out-screens "screenshots/newui_$AGENT"

echo "[newui] done — trajectories/newui_$AGENT/  screenshots/newui_$AGENT/"
