"""
margin_line3.py — leverage axis + per-segment R for the monster configs (GOLD M15).

Broker reality (user): base account = 1:2000 (reduced during high-trading
windows), and UNLIMITED-leverage accounts exist.  SPECS margins were measured
at ~1:400, so the earlier study was the conservative floor.  Broker selection
is part of the strategy.  lev = 400 / 1000 / 2000 / 0 (unlimited).
"""
import numpy as np
from pyramid_engine import run_tf

HDR = (f"{'variant':<28}{'lev':>6}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def seg_row(lbl, lev, res):
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
    segs = " ".join(f"{s:+8.1f}" for s in seg)
    lv = "unl" if lev == 0 else f"{lev:.0f}"
    print(f"{lbl:<28}{lv:>6}{len(R):>5}{tot:>9.1f}{R.mean():>7.2f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6{oneop:>5.0f}%  {segs}")


def dissect(lbl, res, top=8):
    ops, curve, pm, n = res
    print(f"\n--- {lbl}: top {top} ops ---")
    print(f"{'k0':>8}{'kEnd':>8}{'R':>10}{'nPos':>6}  exit")
    for o in sorted(ops, key=lambda o: -o[2])[:top]:
        print(f"{o[0]:>8}{o[1]:>8}{o[2]:>10.1f}{o[3]:>6}  {o[4]}")
    R = np.array([o[2] for o in ops])
    big = R.max()
    print(f"ex-top-1: totR {R.sum()-big:.1f} over {len(R)-1} ops")


CFGS = [
    ("champion geo1.7", dict(sizing="proggeo", unit="base", mult=0.01, prog_step=1.7)),
    ("pinsma f7/s200",  dict(sizing="pinlast", slowP=200)),
    ("pinsma f5/s200",  dict(sizing="pinlast", slowP=200, smaP=5)),
    ("pinsma f10/s200", dict(sizing="pinlast", slowP=200, smaP=10)),
    ("geofloor s200 g1.7", dict(sizing="geofloor", slowP=200, unit="base",
                                mult=0.01, prog_step=1.7)),
    ("pin1R gb0.5",     dict(sizing="pin1R", gb=0.5)),
]


def main(sym="XAU", tf="M15"):
    print(HDR)
    for lbl, kw in CFGS:
        kw = dict(sym=sym, tf=tf, triggers=("bounce",), smaP=kw.pop("smaP", 7), **kw)
        for lev in (400.0, 1000.0, 2000.0, 0.0):
            seg_row(lbl, lev, run_tf(**kw, lev=lev))
        print()

    for lev in (2000.0, 0.0):
        lv = "unlimited" if lev == 0 else f"1:{lev:.0f}"
        dissect(f"pinsma f7/s200 @ {lv}",
                run_tf(sym, tf=tf, triggers=("bounce",), smaP=7,
                       sizing="pinlast", slowP=200, lev=lev))
        dissect(f"geofloor s200 g1.7 @ {lv}",
                run_tf(sym, tf=tf, triggers=("bounce",), smaP=7, sizing="geofloor",
                       slowP=200, unit="base", mult=0.01, prog_step=1.7, lev=lev))


if __name__ == "__main__":
    main()
