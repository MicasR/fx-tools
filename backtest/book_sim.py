"""
Event-driven BOOK simulator for VolumeSpikeBreakOut trade-management modes.

Walks the bar series once, maintaining a book of concurrent positions, and
applies one management mode. All modes share: V-pattern(threshold) trigger →
breakout entry at the break level → structural stop (trigger-bar opposite
extreme) → equal 1-unit sizing → net of a round-trip cost per position.

Modes:
  fix    : 3RR, one-at-a-time (ignore signals while in a trade)        [baseline]
  trail  : 2.5xR chandelier trail, one-at-a-time, no fixed TP          [baseline]
  div    : 3RR base + reverse on an opposite confirmed breakout (close all @ mkt)
  confA  : pyramid on confluent breakout if new SL locks all to BE+;
           ratchet all SLs to latest structure; TP stays at INITIAL target
  confB  : as confA but ratchet all TPs to the RECENT signal's target

R per position = dir*(exit-entry)/range - cost/range.  (range = trigger bar H-L)

Run:  python book_sim.py
"""
import glob
from collections import defaultdict
import numpy as np
import pandas as pd
import signals as sg

WAIT, MAXHOLD, RR, TRAIL = 4, 64, 3.0, 2.5


def entry_events(d):
    """All breakout entries from the V-pattern signal, sorted by fill bar."""
    sig = sg.volumevpattern_signal(d, method="threshold", rise_pct=0.02)
    H, L, C, A = (d[c].to_numpy() for c in ("high", "low", "close", "atr"))
    n = len(d)
    idx = np.flatnonzero(sig.to_numpy())
    idx = idx[(idx + 1 < n) & ~np.isnan(A[idx])]
    evs = []
    for i in idx:
        hi, lo = H[i], L[i]
        dd = 0; entry = None; ej = None
        for j in range(i + 1, min(i + WAIT, n - 1) + 1):
            up = H[j] >= hi; dn = L[j] <= lo
            if up and dn: break
            if up: dd, entry, ej = 1, hi, j; break
            if dn: dd, entry, ej = -1, lo, j; break
        if dd == 0: continue
        rng = hi - lo
        if rng <= 0: continue
        evs.append(dict(ej=ej, d=dd, entry=entry, sl=(hi if dd == -1 else lo), rng=rng))
    evs.sort(key=lambda e: e["ej"])
    return evs, H, L, C, n


