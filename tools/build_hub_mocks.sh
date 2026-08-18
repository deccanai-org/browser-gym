#!/usr/bin/env bash
# Build the 5 gym mocks from a CUA-Gym-Hub checkout, with our patches applied.
#
# WHY THIS EXISTS: every mock in the hub repo ships a .env.production pointing at
#   https://cua-gym-hub.soulhq.ai
# which is the FILE-BACKED instance — it writes to no database and records no
# events. A plain `npm run build` therefore produces a bundle that looks fine and
# silently loses every annotator's work. The API base is baked in at build time,
# so this cannot be fixed after the fact. Always build through this script.
#
# Usage:
#   tools/build_hub_mocks.sh <hub-checkout> [api-base]
#     api-base default: https://cua-gym-hub.delta.soulhq.ai   (Postgres-backed)
#     api-base ""     : same-origin, for local `vite preview` with its own middleware
#
# Output: <hub-checkout>/websites/<mock>/dist per app.
set -euo pipefail

# Default HUB to this repo root — the mock UIs are vendored under ./websites.
HUB="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
API_BASE="${2-https://cua-gym-hub.delta.soulhq.ai}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ours:theirs. Our folders are x-forms; a pristine cua-gym-hub checkout still
# uses amazon_mock etc., and this script builds either tree. The right-hand name
# is also the hub's wire key, which is what VITE_MOCK_ID must carry no matter
# which tree we are standing in.
MOCKS=(
  xmazon_mock:amazon_mock
  xmail_mock:gmail_mock
  xbay_mock:ebay_mock
  xoogle_calendar_mock:google_calendar_mock
  xber_eats_mock:uber_eats_mock
)
ROOT="$(cd "$HERE/.." && pwd)"
# Vendored self-build (HUB == this repo root): websites/ is already the final
# source, so skip the legacy pristine-hub *_bridged.patch step.
if [ "$(cd "$HUB" && pwd)" = "$ROOT" ]; then VENDORED=1; else VENDORED=0; fi

[ -d "$HUB/websites" ] || { echo "!! $HUB is not a hub checkout (no websites/)" >&2; exit 1; }
[ -d "$HUB/shared" ]   || { echo "!! $HUB/shared missing — vite.config.js imports it" >&2; exit 1; }

for entry in "${MOCKS[@]}"; do
  ours="${entry%%:*}"; hub_key="${entry##*:}"
  # Whichever naming this checkout actually uses.
  if   [ -d "$HUB/websites/$ours"     ]; then m="$ours"
  elif [ -d "$HUB/websites/$hub_key"  ]; then m="$hub_key"
  else echo "!! missing $HUB/websites/{$ours,$hub_key}" >&2; exit 1; fi
  d="$HUB/websites/$m"
  echo "==> $m"

  p="$HERE/patches/${ours}_bridged.patch"
  if [ "$VENDORED" != 1 ] && [ -f "$p" ]; then
    # --forward alone is NOT idempotent here: these patches create new files, and
    # re-running appends a second copy of each. Reverse-dry-run first — if that
    # succeeds the patch is already in, so skip.
    if ( cd "$d" && patch -p3 -R --dry-run -s -f < "$p" >/dev/null 2>&1 ); then
      echo "    patch already applied, skipping"
    else
      ( cd "$d" && patch -p3 --forward -s < "$p" ) \
        || { echo "!! $m: patch did not apply cleanly" >&2; exit 1; }
    fi
  fi

  # VITE_MOCK_ID is the hub's key, NOT our folder name: the SPA builds /api/<id>
  # against it, and the hub serves only its own names. Writing "$m" here would
  # bake xmazon_mock into the bundle and every state call would 404.
  printf 'VITE_API_BASE=%s\nVITE_MOCK_ID=%s\n' "$API_BASE" "$hub_key" > "$d/.env.production"

  # Ship our licensed realistic images (products for the storefronts, food for
  # GymEats). vite copies public/ into dist at build. Extra unused files in a
  # given mock are harmless.
  if [ -d "$HERE/product_assets" ] && { [ "$hub_key" = amazon_mock ] || [ "$hub_key" = ebay_mock ] || [ "$hub_key" = uber_eats_mock ]; }; then
    mkdir -p "$d/public/assets"
    cp -R "$HERE/product_assets/." "$d/public/assets/"
  fi

  ( cd "$d"
    [ -d node_modules ] || npm install --silent --no-audit --no-fund
    npx vite build >/dev/null )

  # The baked-in base is the whole point of this script — prove it landed.
  if [ -n "$API_BASE" ]; then
    grep -qF "$API_BASE" "$d"/dist/assets/*.js \
      || { echo "!! $m built WITHOUT $API_BASE — refusing to ship" >&2; exit 1; }
  fi
  echo "    built, api-base=${API_BASE:-<same-origin>}"
done

echo
echo "All 5 built. Deploy each <mock>/dist as the site root (SPA fallback to index.html)."
