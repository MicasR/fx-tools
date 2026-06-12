"""
investigate_f5.py — what is the f5/s200 seg3 lump (+116)?
geofloor f5/s200 TP3 @1:2000: heads / tails(top1 -> -1R) / double-tails
(top2 -> -1R), dissect top ops with dates, and M5 hairline-replay of the
big ops (is the seg3 lump another $0.33-style coin flip?).
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf, margin_line

HDR = (f"{'variant':<28}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def row(lbl, ops, n, flips=0):
    ops = [list(o) for o in ops]
    for _ in range(flips):
        top = max((o for o in ops if o[4] != "SL*"), key=lambda o: o[2])
        top[2], top[4] = -1.0, "SL*"
    R = np.array([o[2] for o in ops])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    pf = w / l if l > 0 else 9.99
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // 6
    seg = [sum(o[2] for o in ops if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    rob = sum(1 for t in seg if t > 0)
    tot = R.sum(); rf = tot / dd if dd > 0 else 0
    oneop = R.max() / tot * 100 if tot > 0 else 0
    segs = " ".join(f"{s:+7.1f}" for s in seg)
    print(f"{lbl:<28}{len(R):>5}{tot:>9.1f}{R.mean():>7.2f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6{oneop:>5.0f}%  {segs}")


def frame15(smaP):
    m = pd.read_csv(glob.glob("data/*XAU*_M15.csv")[0], parse_dates=["time"])
    m["sma"] = m["close"].rolling(smaP).mean()
    m["slow"] = m["close"].rolling(200).mean()
    return m.dropna().reset_index(drop=True)


def replay_m5(info, t15, m5):
    dd, E0, r0, e0, log = info["dir"], info["E0"], info["r0"], info["e0"], info["log"]
    tp = e0 + dd * 3.0 * r0
    sched = [(pd.Timestamp(t15[k]) + pd.Timedelta(minutes=15), P, lot) for k, P, lot in log]
    if sched[0][0] < m5["time"].iloc[0]:
        return "no-M5-data", None, None
    w = m5[(m5["time"] >= sched[0][0] - pd.Timedelta(minutes=15))].reset_index(drop=True)
    pos, si, mg, mgt = [], 0, 1e18, None
    for _, b in w.iterrows():
        while si < len(sched) and sched[si][0] <= b["time"]:
            pos.append((sched[si][1], sched[si][2])); si += 1
        if not pos:
            continue
        ml = margin_line(pos, dd, E0, 1.0, 0.0)
        gap = (b["low"] - ml) if dd == 1 else (ml - b["high"])
        if gap < mg:
            mg, mgt = gap, b["time"]
        if (b["low"] <= ml) if dd == 1 else (b["high"] >= ml):
            return "CLIPPED", mg, mgt
        if (b["high"] >= tp) if dd == 1 else (b["low"] <= tp):
            return "TP", mg, mgt
    return "END", mg, mgt


if __name__ == "__main__":
    champ = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7,
                   sizing="proggeo", unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    f5 = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=5, sizing="geofloor",
                slowP=200, unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    print(HDR)
    row("champion geo1.7", champ[0], champ[3])
    row("geofloor f5/s200", f5[0], f5[3])
    row("geofloor f5/s200 TAILS", f5[0], f5[3], flips=1)
    row("geofloor f5/s200 2xTAILS", f5[0], f5[3], flips=2)

    m = frame15(5)
    t15 = m["time"].to_numpy()
    n = f5[3]; q = n // 6
    m5 = pd.read_csv(glob.glob("data/*XAU*_M5.csv")[0], parse_dates=["time"])

    print(f"\n--- f5/s200 top 8 ops (seg = which sixth) ---")
    print(f"{'open':>17}{'close':>17}{'R':>9}{'nPos':>6}{'maxLot':>8}{'seg':>5}  exit"
          f"   M5-replay (closest $ to line)")
    for o in sorted(f5[0], key=lambda x: -x[2])[:8]:
        info = o[5]
        t0, t1 = m["time"].iloc[o[0]], m["time"].iloc[min(o[1], len(m) - 1)]
        mx = max(l for _, _, l in info["log"])
        sg = min(o[0] // q + 1, 6)
        res, mg, mgt = replay_m5(info, t15, m5)
        extra = (f"{res}, gap {mg:.2f}$ at {mgt}" if mg is not None else res)
        print(f"{str(t0):>17}{str(t1):>17}{o[2]:>9.1f}{o[3]:>6}{mx:>8.2f}{sg:>5}  {o[4]}"
              f"   {extra}")
