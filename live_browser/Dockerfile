# The live-browser service: a CDP screencast + structured-input channel over
# WebSocket, driving a real Chromium. A SEPARATE process from the gym
# (server.main) and from the annotator on purpose — it owns a browser, nothing
# else, and imports neither. Self-contained: only fastapi + pydantic + playwright.
#
# The annotator reaches this at its LIVE_BROWSER_URL, and its LIVE_STREAM_SECRET
# MUST equal the annotator backend's LIVE_STREAM_SECRET or every stream closes
# 4401. LIVE_ALLOWED_ORIGINS is the browser origin(s) the websocket accepts
# (comma-separated; "*" for local dev only).
#
#   docker build -t live-browser -f live_browser/Dockerfile . && \
#   docker run -p 8877:8877 -e LIVE_STREAM_SECRET=... -e LIVE_ALLOWED_ORIGINS=https://app.example live-browser
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY live_browser ./live_browser
RUN pip install --upgrade pip \
    && pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2" "playwright>=1.48" \
    && python -m playwright install chromium

# Cloud Run injects $PORT; 8877 locally. A live browser is heavy — give it
# --memory 2Gi --cpu 2 and a writable /tmp.
ENV PORT=8877
EXPOSE 8877
CMD ["sh", "-c", "uvicorn live_browser.service:app --host 0.0.0.0 --port ${PORT:-8877}"]
