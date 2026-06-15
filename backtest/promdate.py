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
META = ["leg", "sym", "nbpR", "segpos", "rf", "oneop", "extop1R", "nmonster", "ops", "win",
        "sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half",
        "addtrig", "lineplace", "nback", "buffer"]

# §3.6-REDUX archetype/aggression knobs + championship metrics (filled if absent).
REDUX_COLS = {"extop1R": np.nan, "nmonster": 0, "addtrig": 0, "lineplace": 0,
              "nback": 0, "buffer": 0.0, "segpos_ex3": np.nan, "h1R": np.nan, "h2R": np.nan}


def arch_tag(row):
    """Short archetype label: trigger / line-placement / buffer."""
    trig = "pc" if int(row.get("addtrig", 0)) == 1 else "bo"          # poscandle / bounce
    lp = {0: "ml", 1: f"nb{int(row.get('nback', 0))}", 2: "pp"}.get(int(row.get("lineplace", 0)), "ml")
    return f"{trig}/{lp}/b{row.get('buffer', 0.0):.2f}"


def _leg_retain_ex3wk(df):
    """Fraction of a leg's total weekly R retained after dropping its 3 BIGGEST WEEKS.
    The thesis's 'often enough' made concrete on the weeks/growth dimension that drives
    the float-DD growth mirage: a +881R-in-one-week leg retains ~10% (one event); a genuine
    recurring edge retains most. Computed from the weekly vectors already in the pool."""
    Wm = df[WCOLS].to_numpy(dtype=float)
    tot = Wm.sum(axis=1)
    top3 = np.sort(Wm, axis=1)[:, -3:].sum(axis=1)
    return np.where(tot > 0, (tot - top3) / tot, -1.0)


def load_pool(patterns=("out/opt/pool_*.csv", "out/opt/gold_*.csv", "out/opt/btc_*.csv"),
              min_ops=30, min_nbpR=5.0, min_segpos=4, min_segpos_ex3=4,
              require_both_halves=True, min_leg_retain=0.35):
    """Union of the incumbent pool + the §3.6-REDUX archetype sweeps, filtered to the
    CHAMPIONSHIP QUALIFICATION (user, 2026-06-15 — Option B: aggression is ADMITTED, no
    oneop cap; the most aggressive techniques must compete):
      R0  ops >= min_ops, nbpR >= min_nbpR        (sample size + net-positive)
      R1  segpos >= 4                             (robustness: >=4/6 segments positive)
      R2  segpos_ex3 >= 4                          (low single-trade dependency: still >=4/6
                                                    positive after removing the 3 biggest wins)
      R3  h1R > 0 AND h2R > 0                       (anti-recency: positive in BOTH window halves)
      R4  weekly retain (ex top-3 weeks) >= min_leg_retain  (the thesis's 'often enough':
          the edge can't live in a few weeks -> the dimension that drives the growth mirage)
    The capped -1R downside makes high-compound aggression a bounded-cost asymmetric bet; R2+R4
    replace the blunt oneop cut as principled concentration guards (R2 on ops/segments, R4 on
    weeks/growth). Legacy CSVs lacking a metric skip that rule (NaN -> pass)."""
    files = [f for p in patterns for f in glob.glob(p)]
    if not files:
        raise FileNotFoundError(patterns)
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    for c, default in REDUX_COLS.items():
        if c not in df.columns:
            df[c] = default
    r2 = df["segpos_ex3"].isna() | (df["segpos_ex3"] >= min_segpos_ex3)
    r3 = (~require_both_halves) | (df["h1R"].isna() | (df["h2R"].isna()) |
                                   ((df["h1R"] > 0) & (df["h2R"] > 0)))
    df = df[(df["ops"] >= min_ops) & (df["nbpR"] >= min_nbpR) &
            (df["segpos"] >= min_segpos) & r2 & r3].copy()
    df = df[_leg_retain_ex3wk(df) >= min_leg_retain].reset_index(drop=True)   # R4
    # drop exact duplicate strategies (same leg + full param signature) keeping best score
    keyc = ["leg", "sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half",
            "addtrig", "lineplace", "nback", "buffer"]
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


def robust_growth(r, budget=0.24, drop_top=3):
    """Growth@DD after ZEROING the `drop_top` biggest weeks of the series. This is the
    SELECTION objective (not raw growth): it answers 'high CHANCE of high returns' rather
    than the in-sample peak. A genuine recurring-aggression edge retains most of its growth
    when its best few weeks are stripped; a float-DD-blind mega-stack jackpot (e.g. one
    +881R gold op) collapses -> the greedy won't reach for it. Returns (mult, f)."""
    if drop_top <= 0:
        return growth_at_dd(r, budget)
    r2 = r.copy()
    r2[np.argsort(r2)[-drop_top:]] = 0.0
    return growth_at_dd(r2, budget)


def team_rf(r, drop_top=3):
    """Recovery factor (totR / maxDD) of the weekly R series, AFTER zeroing the top-`drop_top`
    weeks (RF is also jackpot-inflatable: a monster week lifts totR with zero DD cost). RF is
    scale-invariant (f cancels) -> ranks DRAWDOWN EFFICIENCY, not size. Returns (rf, 0.0)."""
    r2 = r.copy()
    if drop_top > 0:
        r2[np.argsort(r2)[-drop_top:]] = 0.0
    cum = np.cumsum(r2)
    dd = (np.maximum.accumulate(cum) - cum).max()
    return (cum[-1] / dd if dd > 1e-9 else 0.0), 0.0


def seg_robust(r, nseg=6):
    q = len(r) // nseg
    segs = [r[k * q:(len(r) if k == nseg - 1 else (k + 1) * q)].sum() for k in range(nseg)]
    return sum(1 for s in segs if s > 0), segs


