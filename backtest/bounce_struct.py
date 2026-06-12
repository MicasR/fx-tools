"""
bounce_struct.py — NEW component: SMA-bounce, margin line at the PREVIOUS bounce
extreme (2026-06-12, user idea).

On each bounce-add, anchor the book's liquidation at the previous retracement's
extreme (higher-high for shorts / lower-low for longs) IF it lies beyond the
current retracement extreme; else fallback = skip the add, or pin to the current
extreme (`prev_fb`).  Structure-based stop placement.  Two variants tested vs the
king's swords.  Consistent engine + stress@$0.40, segments.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR

CFG = {
    "pinprev skip":     dict(smaP=7, slowP=0,   sizing="pinprev",  tp_R=3.0, stack=True, prev_fb="skip"),
    "pinprev current":  dict(smaP=7, slowP=0,   sizing="pinprev",  tp_R=3.0, stack=True, prev_fb="current"),
    "geo1.7 (ref)":     dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210 (ref)":       dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
}


def stream(**kw):
    res, tm, H, L, n = run_tf_conc(**kw, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res], tm[0], tm[-1]


if __name__ == "__main__":
    S = {}; t0 = t1 = None
    for nm, c in CFG.items():
        s, a, b = stream(**c); S[nm] = s
        t0 = a if t0 is None else min(t0, a); t1 = b if t1 is None else max(t1, b)
    print(HDR)
    for nm in CFG:
        row(nm, 0.40, stats([(S[nm], 1.0)], 0.40, t0, t1))
