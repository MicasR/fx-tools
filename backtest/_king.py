"""KING = GROWTH-6 weight-optimized. $1000 MT5-style report @ matched 24% DD + equity image
(per-leg weighted + combined, segment vlines). Monsters INCLUDED (full series)."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import promdate as p

WCOLS = [f"w{i}" for i in range(130)]
DEP = 1000.0
pool = p.load_pool()
sel, _, _ = p.promdate(pool, 0.24, 6, max_corr=1.0, drop_top=3, verbose=False)
team = pool.iloc[sel].reset_index(drop=True)
w, combined, _ = p.weight_optimize(team, list(range(len(sel))), budget=0.24)
V = team[WCOLS].to_numpy(float)
g, f = p.growth_at_dd(combined, 0.24)


def report(series, f):
    eq = DEP * np.cumprod(np.maximum(1 + f * series, 1e-9))
    bal = np.concatenate([[DEP], eq]); chg = np.diff(bal)
    peak = np.maximum.accumulate(bal); dd = peak - bal
    net = bal[-1] - DEP; yrs = len(series) / 52.0
    return dict(final=bal[-1], net=net, npct=100 * net / DEP,
                gp=chg[chg > 0].sum(), gl=-chg[chg < 0].sum(),
                pf=chg[chg > 0].sum() / -chg[chg < 0].sum(),
                ddp=100 * (dd / peak).max(), ddc=dd.max(),
                rf=net / dd.max(), winwk=100 * (chg > 0).mean(),
                cagr=100 * ((bal[-1] / DEP) ** (1 / yrs) - 1))


r = report(combined, f)
segp, segs = p.seg_robust(combined)
conc = 100 * f * w.sum()
print("=" * 66)
print(f"  KING = GROWTH-6 weight-optimized  --  $1000 @ 24% DD (f={f*100:.2f}%/unit)")
print("=" * 66)
print(f"  Initial deposit     {DEP:>12,.2f}")
print(f"  Total net profit    {r['net']:>12,.2f}   ({r['npct']:+.0f}%)")
print(f"  Final balance       {r['final']:>12,.2f}")
print(f"  Gross profit/loss   {r['gp']:>12,.0f} / {r['gl']:,.0f}")
print(f"  Profit factor       {r['pf']:>12.2f}")
print(f"  Maximal drawdown    {r['ddc']:>12,.0f}   ({r['ddp']:.1f}%)")
print(f"  Recovery factor     {r['rf']:>12.2f}")
print(f"  CAGR / win-weeks    {r['cagr']:>11.0f}% / {r['winwk']:.0f}%")
print(f"  6-seg: {segp}/6   " + " ".join(f"{s:+.0f}" for s in segs))
print(f"  max concurrent exposure  {conc:.1f}%   (f x sum of weights)")
print("\n  ROSTER + weights:")
for i, row in team.iterrows():
    print(f"   {str(row['sym'])[:3]} {p.arch_tag(row):<10} sma{int(row['smaP'])}/sl{int(row['slowP'])}/"
          f"st{row['step']:.1f}/tp{row['tpR']:.1f}/tr{row['trailR']:.1f}  "
          f"weight={w[i]/w.sum()*100:4.1f}%  eff-risk/op={f*w[i]*100:.2f}%")

fig, ax = plt.subplots(figsize=(13, 7))
for k in range(1, 6):
    ax.axvline(k * (130 // 6), color="grey", ls="--", lw=0.9, alpha=0.6)
for i, row in team.iterrows():
    eq = DEP * np.cumprod(np.maximum(1 + f * w[i] * V[i], 1e-9))
    ax.plot(eq, lw=1.0, alpha=0.6, label=f"{str(row['sym'])[:3]} {p.arch_tag(row)} ({w[i]/w.sum()*100:.0f}%)")
ax.plot(DEP * np.cumprod(np.maximum(1 + f * combined, 1e-9)), lw=2.8, color="black",
        label=f"KING combined -> USD {r['final']:,.0f} ({r['ddp']:.0f}% DD)")
ax.set_yscale("log"); ax.grid(True, which="both", alpha=0.25)
ax.set_title(f"KING (GROWTH-6 weight-opt) -- USD1000 @ 24% DD -> USD {r['final']:,.0f}, PF {r['pf']:.2f} (dashed=segments)")
ax.set_xlabel("week"); ax.set_ylabel("equity USD (log)"); ax.legend(loc="upper left", fontsize=7, ncol=2)
plt.tight_layout(); plt.savefig("out/king_equity.png", dpi=115)
print("\nsaved out/king_equity.png")
