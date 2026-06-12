"""
btc_knobs.py — two untested BTC king knobs (2026-06-12).
(A) STACKING GATE `half`: stacking only arms after price moves half*R in favor
    (default 0.5).  BTC trends long -> arming earlier (more adds, ride more) or
    later (only confirmed trends) could change the monster.  Sweep on BOTH swords.
(B) SHIELD TP: fixed at gold's 2.0; BTC's vol regime may want a different tight TP.
Stress @ $18; king metric = blend growth @24%DD.  King to beat = 34.8x; gold 38.9x.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
GFb = dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)
PGb = dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True)


def build(c):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]


def best_blend(GF, PG, SH):
    best = (0.0, 0, 0)
    for g in (0.55, 0.60, 0.637, 0.70):
        for sh in (0.10, 0.125, 0.15, 0.20):
            sw = 1 - sh
            r = at_dd([(f, *geo_sim([(GF, g*sw), (PG, (1-g)*sw), (SH, sh)], f, THR)) for f in FG], 24.0)
            if r and r[0] > best[0]:
                best = (r[0], g, sh)
    return best


SH20 = build(dict(stack=False, tp_R=2.0))

if __name__ == "__main__":
    print("=== (A) STACKING GATE `half` sweep (both swords; shield TP2.0) ===")
    print("    (incumbent half=0.5 -> 34.8x;  gold 38.9x)\n")
    print(f"{'half':>6}{'blend@24':>10}    gf     pg   shield")
    for h in (0.0, 0.25, 0.5, 0.75, 1.0):
        GF = build({**GFb, "half": h}); PG = build({**PGb, "half": h})
        gr, g, sh = best_blend(GF, PG, SH20); sw = 1-sh
        print(f"{h:>6.2f}{gr:>9.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")

    print("\n=== (B) SHIELD TP sweep (incumbent swords, half=0.5) ===\n")
    GF = build(GFb); PG = build(PGb)
    print(f"{'shTP':>6}{'blend@24':>10}    gf     pg   shield")
    for tp in (1.5, 1.75, 2.0, 2.5, 3.0):
        SH = build(dict(stack=False, tp_R=tp))
        gr, g, sh = best_blend(GF, PG, SH); sw = 1-sh
        print(f"{tp:>6.2f}{gr:>9.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")
