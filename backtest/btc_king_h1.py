"""
btc_king_h1.py — joint weight sweep for the BTC H1 KING (2026-06-12).
Goal: push BTC past gold's crowned 38.9x (growth @24%DD, consistent engine).

Trio mirrors the gold king's decorrelation axis (geofloor vs proggeo sizing),
but BTC-period (SMA15, g1.2) and TRAILING (H1 trends -> ride the fat tail that
TP3R clips):
  gf  = MONSTER sword: geofloor slow210, trail2.5 -> 241R, RF15.6, 18.5x@24% (5/6,
        but LUMPY/late-weighted, seg4 thin -0.6)
  pg  = decorrelated partner: proggeo, trail2.5 -> 104R, RF7.4, 5.7x, EVEN 6/6
        (seg4 +4.8 fills gf's seg4 hole)
  sh  = shield TP2.0: 41.7% win, 6/6 universal smoother

Two free ratios:  gf = g*(1-sh),  pg = (1-g)*(1-sh),  shield = sh.
Stress @ $18 (op_gap tr=0.01 -> liquidation line; geo_sim thr=18 stresses).
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; THR = 18.0
TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]

PG = dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)
GF = dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)
SH = dict(stack=False, tp_R=2.0)
CFG = {"gf": GF, "pg": PG, "shield": SH}

S = {}
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, **c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res]


def grow(g, sh, b=24.0):
    sw = 1 - sh
    legs = [(S["gf"], g*sw), (S["pg"], (1-g)*sw), (S["shield"], sh)]
    cur = [(f, *geo_sim(legs, f, THR)) for f in FG]
    r = at_dd(cur, b)
    return r[0] if r else 0.0


if __name__ == "__main__":
    res = []
    for g in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.875, 1.0):
        for sh in (0.0, 0.075, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30):
            res.append((grow(g, sh), g, sh))
    res.sort(reverse=True)

    print(f"=== BTC {TF} KING — joint weight sweep, growth @24%DD, stress@${THR:.0f} ===")
    print("    (gold king to beat = 38.9x)\n")
    print(f"{'rank':>4}{'@24%':>9}    gf     pg   shield")
    for i, (gr, g, sh) in enumerate(res[:15]):
        sw = 1 - sh
        print(f"{i+1:>4}{gr:>8.1f}x   {g*sw:>5.3f}  {(1-g)*sw:>5.3f}  {sh:>5.3f}")

    best = res[0]
    print("\n=== best blend vs pure gf-monster vs gold king (full DD curve) ===")
    print(f"{'config':<30}{'@13%':>8}{'@18%':>8}{'@24%':>8}{'@30%':>8}")
    for lbl, (g, sh) in [(f"BEST gf{best[1]}/sh{best[2]}", best[1:]),
                         ("pure gf monster (1.0/0)", (1.0, 0.0)),
                         ("even gf.5/pg.5 no shield", (0.5, 0.0))]:
        cells = "".join(f"{grow(g, sh, b):>7.1f}x" for b in (13.0, 18.0, 24.0, 30.0))
        print(f"{lbl:<30}{cells}")
