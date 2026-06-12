"""
verify_monster.py — M5-granularity check of the geofloor s200 monster.
M15 f7/s200 == 105min fast / 3000min slow -> on M5 that's f21/s600.  The M5
cache (~1yr) covers the 2026-02-06..09 melt-up.  Question: does the February
op survive (line never touched) at 3x finer resolution, and how big is it?
Champion benchmark row included per standing rule (same M5 window).
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf

HDR = (f"{'variant':<24}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def row(lbl, res):
    ops, curve, pm, n = res
    R = np.array([o[2] for o in ops])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    pf = w / l if l > 0 else 9.99
    cum = peak = dd = 0.0
    for o in ops:
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // 6
    seg = [sum(o[2] for o in ops if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    rob = sum(1 for t in seg if t > 0)
    tot = R.sum(); rf = tot / dd if dd > 0 else 0
    oneop = R.max() / tot * 100 if tot > 0 else 0
    segs = " ".join(f"{s:+7.1f}" for s in seg)
    print(f"{lbl:<24}{len(R):>5}{tot:>9.1f}{R.mean():>7.2f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6{oneop:>5.0f}%  {segs}")


def dissect(lbl, res, tf, top=6):
    ops, curve, pm, n = res
    m = pd.read_csv(glob.glob(f"data/*XAU*_{tf}.csv")[0], parse_dates=["time"])
    m["x"] = m["close"].rolling(600 if tf == "M5" else 200).mean()
    m = m.dropna().reset_index(drop=True)
    print(f"\n--- {lbl}: top {top} ops ---")
    print(f"{'open':>17}{'close':>17}{'R':>10}{'nPos':>6}  exit")
    for o in sorted(ops, key=lambda o: -o[2])[:top]:
        t0, t1 = m["time"].iloc[o[0]], m["time"].iloc[min(o[1], len(m) - 1)]
        print(f"{str(t0):>17}{str(t1):>17}{o[2]:>10.1f}{o[3]:>6}  {o[4]}")


if __name__ == "__main__":
    m5 = pd.read_csv(glob.glob("data/*XAU*_M5.csv")[0], parse_dates=["time"])
    print(f"M5 window: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({len(m5)} bars)\n")
    print(HDR)
    champ = run_tf("XAU", tf="M5", triggers=("bounce",), smaP=21,
                   sizing="proggeo", unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    row("champion geo1.7 (M5)", champ)
    geo = run_tf("XAU", tf="M5", triggers=("bounce",), smaP=21, sizing="geofloor",
                 slowP=600, unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    row("geofloor f21/s600 (M5)", geo)

    dissect("geofloor f21/s600 (M5)", geo, "M5")
    dissect("champion geo1.7 (M5)", champ, "M5")
