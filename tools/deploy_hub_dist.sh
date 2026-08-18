#!/usr/bin/env bash
# Publish built mock dist/ folders to hosted static sites.
#
# Called by Jenkins (ci/jenkins/cua-hub-mocks-delta.groovy) after build_hub_mocks.sh.
# DevOps: replace the DEPLOY_* blocks below with your real rsync / S3 / k8s flow.
#
# Usage: tools/deploy_hub_dist.sh delta|prod
set -euo pipefail

ENV="${1:?usage: deploy_hub_dist.sh delta|prod}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MOCKS=(
  xmazon_mock:xmazon
  xbay_mock:xbay
  xmail_mock:xmail
  xoogle_calendar_mock:xoogle-calendar
  xber_eats_mock:xber-eats
)

case "$ENV" in
  delta) DOMAIN_SUFFIX="delta.deccanexperts.ai" ;;
  prod)  DOMAIN_SUFFIX="deccanexperts.ai" ;;
  *) echo "!! unknown env: $ENV" >&2; exit 1 ;;
esac

echo "==> deploy_hub_dist: env=$ENV domain=*.$DOMAIN_SUFFIX"

# ---------------------------------------------------------------------------
# DevOps: implement one of these patterns (delete the stub when done).
#
# A) rsync to nginx static roots on a deploy host:
#   RSYNC_TARGET="deploy@static-host:/var/www/cua-hub"
#   for entry in "${MOCKS[@]}"; do
#     mock="${entry%%:*}"; slug="${entry##*:}"
#     rsync -av --delete "$ROOT/websites/$mock/dist/" "$RSYNC_TARGET/$slug/"
#   done
#
# B) S3 + CloudFront per mock (see domains.json slug names):
#   aws s3 sync websites/xmazon_mock/dist/ s3://xmazon-$ENV/ --delete
#
# C) Existing Kashab pipeline — call it here:
#   /opt/cua-hub/deploy-mock.sh "$ENV" "$mock"
# ---------------------------------------------------------------------------

if [ -z "${CUA_HUB_DEPLOY_CMD:-}" ]; then
  echo "!! CUA_HUB_DEPLOY_CMD is not set — dist was built but NOT published."
  echo "   Built artifacts:"
  for entry in "${MOCKS[@]}"; do
    mock="${entry%%:*}"
    echo "     $ROOT/websites/$mock/dist/"
  done
  echo ""
  echo "   Set CUA_HUB_DEPLOY_CMD on the Jenkins job, or edit tools/deploy_hub_dist.sh."
  exit 1
fi

for entry in "${MOCKS[@]}"; do
  mock="${entry%%:*}"
  slug="${entry##*:}"
  host="https://${slug}.${DOMAIN_SUFFIX}"
  dist="$ROOT/websites/$mock/dist"
  echo "   deploying $mock -> $host"
  eval "CUA_HUB_DEPLOY_CMD" "$dist" "$slug" "$ENV" "$host"
done

echo "==> deploy complete"
