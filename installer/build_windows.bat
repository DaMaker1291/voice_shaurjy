@echo off
REM ╔══════════════════════════════════════════════════════════╗
REM ║  JARVIS Standalone Installer Builder                     ║
REM ║  Builds relay-only .exe installer (no Electron)          ║
REM ╚══════════════════════════════════════════════════════════╝

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   JARVIS Standalone Installer Builder                   ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    echo         winget install Python.Python.3.11
    pause
    exit /b 1
)

REM Check NSIS
where makensis >nul 2>&1
if errorlevel 1 (
    echo [INFO] NSIS not found. Install from: https://nsis.sourceforge.io
    echo [INFO] Download: https://nsis.sourceforge.io/Download
    echo.
    echo Falling back to creating portable distribution...
    set BUILD_PORTABLE=1
)

if defined BUILD_PORTABLE (
    echo [1/3] Creating portable distribution...
    mkdir dist\JARVIS_Portable 2>nul
    
    echo [2/3] Copying files...
    xcopy /E /I /Y /Q "..\backend" dist\JARVIS_Portable\backend
    xcopy /E /I /Y /Q "..\frontend\out" dist\JARVIS_Portable\frontend
    copy /Y "..\standalone_relay.py" dist\JARVIS_Portable\
    copy /Y "LICENSE.txt" dist\JARVIS_Portable\
    
    echo [3/3] Creating launcher scripts...
    (
        echo @echo off
        echo title JARVIS — Sovereign Network Orchestrator
        echo color 0A
        echo echo.
        echo echo  JARVIS — Sovereign Network Orchestrator
        echo echo  Starting relay agent...
        echo echo.
        echo cd /d "%%~dp0"
        echo python standalone_relay.py --user local
        echo pause
    ) > dist\JARVIS_Portable\Start_JARVIS.bat
    
    (
        echo @echo off
        echo start "" "%%JARVIS_WEB_URL%%"
    ) > dist\JARVIS_Portable\Open_WebUI.bat
    
    echo.
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║   BUILD COMPLETE — Portable version ready              ║
    echo  ║   Location: dist\JARVIS_Portable\                      ║
    echo  ║                                                          ║
    echo  ║   To use: Copy JARVIS_Portable folder to any PC         ║
    echo  ║   To run: Double-click Start_JARVIS.bat                 ║
    echo  ║   Web UI: Double-click Open_WebUI.bat                   ║
    echo  ╚══════════════════════════════════════════════════════════╝
) else (
    echo [1/3] Building NSIS installer...
    makensis jarvis.nsis
    if errorlevel 1 (
        echo [ERROR] NSIS build failed
        pause
        exit /b 1
    )
    
    echo.
    echo  ╔══════════════════════════════════════════════════════════╗
    echo  ║   BUILD COMPLETE — Installer ready                     ║
    echo  ║   Location: JARVIS_Setup_v3.0.exe                      ║
    echo  ║                                                          ║
    echo  ║   Share the .exe to install on any Windows PC.          ║
    echo  ╚══════════════════════════════════════════════════════════╝
)

echo.
explorer dist 2>nul
pause
