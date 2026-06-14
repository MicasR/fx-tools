# Build + headless-validate the CrossKing EA. Usage: powershell -File run_test.ps1 <iniName> <oracleDesc>
param([string]$iniName = "CK_BtcShield_val", [string]$oracle = "45.8R / 396 ops / 50.3%")

$ErrorActionPreference = 'Stop'
$me   = 'C:\Program Files\MetaTrader 5 EXNESS\MetaEditor64.exe'
$term = 'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe'
$base = 'C:\Users\Dercio Micas\Desktop\projects\fx_tools\ExpertAdvisors\CrossKing_EA'
$src  = "$base\CrossKing_EA.mq5"
$clog = "$base\compile.log"
$dataDir = 'C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06'
$cfg  = "$dataDir\MQL5\Profiles\Tester\$iniName.ini"
$logpath = "$dataDir\Tester\logs\20260614.log"

# 1. compile
Start-Process -FilePath $me -ArgumentList "/compile:`"$src`"","/log:`"$clog`"" -Wait
Start-Sleep -Seconds 1
$cres = (Get-Content $clog -Encoding Unicode | Select-String "Result:").Line
Write-Output ("COMPILE: " + $cres)
if ($cres -notmatch "0 error") { Write-Output "COMPILE FAILED - abort"; exit 1 }

# 2. kill any running Exness terminal (release data-dir lock)
Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*EXNESS*' } | ForEach-Object { Stop-Process -Id $_.Id -Force }
Start-Sleep -Seconds 3

# 3. record log offset, launch test
$offset = if (Test-Path $logpath) { (Get-Item $logpath).Length } else { 0 }
Start-Process -FilePath $term -ArgumentList "/config:`"$cfg`""
Write-Output ("launched test [$iniName], waiting...")

# 4. poll up to 150s for completion in NEW log content
$done = $false; $new = ""
for ($i=0; $i -lt 50; $i++) {
   Start-Sleep -Seconds 3
   if (Test-Path $logpath) {
      $fs = [System.IO.File]::Open($logpath,'Open','Read','ReadWrite'); $fs.Seek($offset,'Begin') | Out-Null
      $sr = New-Object System.IO.StreamReader($fs); $new = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
      if ($new -match "final balance|connection closed") { $done = $true; break }
   }
}
Write-Output ("completed=$done after ~$($i*3)s")

# 5. kill terminal to release lock
Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*EXNESS*' } | ForEach-Object { Stop-Process -Id $_.Id -Force }

# 6. parse this run's ops
$initLine = ($new -split "`n") | Where-Object { $_ -match "init  sym" } | Select-Object -Last 1
Write-Output ("INIT:" + ($initLine -replace '.*\[CrossKing','  [CrossKing'))
$rs = @(); $splits = 0
foreach ($ln in ($new -split "`n")) {
   if ($ln -match "OP CLOSE.*R=(-?\d+\.\d+)") { $rs += [double]$matches[1] }
   if ($ln -match "in (\d+) order") { if ([int]$matches[1] -gt 1) { $splits++ } }
}
Write-Output ("ops=" + $rs.Count + "  splitAdds(>1 order)=" + $splits)
if ($rs.Count -gt 0) {
   $tot=($rs|Measure-Object -Sum).Sum; $w=($rs|Where-Object{$_ -gt 0}).Count
   $mn=($rs|Measure-Object -Minimum).Minimum; $mx=($rs|Measure-Object -Maximum).Maximum
   Write-Output ("RESULT: totR=" + [Math]::Round($tot,1) + "  win%=" + [Math]::Round(100*$w/$rs.Count,1) + "  minR=" + [Math]::Round($mn,2) + "  maxR=" + [Math]::Round($mx,2))
   Write-Output ("ORACLE: $oracle")
}
