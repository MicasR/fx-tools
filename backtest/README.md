# Backtest — VolumeSpike vs VolumeVPattern

Python harness to compare the two indicators' signals on XAU/USD (or any symbol)
using data pulled straight from the local MetaTrader 5 terminal.

## Setup

```powershell
# from backtest/
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **NumPy must be < 2.** `MetaTrader5 5.0.45` is compiled against NumPy 1.x and
> crashes on import with NumPy 2.x. `requirements.txt` pins `numpy<2` and
> `pandas==2.2.3` accordingly.

## Run

MetaTrader 5 must be **open and logged in** for the fetch step.

```powershell
# 1. pull data (caches to data/<symbol>_<tf>.csv)
.\.venv\Scripts\python.exe fetch_data.py --tf M15 --from 2026-01-01

# 2. compare + write charts to out/
.\.venv\Scripts\python.exe compare.py --tf M15 --method stddev --rise 0.02
```

Outputs: `out/equity.png`, `out/metrics.png`, `out/signals_zoom.png` plus a
comparison table printed to the console.

## Files

| File | Role |
|------|------|
| `fetch_data.py` | resolve the gold symbol, pull OHLC + tick_volume from MT5, cache to CSV |
| `signals.py` | faithful Python ports of both signal logics + trade evaluator (forward returns, MFE/MAE, ATR R:R bracket) |
| `compare.py` | load data, run both, print table, render charts |

## Conventions (match the indicators)

- Volume MA = SMA(20), population StdDev (`ddof=0`).
- **VolumeSpike**: signal when volume crosses the level (StdDev: `vol > MA + 2·StdDev`).
- **VolumeVPattern**: signal on C1 when the method's line traces a V —
  `s[i-2] > s[i-1]` and `s[i] > s[i-1]` and `(s[i]-s[i-1])/|s[i-1]| ≥ rise`.
- Both enter at the **next bar's open**; direction = signal bar's candle colour.

## Status / next

- [x] venv, deps, data fetch, signal ports, evaluator, charts written
- [ ] **First full run pending** (interrupted before fetch completed)
- [ ] Inspect charts, sanity-check signal counts vs the MT5 chart
- [ ] Tune evaluation (exit rule / horizons) and add Percentile/RVOL/Threshold sweeps
