"""$1000 money report + equity graph for the crowned PD2 robust team.
Uses the REPRODUCED per-leg weekly NBP-R vectors (out/opt/fin_*.csv). Compounds each op
at a fixed risk fraction f (per leg per op): equity_{t+1} = equity_t * (1 + f * weeklyR_t).
Compares f=1% vs f=2%. Per-leg = that leg alone on $1000 @ f; combined = the pooled team.
Outputs an MT5-style report (console) + out/pd2_equity.png (per-leg + combined, segment vlines)."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import promdate as p

WCOLS = [f"w{i}" for i in range(130)]
DEP = 1000.0
FS = [0.01, 0.02]

pool = p.load_pool()
sel, _, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=1.0, drop_top=3, verbose=False)
team = pool.iloc[sel].reset_index(drop=True)

# reproduced weekly vectors from the finalist single-pass CSVs (fallback: pool vector)
labels, vecs = [], []
for i, r in team.iterrows():
    xau = str(r["sym"]).startswith("XAU")
    style = ("Trail" if r["trailR"] > 0 else ("Pin" if int(r["lineplace"]) == 2 else
             ("Nb" if int(r["lineplace"]) == 1 else "Geo")))
    labels.append(f"{'Gold' if xau else 'BTC'}-{style}(sma{int(r['smaP'])})")
    try:
        f = pd.read_csv(f"out/opt/fin_{i}.csv")
        f = f[f["smaP"] == int(r["smaP"])].sort_values("nbpR", ascending=False).iloc[0]
        vecs.append(np.array([f[c] for c in WCOLS], float))
    except Exception:
        vecs.append(np.array([r[c] for c in WCOLS], float))
vecs = np.array(vecs)
combined = vecs.sum(axis=0)
nseg = 6
q = len(combined) // nseg
seg_bounds = [k * q for k in range(1, nseg)]


def equity(series, f):
    g = 1.0 + f * series
    ruin = np.any(g <= 0)
    eq = DEP * np.cumprod(np.maximum(g, 1e-9))
    return eq, ruin


def mt5_report(series, f):
    eq, ruin = equity(series, f)
    bal = np.concatenate([[DEP], eq])
    chg = np.diff(bal)
    gp, gl = chg[chg > 0].sum(), -chg[chg < 0].sum()
    peak = np.maximum.accumulate(bal)
    dd = peak - bal
    ddpct = dd / peak
    net = bal[-1] - DEP
    wks = len(series)
    yrs = wks / 52.0
    cagr = (bal[-1] / DEP) ** (1 / yrs) - 1 if bal[-1] > 0 else -1
    return dict(final=bal[-1], net=net, netpct=100 * net / DEP, gp=gp, gl=gl,
                pf=(gp / gl if gl > 0 else float("inf")), maxdd_pct=100 * ddpct.max(),
                maxdd_cash=dd.max(), rf=(net / dd.max() if dd.max() > 0 else float("inf")),
                win_wk=100 * (chg > 0).mean(), wks=wks, cagr=100 * cagr, ruin=ruin)


print("=" * 70)
print(f"  CROWNED PD2 TEAM — $1000 MT5-STYLE REPORT  (pooled, NBP, ~{len(combined)/52:.1f}yr)")
print("=" * 70)
for f in FS:
    r = mt5_report(combined, f)
    print(f"\n--- f = {f*100:.0f}% per leg per op {'  *** RUIN (a week wiped the account) ***' if r['ruin'] else ''}")
    print(f"  Initial deposit      {DEP:>12,.2f}")
    print(f"  Total net profit     {r['net']:>12,.2f}   ({r['netpct']:+.0f}%)")
    print(f"  Final balance        {r['final']:>12,.2f}")
    print(f"  Gross profit/loss    {r['gp']:>12,.0f} / {r['gl']:,.0f}")
    print(f"  Profit factor        {r['pf']:>12.2f}")
    print(f"  Maximal drawdown     {r['maxdd_cash']:>12,.0f}   ({r['maxdd_pct']:.1f}%)")
    print(f"  Recovery factor      {r['rf']:>12.2f}")
    print(f"  CAGR / win-weeks     {r['cagr']:>11.0f}% / {r['win_wk']:.0f}%   weeks={r['wks']}")
print("\n  per-leg final balance ($1000 alone):")
for f in FS:
    bals = [equity(v, f)[0][-1] for v in vecs]
    print(f"   @ {f*100:.0f}%: " + "  ".join(f"{l}={b:,.0f}" for l, b in zip(labels, bals)))

# ---- plot: per-leg + combined equity, two panels (1% / 2%), segment vlines ----
fig, axes = plt.subplots(2, 1, figsize=(13, 11), sharex=True)
for ax, f in zip(axes, FS):
    for v, l in zip(vecs, labels):
        ax.plot(equity(v, f)[0], lw=1.0, alpha=0.65, label=l)
    ax.plot(equity(combined, f)[0], lw=2.6, color="black", label="COMBINED (pooled team)")
    for b in seg_bounds:
        ax.axvline(b, color="grey", ls="--", lw=0.8, alpha=0.6)
    rep = mt5_report(combined, f)
    ax.set_yscale("log")
    ax.set_title(f"PD2 team -- USD1000 @ f={f*100:.0f}%/op   ->  USD {rep['final']:,.0f} "
                 f"({rep['netpct']:+.0f}%, maxDD {rep['maxdd_pct']:.0f}%, PF {rep['pf']:.2f})")
    ax.set_ylabel("equity USD (log)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(fontsize=7, ncol=2, loc="upper left")
axes[-1].set_xlabel("week (dashed = 6-segment boundaries)")
plt.tight_layout()
plt.savefig("out/pd2_equity.png", dpi=110)
print("\nsaved out/pd2_equity.png")
