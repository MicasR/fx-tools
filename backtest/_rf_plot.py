"""Visual: GROWTH-team vs RF-team combined equity on $1000 @ f=1%, segment vlines.
Shows the RF-first team's shallower drawdowns + balanced (non-back-loaded) shape."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import promdate as p

pool = p.load_pool()
F = 0.01
fig, ax = plt.subplots(figsize=(13, 6.5))
n = 130
for k in range(1, 6):
    ax.axvline(k * (n // 6), color="grey", ls="--", lw=0.8, alpha=0.6)
for obj, color in (("growth", "tab:blue"), ("rf", "tab:red")):
    _, c, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=0.7, objective=obj, verbose=False)
    eq = 1000 * np.cumprod(np.maximum(1 + F * c, 1e-9))
    peak = np.maximum.accumulate(eq)
    ddmax = 100 * ((peak - eq) / peak).max()
    nlegs = len(p.promdate(pool, 0.24, 6, 0.7, objective=obj, verbose=False)[0])
    ax.plot(eq, lw=2.2, color=color,
            label=f"{obj.upper()} team ({nlegs} legs) -> USD {eq[-1]:,.0f}, maxDD {ddmax:.1f}%")
ax.set_yscale("log")
ax.set_title("PD2: GROWTH vs RECOVERY-FACTOR team -- USD1000 @ f=1%/op (dashed = 6 segments)")
ax.set_xlabel("week")
ax.set_ylabel("equity USD (log)")
ax.grid(True, which="both", alpha=0.25)
ax.legend(loc="upper left")
plt.tight_layout()
plt.savefig("out/pd2_rf_vs_growth.png", dpi=110)
print("saved out/pd2_rf_vs_growth.png")
