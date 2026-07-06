# TOP-UP VALIDATION LOOP (2026-07-06): after the base top-up change,
# (a) recompile; (b) rerun all 6 legs at InpFixedE0=100 — must reproduce the
# archived tester-true streams (shadow gate re-arm); (c) rerun cent-funding
# validation. Streams -> fx_gym\out\centval\ for tools\centval_compare.py.

$ErrorActionPreference = 'Stop'
$me      = 'C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe'
$term    = 'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe'
$base    = 'C:\Users\Dercio Micas\Desktop\projects\fx_tools\ExpertAdvisors\GymTeam_EA'
$dataDir = 'C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06'
$tester  = "$dataDir\MQL5\Profiles\Tester"
$files   = 'C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Tester\53785E099C927DB68A545C249CDBCE06\Agent-127.0.0.1-3000\MQL5\Files'
$outDir  = 'C:\Users\Dercio Micas\Desktop\projects\fx_gym\out\centval'

$legs = [ordered]@{
  'XAU_H4_align'   = @('GT_XAU_H4_align.ini',   3300)
  'XAU_H4_engulf'  = @('GT_XAU_H4_engulf.ini',  3100)
  'BTC_wh_shield'  = @('GT_BtcShield_val.ini',  1600)
  'XAU_H4_keltner' = @('GT_XAU_H4_keltner.ini', 1000)
  'XAU_H1_don55'   = @('GT_XAU_H1_don55.ini',    600)
  'XAU_H1_keltner' = @('GT_XAU_H1_keltner.ini',  400)
}

# 1. compile
Start-Process -FilePath $me -ArgumentList "/compile:`"$base\GymTeam_EA.mq5`"","/log:`"$base\compile.log`"" -Wait
Start-Sleep -Seconds 1
$cres = (Get-Content "$base\compile.log" -Encoding Unicode | Select-String "Result:").Line
Write-Output ("COMPILE: " + $cres)
if ($cres -notmatch "0 error") { Write-Output "COMPILE FAILED - abort"; exit 1 }

function Run-Ini([string]$ini, [string]$leg, [string]$suffix) {
  Get-Process terminal64 -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 3
  Start-Process -FilePath $term -ArgumentList "/config:`"$ini`"" -Wait
  $src = "$files\gt_ops_$leg.csv"
  if (Test-Path $src) {
    Copy-Item $src "$outDir\gt_ops_$leg$suffix.csv" -Force
    $n = (Get-Content $src | Measure-Object -Line).Lines - 1
    Write-Output "    $leg$suffix : $n ops"
  } else { Write-Output "    WARNING: no ops csv for $leg$suffix" }
}

foreach ($leg in $legs.Keys) {
  $b = $legs[$leg][0]; $dep = $legs[$leg][1]
  Write-Output ">>> $leg"
  # (b) e100: shadow-gate re-arm vs archived stream
  $txt = Get-Content "$tester\$b" -Encoding Unicode
  ($txt -replace '^Visual=.*','Visual=0' `
        -replace '^ShutdownTerminal=.*','ShutdownTerminal=1' `
        -replace '^Report=.*',"Report=C:\Users\Dercio Micas\Desktop\projects\fx_tools\backtest\out\GT_${leg}_e100" `
        -replace '^InpFixedE0=.*','InpFixedE0=100') |
    Out-File "$tester\GT_${leg}_e100.ini" -Encoding Unicode
  Run-Ini "$tester\GT_${leg}_e100.ini" $leg '_e100'
  # (c) cent funding
  ($txt -replace '^Visual=.*','Visual=0' `
        -replace '^ShutdownTerminal=.*','ShutdownTerminal=1' `
        -replace '^Report=.*',"Report=C:\Users\Dercio Micas\Desktop\projects\fx_tools\backtest\out\GT_${leg}_centval" `
        -replace '^InpFixedE0=.*',"InpFixedE0=$dep") |
    Out-File "$tester\GT_${leg}_centval.ini" -Encoding Unicode
  Run-Ini "$tester\GT_${leg}_centval.ini" $leg ''
}
Write-Output "done: python tools\centval_compare.py"
