# Run as Administrator to install relay agent as a Windows Service
# Requires nssm.exe in PATH or same directory

$agentPath = Join-Path $PSScriptRoot "relay_agent.py"
$pythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$serviceName = "SecondBrainRelay"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "Downloading nssm..." -ForegroundColor Yellow
    $url = "https://nssm.cc/release/nssm-2.24.zip"
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm" -Force
    $nssm = Get-ChildItem "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" -Recurse | Select-Object -First 1
    if (-not $nssm) {
        Write-Host "Failed to find nssm.exe. Download manually from https://nssm.cc/download" -ForegroundColor Red
        exit 1
    }
    $nssmPath = $nssm.FullName
} else {
    $nssmPath = (Get-Command nssm).Source
}

Write-Host "Installing service '$serviceName'..." -ForegroundColor Green
& $nssmPath install $serviceName $pythonPath $agentPath
& $nssmPath set $serviceName AppDirectory $PSScriptRoot
& $nssmPath set $serviceName DisplayName "Second Brain Relay Agent"
& $nssmPath set $serviceName Description "Bridges cloud backend to Windows actions via WebSocket"
& $nssmPath set $serviceName Start SERVICE_AUTO_START
& $nssmPath set $serviceName AppStdout "$PSScriptRoot\relay.log"
& $nssmPath set $serviceName AppStderr "$PSScriptRoot\relay.err.log"

Write-Host "Starting service..." -ForegroundColor Green
& $nssmPath start $serviceName

Write-Host "Done! Service '$serviceName' is running." -ForegroundColor Green
Write-Host "Check logs: relay.log / relay.err.log" -ForegroundColor Cyan
Write-Host "To stop:   nssm stop $serviceName" -ForegroundColor Cyan
Write-Host "To remove: nssm remove $serviceName confirm" -ForegroundColor Cyan
