"""
fast_sweep.py — fast-SMA sweep (6/7/10/15) on the leading candidate:
geofloor s200 TP3 @1:2000, gold M15.  Each config shown HEADS (as recorded)
and TAILS (top op forced to -1R — the coin-flip discipline from the February
monster).  Champion benchmark row included per standing rule.
"""
import numpy as np
from pyramid_engine import run_tf

HDR = (f"{'variant':<26}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def row(lbl, ops, n, flip_top=False):
    ops = [list(o) for o in ops]
    if flip_top:
        top = max(ops, key=lambda o: o[2])
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
    print(f"{lbl:<26}{len(R):>5}{tot:>9.1f}{R.mean():>7.2f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6{oneop:>5.0f}%  {segs}")


if __name__ == "__main__":
    champ = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7,
                   sizing="proggeo", unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    print(HDR)
    row("champion geo1.7 (f7)", champ[0], champ[3])
    print()
    for fast in (6, 7, 10, 15):
        geo = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=fast,
                     sizing="geofloor", slowP=200, unit="base", mult=0.01,
                     prog_step=1.7, lev=2000.0)
        row(f"geofloor f{fast}/s200", geo[0], geo[3])
        row(f"geofloor f{fast}/s200 TAILS", geo[0], geo[3], flip_top=True)
        print()
