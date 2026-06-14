"""
promdate.py — the "PROM DATE" portfolio selector (FIDELITY §3.6).

Pick a TEAM of candidate EAs (optimizer passes) that lift each other on bad weeks.
Each candidate carries its tester-true WEEKLY performance vector (NBP-clamped R, the
common calendar clock). We greedily build a team: start from the best single dancer,
then repeatedly add the candidate that most improves the COMBINED geometric
growth-at-matched-DD (= "who lifts it on bad times"). Generalizes shield/sword to N
members across instruments; rejects correlated twins automatically (a twin adds vol,
not decorrelation, so it doesn't lift growth-at-matched-DD).

  pool = load_pool("out/opt/pool_*.csv")
  team = promdate(pool, budget=0.24, maxn=6)

Each EA = its own 1R-per-op ops-account; the portfolio weekly R = (weighted) sum of
members' weekly R, compounded at the risk fraction f that pins maxDD to `budget`.
Growth multiple at that f = the ranking metric (matches the king memory's
growth-at-matched-DD).
"""
import glob
import numpy as np
import pandas as pd

WCOLS = [f"w{i}" for i in range(130)]
META = ["leg", "sym", "nbpR", "segpos", "rf", "oneop", "ops", "win",
        "sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half"]


def load_pool(pattern="out/opt/pool_*.csv", min_ops=30, min_nbpR=5.0):
    dfs = [pd.read_csv(f) for f in glob.glob(pattern)]
    if not dfs:
        raise FileNotFoundError(pattern)
    df = pd.concat(dfs, ignore_index=True)
    df = df[(df["ops"] >= min_ops) & (df["nbpR"] >= min_nbpR)].copy()
    # drop exact duplicate strategies (same leg+params) keeping the best score
    keyc = ["leg", "sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half"]
    df = df.sort_values("score", ascending=False).drop_duplicates(keyc).reset_index(drop=True)
    return df


def W(df):
    return df[WCOLS].to_numpy(dtype=float)


def growth_at_dd(r, budget=0.24, fmax=10.0, iters=64):
    """Max geometric growth multiple of the weekly-R series `r` when the risk fraction
    f is scaled so the compounded equity's max drawdown == budget. Returns (mult, f)."""
    def maxdd(f):
        g = 1.0 + f * r
        if np.any(g <= 0):
            return 1e9, 0.0
        eq = np.cumprod(g)
        dd = 1.0 - eq / np.maximum.accumulate(eq)
        return dd.max(), eq[-1]
    lo, hi = 0.0, fmax
    for _ in range(iters):
        f = 0.5 * (lo + hi)
        dd, _ = maxdd(f)
        if dd > budget:
            hi = f
        else:
            lo = f
    dd, mult = maxdd(lo)
    return (mult if dd <= budget * 1.001 else 1.0), lo


def seg_robust(r, nseg=6):
    q = len(r) // nseg
    segs = [r[k * q:(len(r) if k == nseg - 1 else (k + 1) * q)].sum() for k in range(nseg)]
    return sum(1 for s in segs if s > 0), segs


def promdate(df, budget=0.24, maxn=6, verbose=True):
    Wm = W(df)
    n = len(df)
    sel, combined, cur = [], np.zeros(Wm.shape[1]), 1.0
    while len(sel) < maxn:
        best_i, best_g, best_f = -1, cur, 0.0
        for i in range(n):
            if i in sel:
                continue
            g, f = growth_at_dd(combined + Wm[i], budget)
            if g > best_g + 1e-9:
                best_g, best_i, best_f = g, i, f
        if best_i < 0:
            break
        sel.append(best_i); combined = combined + Wm[best_i]; cur = best_g
        if verbose:
            row = df.iloc[best_i]
            segp, _ = seg_robust(combined)
            print(f"  +{len(sel)}: {row['leg']:<11} sz{int(row['sizing'])} sma{int(row['smaP'])} "
                  f"slow{int(row['slowP'])} step{row['step']:.2f} tp{row['tpR']:.2f} tr{row['trailR']:.2f} "
                  f"half{row['half']:.1f} | legNbpR={row['nbpR']:6.1f} legSeg={int(row['segpos'])}/6 "
                  f"|| TEAM growth@{int(budget*100)}%DD={best_g:6.2f}x f={best_f:.3f} teamSeg={segp}/6")
    return sel, combined, cur


