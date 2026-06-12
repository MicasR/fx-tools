"""
btc_king_4leg.py — can a 4th leg push the BTC H1 king past gold's 38.9x? (2026-06-12)
King v2 = gf-monster + pg-TP3 (best partner) + shield = 34.8x @24%DD.
Test: add simple-trail (6/6, RF8.5, EVEN +8.2/+29.2/+9.6/+5.4/+41.1/+11.7) as a
2nd decorrelator -- it's no-stack trail vs gf's stacked trail vs pg's stacked TP,
three distinct mechanics.  Also sweep the shield weight finer.
  swords sum to (1-sh):  gf = g*(1-sh),  rest split pg:simple by q.
Stress @ $18.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]

CFG = {
    "gf":     dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True),
    "pgTP3":  dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True),
    "simple": dict(stack=False, tp_R=0.0, trail_R=2.5),
    "shield": dict(stack=False, tp_R=2.0),
}
S = {}
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]


def grow(g, q, sh, b=24.0):
    sw = 1 - sh
    rest = (1 - g) * sw
    legs = [(S["gf"], g*sw), (S["pgTP3"], rest*q), (S["shield"], sh)]
    if q < 1.0:
        legs.append((S["simple"], rest*(1-q)))
    cur = [(f, *geo_sim(legs, f, THR)) for f in FG]
    r = at_dd(cur, b)
    return r[0] if r else 0.0


if __name__ == "__main__":
    res = []
    for g in (0.55, 0.60, 0.637, 0.65, 0.70):
        for q in (1.0, 0.75, 0.6, 0.5, 0.4, 0.25):   # q=1 -> no simple (3-leg)
            for sh in (0.10, 0.125, 0.15, 0.175, 0.20):
                res.append((grow(g, q, sh), g, q, sh))
    res.sort(reverse=True)

    print(f"=== BTC {TF} KING — 4-leg (gf/pgTP3/simple/shield), growth @24%DD, stress@${THR:.0f} ===")
    print("    (gold king = 38.9x;  king v2 3-leg pg-TP3 = 34.8x)\n")
    print(f"{'rank':>4}{'@24%':>9}     gf   pgTP3  simple shield")
    for i, (gr, g, q, sh) in enumerate(res[:15]):
        sw = 1 - sh; rest = (1-g)*sw
        print(f"{i+1:>4}{gr:>8.1f}x   {g*sw:>6.3f}{rest*q:>7.3f}{rest*(1-q):>7.3f}{sh:>7.3f}")

    best = res[0]
    best3 = max((r for r in res if r[2] == 1.0), key=lambda r: r[0])
    print("\n=== best 4-leg vs best 3-leg (full DD curve) ===")
    print(f"{'config':<34}{'@13%':>8}{'@18%':>8}{'@24%':>8}{'@30%':>8}")
    for lbl, (g, q, sh) in [(f"BEST 4-leg g{best[1]}/q{best[2]}/sh{best[3]}", best[1:]),
                            (f"BEST 3-leg g{best3[1]}/sh{best3[3]}", best3[1:])]:
        cells = "".join(f"{grow(g, q, sh, b):>7.1f}x" for b in (13.0, 18.0, 24.0, 30.0))
        print(f"{lbl:<34}{cells}")
