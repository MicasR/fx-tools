"""
margin_line4.py — is geofloor-ex-monster a real champion-beater, or s200 luck?
geofloor = champion's geo x1.7 ramp, but each add may be LARGER if pin-to-slow-SMA
asks for more (lottery ticket attached to the champion).  lev=2000 (user's broker).
Report ex-top-1 totR + ex-top-1 segments across the slow axis + fast axis.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf

HDR = (f"{'variant':<24}{'ops':>5}{'totR':>9}{'RF':>7}{'win%':>6}{'segs':>6}"
       f"{'exTop1':>8}{'exSegs':>5}   ex-top-1 per-segment R")


def row(lbl, res):
    ops, curve, pm, n = res
    R = np.array([o[2] for o in ops])
    cum = peak = dd = 0.0
    for o in ops:
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    tot = R.sum(); rf = tot / dd if dd > 0 else 0
    q = n // 6
    seg = [sum(o[2] for o in ops if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    rob = sum(1 for t in seg if t > 0)
    # ex-top-1
    top = max(ops, key=lambda o: o[2])
    ex = [o for o in ops if o is not top]
    xseg = [sum(o[2] for o in ex if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
            for k in range(6)]
    xrob = sum(1 for t in xseg if t > 0)
    xs = " ".join(f"{s:+7.1f}" for s in xseg)
    print(f"{lbl:<24}{len(R):>5}{tot:>9.1f}{rf:>7.1f}{100*np.mean(R>0):>6.1f}   {rob}/6"
          f"{tot-top[2]:>8.1f}   {xrob}/6  {xs}")


def main(sym="XAU", tf="M15", lev=2000.0):
    print(f"lev = 1:{lev:.0f}\n"); print(HDR)
    row("champion geo1.7",
        run_tf(sym, tf=tf, triggers=("bounce",), smaP=7, sizing="proggeo",
               unit="base", mult=0.01, prog_step=1.7, lev=lev))
    print()
    for slow in (100, 150, 200, 250, 300, 400):
        row(f"geofloor f7/s{slow}",
            run_tf(sym, tf=tf, triggers=("bounce",), smaP=7, sizing="geofloor",
                   slowP=slow, unit="base", mult=0.01, prog_step=1.7, lev=lev))
    print()
    for fast in (5, 10):
        row(f"geofloor f{fast}/s200",
            run_tf(sym, tf=tf, triggers=("bounce",), smaP=fast, sizing="geofloor",
                   slowP=200, unit="base", mult=0.01, prog_step=1.7, lev=lev))

    m = pd.read_csv(glob.glob(f"data/*{sym}*_{tf}.csv")[0], parse_dates=["time"])
    m["slow"] = m["close"].rolling(200).mean()
    m = m.dropna().reset_index(drop=True)
    print(f"\nmonster op: k0=43823 -> {m['time'].iloc[43823]}  "
          f"close {m['close'].iloc[43823]:.0f};  kEnd=43970 -> {m['time'].iloc[43970]}  "
          f"close {m['close'].iloc[43970]:.0f}")


if __name__ == "__main__":
    main()
