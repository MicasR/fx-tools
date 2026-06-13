"""
cross_weights.py — sweep the GOLD:BTC split of the cross-instrument portfolio (2026-06-13).
Baseline = 1R each (g=0.5).  Tilt the budget between the two kings: gold legs scaled
by 2g, BTC legs by 2(1-g) (so g=0.5 -> both x1.0 = the exact 1R+1R baseline; g=1 pure
gold, g=0 pure BTC).  Each king's INTERNAL 3-leg weights stay fixed.  Growth at matched
DD budget; find the optimum vs the 50/50 baseline.  Streams reused from cross_kings
(stress baked per-instrument, merged by time).
"""
from cross_kings import GOLD, BTC, FG
from concurrent_geo import geo_sim, at_dd


def legs(g):
    return [(s, w * 2 * g) for s, w in GOLD] + [(s, w * 2 * (1 - g)) for s, w in BTC]


def at(g, b):
    r = at_dd([(f, *geo_sim(legs(g), f, 0.0)) for f in FG], b)
    return r[0] if r else 0.0


if __name__ == "__main__":
    print("=== GOLD:BTC split sweep — growth at matched DD budget (g = gold share) ===")
    print("    g=0.5 = 1R each (baseline);  g=1.0 pure gold;  g=0.0 pure BTC\n")
    print(f"{'gold%':>6}{'btc%':>6}{'@13%':>9}{'@18%':>9}{'@24%':>9}{'@30%':>9}")
    grid = [0.0, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 1.0]
    rows = []
    for g in grid:
        cells = {b: at(g, b) for b in (13.0, 18.0, 24.0, 30.0)}
        rows.append((g, cells))
        mark = "  <- 1R each" if abs(g - 0.5) < 1e-9 else ""
        print(f"{g*100:>5.0f}%{(1-g)*100:>5.0f}%{cells[13.0]:>8.1f}x{cells[18.0]:>8.1f}x"
              f"{cells[24.0]:>8.1f}x{cells[30.0]:>8.1f}x{mark}")

    print("\n=== optimum per DD budget vs the 1R-each (g=0.5) baseline ===")
    base = {b: at(0.5, b) for b in (13.0, 18.0, 24.0, 30.0)}
    print(f"{'budget':>8}{'best split':>14}{'best growth':>13}{'baseline':>11}{'uplift':>9}")
    for b in (13.0, 18.0, 24.0, 30.0):
        bg, bv = max(((g, c[b]) for g, c in rows), key=lambda x: x[1])
        up = (bv / base[b] - 1) * 100
        print(f"{b:>7.0f}%{f'{bg*100:.0f}/{(1-bg)*100:.0f}':>14}{bv:>11.1f}x{base[b]:>10.1f}x{up:>+8.1f}%")
