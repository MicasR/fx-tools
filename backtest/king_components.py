"""
king_components.py — segmented R: the King and its 3 components (2026-06-12).

Consistent engine (run_tf_conc, -1R floor on all legs) + stress@$0.40, 1%-units,
common time window.  Components shown STANDALONE (full weight = their character);
KING = the 45/45/10 concurrent blend (its maxDD is the *blended* curve's, not the
sum -- that gap is the diversification).
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR

CFG = {
    "geo1.7 (sword)": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210 (sword)":   dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "TP2.0 (shield)": dict(stack=False, tp_R=2.0),
}
WEIGHT = {"geo1.7 (sword)": 0.45, "s210 (sword)": 0.45, "TP2.0 (shield)": 0.10}

if __name__ == "__main__":
    S = {}; t0 = t1 = None
    for nm, c in CFG.items():
        res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
        S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]
        t0 = tm[0] if t0 is None else min(t0, tm[0])
        t1 = tm[-1] if t1 is None else max(t1, tm[-1])

    print(HDR)
    print("--- components (standalone, full weight = their character) ---")
    for nm in CFG:
        row(nm, 0.40, stats([(S[nm], 1.0)], 0.40, t0, t1))
    print("--- the KING (45/45/10 concurrent blend; weighted contributions sum to this) ---")
    row("KING 45/45/10", 0.40, stats([(S[nm], WEIGHT[nm]) for nm in CFG], 0.40, t0, t1))
