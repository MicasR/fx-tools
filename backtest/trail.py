"""
trail.py — simple trailing-stop component, no gimmicks (2026-06-12).

H1 V-pattern breakout, structural 1R initial stop, then a chandelier trail at
gb_R behind the running extreme (max(structural, ext - gb*R)).  No TP, no
break-even, no stacking.  Sweep the give-back; compare head-to-head with the
fixed-TP shields on the same single-position engine.  Net of spread, segments.
"""
from shield import run_shield, stats

CANDS = [
    ("trail 1.5R",  dict(tp_R=0, trail_act=0.01, gb_R=1.5)),
    ("trail 2.0R",  dict(tp_R=0, trail_act=0.01, gb_R=2.0)),
    ("trail 2.5R",  dict(tp_R=0, trail_act=0.01, gb_R=2.5)),
    ("trail 3.0R",  dict(tp_R=0, trail_act=0.01, gb_R=3.0)),
    ("trail 3.5R",  dict(tp_R=0, trail_act=0.01, gb_R=3.5)),
    ("-- TP refs --", None),
    ("TP2.0 (shield)", dict(tp_R=2.0)),
    ("TP3.0",          dict(tp_R=3.0)),
]

if __name__ == "__main__":
    print(f"=== simple trailing stop vs fixed TP (gold M15, single position, net spread) ===")
    print(f"{'variant':<16}{'ops':>5}{'totR':>8}{'avgR':>7}{'win%':>6}{'PF':>6}{'maxDD':>7}"
          f"{'RF':>6}{'segs':>6}   per-segment R")
    for lbl, kw in CANDS:
        if kw is None:
            print(f"{lbl}")
            continue
        ops, t0, t1 = run_shield(**kw)
        s = stats(ops, t0, t1)
        segs = " ".join(f"{x:+6.1f}" for x in s["seg"])
        print(f"{lbl:<16}{s['n']:>5}{s['tot']:>8.1f}{s['avg']:>7.2f}{s['win']:>6.1f}{s['pf']:>6.2f}"
              f"{s['dd']:>7.1f}{s['rf']:>6.1f}   {s['rob']}/6   {segs}")