def simulate(d, cost, mode):
    evs, H, L, C, n = entry_events(d)
    by_bar = defaultdict(list)
    for e in evs:
        by_bar[e["ej"]].append(e)

    book = []          # open positions
    book_dir = 0
    closed = []        # (entry_bar, exit_bar, R)

    def shut(p, xbar, xprice):
        R = p["d"] * (xprice - p["entry"]) / p["rng"] - cost / p["rng"]
        closed.append((p["entry_bar"], xbar, R))

    def new_pos(e, sl, tp):
        return dict(d=e["d"], entry=e["entry"], sl=sl, tp=tp, rng=e["rng"],
                    entry_bar=e["ej"], ext=e["entry"])

    for k in range(n):
        # ---- 1) exits ----
        survivors = []
        for p in book:
            done = False
            if mode == "trail":
                if p["d"] == 1:
                    stop = max(p["sl"], p["ext"] - TRAIL * p["rng"])
                    if L[k] <= stop: shut(p, k, stop); done = True
                    else: p["ext"] = max(p["ext"], H[k])
                else:
                    stop = min(p["sl"], p["ext"] + TRAIL * p["rng"])
                    if H[k] >= stop: shut(p, k, stop); done = True
                    else: p["ext"] = min(p["ext"], L[k])
            else:
                if p["d"] == 1:
                    hs, ht = L[k] <= p["sl"], (p["tp"] is not None and H[k] >= p["tp"])
                else:
                    hs, ht = H[k] >= p["sl"], (p["tp"] is not None and L[k] <= p["tp"])
                if hs: shut(p, k, p["sl"]); done = True
                elif ht: shut(p, k, p["tp"]); done = True
            if not done and k - p["entry_bar"] >= MAXHOLD:
                shut(p, k, C[k]); done = True
            if not done: survivors.append(p)
        book = survivors
        if not book: book_dir = 0

        # ---- 2) entries filling at bar k ----
        for e in by_bar.get(k, []):
            if mode in ("fix", "trail"):
                if not book:
                    tp = e["entry"] + e["d"] * RR * e["rng"] if mode == "fix" else None
                    book = [new_pos(e, e["sl"], tp)]
            elif mode == "div":
                if not book:
                    book = [new_pos(e, e["sl"], e["entry"] + e["d"] * RR * e["rng"])]
                    book_dir = e["d"]
                elif e["d"] != book_dir:                       # reverse
                    for p in book: shut(p, k, e["entry"])
                    book = [new_pos(e, e["sl"], e["entry"] + e["d"] * RR * e["rng"])]
                    book_dir = e["d"]
                # same side → ignore
            elif mode in ("confA", "confB", "confBdiv"):
                if not book:
                    tp = e["entry"] + e["d"] * RR * e["rng"]
                    book = [new_pos(e, e["sl"], tp)]
                    book_dir = e["d"]
                elif e["d"] == book_dir:                       # confluent → pyramid
                    new_sl = e["sl"]
                    locked = (all(new_sl >= p["entry"] for p in book) if book_dir == 1
                              else all(new_sl <= p["entry"] for p in book))
                    if locked:
                        if mode in ("confB", "confBdiv"):
                            new_tp = e["entry"] + e["d"] * RR * e["rng"]
                            for p in book: p["tp"] = new_tp
                            add_tp = new_tp
                        else:                                  # confA: keep initial TP
                            add_tp = book[0]["tp"]
                        for p in book: p["sl"] = new_sl
                        book.append(new_pos(e, new_sl, add_tp))
                elif mode == "confBdiv":                       # opposite → reverse book
                    for p in book: shut(p, k, e["entry"])
                    book = [new_pos(e, e["sl"], e["entry"] + e["d"] * RR * e["rng"])]
                    book_dir = e["d"]
                # else contrary → ignore

    for p in book:
        shut(p, n - 1, C[n - 1])
    return closed


def stats(closed):
    R = np.array([c[2] for c in closed]) if closed else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    pf = w / l if l > 0 else 9.99
    cum = peak = dd = 0.0
    for _, _, r in sorted(closed, key=lambda c: c[1]):
        cum += r; peak = max(peak, cum); dd = max(dd, peak - cum)
    return dict(n=len(R), totR=R.sum(), avgR=R.mean(), pf=pf,
                win=100 * np.mean(R > 0), maxdd=dd)


def run(sym, cost, segments=6):
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= pd.Timestamp("2024-03-26")].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    n = len(d); q = n // segments
    bounds = [(k * q, n if k == segments - 1 else (k + 1) * q) for k in range(segments)]
    print(f"\n================ {sym}  (cost ${cost})  ================")
    print(f"{'mode':<8}{'n':>5}{'totR':>8}{'avgR':>8}{'PF':>6}{'maxDD':>7}{'win%':>6}  per-segment totR (+/6)")
    for mode, lbl in [("fix", "3RR"), ("trail", "2.5trail"), ("div", "diverge"),
                      ("confA", "confA"), ("confB", "confB"), ("confBdiv", "confB+div")]:
        closed = simulate(d, cost, mode)
        s = stats(closed)
        seg_tot = []
        for lo, hi in bounds:
            seg_tot.append(sum(r for eb, xb, r in closed if lo <= eb < hi))
        pos = sum(1 for t in seg_tot if t > 0)
        segstr = " ".join(f"{t:+5.0f}" for t in seg_tot)
        print(f"{lbl:<8}{s['n']:>5}{s['totR']:>8.1f}{s['avgR']:>8.3f}{s['pf']:>6.2f}"
              f"{s['maxdd']:>7.1f}{s['win']:>6.1f}  {segstr}  ({pos}/{segments})")


if __name__ == "__main__":
    run("XAU", 0.50)
    run("BTC", 18.0)
