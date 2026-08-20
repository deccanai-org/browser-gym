#!/usr/bin/env bash
# Copy (or rebuild) CUA hub mock dist into deploy/filtration/hub_dist for image bake.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RUNNER="$(cd "$HERE/../.." && pwd)"
HUB="${HUB:-/Users/maroonferrari/Deccan/CUA-Gym-Hub}"
OUT="$HERE/hub_dist"
REBUILD="${REBUILD:-0}"

if [ ! -d "$HUB/websites/amazon_mock" ]; then
  echo "FATAL: HUB=$HUB missing websites/amazon_mock" >&2
  exit 1
fi

if [ "$REBUILD" = "1" ]; then
  echo "[prepare] rebuilding hub mocks via tools/build_hub_mocks.sh"
  "$RUNNER/tools/build_hub_mocks.sh" "$HUB" ""
fi

rm -rf "$OUT"
mkdir -p "$OUT"
for m in amazon_mock ebay_mock gmail_mock google_calendar_mock uber_eats_mock; do
  src="$HUB/websites/$m/dist"
  if [ ! -d "$src" ]; then
    echo "FATAL: missing $src — run REBUILD=1 or tools/build_hub_mocks.sh" >&2
    exit 1
  fi
  echo "[prepare] copying $m/dist → hub_dist/$m"
  mkdir -p "$OUT/$m"
  # Prefer rsync if present; fall back to cp -R
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete "$src/" "$OUT/$m/"
  else
    rm -rf "$OUT/$m"
    cp -R "$src" "$OUT/$m"
  fi
done

N_JPG="$(find "$OUT/amazon_mock" -name '*.jpg' -print | wc -l | tr -d ' ')"
echo "[prepare] amazon JPGs=$N_JPG"
if [ "$N_JPG" -lt 100 ]; then
  echo "FATAL: expected >=100 Xmazon JPGs in hub_dist/amazon_mock" >&2
  exit 1
fi
SAMPLE="$(find "$OUT/amazon_mock" -name '*.jpg' -print -quit)"
file "$SAMPLE" || true
echo "[prepare] done → $OUT"
