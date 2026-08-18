# Cloud Run Job image: ONE agent episode per task index, driven against the
# REALISTIC MOCK UIs — never the gym's own Jinja HTML.
#
# Everything an episode needs lives in its own container: the gym, the five mock
# SPAs, and the bridge that joins them. That is not tidiness, it is required.
# `SESSION` is a module-level global and /_harness/reset overwrites it, so two
# concurrent episodes sharing one gym would silently corrupt each other's world.
# One gym per episode is the only safe shape; Cloud Run Jobs then gives fan-out
# for free (--tasks N --parallelism N).
#
# ---------------------------------------------------------------------------
# STAGE 1 — prune the mock bundles.
#
# Each mock's dist ships EVERY app's images, not just its own: xmazon_mock
# carries 43MB of food photography it never renders, xber_eats_mock carries 30MB
# of product shots. Measured 231MB across the five. The pruning has to happen in
# a separate stage because COPY writes its own layer — deleting afterwards in the
# final stage would leave the fat layer in the image and every task would still
# pull it. Verified by grepping each bundle for the asset paths it references:
#   amazon    -> products (+ categories, kept as cheap insurance for data-driven paths)
#   ebay      -> products, categories, vm_categories
#   uber_eats -> food (+ categories)
#   gmail / google_calendar -> no image directories at all
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS mocks
WORKDIR /m
COPY websites/xmazon_mock/dist            ./shop/
COPY websites/xbay_mock/dist              ./market/
COPY websites/xmail_mock/dist             ./mail/
COPY websites/xoogle_calendar_mock/dist   ./calendar/
COPY websites/xber_eats_mock/dist         ./food/
RUN set -eu; \
    rm -rf shop/assets/food shop/assets/vm_categories; \
    rm -rf market/assets/food; \
    rm -rf food/assets/products food/assets/vm_categories; \
    du -sh shop market mail calendar food

# ---------------------------------------------------------------------------
# STAGE 2 — the runner
# ---------------------------------------------------------------------------
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY server ./server
COPY harness ./harness
COPY agents ./agents
COPY eval ./eval
COPY ui ./ui
# tools/ carries the bridge and the world->mock projection; bridged mode is dead
# without it (tools.bridge_service, tools.bridge, tools.seed_to_cuagym).
COPY tools ./tools

RUN pip install --upgrade pip \
    && pip install . \
    && pip install google-cloud-storage \
    && python -m playwright install chromium

RUN python -m server.seeddb.build_seed_db
ENV SEEDDB_MODE=1

COPY --from=mocks /m /app/mocks
COPY cloud/entrypoint.sh /app/cloud/entrypoint.sh
COPY cloud/upload.py     /app/cloud/upload.py
COPY cloud/serve_spa.py  /app/cloud/serve_spa.py
COPY cloud/manifest.json /app/cloud/manifest.json
RUN chmod +x /app/cloud/entrypoint.sh

# Cloud Run's filesystem is read-only apart from /tmp, and the harness writes
# per-step screenshots and trajectories.
ENV TRAJ_DIR=/tmp/traj SCREENSHOT_DIR=/tmp/screenshots

ENTRYPOINT ["/app/cloud/entrypoint.sh"]
