# Run as Administrator to install backend as a Windows Service
param([switch]$Remove)

$serviceName = "SecondBrainBackend"
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $PSScriptRoot "backend\main.py"
$workDir = $PSScriptRoot

if ($Remove) {
    & nssm stop $serviceName 2>$null
    & nssm remove $serviceName confirm
    Write-Host "Service removed." -ForegroundColor Green
    exit
}

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "Downloading nssm..." -ForegroundColor Yellow
    $url = "https://nssm.cc/release/nssm-2.24.zip"
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm" -Force
    $nssm = Get-ChildItem "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" -Recurse | Select-Object -First 1
    if (-not $nssm) { Write-Host "nssm download failed" -ForegroundColor Red; exit 1 }
    $nssmPath = $nssm.FullName
} else {
    $nssmPath = (Get-Command nssm).Source
}

Write-Host "Installing service '$serviceName'..." -ForegroundColor Green
& $nssmPath install $serviceName $pythonPath "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
& $nssmPath set $serviceName AppDirectory $workDir
& $nssmPath set $serviceName DisplayName "Second Brain Backend"
& $nssmPath set $serviceName Description "AI voice assistant backend with full Windows control"
& $nssmPath set $serviceName Start SERVICE_AUTO_START
& $nssmPath set $serviceName AppStdout "$workDir\backend.log"
& $nssmPath set $serviceName AppStderr "$workDir\backend.err.log"
& $nssmPath set $serviceName AppEnvironmentExtra "GROQ_API_KEY=$env:GROQ_API_KEY"

& $nssmPath start $serviceName

Write-Host "Done! http://localhost:8000" -ForegroundColor Green
Write-Host "To stop:   nssm stop $serviceName" -ForegroundColor Cyan
Write-Host "To remove: .\install_backend_service.ps1 -Remove" -ForegroundColor Cyan
