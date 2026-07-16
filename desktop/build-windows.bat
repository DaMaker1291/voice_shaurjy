@echo off
REM ╔══════════════════════════════════════════════════════════╗
REM ║  JARVIS Desktop — Windows Build Script                  ║
REM ║  Builds the .exe installer                              ║
REM ╚══════════════════════════════════════════════════════════╝

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   JARVIS Desktop — Building Windows Installer           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from: https://nodejs.org
    echo         winget install OpenJS.NodeJS.LTS
    pause
    exit /b 1
)

REM Check npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm not found.
    pause
    exit /b 1
)

echo [1/5] Installing dependencies...
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)

echo [2/5] Generating icons...
python generate_icons.py
if errorlevel 1 (
    echo [WARN] Icon generation failed — using defaults
)

echo [3/5] Building Electron app for Windows...
call npx electron-builder --win
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo [4/5] Build complete!
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   ✅  BUILD SUCCESSFUL                                  ║
echo  ║                                                          ║
echo  ║   Installer: dist\JARVIS_Setup_v3.0.exe                 ║
echo  ║   Portable:  dist\JARVIS_3.0.0.exe                      ║
echo  ║                                                          ║
echo  ║   Run the .exe to install JARVIS on any Windows PC.     ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

echo [5/5] Opening output folder...
explorer dist

pause
