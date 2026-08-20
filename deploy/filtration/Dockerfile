# Filtration worker for Cloud Run Jobs — one episode per CLOUD_RUN_TASK_INDEX.
# Bakes bridged hub mock dist (Xmazon JPGs etc.) + gym/bridge/eval harness.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# App install (same surface as root Dockerfile + tools + google-cloud-storage)
COPY pyproject.toml ./
COPY server ./server
COPY harness ./harness
COPY agents ./agents
COPY eval ./eval
COPY tools ./tools
COPY ui ./ui
COPY deploy/filtration ./deploy/filtration

RUN pip install --upgrade pip \
    && pip install . google-cloud-storage \
    && python -m playwright install chromium \
    && chmod +x /app/deploy/filtration/worker_entrypoint.sh \
    && python -m server.seeddb.build_seed_db

ENV SEEDDB_MODE=1
ENV HUB_DIST=/hub_dist
ENV APP_ROOT=/app

# Baked hub mocks (prepared by scripts/prepare_hub_dist.sh before build)
COPY hub_dist /hub_dist

# Prove Xmazon product JPGs are real image bytes, not SPA HTML fallbacks.
RUN python -c "from pathlib import Path; root=Path('/hub_dist/amazon_mock'); jpgs=list(root.rglob('*.jpg')); assert len(jpgs)>=100, len(jpgs); assert jpgs[0].read_bytes()[:3]==b'\\xff\\xd8\\xff', jpgs[0]; print(f'hub bake OK: {len(jpgs)} amazon JPGs; sample={jpgs[0]}')"

# Writable episode dirs (Cloud Run FS is mostly read-only outside /tmp)
ENV OUT_TRAJ=/tmp/trajectories
ENV OUT_SCREENS=/tmp/screenshots
ENV RESULT_DIR=/tmp/results

ENTRYPOINT ["/app/deploy/filtration/worker_entrypoint.sh"]
