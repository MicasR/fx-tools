"""
tp_sweep.py — TP 1.5R..3R on the session's most interesting config:
pinsma f7/s200 (dual-SMA pick-the-line) + geofloor s200, gold M15, lev 1:2000.
Hypothesis: the tight line clips winners before TP3R (win% 35.6 -> 23.7);
a smaller TP banks them first -> more consistency, less lottery.
"""
import numpy as np
from pyramid_engine import run_tf

HDR = (f"{'variant':<22}{'TP':>5}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}{'exTop1':>8}   per-segment R")


def row(lbl, tp, res):
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
    print(f"{lbl:<22}{tp:>5.2f}{len(R):>5}{tot:>9.1f}{R.mean():>7.2f}"
          f"{100*np.mean(R>0):>6.1f}{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6"
          f"{oneop:>5.0f}%{tot-R.max():>8.1f}  {segs}")


if __name__ == "__main__":
    TPS = (1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0)
    print(HDR)
    for tp in TPS:
        row("pinsma f7/s200", tp,
            run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7,
                   sizing="pinlast", slowP=200, lev=2000.0, tp_R=tp))
    print()
    for tp in TPS:
        row("geofloor s200 g1.7", tp,
            run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7,
                   sizing="geofloor", slowP=200, unit="base", mult=0.01,
                   prog_step=1.7, lev=2000.0, tp_R=tp))
