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

## Status / next (updated 2026-06-12)

This harness long outgrew the original indicator A/B test. It is now the research
bed for the **VolumeSpikeBreakOut** breakout system and its two-account / stacking
/ portfolio extensions. The per-step research log lives in the git history (one
commit per result); the headlines:

- **Validated edge:** H1 V-pattern *breakout* entry, deploy only on persistent
  trenders (gold, BTC); never mean-reverting FX crosses.
- **👑 Final gold king (in-sample):** a **shield+sword trio** run as three
  concurrent ops-accounts into one Main account, sized to a drawdown budget —
  `geo1.7` **50%** + `geofloor f5/s210 1.5%` **37.5%** + `TP2.0 shield` **12.5%**.
  Growth @24%-DD ≈ **38.9×**; real-money (`metrics_mt5.py`, $1000 Main, 2.21yr):
  **+437% @1%/op (10.5% DD)** or **+1922% @2%/op (19.9% DD)**. Ranking metric is
  **geometric growth-at-matched-DD** (raw totR inverts under compounding); standard
  robustness exam = spread-stress @ $0.40 (`stress_audit.py`).
- **BTC:** parked at its H1 additive self-funding pyramid (TP5R, G0.25, 2.5R trail);
  **next up** — build the BTC king (does shield+sword generalize? trailing is BTC's natural sword).

Key research artifacts: `pyramid_engine.py` (`run_tf` stacking engine),
`conc_engine.py` (concurrent ops + poscandle/pinprev triggers), `shield.py`,
`concurrent_geo.py` (geometric scale-to-DD), `king_weights4.py` (weight optimizer),
`metrics_mt5.py` (MT5 report + equity chart), `stress_audit.py`, `symbol_specs.py`
(live broker specs). EAs in `../ExpertAdvisors/`.

Backlog (the stack): (1) **BTC king** (generalization + uncorrelated 2nd instrument),
(2) cross-instrument gold-king + BTC-king, (3) **EAs → DEMO forward test** — the
honest out-of-sample gate (everything above is in-sample, one gold regime).
