"""
concurrent_3way.py — 3-way blend vs the best 2-way (2026-06-12).

Add s200 as a third 0.5R-style account: geo1.7 + s210 + s200, equal thirds.
But s200 and s210 are near-siblings (both geofloor f5, both driven by the same
verified March op) -> likely correlated, little extra diversification over
COMBO1.  Test growth-at-matched-DD vs COMBO1 (50/50) and the standalones.
Geometric scale-to-DD machinery, stressed @ $0.40.
"""
from concurrent_geo import geo_sim, at_dd, FGRID
from concurrent_ops import stream, CFG

if __name__ == "__main__":
    S = {nm: stream(nm, 0.005)[0] for nm in CFG}
    t = 1.0 / 3.0
    blends = {
        "COMBO1 geo+s210 (50/50)":     [(S["geo1.7"], 0.5), (S["f5/s210 1.5%"], 0.5)],
        "3WAY geo+s210+s200 (1/3)":    [(S["geo1.7"], t), (S["f5/s210 1.5%"], t), (S["f5/s200"], t)],
        "3WAY geo50/s210 25/s200 25":  [(S["geo1.7"], 0.5), (S["f5/s210 1.5%"], 0.25), (S["f5/s200"], 0.25)],
    }
    budgets = (13.0, 18.0, 24.0, 30.0)
    print(f"=== 3-way vs 2-way: growth x @ matched DD (f%), stressed@$0.40 ===")
    print(f"{'blend':<30}" + "".join(f"{f'DD {int(b)}%':>20}" for b in budgets))
    for lbl, legs in blends.items():
        curve = [(f, *geo_sim(legs, f)) for f in FGRID]
        cells = ""
        for b in budgets:
            r = at_dd(curve, b)
            cells += (f"{r[0]:>11.1f}x @{r[1]*100:>4.2f}%" if r else f"{'--':>20}")
        print(f"{lbl:<30}{cells}")
