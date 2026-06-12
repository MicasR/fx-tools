"""
verify_monster2.py — surgical replay of the EXACT M15 monster book against M5 bars.
Take the recorded geofloor s200 (lev 1:2000) top op — every entry (time, price,
lot) as the M15 sim placed it — and walk M5 bars through the op's life:
was the margin (equity-0) line ever touched by an M5 low that the M15 bars
couldn't see?  Survives -> the trade was at least intrabar-feasible (just
trigger-fragile).  Clipped -> the +903R was pure bar-granularity fantasy.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf, margin_line

TR = 1.0


def replay(sym="XAU"):
    ops, curve, pm, n = run_tf(sym, tf="M15", triggers=("bounce",), smaP=7,
                               sizing="geofloor", slowP=200, unit="base",
                               mult=0.01, prog_step=1.7, lev=2000.0)
    top = max(ops, key=lambda o: o[2])
    info = top[5]
    dd, E0, r0, e0, log = info["dir"], info["E0"], info["r0"], info["e0"], info["log"]
    tp = e0 + dd * 3.0 * r0

    m15 = pd.read_csv(glob.glob(f"data/*{sym}*_M15.csv")[0], parse_dates=["time"])
    m15["sma"] = m15["close"].rolling(7).mean()
    m15["slow"] = m15["close"].rolling(200).mean()
    m15 = m15.dropna().reset_index(drop=True)
    t15 = m15["time"].to_numpy()

    print(f"M15 monster op: R={top[2]:+.1f}, {top[3]} positions, exit {top[4]}")
    print(f"dir={'long' if dd==1 else 'short'}  e0={e0:.2f}  r0={r0:.2f}  TP={tp:.2f}\n")
    print("add schedule (effective at M15 bar close = open+15min):")
    sched = []
    for k, P, lot in log:
        eff = pd.Timestamp(t15[k]) + pd.Timedelta(minutes=15)
        sched.append((eff, P, lot))
        print(f"  {eff}  price {P:>9.2f}  lot {lot:>8.2f}")

    m5 = pd.read_csv(glob.glob(f"data/*{sym}*_M5.csv")[0], parse_dates=["time"])
    t_open = sched[0][0] - pd.Timedelta(minutes=15)
    t_end = pd.Timestamp(t15[min(top[1], len(t15) - 1)]) + pd.Timedelta(hours=2)
    w = m5[(m5["time"] >= t_open) & (m5["time"] <= t_end)].reset_index(drop=True)
    print(f"\nM5 replay window: {w['time'].iloc[0]} .. {w['time'].iloc[-1]}  ({len(w)} bars)")

    pos, si, min_gap = [], 0, 1e18
    for _, b in w.iterrows():
        while si < len(sched) and sched[si][0] <= b["time"]:
            pos.append((sched[si][1], sched[si][2])); si += 1
        if not pos:
            continue
        ml = margin_line(pos, dd, E0, TR, 0.0)
        gap = (b["low"] - ml) if dd == 1 else (ml - b["high"])
        if gap < min_gap:
            min_gap, gap_t, gap_ml = gap, b["time"], ml
        if (b["low"] <= ml) if dd == 1 else (b["high"] >= ml):
            print(f"\nCLIPPED: M5 bar {b['time']} touched the line "
                  f"(low {b['low']:.2f} vs line {ml:.2f}, {len(pos)} pos) -> op = -1R.")
            print("The M15 +R was bar-granularity fantasy.")
            return
        if (b["high"] >= tp) if dd == 1 else (b["low"] <= tp):
            print(f"\nSURVIVED: TP {tp:.2f} hit at {b['time']} with the line never "
                  f"touched at M5 granularity.")
            print(f"closest call: {min_gap:.2f} $ above the line at {gap_t} "
                  f"(line {gap_ml:.2f})")
            return
    print(f"\nwindow ended without SL/TP; closest gap {min_gap:.2f}$ at {gap_t}")


if __name__ == "__main__":
    replay()
