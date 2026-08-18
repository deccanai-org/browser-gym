#!/usr/bin/env bash
# Bake our 5 bridged mock UIs into a cua-gym-hub clone (deccan-ai/cua-gym-hub),
# so Jenkins can build + deploy them to their hosted origins (see
# tools/cua_env.py:DELTA_UI_HOSTS — the five gym mocks are xmazon, xbay, xmail,
# xoogle-calendar and xber-eats; everything else is still cua-hub-<app>).
#
# The Bitbucket repo already carries our EARLIER UI work, so the *_bridged.patch
# files no longer apply cleanly on top of it. Instead we overwrite each mock's
# source (index.html + src/) with our verified final tree (hubdev). git respects
# .gitignore, so node_modules/dist/.mock-states never get staged.
#
# This does NOT push. It stages a diff for you to review, then prints the exact
# commit + push commands. Review the diff before pushing — it should be only the
# latest UI changes.
#
# Usage: tools/push_to_hub.sh <cua-gym-hub-clone> [hubdev-src-root]
#   <cua-gym-hub-clone>  a fresh `git clone` of deccan-ai/cua-gym-hub
#   [hubdev-src-root]    dir containing websites/<mock> with our final source
#                        (default: the a606619c session hubdev working tree)
set -euo pipefail

HUB="${1:?usage: push_to_hub.sh <cua-gym-hub-clone> [hubdev-src-root]}"
SRC="${2:-/private/tmp/claude-501/-Users-dhiren-Deccan-AI-E-Commerce-Broswer-Gym/a606619c-c162-479f-8fd5-31923f720770/scratchpad/hubdev}"
# ours:theirs. We renamed our folders to x-forms; the hub did not, and its
# checkout still has websites/amazon_mock. Syncing ours onto theirs by a single
# name would create brand-new folders in the hub instead of updating the real
# ones, so every path below has to pick the correct side of the pair.
MOCKS=(
  xmazon_mock:amazon_mock
  xbay_mock:ebay_mock
  xmail_mock:gmail_mock
  xoogle_calendar_mock:google_calendar_mock
  xber_eats_mock:uber_eats_mock
)

[ -d "$HUB/.git" ]     || { echo "!! $HUB is not a git clone" >&2; exit 1; }
[ -d "$HUB/websites" ] || { echo "!! $HUB has no websites/ (not a cua-gym-hub checkout)" >&2; exit 1; }
[ -d "$SRC/websites" ] || { echo "!! $SRC has no websites/ (final source tree missing)" >&2; exit 1; }

echo "==> syncing final UI source into: $HUB"
for entry in "${MOCKS[@]}"; do
  m="${entry%%:*}"; hm="${entry##*:}"
  s="$SRC/websites/$m"; d="$HUB/websites/$hm"
  [ -d "$s/src" ] || { echo "!! source missing: $s/src" >&2; exit 1; }
  [ -d "$d" ]     || { echo "!! mock not in clone: $d (is this the right hub?)" >&2; exit 1; }
  # overwrite the UI source only. --delete keeps src an exact mirror (our changes
  # never remove upstream-only files, verified). index.html is a single file.
  rsync -a --delete "$s/src/" "$d/src/"
  cp "$s/index.html" "$d/index.html"
  echo "   $m -> $hm: src/ + index.html synced"
done

cd "$HUB"
for entry in "${MOCKS[@]}"; do hm="${entry##*:}"; git add "websites/$hm/src" "websites/$hm/index.html"; done

if git diff --cached --quiet; then
  echo "==> nothing changed — the clone already matches our final UI."
  exit 0
fi

echo ""
echo "================ REVIEW BEFORE PUSHING ================"
git diff --cached --stat
echo "------------------------------------------------------"
echo "This is the delta being added to cua-gym-hub. It should be ONLY UI changes"
echo "(no node_modules/dist/state). If anything looks like a REVERT of teammate"
echo "work, stop and reconcile. Full diff: git diff --cached"
echo ""
echo "When it looks right:"
echo "  cd '$HUB'"
echo "  git checkout -b shopgym-ui-update            # a feature branch"
echo "  git commit -m 'ShopGym/ValueMart/ShopMail/GymCal/GymEats: latest bridged UI'"
echo "  git push -u origin shopgym-ui-update         # then open a PR / let Jenkins build STAGING"
echo ""
echo "Verify on *.delta.deccanexperts.ai before promoting to prod."
echo "Data needs no deploy: the hosted backend serves our seed from Postgres mock_states"
echo "(run tools/seed_via_psql after any seed change)."
