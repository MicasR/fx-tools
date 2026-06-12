"""
btc_explore.py — BTC swords: TRAIL vs TP, M15 vs H1 (2026-06-12).
Thesis: BTC trends longer -> a trailing exit should RIDE the fat tail that TP3R
clips, transforming BTC's weak M15 stacking.  Stress @ $18 (tr=0.01).
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]


def stream(cfg, tf="M15"):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=tf, **cfg, max_conc=1, conc_dir="same")
    out = []
    for o in res:
        g = op_gap(o, H, L, TR) if o[2] > 0 else None
        R = -1.0 if (o[2] > 0 and g is not None and g < THR) else o[2]
        out.append((tm[o[0]], tm[o[1]], R, None))
    return out, tm[0], tm[-1]


def growth(s, b):
    cur = [(f, *geo_sim([(s, 1.0)], f)) for f in FG]
    r = at_dd(cur, b); return r[0] if r else 0.0


def report(label, cfg, tf="M15"):
    s, t0, t1 = stream(cfg, tf)
    st = stats([(s, 1.0)], 0.0, t0, t1)
    segs = " ".join(f"{x:+6.1f}" for x in st["seg"])
    print(f"{label:<26}{st['n']:>5}{st['tot']:>8.1f}{st['win']:>6.1f}{st['dd']:>7.1f}{st['rf']:>6.1f}"
          f"  {st['rob']}/6{growth(s,24):>7.1f}x{growth(s,30):>8.1f}x  {segs}")


PG = lambda **k: dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, **k)
GF = lambda **k: dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, **k)

if __name__ == "__main__":
    HDR = f"{'BTC sword':<26}{'ops':>5}{'totR':>8}{'win%':>6}{'maxDD':>7}{'RF':>6}  segs{'g@24':>7}{'g@30':>9}   per-seg R"
    print("=== M15 ===\n" + HDR)
    report("pg TP3 (v0)",       PG(tp_R=3.0))
    report("pg trail2.5",       PG(tp_R=0.0, trail_R=2.5))
    report("pg trail2.0",       PG(tp_R=0.0, trail_R=2.0))
    report("pg trail3.0",       PG(tp_R=0.0, trail_R=3.0))
    report("gf trail2.5",       GF(tp_R=0.0, trail_R=2.5))
    report("simple trail2.5",   dict(stack=False, tp_R=0.0, trail_R=2.5))
    report("shield TP2.0",      dict(stack=False, tp_R=2.0))
    print("\n=== H1 ===\n" + HDR)
    report("pg TP3 (v0)",       PG(tp_R=3.0), tf="H1")
    report("pg trail2.5",       PG(tp_R=0.0, trail_R=2.5), tf="H1")
    report("gf trail2.5",       GF(tp_R=0.0, trail_R=2.5), tf="H1")
    report("simple trail2.5",   dict(stack=False, tp_R=0.0, trail_R=2.5), tf="H1")
    report("shield TP2.0",      dict(stack=False, tp_R=2.0), tf="H1")
