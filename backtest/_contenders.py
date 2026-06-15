"""Compare ALL contenders at matched 24% DD, MONSTERS INCLUDED (full series; drops were
only for robustness selection). Per-segment R + champion benchmark row + concentration
diagnostics (per the show-segments-vs-champion standard). $1000 start. + equity graph."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import promdate as p

WCOLS = [f"w{i}" for i in range(130)]
pool = p.load_pool()


def team_combined(objective, max_corr, min_legs):
    sel, c, _ = p.promdate(pool, 0.24, 6, max_corr=max_corr, objective=objective,
                           min_legs=min_legs, drop_top=3, verbose=False)
    return sel, c


# champion = sum of the 3 reproduced PD_*.set leg vectors
champ = np.zeros(130)
for f in sorted(glob.glob("out/opt/champ_*.csv")):
    d = pd.read_csv(f).sort_values("nbpR", ascending=False).iloc[0]
    champ += np.array([d[c] for c in WCOLS], float)

sel_g6, c_g6 = team_combined("growth", 1.0, 1)
sel_g4, c_g4 = team_combined("growth", 0.7, 1)
sel_r2, c_r2 = team_combined("rf", 0.7, 2)
sel_r5, c_r5 = team_combined("rf", 0.7, 3)
# best-weighted growth-6 (weight_optimize maximizes growth@24%DD directly)
w_opt, c_g6w, _ = p.weight_optimize(pool.iloc[sel_g6].reset_index(drop=True),
                                    list(range(len(sel_g6))), budget=0.24)

CONTENDERS = [
    ("CHAMPION (old 3-dancer)", champ, 3),
    ("GROWTH-6 (equal)", c_g6, len(sel_g6)),
    ("GROWTH-4 (equal)", c_g4, len(sel_g4)),
    ("RF-2 (equal)", c_r2, len(sel_r2)),
    ("RF-5 (equal)", c_r5, len(sel_r5)),
    ("GROWTH-6 weight-opt", c_g6w, len(sel_g6)),
]

print("ALL CONTENDERS @ 24% DD, MONSTERS INCLUDED ($1000), per-segment R")
print(f"{'team':26s} legs  $1000->    f%   segpos  topwk%  " + "  ".join(f"S{i+1}" for i in range(6)))
for name, c, nl in CONTENDERS:
    g, f = p.growth_at_dd(c, 0.24)
    segp, segs = p.seg_robust(c)
    topwk = 100 * c.max() / c.sum() if c.sum() > 0 else 0
    segstr = " ".join(f"{s:+5.0f}" for s in segs)
    print(f"{name:26s} {nl:4d}  ${1000*g:>9,.0f} {f*100:4.1f}  {segp}/6   {topwk:5.1f}   {segstr}")

# equity graph: each contender at its 24%-DD f, segment vlines
fig, ax = plt.subplots(figsize=(13, 7))
for k in range(1, 6):
    ax.axvline(k * (130 // 6), color="grey", ls="--", lw=0.8, alpha=0.5)
for name, c, nl in CONTENDERS:
    g, f = p.growth_at_dd(c, 0.24)
    eq = 1000 * np.cumprod(np.maximum(1 + f * c, 1e-9))
    lw = 2.6 if name.startswith("CHAMPION") else 1.8
    ax.plot(eq, lw=lw, label=f"{name}: ${eq[-1]:,.0f}")
ax.set_yscale("log"); ax.grid(True, which="both", alpha=0.25)
ax.set_title("All contenders @ matched 24% DD, monsters IN -- $1000 (dashed = 6 segments)")
ax.set_xlabel("week"); ax.set_ylabel("equity USD (log)"); ax.legend(loc="upper left", fontsize=8)
plt.tight_layout(); plt.savefig("out/pd2_contenders_24dd.png", dpi=110)
print("\nsaved out/pd2_contenders_24dd.png")
