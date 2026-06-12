"""
king_weights4.py — joint weight sweep for the 4-leg contender (2026-06-12).
Three free ratios: sword split (geo share), shield weight, g1.2 weight.
  geo = g*(1-sh-pc),  s210 = (1-g)*(1-sh-pc),  shield = sh,  g1.2 = pc.
Growth-at-matched-DD, consistent engine + stress@$0.40.  Finds the global best
vs the current 4-leg (.425/.425/.10/.05) and the 3-leg king (32.0x).
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd

A12 = dict(trig="poscandle", smaP=7, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True)
CFG = {
    "geo1.7": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
    "g1.2":   A12,
}
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]

S = {}
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]


def grow(g, sh, pc, b=24.0):
    sw = 1 - sh - pc
    legs = [(S["geo1.7"], g*sw), (S["s210"], (1-g)*sw), (S["shield"], sh)]
    if pc > 0:
        legs.append((S["g1.2"], pc))
    cur = [(f, *geo_sim(legs, f)) for f in FG]
    r = at_dd(cur, b)
    return r[0] if r else 0.0


if __name__ == "__main__":
    res = []
    for g in (0.50, 0.55, 0.60, 0.65, 0.70):
        for sh in (0.10, 0.125, 0.15, 0.175, 0.20, 0.25):
            for pc in (0.0, 0.04, 0.06, 0.08):
                res.append((grow(g, sh, pc), g, sh, pc))
    res.sort(reverse=True)

    print("=== top 12 by growth @24%DD (g=geo-share of swords) ===")
    print(f"{'rank':>4}{'@24%':>9}   geo1.7  s210  shield  g1.2")
    for i, (gr, g, sh, pc) in enumerate(res[:12]):
        sw = 1 - sh - pc
        print(f"{i+1:>4}{gr:>8.1f}x   {g*sw:>6.3f}{(1-g)*sw:>6.3f}{sh:>8.3f}{pc:>6.3f}")

    best3 = max((r for r in res if r[3] == 0), key=lambda r: r[0])
    best4 = max((r for r in res if r[3] > 0), key=lambda r: r[0])
    print("\n=== best 3-leg vs best 4-leg vs old king (full DD curve) ===")
    print(f"{'config':<34}{'@13%':>8}{'@18%':>8}{'@24%':>8}{'@30%':>8}")
    for lbl, (g, sh, pc) in [("old king .45/.45/.10", (.5, .10, .0)),
                             (f"BEST 3-leg g{best3[1]}/sh{best3[2]}", best3[1:]),
                             (f"BEST 4-leg g{best4[1]}/sh{best4[2]}/pc{best4[3]}", best4[1:])]:
        cells = "".join(f"{grow(g, sh, pc, b):>7.1f}x" for b in (13.0, 18.0, 24.0, 30.0))
        print(f"{lbl:<34}{cells}")
