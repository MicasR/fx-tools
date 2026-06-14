"""
shadow_streams.py — the PORT-VALIDATION ORACLE (2026-06-14).

Dumps the *expected* per-leg op R-stream for each of the 6 cross-king legs, so the
MQL5 CrossKing_EA can be validated in the MT5 Strategy Tester against a known-good
reference (SYSTEM_PLAN.md §4, Phase B).  Each leg is exactly the cross_kings.py
definition: run_tf_conc(max_conc=1, conc_dir="same") with the leg's params, the
per-instrument spread-stress baked ($0.40/tr1.0 gold, $18/tr0.01 BTC -> a winner
whose closest approach to its liquidation line is under the threshold is flipped to
-1R, the same exam the king takes).

Per leg it writes out/shadow/<leg>.csv (one row per op):
  op, entry_time, exit_time, dir, n_pos, reason, R_raw, gap, R_stress, e0, r0, E0,
  n_adds, adds   (adds = JSON list of [time, price, lot]; first element = the base)
and prints the leg fingerprint (totR / win% / maxDD / RF / 6-seg / 1op share) on the
STRESSED stream, so the totals reconcile to the documented king (gold 194.7R, BTC
162.8R) before any MQL5 is written.

Run:  python shadow_streams.py
"""
import os
import json
import csv
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap

OUT = "out/shadow"

# name, sym, tf, stress_thr ($), TR ($/1.0px/lot), king-weight, run_tf_conc kwargs
# -- mirrors cross_kings.py.  Each EA trades its leg at its OWN full 1R (the raw
# stream below); the WEIGHT is the orchestrator's capital allocation, applied only
# when blending into the king (the weighted sum must reconcile to the documented king).
LEGS = [
    ("GoldGeo17",  "XAU", "M15", 0.40, 1.00, "GOLD", 0.500, dict(smaP=7,  slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldS210",   "XAU", "M15", 0.40, 1.00, "GOLD", 0.375, dict(smaP=5,  slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True)),
    ("GoldShield", "XAU", "M15", 0.40, 1.00, "GOLD", 0.125, dict(stack=False, tp_R=2.0)),
    ("BtcGF",      "BTC", "H1",  18.0, 0.01, "BTC",  0.552, dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True)),
    ("BtcPG",      "BTC", "H1",  18.0, 0.01, "BTC",  0.248, dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True)),
    ("BtcShield",  "BTC", "H1",  18.0, 0.01, "BTC",  0.200, dict(stack=False, tp_R=1.25)),
]

DOC_KING = {"GOLD": 194.7, "BTC": 162.8}   # documented blended king totR (cross_kings.py)


def fingerprint(rows, n):
    """totR / win% / maxDD / RF / 6-seg / 1op-share on the stressed R-stream."""
    R = np.array([r["R_stress"] for r in rows]) if rows else np.array([0.0])
    cum = peak = dd = 0.0
    for r in sorted(rows, key=lambda r: r["k1"]):
        cum += r["R_stress"]; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // 6
    seg = [sum(r["R_stress"] for r in rows if k * q <= r["k0"] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    tot = float(R.sum())
    return dict(n=len(rows), tot=tot, win=100 * float(np.mean(R > 0)), dd=dd,
                rf=(tot / dd if dd > 0 else 0.0), rob=sum(1 for s in seg if s > 0),
                oneop=(float(R.max()) / tot * 100 if tot > 0 else 0.0), seg=seg)


def build_leg(name, sym, tf, thr, tr, king, weight, cfg):
    res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    rows = []
    for i, o in enumerate(res):
        k0, k1, R, npos, reason, info = o
        gap = op_gap(o, H, L, tr) if R > 0 else None
        R_stress = -1.0 if (R > 0 and gap is not None and gap < thr) else R
        adds = [[str(tm[k]), float(P), float(lot)] for (k, P, lot) in info["log"]]
        rows.append(dict(k0=k0, k1=k1, op=i, entry_time=str(tm[k0]), exit_time=str(tm[k1]),
                         dir=info["dir"], n_pos=npos, reason=reason, R_raw=float(R),
                         gap=(None if gap is None else float(gap)), R_stress=float(R_stress),
                         e0=float(info["e0"]), r0=float(info["r0"]), E0=float(info["E0"]),
                         n_adds=len(adds), adds=adds))
    return rows, n


def write_csv(name, rows):
    cols = ["op", "entry_time", "exit_time", "dir", "n_pos", "reason", "R_raw",
            "gap", "R_stress", "e0", "r0", "E0", "n_adds", "adds"]
    with open(f"{OUT}/{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r["op"], r["entry_time"], r["exit_time"], r["dir"], r["n_pos"],
                        r["reason"], f"{r['R_raw']:.6f}",
                        ("" if r["gap"] is None else f"{r['gap']:.4f}"),
                        f"{r['R_stress']:.6f}", f"{r['e0']:.4f}", f"{r['r0']:.4f}",
                        f"{r['E0']:.4f}", r["n_adds"], json.dumps(r["adds"])])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("=== shadow streams — expected per-leg op R-stream (stress baked) ===")
    print(f"   wrote per-op CSVs to {OUT}/  (the Strategy-Tester validation target)\n")
    print(f"{'leg':<12}{'king':>5}{'wt':>6}{'ops':>5}{'totR':>9}{'win%':>7}{'maxDD':>8}{'RF':>7}"
          f"{'segs':>6}{'1op':>6}   per-segment R")
    king_blend = {}
    for name, sym, tf, thr, tr, king, weight, cfg in LEGS:
        rows, n = build_leg(name, sym, tf, thr, tr, king, weight, cfg)
        write_csv(name, rows)
        fp = fingerprint(rows, n)
        king_blend.setdefault(king, 0.0)
        king_blend[king] += weight * fp["tot"]
        segs = " ".join(f"{s:+6.1f}" for s in fp["seg"])
        print(f"{name:<12}{king:>5}{weight:>6.3f}{fp['n']:>5}{fp['tot']:>9.1f}{fp['win']:>6.1f}%"
              f"{fp['dd']:>8.1f}{fp['rf']:>7.1f}{fp['rob']:>4}/6{fp['oneop']:>5.0f}%   {segs}")
    print("\n  weighted-blend reconciliation (sum of weight*legR == documented king):")
    for king, blend in king_blend.items():
        ok = "OK" if abs(blend - DOC_KING[king]) < 0.5 else "MISMATCH"
        print(f"    {king:<4} sum(wt*R) = {blend:>7.1f}R   documented = {DOC_KING[king]:>6.1f}R   [{ok}]")
