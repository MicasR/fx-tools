"""
btc_king.py — gold King AS-IS on BTC vs a first BTC-tuned pass (2026-06-12).
Engine is symbol-generic (run_tf_conc sym='BTC').  BTC spread ~$18, so stress
threshold scales to ~$18 (gold used $0.40).  Show component + blend segments.

AS-IS  = gold king params on BTC (geo1.7 SMA7-proggeo, s210 geofloor f5/slow210,
         TP2.0 shield), gold weights .50/.375/.125.
BTC v0 = BTC-tuned first pass per memory (BTC likes SLOWER bounce SMA(15) +
         gentler ramp): swordA SMA15-proggeo g1.2, swordB SMA15-geofloor slow210
         g1.2, TP2.0 shield -- mirrors the gold king's proggeo-vs-geofloor
         decorrelation but BTC-period.  (Weights = gold's for now; tune later.)
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_ops import stats, row, HDR
from pyramid_engine import SPECS

SYM = "BTC"
TR = SPECS[SYM]["TR"]            # BTC=0.01 — op_gap liquidation line must use it
THR = 18.0
W = (.50, .375, .125)

ASIS = {
    "geo1.7":  dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":    dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield":  dict(stack=False, tp_R=2.0),
}
BTCV0 = {
    "bnc15-pg":  dict(smaP=15, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True),
    "bnc15-gf":  dict(smaP=15, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.2, tp_R=3.0, stack=True),
    "shield":    dict(stack=False, tp_R=2.0),
}


def stream(cfg):
    res, tm, H, L, n = run_tf_conc(sym=SYM, **cfg, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res], tm[0], tm[-1]


def show(title, cfgs):
    S = {}; t0 = t1 = None
    for nm, c in cfgs.items():
        s, a, b = stream(c); S[nm] = s
        t0 = a if t0 is None else min(t0, a); t1 = b if t1 is None else max(t1, b)
    print(f"\n=== {title} (BTC M15, stress @ ${THR:.0f}) ===")
    print(HDR)
    names = list(cfgs)
    for nm in names:
        row(nm, THR, stats([(S[nm], 1.0)], THR, t0, t1))
    legs = [(S[names[0]], W[0]), (S[names[1]], W[1]), (S[names[2]], W[2])]
    row("KING blend .50/.375/.125", THR, stats(legs, THR, t0, t1))
    # heads (no stress) blend for reference
    row("  (heads, no stress)", 0.0, stats(legs, 0.0, t0, t1))


if __name__ == "__main__":
    show("GOLD KING AS-IS on BTC", ASIS)
    show("BTC KING v0 (SMA15 / g1.2)", BTCV0)
