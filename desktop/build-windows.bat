@echo off
REM ╔══════════════════════════════════════════════════════════╗
REM ║  JARVIS Desktop — Full Windows Build Script             ║
REM ║  Builds the .exe NSIS installer + portable .exe         ║
REM ╚══════════════════════════════════════════════════════════╝

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   JARVIS Desktop — Building Windows Installer           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ── Step 0: Check/Install Node.js ─────────────────────────────────────
echo [0/6] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found. Attempting install via winget...
    winget install OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo  [ERROR] Node.js install failed.
        echo  Please install manually from: https://nodejs.org
        echo  Or run: winget install OpenJS.NodeJS.LTS
        echo.
        pause
        exit /b 1
    )
    echo [OK] Node.js installed. You may need to restart this script.
    echo.
    set PATH=%PATH%;%APPDATA%\npm;%ProgramFiles%\nodejs
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VER=%%i
echo [OK] Node.js %NODE_VER%

REM ── Step 1: Check/Install Python ──────────────────────────────────────
echo [1/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Python not found. Attempting install via winget...
    winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo [ERROR] Python install failed.
        echo Please install manually from: https://python.org
        pause
        exit /b 1
    )
    set PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PY_VER=%%i
echo [OK] Python %PY_VER%

REM ── Step 2: Install Python dependencies ───────────────────────────────
echo [2/6] Installing Python dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install fastapi "uvicorn[standard]" python-dotenv pydantic psutil websocket-client certifi Pillow >nul 2>&1
echo [OK] Python packages installed

REM ── Step 3: Install Node.js dependencies ──────────────────────────────
echo [3/6] Installing Electron dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
echo [OK] Node modules installed

REM ── Step 4: Generate icons ───────────────────────────────────────────
echo [4/6] Generating icons...
python generate_icons.py
if errorlevel 1 (
    echo [WARN] Icon generation failed — using existing icons
)

REM ── Step 5: Build Electron app ────────────────────────────────────────
echo [5/6] Building Electron app for Windows...
echo       This may take 2-5 minutes...
echo.
call npx electron-builder --win --x64
if errorlevel 1 (
    echo.
    echo  [ERROR] Build failed. Check the output above.
    echo  Common fixes:
    echo    - Run as Administrator
    echo    - Delete node_modules and re-run npm install
    echo    - Check if antivirus is blocking the build
    echo.
    pause
    exit /b 1
)

REM ── Step 6: Done ─────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   BUILD SUCCESSFUL                                      ║
echo  ║                                                          ║
echo  ║   Output folder: dist\                                  ║
echo  ║                                                          ║
echo  ║   Installer: dist\JARVIS_Setup_v3.0.0.exe              ║
echo  ║   Portable:  dist\JARVIS-3.0.0.exe                     ║
echo  ║                                                          ║
echo  ║   The NSIS installer includes:                          ║
echo  ║     - Welcome page with JARVIS branding                 ║
echo  ║     - License agreement (MIT)                           ║
echo  ║     - Custom install directory chooser                  ║
echo  ║     - Python dependency auto-install                    ║
echo  ║     - Desktop + Start Menu shortcuts                    ║
echo  ║     - Windows Defender exclusion                        ║
echo  ║     - Full uninstaller                                  ║
echo  ║                                                          ║
echo  ║   Share the .exe to install on any Windows PC.          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

echo Opening output folder...
explorer dist

pause
