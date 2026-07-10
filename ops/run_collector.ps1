# Auto-restart wrapper for the pull collector (MT5 investor-login telemetry -> orchestrator).
# Registered as a logon Scheduled Task (see install_services.ps1); relaunches if it exits.
# Loads .env from the project root for ORCH_URL / MT5_READER_PATH / COLLECTOR_POLL_S / CK_DB.
#
# The collector logs into each registered account READ-ONLY (investor pw from
# orchestrator/secrets.json) through a DEDICATED reader terminal set by MT5_READER_PATH -- never a
# live trading terminal, because mt5.login() switches the reader's account and would knock a
# trading terminal off its login. Use a standalone install (e.g. "C:\Program Files\MetaTrader 5").
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = Join-Path $Root "ops\collector.log"
$Env  = Join-Path $Root ".env"
Set-Location $Root
while ($true) {
    if (Test-Path $Env) {
        Get-Content $Env | ForEach-Object {
            if ($_ -match '^\s*([^#=]+)=(.*)$') {
                [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
            }
        }
    } else {
        "$(Get-Date -Format o)  WARNING: .env not found at $Env" | Out-File -Append -Encoding utf8 $Log
    }
    "$(Get-Date -Format o)  starting collector" | Out-File -Append -Encoding utf8 $Log
    & $Py -u -m orchestrator.collector *>> $Log   # -u: unbuffered, else prints never reach the log
    "$(Get-Date -Format o)  collector exited (code $LASTEXITCODE); restarting in 10s" | Out-File -Append -Encoding utf8 $Log
    Start-Sleep -Seconds 10
}
