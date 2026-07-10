# Daily backup of the orchestrator audit DB (DEPLOYMENT_GUIDE §11). state.db holds the immutable
# op + transfer audit. Uses SQLite Online Backup via the venv python so a WAL-mode live DB is
# copied consistently (don't just Copy-Item a WAL db under load). Keeps 30 days, prunes older.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py   = Join-Path $Root ".venv\Scripts\python.exe"
$Db   = Join-Path $Root "orchestrator\state.db"
$Dir  = Join-Path $Root "ops\backups"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$out   = Join-Path $Dir "state-$stamp.db"
& $Py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $Db $out
Write-Host "backed up -> $out"
# prune > 30 days
Get-ChildItem $Dir -Filter "state-*.db" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    ForEach-Object { Remove-Item $_.FullName -Force; Write-Host "pruned $($_.Name)" }
