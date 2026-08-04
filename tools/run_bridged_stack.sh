#!/usr/bin/env bash
# Bring up the FULL bridged gym: real engine behind the realistic UIs.
#
# What this gives you that plain seeding does not:
#   * cross-app effects — placing a shop order drops its confirmation email into
#     the Gmail tab on its own, because the gym's bus actually runs
#   * the engine's own rules (overlapping calendar events refused, coupon expiry,
#     stock limits) instead of whatever the React mock would have allowed
#   * the real 1058-milestone verifier suite, live, via /bridge/<session>/verify
#   * one gym per session, so two annotators never share a world
#
# A gym process holds ONE world, so concurrency == number of gyms in the pool.
#
# Usage:
#   tools/run_bridged_stack.sh <hub-checkout> [n_gyms]
#   tools/run_bridged_stack.sh ~/cua-hub 2
#
# Then:
#   BRIDGE_URL=http://127.0.0.1:8093 CUA_ENV=local \
#     python -m tools.session_manager start --task A1/buy_wireless_mouse --annotator alice
#   -> prints one URL per app, each carrying ?sid=&bridge=&session=
set -euo pipefail

# Default HUB to this repo root — the mock UIs are vendored under ./websites.
HUB="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NGYMS="${2:-2}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
BRIDGE_PORT="${BRIDGE_PORT:-8093}"
export HARNESS_TOKEN="${HARNESS_TOKEN:-bridged-stack}"

declare -a PORTS=(shop:5201 market:5202 mail:5203 calendar:5204 food:5205)

echo "==> building the 5 mocks (same-origin state API, so vite preview serves it)"
"$HERE/build_hub_mocks.sh" "$HUB" "" >/dev/null

echo "==> serving the mocks"
for entry in "${PORTS[@]}"; do
  app="${entry%%:*}"; port="${entry##*:}"
  case "$app" in
    shop) mock=amazon_mock;; mail) mock=gmail_mock;; market) mock=ebay_mock;;
    calendar) mock=google_calendar_mock;; food) mock=uber_eats_mock;;
  esac
  ( cd "$HUB/websites/$mock" && nohup npx vite preview --host 127.0.0.1 --port "$port" --strictPort \
      >"/tmp/vite_$mock.log" 2>&1 & disown )
  sleep 2
done

echo "==> starting $NGYMS gym instance(s) — one world each"
GYMS=""
for i in $(seq 0 $((NGYMS-1))); do
  p=$((8077+i))
  ( cd "$ROOT" && nohup "$PY" -m uvicorn server.main:app --host 127.0.0.1 --port "$p" \
      --log-level warning >"/tmp/gym_$p.log" 2>&1 & disown )
  GYMS="${GYMS:+$GYMS,}http://127.0.0.1:$p"
done
sleep 5

echo "==> starting the bridge on :$BRIDGE_PORT"
( cd "$ROOT" && GYM_URLS="$GYMS" BRIDGE_TICK=1 \
  CUA_HUB_URL_SHOP=http://127.0.0.1:5201 CUA_HUB_URL_MARKET=http://127.0.0.1:5202 \
  CUA_HUB_URL_MAIL=http://127.0.0.1:5203 CUA_HUB_URL_CALENDAR=http://127.0.0.1:5204 \
  CUA_HUB_URL_FOOD=http://127.0.0.1:5205 \
  nohup "$PY" -m uvicorn tools.bridge_service:app --host 127.0.0.1 --port "$BRIDGE_PORT" \
    --log-level warning >/tmp/bridge.log 2>&1 & disown )
sleep 4

echo
for p in 5201 5202 5203 5204 5205; do
  printf "  mock  :%s -> %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://127.0.0.1:$p/")"
done
curl -s -m 5 "http://127.0.0.1:$BRIDGE_PORT/bridge/sessions" \
  | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(f"  bridge:{d[\"capacity\"]} gym(s) in the pool")'
echo
echo "start a session:"
echo "  BRIDGE_URL=http://127.0.0.1:$BRIDGE_PORT CUA_ENV=local \\"
echo "    $PY -m tools.session_manager start --task A1/buy_wireless_mouse --annotator alice"
