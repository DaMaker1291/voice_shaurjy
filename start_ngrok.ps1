# Start ngrok tunnel to expose local backend publicly
# Requires ngrok.exe from https://ngrok.com/download

$ngrok = Get-Command ngrok.exe -ErrorAction SilentlyContinue
if (-not $ngrok) {
    $ngrok = Get-ChildItem "$PSScriptRoot\ngrok.exe" -ErrorAction SilentlyContinue
}
if (-not $ngrok) {
    Write-Host "ngrok.exe not found. Download from https://ngrok.com/download and place in this folder." -ForegroundColor Red
    Write-Host "Or: winget install ngrok" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting ngrok tunnel -> http://localhost:8000" -ForegroundColor Green
Write-Host "Dashboard: http://127.0.0.1:4040" -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath $ngrok.Source -ArgumentList "http 8000"
