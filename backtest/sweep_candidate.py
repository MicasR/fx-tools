"""
sweep_candidate.py — final tuning of the leading candidate geofloor f5/s200 TP3
@1:2000 (gold M15).  Three axes in order, each judged on the SPREAD-STRESS@$0.40
exam (flip every winner whose closest gap to the line was < $0.40), best carried
forward:  A. geo ratio g  ->  B. slow SMA fine grid  ->  C. base-fraction start.
Every config shown heads (thr 0) + stressed (thr 0.40).  Champion row included.
Metrics include avgR/op per standing rule.
"""
import numpy as np
from pyramid_engine import run_tf
from stress_audit import op_gap, frame

HDR = (f"{'variant':<26}{'thr$':>5}{'ops':>5}{'totR':>9}{'avgR':>7}{'win%':>6}{'PF':>6}"
       f"{'maxDD':>7}{'RF':>7}{'segs':>6}{'1op':>6}   per-segment R")


def stats(ops, gaps, n, thr):
    ops = [list(o) for o in ops]
    for o, g in zip(ops, gaps):
        if o[2] > 0 and g is not None and g < thr:
            o[2], o[4] = -1.0, "SL*"
    R = np.array([o[2] for o in ops])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    q = n // 6
    seg = [sum(o[2] for o in ops if k * q <= o[0] < (n if k == 5 else (k + 1) * q))
           for k in range(6)]
    tot = R.sum()
    return dict(n=len(R), tot=tot, avg=R.mean(), win=100 * np.mean(R > 0),
                pf=(w / l if l > 0 else 9.99), dd=dd, rf=(tot / dd if dd > 0 else 0),
                seg=seg, rob=sum(1 for t in seg if t > 0),
                oneop=(R.max() / tot * 100 if tot > 0 else 0))


def row(lbl, thr, s):
    segs = " ".join(f"{x:+7.1f}" for x in s["seg"])
    print(f"{lbl:<26}{thr:>5.2f}{s['n']:>5}{s['tot']:>9.1f}{s['avg']:>7.2f}{s['win']:>6.1f}"
          f"{s['pf']:>6.2f}{s['dd']:>7.1f}{s['rf']:>7.1f}   {s['rob']}/6{s['oneop']:>5.0f}%  {segs}")


def run_cfg(fast, slow, g, mult):
    m = frame(fast, slow)
    H, L = m["high"].to_numpy(), m["low"].to_numpy()
    ops, _, _, n = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=fast,
                          sizing="geofloor", slowP=slow, unit="base", mult=mult,
                          prog_step=g, lev=2000.0)
    gaps = [op_gap(o, H, L) if o[2] > 0 else None for o in ops]
    return ops, gaps, n


def show(lbl, cfg, results):
    ops, gaps, n = run_cfg(*cfg)
    s0, s4 = stats(ops, gaps, n, 0.0), stats(ops, gaps, n, 0.40)
    row(lbl, 0.0, s0)
    row(lbl, 0.40, s4)
    results[cfg] = s4
    return s4


def best(results):
    ok = {c: s for c, s in results.items() if s["rob"] == 6}
    pool = ok if ok else results
    return max(pool, key=lambda c: pool[c]["tot"])


if __name__ == "__main__":
    print(HDR)
    m = frame(7, 0)
    H, L = m["high"].to_numpy(), m["low"].to_numpy()
    ops, _, _, n = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7,
                          sizing="proggeo", unit="base", mult=0.01, prog_step=1.7,
                          lev=2000.0)
    gaps = [op_gap(o, H, L) if o[2] > 0 else None for o in ops]
    row("champion geo1.7", 0.0, stats(ops, gaps, n, 0.0))
    row("champion geo1.7", 0.40, stats(ops, gaps, n, 0.40))

    print("\n=== A. geo ratio g (f5/s200, 1% base) ===")
    res = {}
    for g in (1.5, 1.6, 1.7, 1.8, 2.0):
        show(f"g{g}", (5, 200, g, 0.01), res)
    bg = best(res)[2]
    print(f"--> best g = {bg}")

    print(f"\n=== B. slow fine grid (f5, g{bg}, 1% base) ===")
    res = {}
    for slow in (180, 190, 200, 210, 220):
        show(f"s{slow}", (5, slow, bg, 0.01), res)
    bs = best(res)[1]
    print(f"--> best slow = {bs}")

    print(f"\n=== C. base-fraction start (f5/s{bs}, g{bg}) ===")
    res = {}
    for mult in (0.005, 0.0075, 0.01, 0.015, 0.02):
        show(f"start {mult*100:.2f}%", (5, bs, bg, mult), res)
    bm = best(res)[3]
    print(f"--> best start = {bm*100:.2f}%")
    print(f"\nFINAL: geofloor f5/s{bs} g{bg} start {bm*100:.2f}% TP3 @1:2000")
