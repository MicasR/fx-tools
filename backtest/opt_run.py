"""
opt_run.py — FIDELITY §3.6 king re-search harness (Path A: tester-as-truth).

Drives the MetaTrader-5 strategy-TESTER optimizer (MetaQuotes terminal, which holds
the Exness account + cloud optimization agents) over the CrossKing_EA management
knobs, and collects every pass (local + cloud) via the EA's frame -> ck_opt.csv.
Each pass is scored by OnTester = nbpR * (positive-6-seg / 6) -- the NBP-clamped,
robustness-weighted live metric. Finalists are re-blended into the cross-king
portfolio (Python) and ranked by growth-at-matched-DD.

  run_opt(tag, leg, opt={"InpProgStep": (1.4, 0.1, 2.0), ...}, fixed={...}, mode=1)
    -> DataFrame of passes (one row per param combo), also saved to out/opt/<tag>.csv

Optimizer modes: 1 = complete (full grid), 2 = genetic (large grids).
"""
import io
import os
import shutil
import subprocess
import pandas as pd

TERM = r"C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
EXE = r"C:\Program Files\MetaTrader 5\terminal64.exe"
INI_DIR = rf"{TERM}\MQL5\Profiles\Tester"
CK_CSV = rf"{TERM}\MQL5\Files\ck_opt.csv"
OUT = "out/opt"

# the 6 current legs (symbol, chart period, mgmtTF code, magic, MPL, + king params).
# mgmtTF: 15 = M15 (gold), 16385 = H1 (BTC).
LEGS = {
    "GoldS210":   dict(sym="XAUUSDc", per="H1", mtf=15,    mg=20260602, mpl=0.419,
                       stack="true",  sizing=1, smaP=5,  slowP=210, mult=0.015, step=1.7, tpR=3.0,  trailR=0.0),
    "GoldGeo17":  dict(sym="XAUUSDc", per="H1", mtf=15,    mg=20260601, mpl=0.419,
                       stack="true",  sizing=0, smaP=7,  slowP=0,   mult=0.01,  step=1.7, tpR=3.0,  trailR=0.0),
    "GoldShield": dict(sym="XAUUSDc", per="H1", mtf=15,    mg=20260603, mpl=0.419,
                       stack="false", sizing=0, smaP=7,  slowP=0,   mult=0.01,  step=1.7, tpR=2.0,  trailR=0.0),
    "BtcGF":      dict(sym="BTCUSDc", per="H1", mtf=16385, mg=20260604, mpl=0.318,
                       stack="true",  sizing=1, smaP=15, slowP=210, mult=0.015, step=1.2, tpR=0.0,  trailR=2.5),
    "BtcPG":      dict(sym="BTCUSDc", per="H1", mtf=16385, mg=20260605, mpl=0.318,
                       stack="true",  sizing=0, smaP=15, slowP=0,   mult=0.01,  step=1.2, tpR=3.0,  trailR=0.0),
    "BtcShield":  dict(sym="BTCUSDc", per="H1", mtf=16385, mg=20260606, mpl=0.318,
                       stack="false", sizing=0, smaP=15, slowP=0,   mult=0.01,  step=1.2, tpR=1.25, trailR=0.0),
}

# EA input name for each short knob key
KNOB = {"sizing": "InpSizing", "smaP": "InpSmaP", "slowP": "InpSlowP", "mult": "InpMult",
        "step": "InpProgStep", "tpR": "InpTpR", "trailR": "InpTrailR", "half": "InpHalf",
        "mtf": "InpMgmtTF", "stack": "InpStack"}


def _val(name, base, opt):
    """Render one [TesterInputs] line; optimized knobs get value||start||step||stop||Y."""
    if name in opt:
        lo, st, hi = opt[name]
        return f"{KNOB[name]}={lo}||{lo}||{st}||{hi}||Y"
    return f"{KNOB[name]}={base}"


def run_opt(tag, leg, opt=None, fixed=None, mode=1, timeout=3600):
    opt = dict(opt or {})
    L = dict(LEGS[leg]); L.update(fixed or {})
    half = L.get("half", 0.5)
    knobs = "\n".join(_val(k, L.get(k, half if k == "half" else None), opt)
                      for k in ["sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half"])
    ini = f"""[Tester]
Expert=CrossKing_EA\\CrossKing_EA.ex5
Symbol={L['sym']}
Period={L['per']}
Optimization={mode}
Model=1
OptimizationCriterion=6
FromDate=2024.02.26
ToDate=2026.06.13
ForwardMode=0
Deposit=100000
Currency=USD
Leverage=2000
ExecutionMode=0
Visual=0
ShutdownTerminal=1
[TesterInputs]
InpLegName={leg}
InpMagicNumber={L['mg']}
InpEntryTF=16385
InpMgmtTF={L['mtf']}
InpMAPeriod=20
InpMultiplier=2.0
InpRisePct=0.02
InpBreakBars=4
InpStack={L['stack']}
{knobs}
InpFixedE0=10.0
InpTROverride=0.0
InpMPLOverride={L['mpl']}
InpDeviation=50
InpTelemetryURL=
InpHeartbeatSec=30
"""
    os.makedirs(OUT, exist_ok=True)
    ini_path = rf"{INI_DIR}\ck_opt_{tag}.ini"
    with io.open(ini_path, "w", encoding="utf-16-le") as f:
        f.write(ini)
    if os.path.exists(CK_CSV):
        os.remove(CK_CSV)
    subprocess.run([EXE, f"/config:{ini_path}"], timeout=timeout)
    if not os.path.exists(CK_CSV):
        raise RuntimeError(f"{tag}: no ck_opt.csv produced (optimization failed?)")
    dst = f"{OUT}/{tag}.csv"
    shutil.copy(CK_CSV, dst)
    df = pd.read_csv(dst)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def show(df, n=15):
    cols = ["score", "nbpR", "segpos", "rf", "oneop", "ops", "win",
            "sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half"]
    cols = [c for c in cols if c in df.columns]
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(df[cols].head(n).to_string(index=False))
