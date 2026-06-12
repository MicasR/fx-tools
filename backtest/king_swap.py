"""
king_swap.py — swap the s210 sword for a tamer geo (2026-06-12).

User: replace s210 (DD-expensive, seg3-concentrated) with a more conservative
geo (geo1.6 / geo1.5) -- does the lower DD beat the lost decorrelation?  geo1.7
and geo1.6/1.5 are the SAME M15 SMA7-bounce strategy (only the add-ramp ratio
differs) -> near-siblings, both seg2-loaded.  Growth-at-matched-DD + segments,
consistent engine + stress@$0.40.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats, row, HDR

GEO = lambda g: dict(smaP=7, slowP=0, sizing="proggeo", mult=0.01, prog_step=g, tp_R=3.0, stack=True)
CFG = {
    "geo1.7": GEO(1.7), "geo1.6": GEO(1.6), "geo1.5": GEO(1.5),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
}
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
BUD = (13.0, 18.0, 24.0, 30.0)

S = {}; t0 = t1 = None
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]
    t0 = tm[0] if t0 is None else min(t0, tm[0]); t1 = tm[-1] if t1 is None else max(t1, tm[-1])

VARIANTS = {
    "KING geo1.7+s210":  ["geo1.7", "s210"],
    "geo1.7+geo1.6":     ["geo1.7", "geo1.6"],
    "geo1.7+geo1.5":     ["geo1.7", "geo1.5"],
}

print("=== growth x @ matched DD (consistent engine, stress@$0.40) ===")
print(f"{'2nd sword (45/45/10)':<24}" + "".join(f"{f'@{int(b)}%':>10}" for b in BUD))
for lbl, (a, b) in VARIANTS.items():
    legs = [(S[a], 0.45), (S[b], 0.45), (S["shield"], 0.10)]
    cur = [(f, *geo_sim(legs, f)) for f in FG]
    cells = "".join(f"{at_dd(cur, x)[0]:>9.1f}x" if at_dd(cur, x) else f"{'--':>10}" for x in BUD)
    print(f"{lbl:<24}{cells}")

print("\n" + HDR)
for nm in ("geo1.7", "geo1.6", "geo1.5", "s210"):
    row(f"{nm} (standalone)", 0.40, stats([(S[nm], 1.0)], 0.40, t0, t1))
print("--- king variants (45/45/10 blend) ---")
for lbl, (a, b) in VARIANTS.items():
    row(lbl, 0.40, stats([(S[a], 0.45), (S[b], 0.45), (S["shield"], 0.10)], 0.40, t0, t1))
