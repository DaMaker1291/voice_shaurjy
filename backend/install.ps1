# ╔══════════════════════════════════════════════════════════════════╗
# ║  JARVIS — Sovereign Network Orchestrator                       ║
# ║  Windows Installer v3.0                                        ║
# ║                                                                  ║
# ║  USAGE (PowerShell as Admin):                                   ║
# ║    irm <YOUR_SERVER_URL>/install | iex                        ║
# ╚══════════════════════════════════════════════════════════════════╝

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# ── Colors ──────────────────────────────────────────────────────────────
function Write-Step    { param($n,$t,$m) Write-Host "`n  [" -NoNewline; Write-Host "$n/$t" -ForegroundColor Green -NoNewline; Write-Host "] $m" -ForegroundColor White }
function Write-OK      { param($m) Write-Host "    " -NoNewline; Write-Host "✓ " -ForegroundColor Green -NoNewline; Write-Host $m -ForegroundColor Gray }
function Write-Warn    { param($m) Write-Host "    " -NoNewline; Write-Host "⚠ " -ForegroundColor Yellow -NoNewline; Write-Host $m -ForegroundColor Gray }
function Write-Info    { param($m) Write-Host "    " -NoNewline; Write-Host "▸ " -ForegroundColor Cyan -NoNewline; Write-Host $m -ForegroundColor Gray }
function Write-Err     { param($m) Write-Host "    " -NoNewline; Write-Host "✗ " -ForegroundColor Red -NoNewline; Write-Host $m -ForegroundColor Gray }

# ── Banner ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor DarkGreen
Write-Host "  ║                                                          ║" -ForegroundColor DarkGreen
Write-Host "  ║      ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗            ║" -ForegroundColor Green
Write-Host "  ║      ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝            ║" -ForegroundColor Green
Write-Host "  ║      ██║███████║██████╔╝██║   ██║██║███████╗            ║" -ForegroundColor Green
Write-Host "  ║ ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║            ║" -ForegroundColor Green
Write-Host "  ║ ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║            ║" -ForegroundColor Green
Write-Host "  ║  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝            ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor DarkGreen
Write-Host "  ║   Sovereign Network Orchestrator — Installer v3.0       ║" -ForegroundColor DarkGreen
Write-Host "  ║                                                          ║" -ForegroundColor DarkGreen
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor DarkGreen
Write-Host ""

$total = 9

# ── Step 1: Check Python ───────────────────────────────────────────────
Write-Step 1 $total "Checking Python..."

$py = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 9) {
                $py = $cmd
                Write-OK "$ver ✓"
                break
            }
        }
    } catch {}
}

if (-not $py) {
    Write-Warn "Python 3.9+ not found. Installing Python 3.11..."
    try {
        winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $py = "python"
        Write-OK "Python 3.11 installed"
    } catch {
        Write-Err "Failed to install Python. Download manually: https://python.org"
        Write-Host "`n  Press Enter to exit..." -ForegroundColor DarkGray; Read-Host; exit 1
    }
}

# ── Step 2: Install pip packages ───────────────────────────────────────
Write-Step 2 $total "Installing dependencies..."

$pkgs = @("fastapi", "uvicorn[standard]", "python-dotenv", "pydantic", "psutil", "websocket-client", "certifi", "Pillow", "pywin32")
foreach ($pkg in $pkgs) {
    $importName = $pkg.Split("[")[0].Replace("-","_")
    $check = & $py -c "import $importName" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Info "Installing $pkg..."
        & $py -m pip install $pkg -q 2>&1 | Out-Null
    }
}
Write-OK "All dependencies installed"

# ── Step 3: Create directories ────────────────────────────────────────
Write-Step 3 $total "Creating directories..."

$jarvisDir = "$env:USERPROFILE\.jarvis"
$dataDir = "$jarvisDir\data"
$modelsDir = "$jarvisDir\models"

New-Item -ItemType Directory -Force -Path $jarvisDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
Write-OK "Created $jarvisDir"

# ── Step 4: Download relay agent ──────────────────────────────────────
Write-Step 4 $total "Downloading relay agent..."

$relayPath = "$jarvisDir\relay.py"
$hfUrl = $env:HF_API_URL
if (-not $hfUrl) { $hfUrl = "https://$env:HF_API_HOST" }
if (-not $hfUrl) { Write-Warn "HF_API_URL not set — skipping relay download"; $hfUrl = "" }

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "$hfUrl/relay" -OutFile $relayPath -UseBasicParsing -TimeoutSec 30
    Write-OK "Relay saved to $relayPath"
} catch {
    Write-Err "Download failed: $_"
    Write-Host "`n  Press Enter to exit..." -ForegroundColor DarkGray; Read-Host; exit 1
}

# ── Step 5: Create launcher scripts ───────────────────────────────────
Write-Step 5 $total "Creating launcher scripts..."

