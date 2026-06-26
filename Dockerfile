FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements-render.txt .
RUN pip install --no-cache-dir -r requirements-render.txt
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.playwright python3 -m playwright install chromium
COPY backend/ ./backend/
COPY frontend/out/ ./frontend/out/
ENV PYTHONPATH=/app
ENV GROQ_API_KEY=""
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
EXPOSE 7860
CMD uvicorn backend.main:app --host 0.0.0.0 --port 7860