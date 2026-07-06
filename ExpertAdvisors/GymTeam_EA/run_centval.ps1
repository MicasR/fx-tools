# CENT-VALIDATION batch (deploy gate, NEXT_SESSION 2026-07-06).
# Reruns each deploy leg's tester ini with Deposit = its shakedown funding
# (cent-account USc: $33 -> 3300 etc.) using the FROZEN binary (no compile).
# Streams land in fx_gym\out\centval\ for tools\centval_compare.py.
# NOTE: kills any running EXNESS terminal (data-dir lock, CK workflow).

$ErrorActionPreference = 'Stop'
$term    = 'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe'
$dataDir = 'C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06'
$tester  = "$dataDir\MQL5\Profiles\Tester"
# tester EAs write FileOpen output to the AGENT sandbox, not the terminal dir
$files   = 'C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Tester\53785E099C927DB68A545C249CDBCE06\Agent-127.0.0.1-3000\MQL5\Files'
$outDir  = 'C:\Users\Dercio Micas\Desktop\projects\fx_gym\out\centval'
$bakDir  = "$files\backup_pre_centval"

# leg -> (base ini, deposit in tester units = USc)
$legs = [ordered]@{
  'XAU_H4_align'   = @('GT_XAU_H4_align.ini',   3300)
  'XAU_H4_engulf'  = @('GT_XAU_H4_engulf.ini',  3100)
  'BTC_wh_shield'  = @('GT_BtcShield_val.ini',  1600)
  'XAU_H4_keltner' = @('GT_XAU_H4_keltner.ini', 1000)
  'XAU_H1_don55'   = @('GT_XAU_H1_don55.ini',    600)
  'XAU_H1_keltner' = @('GT_XAU_H1_keltner.ini',  400)
}

New-Item -ItemType Directory -Force $outDir | Out-Null
New-Item -ItemType Directory -Force $bakDir | Out-Null
Get-ChildItem "$files\gt_ops_*.csv" -ErrorAction SilentlyContinue |
  ForEach-Object { Copy-Item $_.FullName $bakDir -Force }
Write-Output "backed up existing gt_ops_*.csv -> $bakDir"

foreach ($leg in $legs.Keys) {
  $base = $legs[$leg][0]; $dep = $legs[$leg][1]
  $ini  = "$tester\GT_${leg}_centval.ini"
  $txt  = Get-Content "$tester\$base" -Encoding Unicode
  # InpFixedE0 = the leg's live funding (USc): lots size exactly as the live
  # cent account's first op -> min-lot/min-stop granularity is THE thing
  # measured. Deposit stays large: InpFixedE0=0 (whole balance) would zero
  # the tester account on the first -1R (live, Main refunds the ops account).
  $txt  = $txt -replace '^Report=.*',  "Report=C:\Users\Dercio Micas\Desktop\projects\fx_tools\backtest\out\GT_${leg}_centval" `
               -replace '^Visual=.*',  'Visual=0' `
               -replace '^ShutdownTerminal=.*', 'ShutdownTerminal=1' `
               -replace '^InpFixedE0=.*', "InpFixedE0=$dep"
  $txt | Out-File $ini -Encoding Unicode
  Write-Output ""
  Write-Output ">>> $leg  (deposit $dep USc = `$$($dep/100))"

  Get-Process terminal64 -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like '*EXNESS*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force }
  Start-Sleep -Seconds 3

  $sw = [Diagnostics.Stopwatch]::StartNew()
  Start-Process -FilePath $term -ArgumentList "/config:`"$ini`"" -Wait
  Write-Output ("    tester done in {0:n0}s" -f $sw.Elapsed.TotalSeconds)

  $src = "$files\gt_ops_$leg.csv"
  if (Test-Path $src) {
    Copy-Item $src "$outDir\gt_ops_$leg.csv" -Force
    $n = (Get-Content $src | Measure-Object -Line).Lines - 1
    Write-Output "    ops logged: $n -> out\centval\gt_ops_$leg.csv"
  } else {
    Write-Output "    WARNING: no gt_ops_$leg.csv produced"
  }
}
Write-Output ""
Write-Output "next: python tools\centval_compare.py   (fx_gym)"
