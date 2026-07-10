# Auto-restart wrapper for the Telegram bot. Loads .env (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID /
# ORCH_URL) from the project root, then runs orchestrator.bot, relaunching if it exits.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Log  = Join-Path $Root "ops\bot.log"
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
    "$(Get-Date -Format o)  starting bot" | Out-File -Append -Encoding utf8 $Log
    & $Py -u -m orchestrator.bot *>> $Log   # -u: unbuffered, else prints never reach the log
    "$(Get-Date -Format o)  bot exited (code $LASTEXITCODE); restarting in 10s" | Out-File -Append -Encoding utf8 $Log
    Start-Sleep -Seconds 10
}
