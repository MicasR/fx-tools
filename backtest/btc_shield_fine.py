"""
btc_shield_fine.py — confirm/refine the TIGHTER-SHIELD lead (2026-06-12).
btc_knobs found shield TP1.5 -> 37.4x @24%DD (vs TP2.0 34.8x), but on a coarse 4x4
weight grid + a non-monotonic TP curve -> verify it's not a grid artifact.  Build
shields TP {1.0,1.25,1.5,2.0}, FINE weight sweep, full DD curve, and AUDIT the
winner (6 segs, 1-op, stress-sensitivity).  Tighter shield = higher win = smoother
= better DD-smoothing (the shield's only job).  King to beat = 34.8x; gold 38.9x.
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]


def build(c):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res], tm[0], tm[-1]


GF, t0, t1 = build(dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True))
PG, _, _ = build(dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True))


def grow(SH, g, sh, b=24.0, thr=THR):
    sw = 1 - sh
    legs = [(GF, g*sw), (PG, (1-g)*sw), (SH, sh)]
    r = at_dd([(f, *geo_sim(legs, f, thr)) for f in FG], b)
    return r[0] if r else 0.0


def fine(SH):
    best = (0.0, 0, 0)
    for gi in range(45, 72, 3):
        for shi in range(8, 27, 2):
            g, sh = gi/100, shi/100
            v = grow(SH, g, sh)
            if v > best[0]:
                best = (v, g, sh)
    return best


if __name__ == "__main__":
    print("=== shield TP fine weight sweep (best @24%DD) — king to beat 34.8x, gold 38.9x ===\n")
    print(f"{'shTP':>6}{'win%':>6}{'best@24':>9}    gf     pg   shield")
    SHs = {}
    for tp in (1.0, 1.25, 1.5, 1.75, 2.0):
        SH, _, _ = build(dict(stack=False, tp_R=tp)); SHs[tp] = SH
        st = stats([(SH, 1.0)], THR, t0, t1)
        gr, g, sh = fine(SH); sw = 1-sh
        print(f"{tp:>6.2f}{st['win']:>6.1f}{gr:>8.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")

    # pick best TP, audit
    bestp = max((tp for tp in SHs), key=lambda tp: fine(SHs[tp])[0])
    SH = SHs[bestp]; gr, g, sh = fine(SH); sw = 1-sh
    legs = [(GF, g*sw), (PG, (1-g)*sw), (SH, sh)]
    print(f"\n=== WINNER shield TP{bestp}: gf {g*sw:.3f} / pg {(1-g)*sw:.3f} / shield {sh:.3f} ===")
    print(f"{'':<14}" + "".join(f"{'@'+str(b)+'%':>8}" for b in (13, 18, 24, 30)))
    print(f"{'BTC king':<14}" + "".join(f"{grow(SH,g,sh,b):>7.1f}x" for b in (13.0,18.0,24.0,30.0)))
    print(f"{'gold king':<14}{7.7:>7.1f}x{16.1:>7.1f}x{38.9:>7.1f}x{85.4:>7.1f}x")
    st = stats([legs[0], legs[1], legs[2]], THR, t0, t1)
    print(f"\nblend stress@$18: totR {st['tot']:.0f}  win {st['win']:.0f}%  maxDD {st['dd']:.1f}  RF {st['rf']:.1f}  {st['rob']}/6  1op {st['oneop']:.0f}%")
    print("per-seg: " + " ".join(f"{x:+.0f}" for x in st["seg"]))
    print("stress-sensitivity g@24:  " + "  ".join(f"${t}:{grow(SH,g,sh,24.0,float(t)):.1f}x" for t in (18,40,60,90)))
