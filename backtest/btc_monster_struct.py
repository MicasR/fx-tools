"""
btc_monster_struct.py — sweep the gf-trail MONSTER's STRUCTURAL params (2026-06-12).
The monster carries ~64% of the king's weight, yet its bounce period (smaP) and
geofloor anchor (slowP) were only roughly set to 15/210 BEFORE the H1+trail thesis.
Sweep smaP x slowP solo g@24 on H1; reblend the best with the fixed pg-TP3 + shield.
Also probe mult (geo start size).  King to beat = 34.8x;  gold = 38.9x.  Stress @ $18.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]


def build(c):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]


def g24(legs):
    r = at_dd([(f, *geo_sim(legs, f, THR)) for f in FG], 24.0); return r[0] if r else 0.0


PGTP3 = build(dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True))
SHIELD = build(dict(stack=False, tp_R=2.0))


def blend(MON):
    best = (0.0, 0, 0)
    for g in (0.55, 0.60, 0.637, 0.70, 0.75):
        for sh in (0.10, 0.125, 0.15, 0.20):
            sw = 1 - sh
            r = at_dd([(f, *geo_sim([(MON, g*sw), (PGTP3, (1-g)*sw), (SHIELD, sh)], f, THR)) for f in FG], 24.0)
            if r and r[0] > best[0]:
                best = (r[0], g, sh)
    return best


def mon(smaP, slowP, mult=0.015):
    return build(dict(smaP=smaP, slowP=slowP, sizing="geofloor", unit="base",
                      mult=mult, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True))


if __name__ == "__main__":
    print("=== BTC H1 monster structural sweep — smaP x slowP (solo g@24 / blend@24) ===")
    print("    (current monster smaP15/s210 = 18.5x solo, 34.8x blend;  gold king = 38.9x)\n")
    print(f"{'smaP':>5}{'slowP':>7}{'solo@24':>9}{'blend@24':>10}    gf     pg   shield")
    rows = []
    for smaP in (8, 10, 12, 15, 18, 22):
        for slowP in (120, 180, 210, 280, 360):
            MON = mon(smaP, slowP)
            solo = g24([(MON, 1.0)])
            bl, g, sh = blend(MON)
            rows.append((bl, smaP, slowP, solo, g, sh))
    rows.sort(reverse=True)
    for bl, smaP, slowP, solo, g, sh in rows[:14]:
        sw = 1 - sh
        print(f"{smaP:>5}{slowP:>7}{solo:>8.1f}x{bl:>9.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")
