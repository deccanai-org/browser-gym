#!/usr/bin/env bash
# Bring up all 5 realistic mock UIs seeded from a gym task — the self-contained pilot.
#
#   HUB=/path/to/CUA-Gym-Hub TASK="M301/stale_tracking_forward_sycophancy" SEED=0 tools/run_pilot.sh
#
# For each app it starts the mock's vite server (if not already up), waits, then
# seeds EVERY app of the task into its mock and prints the URLs to open — each URL
# carries its own seed sid, so opening it shows the gym task's data in the realistic UI.
#
# Requires: the CUA-Gym-Hub repo cloned (github.com/xlang-ai/CUA-Gym-Hub) with each
# mock's deps installed (npm install per websites/<app>).
#
# NOTE: xber_eats_mock ships internally broken (two parallel context systems,
# cross-wired) — apply tools/patches/xber_eats_mock_systemB.patch to the clone
# first (see tools/PILOT_SETUP.md); then it renders like the other four.
set -uo pipefail

GYM="$(cd "$(dirname "$0")/.." && pwd)"
HUB="${HUB:-$GYM/../CUA-Gym-Hub}"
TASK="${TASK:-M301/stale_tracking_forward_sycophancy}"
SEED="${SEED:-0}"
PY="${PY:-$GYM/.venv/bin/python}"; [ -x "$PY" ] || PY=python3

# gym-app : mock-dir : port
apps=(
  "shop:xmazon_mock:5201"
  "market:xbay_mock:5202"
  "mail:xmail_mock:5203"
  "calendar:xoogle_calendar_mock:5204"
  "food:xber_eats_mock:5205"
)

echo "Starting mocks from $HUB ..."
for a in "${apps[@]}"; do
  IFS=: read -r app dir port <<< "$a"
  if curl -sf -m2 "http://127.0.0.1:$port/" -o /dev/null 2>/dev/null; then
    echo "  $dir already up on $port"
  else
    ( cd "$HUB/websites/$dir" && nohup ./node_modules/.bin/vite --port "$port" --strictPort --host 127.0.0.1 >"/tmp/mock_$dir.log" 2>&1 & )
    echo "  started $dir on $port"
  fi
done

echo "Waiting for servers ..."
for a in "${apps[@]}"; do
  IFS=: read -r app dir port <<< "$a"
  curl --retry 60 --retry-delay 1 --retry-connrefused -sf -m3 "http://127.0.0.1:$port/" -o /dev/null \
    && echo "  $dir ready ($port)" || echo "  $dir NOT ready ($port)"
done

# build the app=url map for the seeder
map=""
for a in "${apps[@]}"; do
  IFS=: read -r app dir port <<< "$a"
  map="${map:+$map,}$app=http://127.0.0.1:$port"
done

echo "Seeding task $TASK (seed $SEED) across all mocks ..."
( cd "$GYM" && "$PY" -m tools.seed_to_cuagym --task "$TASK" --seed "$SEED" --mock-map "$map" ) | grep -E "^open:" || true
echo "Done. Open the URLs above to see the gym task in each realistic UI."
