@echo off
REM JARVIS Windows Build Script
REM Builds the .exe installer using PyInstaller + NSIS

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   JARVIS Windows Installer Builder                     ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    echo         winget install Python.Python.3.11
    pause
    exit /b 1
)

REM Check PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

REM Check NSIS (optional — for .exe installer)
where makensis >nul 2>&1
if errorlevel 1 (
    echo [INFO] NSIS not found. Download from: https://nsis.sourceforge.io
    echo [INFO] Falling back to PyInstaller portable build...
    set BUILD_PORTABLE=1
)

echo.
echo [1/4] Building backend...
cd /d "%~dp0"
python -m py_compile backend\main.py
if errorlevel 1 (
    echo [ERROR] Backend compilation failed
    pause
    exit /b 1
)

echo [2/4] Building PyInstaller bundle...
python -m PyInstaller --onefile --name JARVIS --icon icon.ico --add-data "backend;backend" --add-data "relay.py;." installer\installer.py
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

if defined BUILD_PORTABLE (
    echo.
    echo [3/4] Creating portable distribution...
    mkdir dist\JARVIS_Portable 2>nul
    copy dist\JARVIS.exe dist\JARVIS_Portable\
    copy relay.py dist\JARVIS_Portable\
    xcopy /E /I /Y backend dist\JARVIS_Portable\backend
    
    echo [4/4] Creating launcher batch...
    echo @echo off > dist\JARVIS_Portable\Start_JARVIS.bat
    echo title JARVIS >> dist\JARVIS_Portable\Start_JARVIS.bat
    echo cd /d "%%~dp0" >> dist\JARVIS_Portable\Start_JARVIS.bat
    echo python relay.py --user local >> dist\JARVIS_Portable\Start_JARVIS.bat
    echo pause >> dist\JARVIS_Portable\Start_JARVIS.bat
    
    echo.
    echo ╔══════════════════════════════════════════════════════════╗
    echo ║   BUILD COMPLETE — Portable version ready              ║
    echo ║   Location: dist\JARVIS_Portable\                      ║
    echo ║                                                          ║
    echo ║   To install: Copy JARVIS_Portable folder anywhere      ║
    echo ║   To run: Start_JARVIS.bat                              ║
    echo ╚══════════════════════════════════════════════════════════╝
) else (
    echo [3/4] Building NSIS installer...
    makensis installer\jarvis.nsis
    if errorlevel 1 (
        echo [ERROR] NSIS build failed
        pause
        exit /b 1
    )
    
    echo.
    echo ╔══════════════════════════════════════════════════════════╗
    echo ║   BUILD COMPLETE — Installer ready                     ║
    echo ║   Location: JARVIS_Setup_v3.0.exe                      ║
    echo ╚══════════════════════════════════════════════════════════╝
)

echo.
pause
