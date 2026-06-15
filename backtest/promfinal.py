"""Final prom-date team on the (densified) pool: diversity-guarded greedy + weight
sweep, with the per-instrument capital split and the team's equity fingerprint."""
import numpy as np
import promdate as P

BUDGET = 0.24


def build(cap, maxn, max_corr):
    pool = P.load_pool(max_oneop=cap)
    sel, comb_eq, g_eq = P.promdate(pool, budget=BUDGET, maxn=maxn, max_corr=max_corr, verbose=False)
    w, comb_w, g_w = P.weight_optimize(pool, sel, budget=BUDGET)
    return pool, sel, w, comb_w, g_eq, g_w


def show(tag, pool, sel, w, comb_w, g_eq, g_w):
    walloc = w / w.sum()
    print(f"\n############ {tag}  —  {len(sel)} dancers ############")
    print(f"{'dancer':<11}{'sym':>4}{'sz':>3}{'sma':>4}{'slow':>5}{'step':>5}{'tpR':>5}{'trR':>4}"
          f"{'half':>5}{'nbpR':>7}{'seg':>4}{'1op':>5}{'wt%':>6}")
    gold_w = btc_w = 0.0
    for r, i in enumerate(sel):
        row = pool.iloc[i]
        a = walloc[r]
        if str(row['sym']).startswith('XAU'): gold_w += a
        else: btc_w += a
        print(f"{row['leg']:<11}{str(row['sym'])[:3]:>4}{int(row['sizing']):>3}{int(row['smaP']):>4}"
              f"{int(row['slowP']):>5}{row['step']:>5.2f}{row['tpR']:>5.2f}{row['trailR']:>4.1f}"
              f"{row['half']:>5.1f}{row['nbpR']:>7.1f}{int(row['segpos']):>3}/6{row['oneop']:>4.0f}%{a:>6.1%}")
    segp, segs = P.seg_robust(comb_w)
    _, f = P.growth_at_dd(comb_w, BUDGET)
    print(f"  split: GOLD {gold_w:.0%} / BTC {btc_w:.0%}   growth@24%DD = {g_w:.2f}x (equal {g_eq:.2f}x)"
          f"  f={f:.3f}  segs {segp}/6")
    print("  per-seg: " + " ".join(f"{s:+.0f}" for s in segs))


if __name__ == "__main__":
    pool0 = P.load_pool()
    print(f"DENSE POOL: {len(pool0)} candidates  {pool0['sym'].astype(str).str[:3].value_counts().to_dict()}")
    for cap in (40, 50):
        for mc in (0.5, 0.35):
            pool, sel, w, comb_w, g_eq, g_w = build(cap, 6, mc)
            show(f"1op<{cap}%  corr<{mc}", pool, sel, w, comb_w, g_eq, g_w)
