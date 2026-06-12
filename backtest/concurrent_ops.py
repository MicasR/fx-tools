"""
concurrent_ops.py — TWO operations-accounts in parallel (user's idea, 2026-06-12).

Drop one-at-a-time at the PORTFOLIO level: instead of one 1R ops-account on one
config, run TWO 0.5R ops-accounts, each its own config, feeding ONE Main account.
run_tf stakes a fixed fraction of cap0 (not geometric), so the two accounts are
independent fixed-stake streams -> joint Main growth = each config run at
risk_frac=0.005, merged.  Each 0.5R op contributes x0.5 in the champions' 1%-of-
capital R units, so combined totR is directly comparable to the 1R champions.

Thesis: geo1.7's profit is in seg2, geofloor's in seg3 -> combining at half size
should SMOOTH the curve (lower DD / concentration) at the same 1R total exposure.

Combos tested:  1) geo1.7 + f5/s210 1.5%   2) geo1.7 + f5/s200
Judged on stress@$0.40, segmented by TIME (configs have different SMA warmups).
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf
from stress_audit import op_gap

BASE = dict(sym="XAU", tf="M15", triggers=("bounce",), unit="base",
            prog_step=1.7, lev=2000.0)
CFG = {
    "geo1.7":      dict(smaP=7, slowP=0,   sizing="proggeo", mult=0.01),
    "f5/s210 1.5%":dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015),
    "f5/s200":     dict(smaP=5, slowP=200, sizing="geofloor", mult=0.01),
}
HDR = (f"{'config / combo':<30}{'thr$':>5}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}"
       f"{'PF':>6}{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R (by time)")


def frame_for(c):
    m = pd.read_csv(glob.glob("data/*XAU*_M15.csv")[0], parse_dates=["time"])
    m["sma"] = m["close"].rolling(c["smaP"]).mean()
    if c["slowP"]:
        m["slow"] = m["close"].rolling(c["slowP"]).mean()
    return m.dropna().reset_index(drop=True)


def stream(name, risk):
    """Run one config at `risk`; return per-op (t0, t1, R, gap) in own-stake units."""
    c = CFG[name]
    m = frame_for(c)
    H, L = m["high"].to_numpy(), m["low"].to_numpy()
    tm = m["time"].to_numpy()
    ops, _, _, n = run_tf(smaP=c["smaP"], slowP=c["slowP"], sizing=c["sizing"],
                          mult=c["mult"], risk_frac=risk, **BASE)
    out = []
    for o in ops:
        g = op_gap(o, H, L) if o[2] > 0 else None
        out.append((tm[o[0]], tm[o[1]], o[2], g))
    return out, tm[0], tm[-1]


def stats(legs, thr, t0, t1):
    """legs = list of (stream, weight); combine in 1%-units, stress-flip, score."""
    rows = []          # (t_open, t_close, contribution)
    for s, w in legs:
        for to, tc, R, g in s:
            r = -1.0 if (R > 0 and g is not None and g < thr) else R
            rows.append((to, tc, w * r, R if r > 0 else -1.0))
    contrib = np.array([x[2] for x in rows])
    w_, l_ = contrib[contrib > 0].sum(), -contrib[contrib <= 0].sum()
    cum = peak = dd = 0.0
    for x in sorted(rows, key=lambda x: x[1]):
        cum += x[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    span = (t1 - t0) / 6
    seg = [0.0] * 6
    for to, tc, ct, _ in rows:
        i = min(5, int((to - t0) / span))
        seg[i] += ct
    tot = contrib.sum()
    return dict(n=len(rows), tot=tot, avg=contrib.mean(), win=100*np.mean(contrib > 0),
                pf=(w_/l_ if l_ > 0 else 9.99), dd=dd, rf=(tot/dd if dd > 0 else 0),
                seg=seg, rob=sum(1 for s in seg if s > 0),
                oneop=(contrib.max()/tot*100 if tot > 0 else 0))


def row(lbl, thr, s):
    segs = " ".join(f"{x:+7.1f}" for x in s["seg"])
    print(f"{lbl:<30}{thr:>5.2f}{s['n']:>5}{s['tot']:>9.1f}{s['avg']:>7.2f}{s['win']:>6.1f}"
          f"{s['pf']:>6.2f}{s['dd']:>7.1f}{s['rf']:>7.1f}   {s['rob']}/6{s['oneop']:>5.0f}%  {segs}")


if __name__ == "__main__":
    print(HDR)
    # full-1R streams (benchmarks) and half-0.5R streams (combo legs) + time spans
    S1, S5, span = {}, {}, {}
    for nm in CFG:
        S1[nm], a, b = stream(nm, 0.01)                # 1%-units directly
        S5[nm], _, _ = stream(nm, 0.005)               # 0.5%-units -> x0.5
        span[nm] = (a, b)

    print("--- champions solo @1R (benchmarks to beat) ---")
    for nm in ("geo1.7", "f5/s210 1.5%", "f5/s200"):
        t0, t1 = span[nm]
        for thr in (0.0, 0.40):
            row(f"{nm} @1R", thr, stats([(S1[nm], 1.0)], thr, t0, t1))

    combos = [("COMBO1 geo1.7 + s210", ["geo1.7", "f5/s210 1.5%"]),
              ("COMBO2 geo1.7 + s200", ["geo1.7", "f5/s200"])]
    print("\n--- combos: two 0.5R accounts, one Main (1%-units) ---")
    for lbl, names in combos:
        t0 = min(span[n][0] for n in names); t1 = max(span[n][1] for n in names)
        legs = [(S5[n], 0.5) for n in names]           # 0.5R each -> x0.5 weight
        for thr in (0.0, 0.40):
            row(lbl, thr, stats(legs, thr, t0, t1))
