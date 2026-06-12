"""
btc_vs_gold_segments.py — BTC king v3 + its components by SEGMENT vs the gold king (2026-06-12).
Shows the per-seg R fingerprint that proves the decorrelation: gf (lumpy fat-tail sword,
seg2/5/6) + pg-TP3 (even partner, fills seg3/4) + shield-TP1.25 (high-win smoother) ->
the BLEND lifts the holes flat.  Gold king (geo1.7/s210/shield-TP2.0) as the benchmark row.
BTC stress @ $18 (tr=0.01, H1);  gold stress @ $0.40 (tr=1.0, M15).  Weights:
  BTC v3 = gf .552 / pg-TP3 .248 / shield-TP1.25 .200
  gold   = geo1.7 .50 / s210 .375 / shield-TP2.0 .125
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR
from pyramid_engine import SPECS


def stream(sym, tf, thr_tr, **cfg):
    res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    s = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, thr_tr) if o[2] > 0 else None) for o in res]
    return s, tm[0], tm[-1]


# ---- BTC king v3 (H1, stress $18, tr=0.01) ----
BTC_TR = SPECS["BTC"]["TR"]
BTC = {
    "gf  (geofloor s210 trail2.5)": dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True),
    "pg-TP3 (proggeo TP3R)":        dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True),
    "shield-TP1.25":                dict(stack=False, tp_R=1.25),
}
BTC_W = [0.552, 0.248, 0.200]

# ---- gold king (M15, stress $0.40, tr=1.0) ----
GOLD = {
    "geo1.7 (proggeo)":   dict(smaP=7, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210 (geofloor)":    dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield-TP2.0":       dict(stack=False, tp_R=2.0),
}
GOLD_W = [0.50, 0.375, 0.125]


def show(title, sym, tf, thr, tr, cfgs, ws):
    S, t0, t1 = {}, None, None
    for nm, c in cfgs.items():
        s, a, b = stream(sym, tf, tr, **c); S[nm] = s
        t0 = a if t0 is None else min(t0, a); t1 = b if t1 is None else max(t1, b)
    print(f"\n=== {title} ===")
    print(HDR)
    names = list(cfgs)
    for nm in names:
        row(nm, thr, stats([(S[nm], 1.0)], thr, t0, t1))
    legs = [(S[names[i]], ws[i]) for i in range(3)]
    w = "/".join(f"{x:.3f}" for x in ws)
    row(f"  KING blend {w}", thr, stats(legs, thr, t0, t1))
    return S, t0, t1, legs


if __name__ == "__main__":
    print("Per-segment R (by time, stressed).  Components shown at 1.0 own-stake; blend at king weights.")
    print("BTC = H1 / stress $18 (2024-02..2026-06);  GOLD = M15 / stress $0.40 (different window) — compare the")
    print("FINGERPRINT (which segs each leg carries + how the blend fills holes), not calendar-aligned cells.")
    sb, *_ , blegs = show("BTC KING v3  (H1, stress $18)", "BTC", "H1", 18.0, BTC_TR, BTC, BTC_W)
    sg, *_ , glegs = show("GOLD KING  (M15, stress $0.40)", "XAU", "M15", 0.40, 1.0, GOLD, GOLD_W)
