# CrossKing watchdog (DEPLOYMENT_GUIDE §11). One pass: ensure the orchestrator (:8800), the bot,
# and the 7 portable terminals are running; relaunch any that are down. Schedule it every few
# minutes (Scheduled Task) OR loop it. Idempotent + safe to run repeatedly.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Base = "C:\ck\mt5"
$Log  = Join-Path $Root "ops\watchdog.log"
function W($m) { "$(Get-Date -Format o)  $m" | Tee-Object -Append -FilePath $Log }

# 1. orchestrator
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:8800/status" -TimeoutSec 5
} catch {
    W "orchestrator DOWN -> starting"
    if (Get-ScheduledTask -TaskName "CrossKing-Orchestrator" -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName "CrossKing-Orchestrator"
    } else {
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Root\ops\run_orchestrator.ps1`""
    }
}

# 2. bot (only if .env exists)
if (Test-Path (Join-Path $Root ".env")) {
    $bot = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -match "orchestrator\.bot" }
    if (-not $bot) {
        W "bot DOWN -> starting"
        if (Get-ScheduledTask -TaskName "CrossKing-Bot" -ErrorAction SilentlyContinue) {
            Start-ScheduledTask -TaskName "CrossKing-Bot"
        } else {
            Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Root\ops\run_bot.ps1`""
        }
    }
}

# 3. terminals T1..T7
$running = Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue
foreach ($n in 1..7) {
    $dir = Join-Path $Base "T$n"
    $exe = Join-Path $dir "terminal64.exe"
    if (-not (Test-Path $exe)) { continue }   # not scaffolded yet
    $up = $running | Where-Object { $_.CommandLine -match [regex]::Escape("$Base\T$n\") }
    if (-not $up) {
        W "terminal T$n DOWN -> launching"
        Start-Process $exe -ArgumentList "/portable", "/config:`"$dir\startup.ini`""
    }
}
W "watchdog pass complete"