def weight_optimize(df, sel, budget=0.24, rounds=40, step=0.25):
    """Coordinate-ascent on per-member capital weights to maximize growth-at-matched-DD.
    Starts equal-weight (each = 1 ops-account). Weights are relative capital allocations."""
    Wm = W(df)
    mem = [Wm[i] for i in sel]
    w = np.ones(len(sel))

    def obj(w):
        return growth_at_dd(sum(wi * mi for wi, mi in zip(w, mem)), budget)[0]

    best = obj(w)
    for _ in range(rounds):
        improved = False
        for i in range(len(w)):
            for d in (1 + step, 1 / (1 + step)):
                w2 = w.copy(); w2[i] *= d
                w2 = w2 / w2.mean()                      # keep scale ~1 (compounding handles total)
                g = obj(w2)
                if g > best + 1e-9:
                    best, w, improved = g, w2, True
        if not improved:
            break
    combined = sum(wi * mi for wi, mi in zip(w, mem))
    return w, combined, best


def report(df, sel, combined, budget=0.24):
    g, f = growth_at_dd(combined, budget)
    segp, segs = seg_robust(combined)
    print(f"\n=== PROM-DATE TEAM ({len(sel)}) — growth@{int(budget*100)}%DD = {g:.2f}x  (f={f:.3f}) ===")
    print(f"  team 6-seg: {segp}/6   " + " ".join(f"{s:+.1f}" for s in segs))
    # member weekly correlations to the rest of the team (lower = better complement)
    Wm = W(df)
    for r, i in enumerate(sel):
        others = combined - Wm[i]
        c = np.corrcoef(Wm[i], others)[0, 1] if others.any() else 0.0
        row = df.iloc[i]
        print(f"   {row['leg']:<11} corr_to_rest={c:+.2f}  nbpR={row['nbpR']:6.1f} seg={int(row['segpos'])}/6 "
              f"1op={row['oneop']:.0f}%")
    return g, f


def compare_instruments(pool, budget=0.24, maxn=6):
    """The 'BTC helps gold and vice versa' check: the pool is ONE instrument-agnostic
    bag, so the greedy can pick a gold+BTC mix. Show that the MIXED team beats the best
    single-instrument team at matched DD (cross-instrument time-decorrelation = the lift)."""
    gold = pool[pool["sym"].astype(str).str.startswith("XAU")].reset_index(drop=True)
    btc = pool[pool["sym"].astype(str).str.startswith("BTC")].reset_index(drop=True)
    gg = promdate(gold, budget, maxn, verbose=False)[2] if len(gold) else 1.0
    gb = promdate(btc, budget, maxn, verbose=False)[2] if len(btc) else 1.0
    sel, combined, gm = promdate(pool, budget, maxn, verbose=False)
    base = max(gg, gb)
    print(f"\n=== cross-instrument lift (growth@{int(budget*100)}%DD) ===")
    print(f"  gold-only team : {gg:6.2f}x")
    print(f"  btc-only  team : {gb:6.2f}x")
    print(f"  MIXED team     : {gm:6.2f}x   (+{100*(gm/base-1):.0f}% vs best single-instrument)")
    mix = pool.iloc[sel]["sym"].astype(str).str[:3].value_counts().to_dict()
    print(f"  mixed team composition: {mix}")
    return sel, combined, gm


if __name__ == "__main__":
    pool = load_pool()
    print(f"pool: {len(pool)} candidates from {pool['leg'].nunique()} legs "
          f"({pool['sym'].astype(str).str[:3].value_counts().to_dict()})")
    print("\n--- greedy team build (cross-instrument pool) ---")
    sel, combined, _ = promdate(pool, budget=0.24, maxn=6)
    report(pool, sel, combined, budget=0.24)
    compare_instruments(pool, budget=0.24, maxn=6)
