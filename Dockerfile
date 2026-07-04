FROM python:3.12-slim
WORKDIR /app

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.playwright python3 -m playwright install chromium
COPY backend/ ./backend/
COPY frontend/out/ ./frontend/out/
COPY standalone_relay.py ./standalone_relay.py
ENV PYTHONPATH=/app
ENV GROQ_API_KEY=""
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860
