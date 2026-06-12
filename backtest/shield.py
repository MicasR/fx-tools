"""
shield.py — the SHIELD half of a shield+sword portfolio (2026-06-12).

Every gold config so far is the same fat-tail / low-win archetype (TP3R+, win
22-36%).  A SHIELD is the opposite return distribution: tight exit, HIGH win%,
tiny DD.  Its job in the two-account model isn't profit -- it's to lower the
PORTFOLIO drawdown so the sword's risk fraction can scale up (geometric lesson:
smoothness compounds).  Genuinely uncorrelated with the swords by construction.

Single-position, R-space (lot = 1/rng so 1R move = 1.0), base = H1 V-pattern
breakout, structural 1R stop.  Knobs:
  tp_R       -> fixed take-profit (R).  0 = none.
  be_R       -> after +be_R favorable, move stop to break-even ("free trade").
  trail_act  -> after +trail_act favorable, engage a gb_R chandelier trail.
Exits net of real spread (COST/rng in R).  Streams plug into concurrent_geo.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import SPECS, h1_events


def run_shield(sym="XAU", tf="M15", tp_R=2.0, be_R=0.0, trail_act=0.0, gb_R=2.5):
    sp = SPECS[sym]; COST = sp["cost"]
    m = pd.read_csv(glob.glob(f"data/*{sym}*_{tf}.csv")[0], parse_dates=["time"]).reset_index(drop=True)
    tm = m["time"].to_numpy()
    H, L, C = (m[c].to_numpy() for c in ("high", "low", "close"))
    n = len(m)
    evs = h1_events(sym, m["time"].iloc[0])
    ev_at = {}
    for e in evs:
        j = int(np.searchsorted(tm, np.datetime64(e[0])))
        if 0 <= j < n:
            ev_at.setdefault(j, []).append(e)

    ops, op = [], None
    for k in range(n):
        if op is not None:
            dd, e0, r0 = op["dir"], op["e0"], op["r0"]
            op["ext"] = max(op["ext"], H[k]) if dd == 1 else min(op["ext"], L[k])
            fav = dd * ((H[k] if dd == 1 else L[k]) - e0) / r0
            if be_R > 0 and fav >= be_R:
                op["stop"] = max(op["stop"], e0) if dd == 1 else min(op["stop"], e0)
            if trail_act > 0 and fav >= trail_act:
                tl = op["ext"] - dd * gb_R * r0
                op["stop"] = max(op["stop"], tl) if dd == 1 else min(op["stop"], tl)
            sl_hit = (L[k] <= op["stop"]) if dd == 1 else (H[k] >= op["stop"])
            tp = e0 + dd * tp_R * r0
            tp_hit = tp_R > 0 and ((H[k] >= tp) if dd == 1 else (L[k] <= tp))
            if sl_hit:                                   # pessimistic: stop before TP
                ops.append((op["t0"], tm[k], dd * (op["stop"] - e0) / r0 - COST / r0))
                op = None
            elif tp_hit:
                ops.append((op["t0"], tm[k], tp_R - COST / r0))
                op = None
        if op is None:
            for e in ev_at.get(k, []):
                dd, entry, sl, rng = e[1], e[2], e[3], e[4]
                if rng <= 0:
                    continue
                op = dict(dir=dd, e0=entry, r0=rng, ext=entry, stop=sl, t0=tm[k])
                break
    if op is not None:
        dd = op["dir"]
        ops.append((op["t0"], tm[-1], dd * (C[n-1] - op["e0"]) / op["r0"] - COST / op["r0"]))
    return ops, tm[0], tm[-1]


def stats(ops, t0, t1):
    R = np.array([o[2] for o in ops]) if ops else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    span = (t1 - t0) / 6
    seg = [0.0] * 6
    for to, _, r in ops:
        seg[min(5, int((to - t0) / span))] += r
    tot = R.sum()
    return dict(n=len(R), tot=tot, avg=R.mean(), win=100*np.mean(R > 0),
                pf=(w/l if l > 0 else 9.99), dd=dd, rf=(tot/dd if dd > 0 else 0),
                seg=seg, rob=sum(1 for s in seg if s > 0))


CANDS = [
    ("TP1.5",          dict(tp_R=1.5)),
    ("TP2.0",          dict(tp_R=2.0)),
    ("TP2.5",          dict(tp_R=2.5)),
    ("TP3.0 (ref)",    dict(tp_R=3.0)),
    ("BE@1 + TP2",     dict(tp_R=2.0, be_R=1.0)),
    ("BE@1 + TP2.5",   dict(tp_R=2.5, be_R=1.0)),
    ("BE@1 + TP3",     dict(tp_R=3.0, be_R=1.0)),
    ("BE@0.5 + TP2",   dict(tp_R=2.0, be_R=0.5)),
    ("BE@1 + trail2.5",dict(tp_R=0.0, be_R=1.0, trail_act=1.0, gb_R=2.5)),
    ("trail2.5 only",  dict(tp_R=0.0, trail_act=0.5, gb_R=2.5)),
]

if __name__ == "__main__":
    print(f"=== SHIELD candidates (gold M15, net spread) ===")
    print(f"{'shield':<18}{'ops':>5}{'totR':>8}{'avgR':>7}{'win%':>6}{'PF':>6}{'maxDD':>7}"
          f"{'RF':>6}{'segs':>6}   per-segment R")
    for lbl, kw in CANDS:
        ops, t0, t1 = run_shield(**kw)
        s = stats(ops, t0, t1)
        segs = " ".join(f"{x:+6.1f}" for x in s["seg"])
        print(f"{lbl:<18}{s['n']:>5}{s['tot']:>8.1f}{s['avg']:>7.2f}{s['win']:>6.1f}{s['pf']:>6.2f}"
              f"{s['dd']:>7.1f}{s['rf']:>6.1f}   {s['rob']}/6   {segs}")
