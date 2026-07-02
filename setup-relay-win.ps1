# J.A.R.V.I.S. Relay Agent — Windows auto-installer
# Installs the relay as a scheduled task so it runs silently in the background.

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "JARVISRelayAgent"
$PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "[ERROR] Python not found. Install Python 3.12+ from https://python.org" -ForegroundColor Red
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "relay_agent.py --user local" -WorkingDirectory $ScriptPath
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId (whoami) -LogonType S4U -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

Write-Host "✅ J.A.R.V.I.S. Relay Agent installed as a scheduled task." -ForegroundColor Green
Write-Host "   It will start automatically on login and stay running."
Write-Host "   Stop: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host ""
Write-Host "Test it now by saying 'lock my PC' or 'open spotify' in the app." -ForegroundColor Cyan
