$env:CLOUDFLARE_API_TOKEN=$env:CF_API_TOKEN
$env:CLOUDFLARE_ACCOUNT_ID=$env:CF_ACCOUNT_ID
$env:MAX_ITERATIONS="1"
$env:FIX_MODE="manual"
$env:LOOP_DELAY_SECONDS="0"
$bd="C:\Users\supro\Downloads\CODE\voice_shaurjy\backend"
$pyw="$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe"
if(-not (Test-Path $pyw)){$pyw="pythonw"}
Write-Host "Running pipeline..."
Start-Process -FilePath $pyw -ArgumentList "main_loop.py" -WorkingDirectory $bd -WindowStyle Hidden -Wait
Write-Host "Pipeline complete. Checking logs..."
if(Test-Path "$bd\main_loop.log"){Get-Content "$bd\main_loop.log" -Tail 20}
if(Test-Path "$bd\ai_analysis.txt"){Write-Host "`n--- AI ANALYSIS ---";Get-Content "$bd\ai_analysis.txt" -Tail 50}