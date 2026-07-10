# Clean the orchestrator audit DB before go-live so the immutable op/transfer audit starts empty
# (the running tests + smoke leave rows in state.db). Backs up the old DB first, then removes
# state.db + WAL/SHM so the orchestrator recreates a fresh schema on next start.
# RUN THIS ONLY ONCE, right before real go-live, with the orchestrator STOPPED.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Db   = Join-Path $Root "orchestrator\state.db"
if (Get-NetTCPConnection -LocalPort 8800 -State Listen -ErrorAction SilentlyContinue) {
    throw "orchestrator appears to be running (port 8800). Stop it first, then re-run."
}
if (Test-Path $Db) {
    $bak = Join-Path $Root ("ops\backups\pre-reset-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".db")
    New-Item -ItemType Directory -Force -Path (Split-Path $bak) | Out-Null
    Copy-Item $Db $bak -Force
    Write-Host "old DB archived -> $bak"
}
Remove-Item "$Db", "$Db-wal", "$Db-shm" -Force -ErrorAction SilentlyContinue
Write-Host "state.db cleared. It will be recreated fresh on next orchestrator start."
