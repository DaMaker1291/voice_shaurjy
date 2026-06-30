# J.A.R.V.I.S. Relay Agent — Windows PowerShell Launcher
# Connects your PC to the HF Space backend for desktop actions

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  J.A.R.V.I.S. Relay Agent — Windows" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$python = $null
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $python = "python3"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} else {
    Write-Host "[ERROR] Python not found. Install Python 3.12+ from https://python.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install Playwright if needed
try {
    & $python -c "import playwright" 2>&1 | Out-Null
} catch {
    Write-Host "[SETUP] Installing Playwright..." -ForegroundColor Yellow
    & $python -m pip install playwright
    & $python -m playwright install chromium
}

Write-Host "[RELAY] Starting agent..." -ForegroundColor Green
Write-Host "[RELAY] Server: https://dgfhgjhj-jarvis-ai-brain.hf.space" -ForegroundColor Green
Write-Host "[RELAY] User ID: local" -ForegroundColor Green
Write-Host ""
Write-Host "Commands will be processed on THIS computer." -ForegroundColor Yellow
Write-Host "Close this window to stop the agent." -ForegroundColor Yellow
Write-Host ""

& $python relay_agent.py --user local
Read-Host "Press Enter to exit"
