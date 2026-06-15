"""Sweep the prom-date team's capital WEIGHTS (equal -> optimized) and show the lift."""
import numpy as np
import promdate as P

BUDGET = 0.24

MAXCORR = 0.5   # diversity guard: reject a dancer >this weekly corr with a team member

for cap, maxn in ((40, 6), (50, 6)):
    pool = P.load_pool(max_oneop=cap)
    sel, combined_eq, g_eq = P.promdate(pool, budget=BUDGET, maxn=maxn, max_corr=MAXCORR, verbose=False)
    w, combined_w, g_w = P.weight_optimize(pool, sel, budget=BUDGET)
    walloc = w / w.sum()                                  # capital allocation %

    print(f"\n############ 1op cap {cap}%  —  {len(sel)} dancers ############")
    print(f"{'dancer':<11}{'sz':>3}{'sma':>4}{'slow':>5}{'step':>5}{'tpR':>5}{'trR':>4}{'half':>5}"
          f"{'nbpR':>7}{'seg':>4}{'1op':>5}{'  EQwt':>7}{'OPTwt':>7}")
    for r, i in enumerate(sel):
        row = pool.iloc[i]
        print(f"{row['leg']:<11}{int(row['sizing']):>3}{int(row['smaP']):>4}{int(row['slowP']):>5}"
              f"{row['step']:>5.2f}{row['tpR']:>5.2f}{row['trailR']:>4.1f}{row['half']:>5.1f}"
              f"{row['nbpR']:>7.1f}{int(row['segpos']):>3}/6{row['oneop']:>4.0f}%"
              f"{1.0/len(sel):>7.1%}{walloc[r]:>7.1%}")
    segp_eq, segs_eq = P.seg_robust(combined_eq)
    segp_w, segs_w = P.seg_robust(combined_w)
    _, f_eq = P.growth_at_dd(combined_eq, BUDGET)
    _, f_w = P.growth_at_dd(combined_w, BUDGET)
    print(f"  EQUAL  weights: growth@{int(BUDGET*100)}%DD = {g_eq:7.2f}x  f={f_eq:.3f}  segs {segp_eq}/6  "
          + " ".join(f"{s:+.0f}" for s in segs_eq))
    print(f"  SWEPT  weights: growth@{int(BUDGET*100)}%DD = {g_w:7.2f}x  f={f_w:.3f}  segs {segp_w}/6  "
          + " ".join(f"{s:+.0f}" for s in segs_w))
    print(f"  weight sweep lift: +{100*(g_w/g_eq-1):.0f}%")
