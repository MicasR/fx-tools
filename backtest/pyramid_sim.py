"""
Self-funding 1R pyramid — granularity sweep.

One directional operation per signal, shared trailing SL (chandelier, 2.5R
give-back), stepped in G*R increments. On EACH trail step we top the AT-RISK
positions back up to exactly 1R by opening a new trade G*R-style at the current
price — *ignoring* positions already locked safe (entry behind the SL). Locked
positions accumulate as a profit cushion; if the SL is hit the operation banks
(safe gains − 1R). Each op risks exactly 1R, so totR sums R-multiples per op.

Sweeps the step granularity G (0.1 / 0.25 / 0.5 / 1.0 R) vs a no-pyramid
baseline (just the first position trails out). Gold + BTC, full + 6 segments.

Run:  python pyramid_sim.py
"""
import glob
from collections import defaultdict
import numpy as np
import pandas as pd
import signals as sg
from book_sim import entry_events

TRAIL = 2.5     # give-back, in R (R = the operation's first-signal range)


def run_sym(d, cost, G):
    """Returns list of operations: (entry_bar, exit_bar, R, n_positions)."""
    evs, H, L, C, n = entry_events(d)
    by_bar = defaultdict(list)
    for e in evs:
        by_bar[e["ej"]].append(e)

    ops = []
    op = None
    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            gb, step = TRAIL * r0, G * r0

            # ---- exit check first (pessimistic: SL as it entered the bar) ----
            hit = (L[k] <= op["sl"]) if dd == 1 else (H[k] >= op["sl"])
            if hit:
                pnl = sum(lot * dd * (op["sl"] - e) for e, lot in op["pos"])
                pnl -= sum(cost * lot for e, lot in op["pos"])          # round-trip cost
                ops.append((op["ebar"], k, pnl, len(op["pos"])))
                op = None
            else:
                if dd == 1:
                    op["ext"] = max(op["ext"], H[k])
                    chand = op["ext"] - gb
                    if G > 0:
                        while op["sl"] + step <= chand and len(op["pos"]) < 200:
                            op["sl"] += step
                            ar = sum(lot * (e - op["sl"]) for e, lot in op["pos"] if e > op["sl"])
                            if ar < 1.0:
                                op["pos"].append((op["sl"] + gb, (1.0 - ar) / gb))
                    else:
                        op["sl"] = max(op["sl"], chand)              # baseline: trail, no adds
                else:
                    op["ext"] = min(op["ext"], L[k])
                    chand = op["ext"] + gb
                    if G > 0:
                        while op["sl"] - step >= chand and len(op["pos"]) < 200:
                            op["sl"] -= step
                            ar = sum(lot * (op["sl"] - e) for e, lot in op["pos"] if e < op["sl"])
                            if ar < 1.0:
                                op["pos"].append((op["sl"] - gb, (1.0 - ar) / gb))
                    else:
                        op["sl"] = min(op["sl"], chand)

        if op is None:                                                # flat → take next signal
            for e in by_bar.get(k, []):
                if e["rng"] <= 0:
                    continue
                op = dict(dir=e["d"], r0=e["rng"], ebar=k, ext=e["entry"],
                          sl=e["sl"], pos=[(e["entry"], 1.0 / e["rng"])])
                break

    if op is not None:
        pnl = sum(lot * op["dir"] * (C[n - 1] - e) for e, lot in op["pos"])
        pnl -= sum(cost * lot for e, lot in op["pos"])
        ops.append((op["ebar"], n - 1, pnl, len(op["pos"])))
    return ops


def stat(ops):
    R = np.array([o[2] for o in ops]) if ops else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    cum = peak = dd = 0.0
    for _, _, r, _ in sorted(ops, key=lambda o: o[1]):
        cum += r; peak = max(peak, cum); dd = max(dd, peak - cum)
    npos = [o[3] for o in ops]
    return dict(n=len(R), totR=R.sum(), avgR=R.mean(), pf=(w / l if l > 0 else 9.99),
                maxdd=dd, win=100 * np.mean(R > 0),
                avgpos=np.mean(npos) if npos else 0, maxpos=max(npos) if npos else 0)


def run(sym, cost):
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= pd.Timestamp("2024-03-26")].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    n = len(d); q = n // 6
    print(f"\n================ {sym}  (cost ${cost})  ================")
    print(f"{'step G':<10}{'ops':>5}{'totR':>8}{'avgR':>8}{'PF':>6}{'maxDD':>7}{'win%':>6}"
          f"{'avgPos':>8}{'mxPos':>6}  segs+")
    for G, lbl in [(0, "none(1pos)"), (0.1, "0.10R"), (0.25, "0.25R"),
                   (0.5, "0.50R"), (1.0, "1.00R")]:
        ops = run_sym(d, cost, G)
        s = stat(ops)
        seg = [sum(r for eb, xb, r, _ in ops if k*q <= eb < (n if k == 5 else (k+1)*q)) for k in range(6)]
        pos = sum(1 for t in seg if t > 0)
        print(f"{lbl:<10}{s['n']:>5}{s['totR']:>8.1f}{s['avgR']:>8.3f}{s['pf']:>6.2f}"
              f"{s['maxdd']:>7.1f}{s['win']:>6.1f}{s['avgpos']:>8.1f}{s['maxpos']:>6.0f}   {pos}/6")


if __name__ == "__main__":
    run("XAU", 0.50)
    run("BTC", 18.0)
