@echo off
cd /d "%~dp0"
echo Starting Second Brain Backend...
echo Access at http://localhost:8000
echo.
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
