"""
btc_h4.py — does the BTC trail thesis get STRONGER on H4? (2026-06-12)
Only M15 (meh) and H1 (the monster) were ever tested.  BTC trends LONG -> H4 (even
coarser bars, less whipsaw, longer holds) is the natural next step up.  Run the
king's components + the full blend on H4 vs the H1 baseline.  Stress @ $18.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]

GF = dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)
PG = dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True)
SH = dict(stack=False, tp_R=2.0)
CFG = {"gf": GF, "pgTP3": PG, "shield": SH}


def build(c, tf):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=tf, **c, max_conc=1, conc_dir="same")
    s = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]
    return s, tm[0], tm[-1]


def g24(legs):
    r = at_dd([(f, *geo_sim(legs, f, THR)) for f in FG], 24.0); return r[0] if r else 0.0


def run(tf):
    S = {}; t0 = t1 = None
    for nm, c in CFG.items():
        s, a, b = build(c, tf); S[nm] = s
        t0 = a if t0 is None else min(t0, a); t1 = b if t1 is None else max(t1, b)
    print(f"\n=== BTC {tf} (stress @ $18) ===")
    print(f"{'component':<14}{'ops':>5}{'totR':>8}{'win%':>6}{'maxDD':>7}{'RF':>6}  segs{'g@24':>8}   per-seg R")
    for nm in CFG:
        st = stats([(S[nm], 1.0)], THR, t0, t1)
        segs = " ".join(f"{x:+6.1f}" for x in st["seg"])
        print(f"{nm:<14}{st['n']:>5}{st['tot']:>8.1f}{st['win']:>6.1f}{st['dd']:>7.1f}{st['rf']:>6.1f}"
              f"  {st['rob']}/6{g24([(S[nm],1.0)]):>7.1f}x   {segs}")
    # best blend (reuse the v2 weights neighborhood)
    best = (0, 0, 0)
    for g in (0.50, 0.55, 0.60, 0.637, 0.65, 0.70, 0.75):
        for sh in (0.075, 0.10, 0.125, 0.15, 0.20):
            sw = 1 - sh
            legs = [(S["gf"], g*sw), (S["pgTP3"], (1-g)*sw), (S["shield"], sh)]
            r = at_dd([(f, *geo_sim(legs, f, THR)) for f in FG], 24.0)
            if r and r[0] > best[0]:
                best = (r[0], g, sh)
    gr, g, sh = best; sw = 1-sh
    print(f"{'KING blend':<14}  ->  best @24%DD = {gr:.1f}x   (gf {g*sw:.3f} / pgTP3 {(1-g)*sw:.3f} / shield {sh:.3f})")


if __name__ == "__main__":
    print("BTC king to beat (H1) = 34.8x @24%DD;  gold king = 38.9x")
    run("H1")
    run("H4")
