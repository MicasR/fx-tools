"""
shield_combo.py — shield + sword vs the king (2026-06-12).

Does a high-win-rate SHIELD (tight-TP, even across segments) decorrelate from the
sword (s210) better than geo1.7 does -> beat the king COMBO1 on growth-at-DD?
Three families:
  A) REPLACE geo1.7 with a shield:  [shield + s210], 50/50.
  B) ADD a shield to the king:      [geo1.7 + s210 + shield], various weights
     (now the 3rd leg is genuinely uncorrelated, unlike the s200 3-way).
Geometric scale-to-DD machinery, stressed @ $0.40 (shield ops carry no margin
hairline so they never flip).
"""
from concurrent_geo import geo_sim, at_dd, FGRID
from concurrent_ops import stream, CFG
from shield import run_shield

SHIELDS = {"TP1.5": dict(tp_R=1.5), "TP2.0": dict(tp_R=2.0), "TP2.5": dict(tp_R=2.5)}


def sh_stream(kw):
    ops, _, _ = run_shield(**kw)
    return [(t0, t1, R, None) for t0, t1, R in ops]


if __name__ == "__main__":
    G = stream("geo1.7", 0.005)[0]
    S210 = stream("f5/s210 1.5%", 0.005)[0]
    SH = {nm: sh_stream(kw) for nm, kw in SHIELDS.items()}
    budgets = (13.0, 18.0, 24.0, 30.0)

    def show(lbl, legs):
        curve = [(f, *geo_sim(legs, f)) for f in FGRID]
        cells = ""
        for b in budgets:
            r = at_dd(curve, b)
            cells += (f"{r[0]:>11.1f}x @{r[1]*100:>4.2f}%" if r else f"{'--':>20}")
        print(f"{lbl:<30}{cells}")

    print("=== growth x @ matched DD (f%), stressed@$0.40 ===")
    print(f"{'portfolio':<30}" + "".join(f"{f'DD {int(b)}%':>20}" for b in budgets))
    show("KING COMBO1 geo+s210", [(G, 0.5), (S210, 0.5)])
    print("-- A) REPLACE geo1.7 with shield (50/50) --")
    for nm in SHIELDS:
        show(f"{nm} + s210", [(SH[nm], 0.5), (S210, 0.5)])
    print("-- B) ADD shield to the king --")
    for nm in SHIELDS:
        show(f"geo+s210+{nm} (1/3)", [(G, 1/3), (S210, 1/3), (SH[nm], 1/3)])
    for nm in SHIELDS:
        show(f"geo.4/s210.4/{nm}.2", [(G, 0.4), (S210, 0.4), (SH[nm], 0.2)])

    print("-- C) shield-sleeve weight sweep (geo=s210=(1-sh)/2) --")
    for nm in ("TP2.0", "TP2.5"):
        for sh in (0.0, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.30):
            half = (1 - sh) / 2
            show(f"{nm} sleeve {int(sh*100)}%", [(G, half), (S210, half), (SH[nm], sh)])
