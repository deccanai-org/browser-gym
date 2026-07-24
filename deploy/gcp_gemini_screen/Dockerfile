# Gemini 3.1 Pro census worker — Cloud Run Jobs
# Build from repo root:
#   docker build -f deploy/gcp_gemini_screen/Dockerfile -t gemini-census-worker .
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AGENT_EVAL_MODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# System deps beyond the Playwright image (uvicorn gym + pillow already covered).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY server ./server
COPY harness ./harness
COPY agents ./agents
COPY eval ./eval
COPY deploy/gcp_gemini_screen ./deploy/gcp_gemini_screen

RUN pip install --upgrade pip \
    && pip install -e . \
    && pip install -r deploy/gcp_gemini_screen/requirements.txt \
    && python -m playwright install --with-deps chromium

# Generate manifests into the image so workers don't need the live TASKS import
# to fail closed — still re-generated at build from source of truth.
RUN python deploy/gcp_gemini_screen/generate_manifest.py

ENV MANIFEST_PATH=/app/deploy/gcp_gemini_screen/manifests/full_manifest_945.json \
    GEMINI_MODEL=gemini-3.1-pro-preview \
    WORKER_BASE_PORT=8100

# Cloud Run Jobs invokes the container command once per task index.
ENTRYPOINT ["python", "deploy/gcp_gemini_screen/worker/main.py"]
