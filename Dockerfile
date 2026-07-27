# The gym server + Playwright (run_agent / resume_run drive a real browser).
#
# Best hosted on a small VM (Compute Engine e2-small+) or Cloud Run with a
# writable filesystem — the harness writes per-step screenshots + trajectories
# to disk and serves them back. On Cloud Run, mount a tmpfs at /app/screenshots
# and /app/trajectories (its default FS is read-only apart from /tmp) and give it
# --memory 2Gi --cpu 2 (a headless browser is heavy). The annotator reaches this
# service via its GYM_URL, with HARNESS_TOKEN matching GYM_HARNESS_TOKEN.
#
#   docker build -t gym . && docker run -p 8000:8000 \
#     -e HARNESS_TOKEN=dev-annotator-token -e ANTHROPIC_API_KEY=... gym
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Source first (setuptools finds the packages from these dirs), then install.
COPY pyproject.toml ./
COPY server ./server
COPY harness ./harness
COPY agents ./agents
COPY eval ./eval
# The server mounts ui/static at import time and renders ui/pages, so a build
# without them cannot start at all — it fails in server/main.py before uvicorn
# ever binds. Verified: the image built without this exited 1 with
# "Directory '/app/ui/static' does not exist".
COPY ui ./ui
RUN pip install --upgrade pip && pip install . \
    && python -m playwright install chromium

# Cloud Run injects $PORT; 8000 locally. HARNESS_TOKEN gates every /_harness/*
# call and MUST match the annotator's GYM_HARNESS_TOKEN.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
