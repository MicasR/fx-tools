"""
btc_king_partner.py — which PARTNER best decorrelates the gf-trail monster? (2026-06-12)
King v1 (gf/pg-trail/shield) = 31.7x @24%DD, short of gold's 38.9x.  pg-trail may
be too CORRELATED with gf (both trail the same H1 tail).  The monster's holes are
segs 3-4 (gf: +3.3, -0.6) -- a partner that's POSITIVE+steady THERE shrinks the
blend DD and lets f rise.  Candidates:
  pg-tr2.5  proggeo trail2.5  (king v1 partner; seg4 +4.8)
  pg-TP3    proggeo TP3R      (EVEN, seg3+4 = +10.4/+6.2 -> best filler, but seg1 -2.2)
  pg-tr3.0  proggeo trail3.0
  simple    no-stack trail2.5 (RF8.5, 6/6)
For each: joint-sweep (g=gf share of swords, sh=shield) -> best growth @24%DD.
Stress @ $18.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]

GF = dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)
SH = dict(stack=False, tp_R=2.0)
PARTNERS = {
    "pg-tr2.5": dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True),
    "pg-TP3":   dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True),
    "pg-tr3.0": dict(smaP=15, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=0.0, trail_R=3.0, stack=True),
    "simple":   dict(stack=False, tp_R=0.0, trail_R=2.5),
}


def build(c):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]


GFS = build(GF); SHS = build(SH)


def best_blend(PS):
    best = (0.0, 0, 0)
    for g in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        for sh in (0.0, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25):
            sw = 1 - sh
            legs = [(GFS, g*sw), (PS, (1-g)*sw), (SHS, sh)]
            cur = [(f, *geo_sim(legs, f, THR)) for f in FG]
            r = at_dd(cur, 24.0)
            if r and r[0] > best[0]:
                best = (r[0], g, sh)
    return best


if __name__ == "__main__":
    print(f"=== BTC {TF} KING — best partner for the gf-trail monster (growth @24%DD) ===")
    print("    (gold king to beat = 38.9x;  king v1 pg-tr2.5 = 31.7x)\n")
    print(f"{'partner':<12}{'best@24%':>10}    gf     pg   shield")
    rows = []
    for nm, c in PARTNERS.items():
        PS = build(c)
        gr, g, sh = best_blend(PS)
        rows.append((gr, nm, g, sh))
    rows.sort(reverse=True)
    for gr, nm, g, sh in rows:
        sw = 1 - sh
        print(f"{nm:<12}{gr:>9.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")
