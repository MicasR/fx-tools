"""
margin_line.py — "where to put the margin line" study (GOLD, M15).

Premise (user): the add lot and the resulting liquidation line are the SAME
degree of freedom.  Instead of picking the lot (min-lot / geo families), pick
the LINE and back out the lot — deliberately high lots.  Judged PURELY on the
Main account: totR / avgR / win% / PF / RF / 6-seg robustness.  mtmDD is NOT a
criterion (ops-account loss is capped at -1R by the 2-account technique).

Strategies vs the 178R champion (SMA7 bounce, 1%-base geo x1.7):
  1. pinsma  — dual SMA: fast SMA(7) bounce says WHEN to add, a slow SMA says
               WHERE the line goes (sizing='pinlast' + slowP).  Sweep both.
  2. geopin  — champion's geo ramp, but each add capped so the line never
               crosses the slow SMA -> push the ratio past the g1.9 cliff.
  3. pinfrac — pin the line a fraction of the gap (current line -> price).
  4. pinlast / pin1R — the old detonators, re-judged on Main metrics only.

Run:  python margin_line.py
"""
import numpy as np
from pyramid_engine import run_tf

HDR = (f"{'variant':<36}{'ops':>5}{'totR':>8}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>6}{'segs':>6}{'topsg':>7}{'1op':>6}{'avgP':>6}{'mxP':>5}{'minR':>7}")


def row(lbl, res):
    ops, curve, pm, n = res
    if not ops:
        print(f"{lbl:<36}{'-':>5}")
        return
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
    topsg = max(seg) / tot * 100 if tot > 0 else 0
    oneop = R.max() / tot * 100 if tot > 0 else 0
    npos = [o[3] for o in ops]
    print(f"{lbl:<36}{len(R):>5}{tot:>8.1f}{R.mean():>7.2f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>6.1f}   {rob}/6{topsg:>6.0f}%{oneop:>5.0f}%"
          f"{np.mean(npos):>6.1f}{max(npos):>5}{R.min():>7.2f}")


def main(sym="XAU", tf="M15"):
    base = dict(sym=sym, tf=tf, triggers=("bounce",), smaP=7)

    print(f"\n=== 0. benchmark ({sym} {tf}) ==="); print(HDR)
    row("champion geo1.7 (178R bench)",
        run_tf(**base, sizing="proggeo", unit="base", mult=0.01, prog_step=1.7))
    row("no-add base",
        run_tf(sym, tf=tf, triggers=(), sizing="minlot", mult=0.0))

    print(f"\n=== 1. old pin modes, Main-metrics re-judge ==="); print(HDR)
    row("pinlast (bounce low)", run_tf(**base, sizing="pinlast"))
    for gb in (0.5, 1.0, 1.5, 2.0, 2.5):
        row(f"pin1R gb{gb}", run_tf(**base, sizing="pin1R", gb=gb))

    print(f"\n=== 2. dual-SMA pin: fast=WHEN, slow=WHERE ==="); print(HDR)
    for fast in (5, 7, 10):
        for slow in (20, 50, 100, 200):
            row(f"pinsma f{fast}/s{slow}",
                run_tf(**{**base, "smaP": fast}, sizing="pinlast", slowP=slow))

    print(f"\n=== 3. geopin: geo ramp capped at the slow-SMA line ==="); print(HDR)
    for slow in (50, 100, 200):
        for g in (1.7, 1.9, 2.1, 2.4, 3.0):
            row(f"geopin s{slow} g{g}",
                run_tf(**base, sizing="geopin", slowP=slow,
                       unit="base", mult=0.01, prog_step=g))

    print(f"\n=== 4. pinfrac: line moves frac of (line->price) gap ==="); print(HDR)
    for fr in (0.1, 0.25, 0.5, 0.75, 1.0):
        row(f"pinfrac {fr}", run_tf(**base, sizing="pinfrac", gb=fr))


if __name__ == "__main__":
    main()
