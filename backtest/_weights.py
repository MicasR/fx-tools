"""Weighting / capital-allocation study for the 6-leg team (user: equal 1%/leg = up to 6%
concurrent exposure; that's the real DD driver). Compare schemes by FINAL $, maxDD%, RF, and
MAX CONCURRENT exposure (= sum of per-leg weights = worst-case simultaneous risk-on):
  - equal 1%/leg (baseline, 6% concurrent)
  - per-instrument budgets (gold G%, BTC B%, equal within) -- the user's idea
  - risk-parity (w_i proportional to 1/leg-vol -- the smooth legs get more) scaled to a budget
  - RF-optimal distribution (coordinate-ascent on weights to max recovery factor) scaled to a budget
Uses reproduced leg vectors (out/opt/fin_*.csv). $1000 start."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import promdate as p

WCOLS = [f"w{i}" for i in range(130)]
sel, _, _ = p.promdate(p.load_pool(), 0.24, 6, max_corr=1.0, drop_top=3, verbose=False)
team = p.load_pool().iloc[sel].reset_index(drop=True)
sel2, _, _ = p.promdate(p.load_pool(), 0.24, 6, max_corr=1.0, drop_top=3, verbose=False)
team = p.load_pool().iloc[sel2].reset_index(drop=True)
isgold = np.array([str(s).startswith("XAU") for s in team["sym"]])
V = []
for i in range(len(team)):
    f = pd.read_csv(f"out/opt/fin_{i}.csv")
    f = f[f["smaP"] == int(team.iloc[i]["smaP"])].sort_values("nbpR", ascending=False).iloc[0]
    V.append(np.array([f[c] for c in WCOLS], float))
V = np.array(V)                                   # legs x weeks (R units)


def metrics(w):
    w = np.asarray(w, float)
    comb = w @ V                                  # weekly portfolio return fraction
    eq = np.cumprod(np.maximum(1 + comb, 1e-9))
    peak = np.maximum.accumulate(eq)
    ddp = ((peak - eq) / peak).max()
    net = eq[-1] - 1
    return dict(final=1000 * eq[-1], dd=100 * ddp, rf=(net / ddp if ddp > 0 else float("inf")),
                conc=100 * w.sum())


def inst_budget(g_tot, b_tot):
    w = np.zeros(len(team))
    w[isgold] = g_tot / max(isgold.sum(), 1)
    w[~isgold] = b_tot / max((~isgold).sum(), 1)
    return w


def risk_parity(budget):
    vol = V.std(axis=1)
    w = (1 / vol); w = w / w.sum() * budget
    return w


def rf_optimal(budget):                            # coordinate-ascent on weights to max RF
    w = np.ones(len(team)) / len(team)
    best = metrics(w * budget / w.sum())["rf"]
    for step in (0.5, 0.2, 0.08, 0.03):
        for _ in range(80):
            imp = False
            for i in range(len(w)):
                for d in (1 + step, 1 / (1 + step)):
                    w2 = w.copy(); w2[i] *= d; w2 = w2 / w2.sum()
                    r = metrics(w2 * budget)["rf"]
                    if r > best + 1e-9:
                        best, w, imp = r, w2, True
            if not imp:
                break
    return w / w.sum() * budget


SCHEMES = [
    ("equal 1%/leg (baseline)", np.full(len(team), 0.01)),
    ("equal -> 4% concurrent", np.full(len(team), 0.04 / len(team))),
    ("per-inst  G2% / B2%", inst_budget(0.02, 0.02)),
    ("per-inst  G2% / B4%", inst_budget(0.02, 0.04)),
    ("per-inst  G1% / B2%", inst_budget(0.01, 0.02)),
    ("risk-parity @4%", risk_parity(0.04)),
    ("RF-optimal @4%", rf_optimal(0.04)),
    ("RF-optimal @3%", rf_optimal(0.03)),
]
print(f"{'scheme':28s} concurrent  final$     maxDD%   ret/DD")
pts = []
for name, w in SCHEMES:
    m = metrics(w)
    eff = (m["final"] / 1000 - 1) / (m["dd"] / 100)         # net-multiple per unit DD-fraction
    pts.append((name, m["dd"], m["final"], m["conc"]))
    print(f"{name:28s} {m['conc']:6.1f}%   ${m['final']:>9,.0f}  {m['dd']:6.1f}  {eff:6.1f}")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(11, 7))
for name, dd, fin, conc in pts:
    ax.scatter(dd, fin, s=60)
    ax.annotate(f"{name}\n({conc:.0f}% concurrent)", (dd, fin), fontsize=7,
                xytext=(5, 4), textcoords="offset points")
ax.set_xlabel("max drawdown %  (lower = better)")
ax.set_ylabel("final equity USD from 1000  (log)")
ax.set_yscale("log")
ax.set_title("6-leg team: capital-allocation efficient frontier (up & left = better)")
ax.grid(True, which="both", alpha=0.3)
plt.tight_layout(); plt.savefig("out/pd2_weights_frontier.png", dpi=110)
print("saved out/pd2_weights_frontier.png")
print("\nweights (per leg, %):  legs = " +
      " ".join(f"{('G' if g else 'B')}{i}" for i, g in enumerate(isgold)))
for name, w in SCHEMES[-3:]:
    print(f"  {name:18s} " + " ".join(f"{100*x:4.1f}" for x in w))
