"""
cross_kings.py — GOLD king + BTC king concurrently, 1R each (2026-06-13).
The cross-instrument prize: gold (M15, profit FRONT-loaded seg2-3) and BTC (H1,
profit BACK-loaded seg5-6) peak in opposite halves of the same 2024-02..2026-06
window -> blending the two kings should smooth the whole curve and out-grow either
alone at a matched DD budget.

Each king = its own 3-leg blend summing to 1.0 ("1R"); stress baked per-instrument
($0.40/tr1.0 gold, $18/tr0.01 BTC), gaps then None so geo_sim merges by TIME without
re-stressing.  BOTH = all 6 legs (gold group sum 1.0 + BTC group sum 1.0 = 1R each).
Size the risk fraction f to a DD budget; compare terminal growth.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats
from pyramid_engine import SPECS

FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]


def strm(sym, tf, thr, tr, **cfg):
    res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    out = []
    for o in res:
        g = op_gap(o, H, L, tr) if o[2] > 0 else None
        R = -1.0 if (o[2] > 0 and g is not None and g < thr) else o[2]
        out.append((tm[o[0]], tm[o[1]], R, None))   # gap=None -> no re-stress in geo_sim/stats
    return out


# ---- GOLD king (M15, stress $0.40) : geo1.7 .50 / s210 .375 / shield-TP2.0 .125 ----
GOLD = [
    (strm("XAU", "M15", 0.40, 1.0, smaP=7, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True), 0.500),
    (strm("XAU", "M15", 0.40, 1.0, smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True), 0.375),
    (strm("XAU", "M15", 0.40, 1.0, stack=False, tp_R=2.0), 0.125),
]
# ---- BTC king v3 (H1, stress $18) : gf .552 / pg-TP3 .248 / shield-TP1.25 .200 ----
BTC = [
    (strm("BTC", "H1", 18.0, 0.01, smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True), 0.552),
    (strm("BTC", "H1", 18.0, 0.01, smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True), 0.248),
    (strm("BTC", "H1", 18.0, 0.01, stack=False, tp_R=1.25), 0.200),
]
BOTH = GOLD + BTC

ALL = [s for s, _ in BOTH]
T0 = min(min(t for t, *_ in s) for s in ALL)
T1 = max(max(c for _, c, *_ in s) for s in ALL)


def at(legs, b):
    r = at_dd([(f, *geo_sim(legs, f, 0.0)) for f in FG], b)
    return r


if __name__ == "__main__":
    print("=== GOLD king + BTC king, 1R each — growth at MATCHED DD budget ===")
    print("    (each king's 3 legs sum to 1.0; BOTH = 6 legs, 1R per king; stress baked per-instrument)\n")
    print(f"{'DD budget':>10}{'GOLD alone':>16}{'BTC alone':>16}{'BOTH (1R+1R)':>18}{'  uplift vs best-alone':>0}")
    for b in (13.0, 18.0, 24.0, 30.0):
        g, c, both = at(GOLD, b), at(BTC, b), at(BOTH, b)
        best = max(g[0], c[0])
        up = (both[0] / best - 1) * 100
        print(f"{b:>9.0f}%{g[0]:>13.1f}x  {c[0]:>13.1f}x  {both[0]:>13.1f}x @f{both[1]*100:>4.2f}%   {up:>+6.1f}%")

    print("\n=== combined R-stream fingerprint (1R each, stress baked, by time) ===")
    for nm, legs in (("GOLD alone", GOLD), ("BTC alone", BTC), ("BOTH 1R+1R", BOTH)):
        st = stats(legs, 0.0, T0, T1)
        segs = " ".join(f"{x:+6.1f}" for x in st["seg"])
        print(f"{nm:<12} totR{st['tot']:>7.1f}  win{st['win']:>5.1f}%  maxDD{st['dd']:>6.1f}  RF{st['rf']:>6.1f}  {st['rob']}/6"
              f"  1op{st['oneop']:>4.0f}%   {segs}")