# Main launcher bat
$batContent = @"
@echo off
title JARVIS — Sovereign Network Orchestrator
color 0A
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║   JARVIS — Starting...                          ║
echo  ╚══════════════════════════════════════════════════╝
echo.
cd /d "$jarvisDir"
"$py" relay.py --user local
pause
"@
$batPath = "$jarvisDir\JARVIS.bat"
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Write-OK "Launcher: $batPath"

# Quick-launch bat (silent)
$silentBat = @"
@echo off
cd /d "$jarvisDir"
start /min "" "$py" relay.py --user local
"@
Set-Content -Path "$jarvisDir\JARVIS_Silent.bat" -Value $silentBat -Encoding ASCII

# ── Step 6: Create shortcuts ──────────────────────────────────────────
Write-Step 6 $total "Creating shortcuts..."

# Start Menu
$startMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\JARVIS"
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null

$wshShell = New-Object -ComObject WScript.Shell

# Start Menu shortcut
$lnk = $wshShell.CreateShortcut("$startMenu\JARVIS.lnk")
$lnk.TargetPath = $batPath
$lnk.WorkingDirectory = $jarvisDir
$lnk.Description = "JARVIS — Sovereign Network Orchestrator"
$lnk.WindowStyle = 1
$lnk.Save()
Write-OK "Start Menu shortcut"

# Desktop shortcut
$desktop = [System.Environment]::GetFolderPath("Desktop")
$lnk = $wshShell.CreateShortcut("$desktop\JARVIS.lnk")
$lnk.TargetPath = $batPath
$lnk.WorkingDirectory = $jarvisDir
$lnk.Description = "JARVIS — Sovereign Network Orchestrator"
$lnk.WindowStyle = 1
$lnk.Save()
Write-OK "Desktop shortcut"

# ── Step 7: Write config ──────────────────────────────────────────────
Write-Step 7 $total "Writing configuration..."

$config = @{
    version = "3.0"
    platform = "windows"
    hf_url = $hfUrl
    installed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    relay_user = "local"
} | ConvertTo-Json -Depth 3

Set-Content -Path "$jarvisDir\config.json" -Value $config -Encoding UTF8
Write-OK "Config saved"

# ── Step 8: Windows Defender exclusion ────────────────────────────────
Write-Step 8 $total "Configuring Windows Defender..."

try {
    Add-MpExclusion -ExclusionPath $jarvisDir -ErrorAction SilentlyContinue
    Add-MpExclusion -ExclusionPath "$env:TEMP\jarvis_*" -ErrorAction SilentlyContinue
    Write-OK "Defender exclusion added for $jarvisDir"
} catch {
    Write-Warn "Could not add Defender exclusion (run as Admin for full access)"
}

# ── Step 9: Auto-start on login ────────────────────────────────────────
Write-Step 9 $total "Setting up auto-start on login..."

# Method 1: Windows Registry Run key
try {
    $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    $regValue = "`"$batPath`" /min"
    Set-ItemProperty -Path $regPath -Name "JARVIS Relay" -Value $regValue -ErrorAction Stop
    Write-OK "Registry auto-start entry added"
} catch {
    Write-Warn "Could not add registry auto-start: $_"
}

# Method 2: Startup folder shortcut (fallback)
try {
    $startupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    $startupShortcut = $wshShell.CreateShortcut("$startupFolder\JARVIS Relay.lnk")
    $startupShortcut.TargetPath = "cmd.exe"
    $startupShortcut.Arguments = "/c `"$batPath`" /min"
    $startupShortcut.WorkingDirectory = $jarvisDir
    $startupShortcut.Description = "JARVIS Relay — Auto-start on login"
    $startupShortcut.WindowStyle = 7  # Minimized
    $startupShortcut.Save()
    Write-OK "Startup folder shortcut created"
} catch {
    Write-Warn "Could not create startup shortcut: $_"
}

# ── Done ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ║   " -ForegroundColor Green -NoNewline; Write-Host "✅  JARVIS INSTALLED SUCCESSFULLY" -ForegroundColor White -NoNewline; Write-Host "                    ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ║   Quick Start:                                           ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ║   1. Double-click JARVIS on your Desktop                 ║" -ForegroundColor Green
Write-Host "  ║      or search 'JARVIS' in Start Menu                    ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ║   2. Open: " -ForegroundColor Green -NoNewline; Write-Host "$hfUrl" -ForegroundColor White -NoNewline; Write-Host "     ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ║   The relay pairs automatically.                         ║" -ForegroundColor Green
Write-Host "  ║                                                          ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Ask to start
$answer = Read-Host "  Start JARVIS now? [Y/n]"
if ($answer -ne "n" -and $answer -ne "N") {
    Write-Host ""
    Write-Info "Starting JARVIS relay..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$batPath`"" -WindowStyle Normal
    Write-Host ""
    Write-Info "Opening JARVIS cockpit..."
    Start-Process "$hfUrl"
}

Write-Host "`n  Press Enter to exit..." -ForegroundColor DarkGray
Read-Host
