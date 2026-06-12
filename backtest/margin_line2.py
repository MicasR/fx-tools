"""
margin_line2.py — interrogate the pinsma s200 spike (GOLD M15).
(a) smoothness sweep around slow=200; (b) dissect the monster op; (c) geofloor
    (max of geo lot and pin-to-slow lot) as one more challenger.
"""
import numpy as np
from pyramid_engine import run_tf
from margin_line import HDR, row


def main(sym="XAU", tf="M15"):
    print(f"\n=== A. slow-period ridge around 200 ==="); print(HDR)
    for fast in (5, 7, 10):
        for slow in (150, 200, 250, 300, 400, 600):
            row(f"pinsma f{fast}/s{slow}",
                run_tf(sym, tf=tf, triggers=("bounce",), smaP=fast,
                       sizing="pinlast", slowP=slow))

    print(f"\n=== B. f7/s200 op breakdown (top 10 by R) ===")
    ops, curve, pm, n = run_tf(sym, tf=tf, triggers=("bounce",), smaP=7,
                               sizing="pinlast", slowP=200)
    srt = sorted(ops, key=lambda o: -o[2])[:10]
    print(f"{'k0':>8}{'kEnd':>8}{'R':>9}{'nPos':>6}  exit   (bars are M15 indices of {n})")
    for o in srt:
        print(f"{o[0]:>8}{o[1]:>8}{o[2]:>9.1f}{o[3]:>6}  {o[4]}")
    R = np.array([o[2] for o in ops])
    big = srt[0][2]
    print(f"ex-top-1: totR {R.sum()-big:.1f} over {len(R)-1} ops "
          f"(champion ex-top-1 ~137R)")

    print(f"\n=== C. geofloor: lot = max(geo x1.7, pin-to-slow) ==="); print(HDR)
    for slow in (100, 200, 400):
        row(f"geofloor s{slow} g1.7",
            run_tf(sym, tf=tf, triggers=("bounce",), smaP=7, sizing="geofloor",
                   slowP=slow, unit="base", mult=0.01, prog_step=1.7))


if __name__ == "__main__":
    main()
