"""
king_contenders.py — segment breakdown of the real crown contenders (2026-06-12).
After the joint weight sweep: g1.2 add is rejected; the win is REWEIGHTING the
3-leg.  old king (45/45/10, 32.0x) vs reweighted king (geo .525/s210 .35/shield
.125, 38.9x).  Best 4-leg shown for completeness (rejected, 37.3x).
Weighted R-stream blend, stressed@$0.40.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR

A12 = dict(trig="poscandle", smaP=7, slowP=0, sizing="proggeo", unit="base", mult=0.01, prog_step=1.2, tp_R=3.0, stack=True)
CFG = {
    "geo1.7": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
    "g1.2":   A12,
}
S = {}; t0 = t1 = None
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]
    t0 = tm[0] if t0 is None else min(t0, tm[0]); t1 = tm[-1] if t1 is None else max(t1, tm[-1])

CONTENDERS = {
    "OLD king .45/.45/.10 (32.0x)":   [("geo1.7", .45), ("s210", .45), ("shield", .10)],
    "NEW king .525/.35/.125 (38.9x)": [("geo1.7", .525), ("s210", .35), ("shield", .125)],
    "best 4-leg +g1.2 (37.3x, rej)":  [("geo1.7", .459), ("s210", .376), ("shield", .125), ("g1.2", .04)],
}
print(HDR)
print("--- components (standalone) ---")
for nm in ("geo1.7", "s210", "shield"):
    row(nm, 0.40, stats([(S[nm], 1.0)], 0.40, t0, t1))
print("--- crown contenders (weighted blend) ---")
for lbl, legs in CONTENDERS.items():
    row(lbl, 0.40, stats([(S[nm], w) for nm, w in legs], 0.40, t0, t1))
