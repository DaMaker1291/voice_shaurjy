FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt

COPY backend/ ./backend/
COPY frontend/out/ ./frontend/out/
COPY standalone_relay.py ./standalone_relay.py

ENV PYTHONPATH=/app
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
