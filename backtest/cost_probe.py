"""
cost_probe.py — FIDELITY §3.1/§3.3 probe: how much of the Python<->tester gap does
a *parameter-free* real per-fill SPREAD model close?  (Hypothesis H1.)

For each of the 6 cross-king legs we re-run the exact shadow definition
(run_tf_conc, max_conc=1, conc_dir="same"), then re-cost every op by REPLACING the
engine's flat per-lot COST with the broker's REAL spread from the CSV `spread`
column, charged once per position (the open-at-ask / value-at-bid haircut that the
mid-price Python engine omits):

    spread_$(position) = spread_points[entry_bar] * point * TR * lot

new_R = max( R_raw*E0 + oldCost_$ - spread_$ , -E0 ) / E0     (losers stay floored)

No free parameters, no per-leg fudge.  We then compare the spread-adjusted totR to
the Phase-B MQL5 tester totals (Model 1) to see how much of the documented gap is
explained by spread alone (and how much residual is left for commission/swap/H5).

Run:  python cost_probe.py
"""
import glob
import numpy as np
import pandas as pd
from conc_engine import run_tf_conc
from pyramid_engine import SPECS

# symbol -> price point (10^-digits): gold 3dp, BTC 2dp (verified from the CSVs)
POINT = {"XAU": 0.001, "BTC": 0.01}

# leg, sym, tf, run_tf_conc kwargs  (mirrors shadow_streams.LEGS, sans stress/weight)
LEGS = [
    ("GoldGeo17",  "XAU", "M15", dict(smaP=7,  slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldS210",   "XAU", "M15", dict(smaP=5,  slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldShield", "XAU", "M15", dict(stack=False, tp_R=2.0)),
    ("BtcGF",      "BTC", "H1",  dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)),
    ("BtcPG",      "BTC", "H1",  dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True)),
    ("BtcShield",  "BTC", "H1",  dict(stack=False, tp_R=1.25)),
]

# Phase-B MQL5 tester totals (Model 1, 1:2000, fixed-E0=10) — the match target
TESTER = {"GoldGeo17": 40.3, "GoldS210": 51.8, "GoldShield": 35.4,
          "BtcGF": 189.9, "BtcPG": 39.5, "BtcShield": 16.0}
ORACLE = {"GoldGeo17": 174.1, "GoldS210": 259.5, "GoldShield": 82.7,
          "BtcGF": 241.3, "BtcPG": 82.3, "BtcShield": 45.8}

E0 = 10.0   # validation 1R (matches the tester's InpFixedE0)


def frame_spread(sym, tf, stack, smaP, slowP):
    """Rebuild run_tf_conc's frame exactly so spread aligns to the op-log bar index k."""
    m = pd.read_csv(glob.glob(f"data/*{sym}*_{tf}.csv")[0], parse_dates=["time"])
    if stack:
        m["sma"] = m["close"].rolling(smaP).mean()
    if slowP > 0:
        m["slow"] = m["close"].rolling(slowP).mean()
    m = m.dropna().reset_index(drop=True)
    return m["spread"].to_numpy()


def probe(name, sym, tf, cfg):
    sp = SPECS[sym]; TR, COST = sp["TR"], sp["cost"]
    point = POINT[sym]
    stack = cfg.get("stack", True)
    spread_pts = frame_spread(sym, tf, stack, cfg.get("smaP", 7), cfg.get("slowP", 0))
    res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")

    raw_tot = spr_tot = 0.0
    fills = 0
    spread_cost_tot = 0.0
    for o in res:
        k0, k1, R, npos, reason, info = o
        log, dd, e0 = info["log"], info["dir"], info["E0"]
        raw_tot += R
        old_cost = sum(COST * TR * lot for (_, _, lot) in log)            # engine's flat cost ($)
        spread_cost = sum(spread_pts[k] * point * TR * lot for (k, _, lot) in log)  # real spread ($)
        spread_cost_tot += spread_cost
        fills += len(log)
        # rebuild $ floating, swap flat cost -> real spread, refloor at -E0
        floating = R * e0 + old_cost                                      # pre-cost $ P&L
        new_R = max(floating - spread_cost, -e0) / e0
        spr_tot += new_R
    return dict(n=len(res), raw=raw_tot, spr=spr_tot, fills=fills,
                spread_cost=spread_cost_tot, avg_spread_R=spread_cost_tot / E0 / max(1, len(res)))


if __name__ == "__main__":
    print(f"{'leg':<11}{'ops':>5}{'fills':>6}{'rawR':>8}{'+spread':>9}{'tester':>8}{'oracle':>8}"
          f"{'spr/tst':>8}{'avgSprR':>8}")
    for name, sym, tf, cfg in LEGS:
        r = probe(name, sym, tf, cfg)
        tst, orc = TESTER[name], ORACLE[name]
        ratio = r["spr"] / tst if tst else 0.0
        print(f"{name:<11}{r['n']:>5}{r['fills']:>6}{r['raw']:>8.1f}{r['spr']:>9.1f}{tst:>8.1f}"
              f"{orc:>8.1f}{ratio:>7.2f}x{r['avg_spread_R']:>8.3f}")
    print("\n  rawR   = modeled totR, no stress (engine flat cost only)")
    print("  +spread= rawR re-costed with REAL per-fill spread from the CSV (param-free)")
    print("  tester = Phase-B MQL5 Model-1 totR (the match target)")
    print("  spr/tst= spread-adjusted / tester  (1.00 = spread fully explains the gap)")
