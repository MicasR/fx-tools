"""
stress_audit.py — systematic spread-stress: flip EVERY winner whose closest
approach to the liquidation line was under a threshold (it would likely have
been clipped at real spread), then re-score.  Champion takes the same exam —
its base lot also pins the line at entry-1R, so this is like-for-like.
M15 lows are exact intrabar minima, so gaps are granularity-exact.
Thresholds: $0 (as recorded) / 0.25 / 0.40 (round-trip cost) / 0.60 / 1.00.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf, margin_line

HDR = (f"{'variant':<24}{'thr$':>6}{'flips':>6}{'totR':>9}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def op_gap(o, H, L, tr=1.0):
    """Closest $ between price and the op's liquidation line over its life.
    tr = symbol TR ($ P&L per 1.0 price move per lot); MUST match the symbol
    (gold TR=1.0 default; BTC TR=0.01) or the liquidation line is mis-scaled."""
    info = o[5]
    dd, E0, log = info["dir"], info["E0"], info["log"]
    k0, k1 = o[0], o[1]
    adds = sorted(log)  # (k, P, lot), applied from bar k+1 onward
    pos, ai, mg = [], 0, 1e18
    for j in range(k0, k1 + 1):
        while ai < len(adds) and adds[ai][0] < j:
            pos.append((adds[ai][1], adds[ai][2])); ai += 1
        if not pos:
            continue
        ml = margin_line(pos, dd, E0, tr, 0.0)
        gap = (L[j] - ml) if dd == 1 else (ml - H[j])
        mg = min(mg, gap)
    return mg


def row(lbl, thr, ops, gaps, n):
    ops = [list(o) for o in ops]
    flips = 0
    for o, g in zip(ops, gaps):
        if o[2] > 0 and g is not None and g < thr:
            o[2], o[4] = -1.0, "SL*"; flips += 1
    R = np.array([o[2] for o in ops])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    pf = w / l if l > 0 else 9.99
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // 6
    seg = [sum(o[2] for o in ops if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    rob = sum(1 for t in seg if t > 0)
    tot = R.sum(); rf = tot / dd if dd > 0 else 0
    oneop = R.max() / tot * 100 if tot > 0 else 0
    segs = " ".join(f"{s:+7.1f}" for s in seg)
    print(f"{lbl:<24}{thr:>6.2f}{flips:>6}{tot:>9.1f}{100*np.mean(R>0):>6.1f}"
          f"{pf:>6.2f}{dd:>7.1f}{rf:>7.1f}   {rob}/6{oneop:>5.0f}%  {segs}")


def audit(lbl, res, H, L):
    ops, _, _, n = res
    gaps = [op_gap(o, H, L) if o[2] > 0 else None for o in ops]
    for thr in (0.0, 0.25, 0.40, 0.60, 1.00):
        row(lbl, thr, ops, gaps, n)
    print()


def frame(smaP, slowP):
    m = pd.read_csv(glob.glob("data/*XAU*_M15.csv")[0], parse_dates=["time"])
    m["sma"] = m["close"].rolling(smaP).mean()
    if slowP:
        m["slow"] = m["close"].rolling(slowP).mean()
    return m.dropna().reset_index(drop=True)


if __name__ == "__main__":
    print(HDR)
    m = frame(7, 0)
    H, L = m["high"].to_numpy(), m["low"].to_numpy()
    audit("champion geo1.7",
          run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7, sizing="proggeo",
                 unit="base", mult=0.01, prog_step=1.7, lev=2000.0), H, L)
    for fast in (5, 7):
        m = frame(fast, 200)
        H, L = m["high"].to_numpy(), m["low"].to_numpy()
        audit(f"geofloor f{fast}/s200",
              run_tf("XAU", tf="M15", triggers=("bounce",), smaP=fast,
                     sizing="geofloor", slowP=200, unit="base", mult=0.01,
                     prog_step=1.7, lev=2000.0), H, L)
