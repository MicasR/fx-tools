"""
screen_new.py — viability screen for two add ideas (2026-06-12, user).

A) add on EVERY positive (confluent) candle, gentle geo ramp (small first, slow
   increment): trig='poscandle', proggeo mult=0.01, prog_step swept gentle.
B) margin line N candles back on the low/high: geofloor anchored nback bars back
   (bounce trigger), N swept.
Screen = does it clear 6/6 (legs across all segments)?  Consistent engine +
stress@$0.40, segments.  geo1.7 / s210 as references.
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR

A = lambda g: dict(trig="poscandle", smaP=7, slowP=0, sizing="proggeo", unit="base",
                   mult=0.01, prog_step=g, tp_R=3.0, stack=True)
B = lambda N: dict(trig="bounce", smaP=7, slowP=0, sizing="geofloor", unit="base",
                   mult=0.015, prog_step=1.7, nback=N, tp_R=3.0, stack=True)
CFG = {
    "A poscandle g1.1": A(1.1), "A poscandle g1.2": A(1.2), "A poscandle g1.3": A(1.3),
    "B nback5":  B(5), "B nback10": B(10), "B nback20": B(20), "B nback40": B(40),
    "geo1.7 (ref)": dict(smaP=7, slowP=0, sizing="proggeo", mult=0.01, prog_step=1.7, tp_R=3.0, stack=True),
    "s210 (ref)":   dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
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
