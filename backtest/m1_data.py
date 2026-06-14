"""
m1_data.py — DATA PARITY layer for the M1-intrabar engine (FIDELITY §3.3).

The MQL5 tester's Model 1 builds EVERYTHING from M1: the H1 entry bars (incl. their
tick_volume, which drives the V-pattern), the M15 management bars, and the intrabar
path. So Python must consume the SAME single source: dump M1, then DERIVE H1 & M15
from it by aggregation. H1 tick_volume = SUM of the constituent M1 tick_volumes.

This module loads the dumped M1 and resamples to any TF. MT5 bar timestamp = the
bar's OPEN time, and an H1 bar at 14:00 spans the M1 bars 14:00..14:59 -> resample
left-labelled, left-closed.

  derive(sym, tf) -> DataFrame[time, open, high, low, close, tick_volume, spread]
"""
import glob
import pandas as pd

_TF_RULE = {"M1": "1min", "M5": "5min", "M15": "15min", "M30": "30min",
            "H1": "1h", "H4": "4h", "D1": "1D"}

_cache = {}


def load_m1(sym):
    if sym not in _cache:
        path = glob.glob(f"data/*{sym}*_M1.csv")[0]
        df = pd.read_csv(path, parse_dates=["time"])
        _cache[sym] = df
    return _cache[sym]


def derive(sym, tf):
    """Aggregate the dumped M1 up to timeframe `tf` (left-labelled, left-closed).
    tick_volume & real_volume SUM; spread takes the mean (per-bar representative)."""
    if tf == "M1":
        return load_m1(sym).copy()
    m1 = load_m1(sym).set_index("time")
    rule = _TF_RULE[tf]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "tick_volume": "sum"}
    if "spread" in m1.columns:
        agg["spread"] = "mean"
    if "real_volume" in m1.columns:
        agg["real_volume"] = "sum"
    out = m1.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return out.reset_index()


if __name__ == "__main__":
    # DATA PARITY check: M1->H1 tick_volume reconciliation + entry-set diff vs old H1
    import numpy as np
    import signals as sg
    from book_sim import entry_events

    for sym in ("XAU", "BTC"):
        print(f"\n================ {sym}  DATA PARITY ================")
        m1 = load_m1(sym)
        print(f"  M1: {len(m1):,} bars  {m1['time'].iloc[0]} -> {m1['time'].iloc[-1]}")
        h1d = derive(sym, "H1")
        print(f"  derived H1: {len(h1d):,} bars  {h1d['time'].iloc[0]} -> {h1d['time'].iloc[-1]}")

        # old separately-pulled H1
        old = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
        print(f"  old H1 CSV: {len(old):,} bars  {old['time'].iloc[0]} -> {old['time'].iloc[-1]}")

        # tick_volume reconciliation on overlapping timestamps
        merged = pd.merge(h1d[["time", "tick_volume"]], old[["time", "tick_volume"]],
                          on="time", suffixes=("_m1", "_old"))
        if len(merged):
            a, b = merged["tick_volume_m1"].to_numpy(float), merged["tick_volume_old"].to_numpy(float)
            rel = np.abs(a - b) / np.maximum(b, 1)
            print(f"  overlap {len(merged):,} H1 bars | tick_volume "
                  f"identical={100*np.mean(a == b):.1f}%  "
                  f"median|Δ%|={100*np.median(rel):.2f}  mean|Δ%|={100*np.mean(rel):.2f}  "
                  f"max|Δ%|={100*np.max(rel):.1f}")

        # entry-set diff: V-pattern breakouts on derived-H1 vs old-H1
        def evset(h1):
            d = sg.add_features(h1, period=20, mult=2.0)
            evs, *_ = entry_events(d)
            t = d["time"].to_numpy()
            return {(str(t[e["ej"]]), e["d"]) for e in evs}, len(evs)
        s_new, n_new = evset(h1d)
        s_old, n_old = evset(old)
        common = s_new & s_old
        print(f"  entries: derived-H1={n_new}  old-H1={n_old}  "
              f"shared(time+dir)={len(common)}  new-only={len(s_new - s_old)}  "
              f"old-only={len(s_old - s_new)}")
