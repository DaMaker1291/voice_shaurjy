@echo off
REM J.A.R.V.I.S. Relay Agent — Windows Launcher
REM Connects your PC to the HF Space backend for desktop actions

echo ========================================
echo   J.A.R.V.I.S. Relay Agent — Windows
echo ========================================
echo.

REM Check Python
where python3 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where python >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python not found. Install Python 3.12+ from https://python.org
        pause
        exit /b 1
    )
    set PY=python
) else (
    set PY=python3
)

REM Install Playwright if needed
%PY% -c "import playwright" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [SETUP] Installing Playwright...
    %PY% -m pip install playwright
    %PY% -m playwright install chromium
)

echo [RELAY] Starting agent...
if "%HF_API_URL%"=="" (
    echo [RELAY] Server: http://localhost:8000
) else (
    echo [RELAY] Server: %HF_API_URL%
)
echo [RELAY] User ID: local
echo.
echo Commands will be processed on THIS computer.
echo Close this window to stop the agent.
echo.

%PY% relay_agent.py --user local
pause
