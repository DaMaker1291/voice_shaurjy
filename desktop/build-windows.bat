@echo off
REM ╔══════════════════════════════════════════════════════════╗
REM ║  JARVIS Desktop — Windows Build Script                  ║
REM ║  Builds the NSIS installer + portable .exe              ║
REM ║                                                         ║
REM ║  "The Ambient Operating Layer"                          ║
REM ║  WhatsApp-level distribution + Perplexity-level search  ║
REM ║  + OS-level execution in one native app.                ║
REM ╚══════════════════════════════════════════════════════════╝

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   JARVIS — Ambient Operating Layer                      ║
echo  ║   Building Windows Installer                            ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ── Step 0: Check/Install Node.js ─────────────────────────────────────
echo [0/7] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found. Installing via winget...
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [ERROR] Node.js install failed. Install manually: https://nodejs.org
        pause
        exit /b 1
    )
    set PATH=%PATH%;%APPDATA%\npm;%ProgramFiles%\nodejs
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
echo [OK] Node.js %NODE_VER%

REM ── Step 1: Check/Install Python ──────────────────────────────────────
echo [1/7] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Python not found. Installing via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [ERROR] Python install failed. Install manually: https://python.org
        pause
        exit /b 1
    )
    set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] Python %PY_VER%

REM ── Step 2: Install Python dependencies ───────────────────────────────
echo [2/7] Installing Python dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install fastapi "uvicorn[standard]" python-dotenv pydantic psutil websocket-client certifi Pillow pynput >nul 2>&1
echo [OK] Python packages installed

REM ── Step 3: Build Frontend ────────────────────────────────────────────
echo [3/7] Building frontend...
if exist "..\frontend\package.json" (
    pushd "..\frontend"
    call npm install --silent 2>nul
    call npm run build 2>nul
    popd
    if exist "..\frontend\out\index.html" (
        echo [OK] Frontend built
    ) else (
        echo [WARN] Frontend build incomplete — using existing build
    )
) else (
    echo [SKIP] No frontend source found
)

REM ── Step 4: Generate icons ───────────────────────────────────────────
echo [4/7] Generating icons...
python generate_icons.py
if errorlevel 1 echo [WARN] Icon generation failed — using existing icons

REM ── Step 5: Install Node.js dependencies ──────────────────────────────
echo [5/7] Installing Electron dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
echo [OK] Node modules installed

REM ── Step 6: Build Electron app ────────────────────────────────────────
echo [6/7] Building Electron app for Windows...
echo       This may take 2-5 minutes...
echo.
call npx electron-builder --win --x64
if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed. Common fixes:
    echo    - Run as Administrator
    echo    - Delete node_modules and re-run npm install
    echo    - Check antivirus exclusions
    echo.
    pause
    exit /b 1
)

REM ── Step 7: Done ─────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   BUILD SUCCESSFUL                                      ║
echo  ║                                                         ║
echo  ║   JARVIS v5.0.0                                         ║
echo  ║   Ambient Operating Layer                               ║
echo  ║                                                         ║
echo  ║   Output: dist\                                         ║
echo  ║     - Installer: JARVIS_Setup_v5.0.0.exe                ║
echo  ║     - Portable:  JARVIS-5.0.0.exe                       ║
echo  ║                                                         ║
echo  ║   Includes:                                             ║
echo  ║     - Ambient overlay (Ctrl+Shift+J)                    ║
echo  ║     - System tray with full control                     ║
echo  ║     - Python backend (auto-installs deps)               ║
echo  ║     - Local ML inference engine                         ║
echo  ║     - MCP protocol support                             ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

echo Opening output folder...
explorer dist
echo.
echo Done! Share the .exe to install on any Windows PC.
pause
