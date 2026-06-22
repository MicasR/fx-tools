# Supervisor for the CrossKing orchestrator (FastAPI + dashboard on :8800).
# Registered as a Scheduled Task at logon (see install_services.ps1). Polls /health every 10s and
# (re)launches uvicorn whenever it is not responding -- catches both crashes and hangs. Launches
# via Start-Process (the venv launcher misbehaves with a foreground `& python *>> log`).
# Trading never depends on this being up (control poll is fail-open), so a restart gap is harmless.
#   --timeout-keep-alive 0 : with the app's Connection: close header, avoids the MT5/WinINet
#                            keep-alive reuse failure (err=5203).
$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot          # project root (parent of ops\)
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = Join-Path $Root "ops\orchestrator.log"
$Out  = Join-Path $Root "ops\orchestrator.out"
$Err  = Join-Path $Root "ops\orchestrator.err"

function Test-Health {
    try { return (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8800/health" -TimeoutSec 4).StatusCode -eq 200 }
    catch { return $false }
}

while ($true) {
    if (-not (Test-Health)) {
        # clear any half-dead listener, then (re)launch
        Get-NetTCPConnection -LocalPort 8800 -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }
        Start-Sleep -Milliseconds 500
        "$(Get-Date -Format o)  (re)starting orchestrator" | Out-File -Append -Encoding utf8 $Log
        Start-Process -FilePath $Py `
            -ArgumentList "-m","uvicorn","orchestrator.app:app","--host","0.0.0.0","--port","8800","--timeout-keep-alive","0" `
            -WorkingDirectory $Root -RedirectStandardOutput $Out -RedirectStandardError $Err -WindowStyle Hidden
        Start-Sleep -Seconds 6        # give it time to bind before the next health check
    }
    Start-Sleep -Seconds 10
}
