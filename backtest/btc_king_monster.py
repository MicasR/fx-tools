"""
btc_king_monster.py — tune the gf-trail MONSTER, then re-blend (2026-06-12).
King v2 = 34.8x @24%DD, ~10% short of gold's 38.9x.  The monster carries ~64% of
the weight, so its ramp/trail is the highest-leverage remaining knob.  v2 uses
prog_step=1.2, trail_R=2.5 (gold's monster ramped harder at g1.7).  Sweep the
monster solo g@24, then blend the best with the fixed pg-TP3 + shield trio.
Stress @ $18.
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
    cur = [(f, *geo_sim(legs, f, THR)) for f in FG]
    r = at_dd(cur, 24.0); return r[0] if r else 0.0


PGTP3 = build(dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True))
SHIELD = build(dict(stack=False, tp_R=2.0))


def best_blend(MON):
    best = (0.0, 0, 0)
    for g in (0.55, 0.60, 0.637, 0.65, 0.70, 0.75):
        for sh in (0.10, 0.125, 0.15, 0.175, 0.20):
            sw = 1 - sh
            legs = [(MON, g*sw), (PGTP3, (1-g)*sw), (SHIELD, sh)]
            r = at_dd([(f, *geo_sim(legs, f, THR)) for f in FG], 24.0)
            if r and r[0] > best[0]:
                best = (r[0], g, sh)
    return best


if __name__ == "__main__":
    print(f"=== BTC {TF} — tune gf-trail monster, then re-blend (growth @24%DD, stress@${THR:.0f}) ===")
    print("    (gold king = 38.9x;  king v2 monster ps1.2/tr2.5 = 34.8x)\n")
    print(f"{'monster (ps/trail)':<20}{'solo@24':>9}{'blend@24':>10}    gf     pg   shield")
    rows = []
    for ps in (1.2, 1.5, 1.7, 2.0):
        for tr in (2.0, 2.5, 3.0):
            MON = build(dict(smaP=15, slowP=210, sizing="geofloor", unit="base",
                             mult=0.015, prog_step=ps, tp_R=0.0, trail_R=tr, stack=True))
            solo = g24([(MON, 1.0)])
            bl, g, sh = best_blend(MON)
            rows.append((bl, f"ps{ps}/tr{tr}", solo, g, sh))
    rows.sort(reverse=True)
    for bl, nm, solo, g, sh in rows:
        sw = 1 - sh
        print(f"{nm:<20}{solo:>8.1f}x{bl:>9.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")