def _corr(a, b):
    if not a.any() or not b.any():
        return 0.0
    sa, sb = a.std(), b.std()
    if sa == 0 or sb == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def promdate(df, budget=0.24, maxn=6, max_corr=1.0, drop_top=3, objective="growth", verbose=True):
    """Greedy team build. SELECTION objective:
       "growth" = robust_growth (growth@DD after dropping the `drop_top` biggest weeks) — max
                  CHANCE of high returns, not a jackpot-inflatable in-sample peak.
       "rf"     = team_rf (recovery factor, ex-top-`drop_top` weeks) — DRAWDOWN EFFICIENCY first;
                  surfaces lower-DD teams whose legs cover each other's bad stretches.
    max_corr < 1 = DIVERSITY GUARD (reject a dancer correlating > max_corr with a member)."""
    obj = team_rf if objective == "rf" else (lambda r, *_: robust_growth(r, budget, drop_top))
    Wm = W(df)
    n = len(df)
    sel, combined, cur = [], np.zeros(Wm.shape[1]), (0.0 if objective == "rf" else 1.0)
    while len(sel) < maxn:
        best_i, best_g, best_f = -1, cur, 0.0
        for i in range(n):
            if i in sel:
                continue
            if max_corr < 1.0 and any(_corr(Wm[i], Wm[j]) > max_corr for j in sel):
                continue                                  # too correlated with a member -> skip
            g, f = obj(combined + Wm[i], drop_top)
            if g > best_g + 1e-9:
                best_g, best_i, best_f = g, i, f
        if best_i < 0:
            break
        sel.append(best_i); combined = combined + Wm[best_i]; cur = best_g
        if verbose:
            row = df.iloc[best_i]
            segp, _ = seg_robust(combined)
            print(f"  +{len(sel)}: {row['sym'][:3]} {arch_tag(row):<10} sma{int(row['smaP'])} "
                  f"slow{int(row['slowP'])} step{row['step']:.2f} tp{row['tpR']:.2f} tr{row['trailR']:.2f} "
                  f"half{row['half']:.1f} | legNbpR={row['nbpR']:6.1f} legSeg={int(row['segpos'])}/6 "
                  f"extop1R={row['extop1R']:6.1f} | TEAM robustG@{int(budget*100)}%DD={best_g:6.2f}x "
                  f"f={best_f:.3f} teamSeg={segp}/6")
    return sel, combined, cur


def weight_optimize(df, sel, budget=0.24, steps=(0.5, 0.25, 0.1, 0.05, 0.02)):
    """Multi-resolution coordinate-ascent on per-member capital weights to maximize
    growth-at-matched-DD. Starts equal-weight. Weights = relative capital allocations
    (scale is free -- the compounding fraction f absorbs total size)."""
    Wm = W(df)
    mem = [Wm[i] for i in sel]
    w = np.ones(len(sel))

    def obj(w):
        return growth_at_dd(sum(wi * mi for wi, mi in zip(w, mem)), budget)[0]

    best = obj(w)
    for step in steps:                              # coarse -> fine
        for _ in range(60):
            improved = False
            for i in range(len(w)):
                for d in (1 + step, 1 / (1 + step)):
                    w2 = w.copy(); w2[i] *= d
                    w2 = w2 / w2.mean()
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
        print(f"   {row['sym'][:3]} {arch_tag(row):<10} corr_to_rest={c:+.2f}  nbpR={row['nbpR']:6.1f} "
              f"seg={int(row['segpos'])}/6 extop1R={row['extop1R']:6.1f} nmon={int(row['nmonster'])} "
              f"1op={row['oneop']:.0f}%")
    return g, f


def team_robustness(combined, budget=0.24, drop=5, nboot=1000, seed=0):
    """Team-level backstop (analogue of leg-rule R2): the team's growth@DD must not hinge on
    a handful of monster WEEKS. Reports:
      - g_ex_top / retain : growth@DD after zeroing the `drop` biggest weeks (vs base)
      - team segpos + both-halves (R1/R3 at team level)
      - bootstrap: resample weeks with replacement -> median & 5th-pct growth@DD
        (P05 = a conservative 'bad-luck' growth; tests dependence on which weeks landed)."""
    base = growth_at_dd(combined, budget)[0]
    c2 = combined.copy()
    c2[np.argsort(c2)[-drop:]] = 0.0
    g_ex = growth_at_dd(c2, budget)[0]
    segp, _ = seg_robust(combined)
    h = len(combined) // 2
    rng = np.random.default_rng(seed)
    n = len(combined)
    gs = np.array([growth_at_dd(combined[rng.integers(0, n, n)], budget)[0] for _ in range(nboot)])
    return dict(base=base, g_ex_top=g_ex, retain=(g_ex / base if base > 0 else 0.0),
                segpos=segp, h1=float(combined[:h].sum()), h2=float(combined[h:].sum()),
                boot_median=float(np.median(gs)), boot_p05=float(np.percentile(gs, 5)))


def print_robustness(combined, budget=0.24, drop=5):
    r = team_robustness(combined, budget, drop)
    print(f"\n  --- team robustness backstop ---")
    print(f"  growth@DD base={r['base']:.1f}x  ex-top{drop}-weeks={r['g_ex_top']:.1f}x "
          f"(retain {100*r['retain']:.0f}%)  teamSeg={r['segpos']}/6  h1={r['h1']:+.0f} h2={r['h2']:+.0f}")
    print(f"  bootstrap-over-weeks: median={r['boot_median']:.1f}x  p05(bad-luck)={r['boot_p05']:.1f}x")
    return r


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
