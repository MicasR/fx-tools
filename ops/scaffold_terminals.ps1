# Scaffold 7 portable MT5 terminals (DEPLOYMENT_GUIDE §5) at C:\ck\mt5\T1..T7.
# Per terminal: copy the MT5 program dir, drop in CrossKing_EA.ex5 + the leg's PD3 preset (with
# InpTelemetryURL injected), and a startup.ini ([StartUp] auto-attaches the EA to the right chart).
# Does NOT log in or tick WebRequest/Algo — that's the one-time GUI step (creds in terminals.xlsx).
# Launch each later with:  C:\ck\mt5\Tn\terminal64.exe /portable /config:C:\ck\mt5\Tn\startup.ini
$ErrorActionPreference = "Stop"
$Root   = Split-Path -Parent $PSScriptRoot
$SrcMT5 = "C:\Program Files\MetaTrader 5"
$Ex5    = Join-Path $Root "ExpertAdvisors\CrossKing_EA\CrossKing_EA.ex5"
$Presets= Join-Path $Root "ExpertAdvisors\CrossKing_EA\presets"
$Base   = "C:\ck\mt5"
$OrchUrl= "http://127.0.0.1:8800"

if (-not (Test-Path $Ex5)) { throw "compiled EA not found: $Ex5 (compile it first)" }

# leg map (from terminals.xlsx). symbol/period per the §1 table; charts are always H1.
$legs = @(
  @{ t="T1"; leg="PD3_BtcTrail_1"; preset="PD3_BtcTrail_1.set"; symbol="BTCUSDc"; period="H1"; reporter=$false },
  @{ t="T2"; leg="PD3_GoldGeo_0";  preset="PD3_GoldGeo_0.set";  symbol="XAUUSDc"; period="H1"; reporter=$false },
  @{ t="T3"; leg="PD3_BtcTrail_4"; preset="PD3_BtcTrail_4.set"; symbol="BTCUSDc"; period="H1"; reporter=$false },
  @{ t="T4"; leg="PD3_BtcNb_2";    preset="PD3_BtcNb_2.set";    symbol="BTCUSDc"; period="H1"; reporter=$false },
  @{ t="T5"; leg="PD3_BtcPin_5";   preset="PD3_BtcPin_5.set";   symbol="BTCUSDc"; period="H1"; reporter=$false },
  @{ t="T6"; leg="PD3_GoldGeo_3";  preset="PD3_GoldGeo_3.set";  symbol="XAUUSDc"; period="H1"; reporter=$false },
  @{ t="T7"; leg="Main";           preset="Main_reporter.set";  symbol="BTCUSDc"; period="H1"; reporter=$true  }
)

foreach ($L in $legs) {
    $dst = Join-Path $Base $L.t
    Write-Host "=== $($L.t)  ($($L.leg))  ->  $dst ==="
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    # copy program files (skip history caches + logs; they regenerate). robocopy: 1/3 = success.
    robocopy $SrcMT5 $dst /E /XD Bases Logs Tester /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $($L.t) (code $LASTEXITCODE)" }
    $expDir = Join-Path $dst "MQL5\Experts"
    $preDir = Join-Path $dst "MQL5\Presets"
    New-Item -ItemType Directory -Force -Path $expDir, $preDir | Out-Null
    Copy-Item $Ex5 (Join-Path $expDir "CrossKing_EA.ex5") -Force

    # build the per-terminal preset with the telemetry URL injected
    $setDst = Join-Path $preDir $L.preset
    if ($L.reporter) {
        @"
; Main reporter (T7) -- heartbeats balance/equity ONLY, never enters (InpRisePct impossible).
InpLegName=Main
InpMagicNumber=30260699
InpRisePct=999
InpStack=false
InpFixedE0=0.0
InpTelemetryURL=$OrchUrl
InpHeartbeatSec=30
"@ | Out-File -Encoding ascii $setDst
    } else {
        $content = Get-Content (Join-Path $Presets $L.preset) -Raw
        if ($content -match '(?m)^InpTelemetryURL=') {
            $content = $content -replace '(?m)^InpTelemetryURL=.*$', "InpTelemetryURL=$OrchUrl"
        } else {
            $content = $content.TrimEnd() + "`r`nInpTelemetryURL=$OrchUrl`r`n"
        }
        $content | Out-File -Encoding ascii $setDst
    }

    # startup.ini: auto-attach the EA to the right chart on launch
    @"
[StartUp]
Expert=CrossKing_EA
Symbol=$($L.symbol)
Period=$($L.period)
ExpertParameters=$($L.preset)
ShutdownTerminal=0
"@ | Out-File -Encoding ascii (Join-Path $dst "startup.ini")
    Write-Host "  ok: EA + $($L.preset) + startup.ini in place"
}
Write-Host "`nDONE. Next (per terminal, GUI): launch with /portable /config:startup.ini, then"
Write-Host "File>Login (creds in terminals.xlsx), Tools>Options>Expert Advisors: Allow WebRequest -> $OrchUrl, enable Algo Trading."
