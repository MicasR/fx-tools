"""
m1_validate.py — does the M1-intrabar Python engine match the MQL5 tester?

Runs the 6 cross-king legs through run_m1_conc, applies NBP (clamp every op at -1R),
and compares per-leg nbpR + 6-segment fingerprint to the tester TRUTH (the NBP-clamped
Model-1 tester numbers, FIDELITY_FINDINGS "Path A + NBP" table). Gate: < 5% per leg.

Run:  python m1_validate.py
"""
import numpy as np
from m1_engine import run_m1_conc
from tester_truth import nbp, fingerprint

# leg defs mirror shadow_streams.py / cross_kings.py
LEGS = [
    ("GoldGeo17",  "XAU", "M15", dict(smaP=7,  slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldS210",   "XAU", "M15", dict(smaP=5,  slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldShield", "XAU", "M15", dict(stack=False, tp_R=2.0)),
    ("BtcGF",      "BTC", "H1",  dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)),
    ("BtcPG",      "BTC", "H1",  dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True)),
    ("BtcShield",  "BTC", "H1",  dict(stack=False, tp_R=1.25)),
]

# tester TRUTH (NBP-clamped Model-1), FIDELITY_FINDINGS:
#                  nbpR   win%  maxDD   RF   segs  1op
TRUTH = {
    "BtcGF":      (191.0, 23.4, 18.8, 10.2, 5, 50),
    "BtcPG":      ( 40.6, 28.6, 25.9,  1.6, 4,  8),
    "BtcShield":  ( 16.5, 46.4, 20.3,  0.8, 3,  8),
    "GoldGeo17":  (124.3, 27.7, 19.9,  6.3, 5, 33),
    "GoldS210":   (157.4, 20.6, 33.4,  4.7, 3, 57),
    "GoldShield": ( 37.7, 37.6, 16.0,  2.4, 4,  5),
}


def main():
    print("=== M1-intrabar engine vs MQL5 tester TRUTH (NBP-clamped) ===")
    print(f"{'leg':<12}{'ops':>5}{'nbpR':>8}{'truth':>8}{'Δ%':>7}{'win%':>6}{'maxDD':>7}"
          f"{'RF':>6}{'segs':>6}{'1op':>5}   per-seg R")
    worst = 0.0
    for name, sym, tf, cfg in LEGS:
        res, *_ = run_m1_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
        R = [o[2] for o in res]
        fp = fingerprint(R)
        tr = TRUTH[name][0]
        dpct = 100 * (fp["tot"] - tr) / tr if tr else 0.0
        worst = max(worst, abs(dpct))
        flag = "" if abs(dpct) < 5 else "  <-- >5%"
        segs = " ".join(f"{s:+5.0f}" for s in fp["seg"])
        print(f"{name:<12}{fp['n']:>5}{fp['tot']:>8.1f}{tr:>8.1f}{dpct:>+6.1f}%"
              f"{fp['win']:>5.1f}%{fp['dd']:>7.1f}{fp['rf']:>6.1f}{fp['rob']:>4}/6"
              f"{fp['oneop']:>4.0f}%   {segs}{flag}")
    print(f"\n  worst per-leg |Δ| = {worst:.1f}%   (< 5% gate {'PASSED' if worst < 5 else 'NOT met'})")
    print("  truth = NBP Model-1 tester (FIDELITY_FINDINGS). Δ% = (M1 engine - truth)/truth.")


if __name__ == "__main__":
    main()
