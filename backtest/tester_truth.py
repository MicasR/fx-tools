"""
tester_truth.py — the CANONICAL reader of MQL5-tester results (FIDELITY Path A).

As of 2026-06-14 the **MQL5 Strategy Tester is our ground-truth research engine**
(not the Python oracle): we proved Model 1 (1-min OHLC) reproduces Model 4 (real
ticks) over the full window once **negative-balance protection (NBP)** is applied,
so the fast headless Model-1 tester *is* reality. This module parses a tester log
into per-leg op R-streams and reports the live-faithful fingerprint.

THE NBP RULE (the standard accounting, applied here and everywhere downstream):
  Each ops-account is funded with exactly **1R** (the EA-dumb / orchestrator-brain
  model: E0 = the whole account). A liquidation can momentarily overshoot the
  equity-0 line (the tester, run on a large deposit, *reports* losses of -1.1 to
  -2.0R), but the broker's **negative-balance protection** instantly resets the
  account to 0 -> the realized loss is **capped at -1R**. So every op's realized R
  is clamped:  R_live = max(R_tester, -1.0).
  This clamp also makes **Model 1 == Model 4** (the overshoot was their only
  divergence), and it must be applied to ALL accounting derived from the stream
  (totR, maxDD, RF, segments, geometric growth) — losses in the live equity curve
  cannot exceed -1R.

Usage:
  python tester_truth.py [logpath]          # default: the daily tester log
  from tester_truth import read_legs, fingerprint
"""
import io
import re
import sys
import numpy as np

DEFAULT_LOG = (r"C:\Users\Dercio Micas\AppData\Roaming\MetaQuotes"
               r"\Terminal\53785E099C927DB68A545C249CDBCE06\Tester\logs\20260614.log")

RE_INIT  = re.compile(r"\[CrossKing:(\S+)\] init  sym")
RE_CLOSE = re.compile(r"\[CrossKing:(\S+)\] OP CLOSE  R=(-?[\d.]+)")

# documented Python-oracle totR per leg (the suspect idealized numbers, for reference)
ORACLE = {"GoldGeo17": 174.1, "GoldS210": 259.5, "GoldShield": 82.7,
          "BtcGF": 241.3, "BtcPG": 82.3, "BtcShield": 45.8}


def read_legs(logpath=DEFAULT_LOG):
    """Parse a tester log -> {leg: [R, ...]} using the LAST run of each leg
    (init-delimited). Strips the '_M4'/'_val' run-suffix so model variants merge
    under the base leg name only if you want — here we keep the exact init name."""
    segs, cur = [], None
    with io.open(logpath, "r", encoding="utf-16", errors="ignore") as f:
        for line in f:
            if "CrossKing" not in line:
                continue
            mi = RE_INIT.search(line)
            if mi:
                cur = {"leg": mi.group(1), "R": []}
                segs.append(cur)
                continue
            mc = RE_CLOSE.search(line)
            if mc and cur is not None:
                cur["R"].append(float(mc.group(2)))
    last = {}
    for s in segs:
        if s["R"]:
            last[s["leg"]] = s["R"]
    return last


def nbp(R):
    """Apply negative-balance protection: clamp every op's realized R at -1."""
    return np.maximum(np.asarray(R, dtype=float), -1.0)


def fingerprint(R, nseg=6):
    """Live-faithful fingerprint on the NBP-clamped stream (ops in chronological
    order). Segments = nseg equal-count chunks (sign per chunk = robustness)."""
    R = nbp(R)
    n = len(R)
    cum = peak = dd = 0.0
    for r in R:
        cum += r; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // nseg if nseg else n
    seg = [float(R[k * q:(n if k == nseg - 1 else (k + 1) * q)].sum()) for k in range(nseg)]
    tot = float(R.sum())
    return dict(n=n, tot=tot, win=100.0 * float(np.mean(R > 0)), dd=dd,
                rf=(tot / dd if dd > 0 else 0.0), rob=sum(1 for s in seg if s > 0),
                oneop=(float(R.max()) / tot * 100 if tot > 0 else 0.0), seg=seg)


def main():
    logpath = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOG
    legs = read_legs(logpath)
    print("=== tester TRUTH (NBP-clamped, live-faithful) ===")
    print(f"{'leg':<13}{'ops':>5}{'rawR':>8}{'nbpR':>8}{'win%':>6}{'maxDD':>7}{'RF':>6}"
          f"{'segs':>6}{'1op':>6}{'oracle':>8}{'vsOrc':>7}   per-seg")
    for leg in sorted(legs):
        R = legs[leg]
        raw = float(np.sum(R))
        fp = fingerprint(R)
        base = re.sub(r"_(M4|val|M1)$", "", leg)
        orc = ORACLE.get(base, 0.0)
        segs = " ".join(f"{s:+5.0f}" for s in fp["seg"])
        vs = f"{fp['tot']/orc:.2f}" if orc else "  -  "
        print(f"{leg:<13}{fp['n']:>5}{raw:>8.1f}{fp['tot']:>8.1f}{fp['win']:>5.1f}%"
              f"{fp['dd']:>7.1f}{fp['rf']:>6.1f}{fp['rob']:>4}/6{fp['oneop']:>5.0f}%"
              f"{orc:>8.1f}{vs:>7}   {segs}")
    print("\n  nbpR = totR with negative-balance protection (loss capped at -1R) = the LIVE number.")
    print("  Model 1 == Model 4 under NBP -> the fast headless Model-1 tester is ground truth.")


if __name__ == "__main__":
    main()
