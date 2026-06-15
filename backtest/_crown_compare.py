"""Head-to-head of the crown candidates (same R1-R4 pool, max_corr=0.7):
  GROWTH (4 legs) | RF-2 (natural) | RF-3 | RF-4 (RF objective, forced to >=N legs).
Reports legs, RF, growth@24%DD, $1000 @ f=1% (DD comparable) and @ matched 24%-DD,
half-split (back-loading), bootstrap median/p05. Plus an equity overlay graph."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import promdate as p

pool = p.load_pool()


def stats_at_f(c, f):
    eq = np.cumprod(np.maximum(1 + f * c, 1e-9))
    peak = np.maximum.accumulate(eq)
    return 1000 * eq[-1], 100 * ((peak - eq) / peak).max()


CANDS = [("GROWTH-4", "growth", 1), ("RF-2", "rf", 2), ("RF-3", "rf", 3), ("RF-4", "rf", 4)]
results = []
print(f"{'team':9s} legs  RF   g@24DD  $@f=1%     DD%    $@24DD    f%    h1/h2      bootMed p05")
for name, obj, ml in CANDS:
    sel, c, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=0.7, objective=obj, min_legs=ml, verbose=False)
    team = pool.iloc[sel].reset_index(drop=True)
    rf = p.team_rf(c, 0)[0]
    g24, f24 = p.growth_at_dd(c, 0.24)
    fin1, dd1 = stats_at_f(c, 0.01)
    fin24, _ = stats_at_f(c, f24)
    h = len(c) // 2
    h1, h2 = c[:h].sum(), c[h:].sum()
    rob = p.team_robustness(c, 0.24, 5)
    results.append((name, c, fin1, dd1))
    print(f"{name:9s} {len(team):4d} {rf:5.1f} {g24:6.1f}x ${fin1:>8,.0f} {dd1:5.1f}% ${fin24:>8,.0f} "
          f"{f24*100:4.1f} {h1:4.0f}/{h2:<4.0f} {rob['boot_median']:6.1f}x {rob['boot_p05']:.1f}")
    print(f"          legs: " + " | ".join(f"{str(r['sym'])[:3]} {p.arch_tag(r)} sma{int(r['smaP'])}"
          f"/sl{int(r['slowP'])}/st{r['step']:.1f}/tp{r['tpR']:.1f}/tr{r['trailR']:.1f}"
          for _, r in team.iterrows()))

fig, ax = plt.subplots(figsize=(13, 6.5))
for k in range(1, 6):
    ax.axvline(k * (130 // 6), color="grey", ls="--", lw=0.8, alpha=0.5)
for name, c, fin1, dd1 in results:
    eq = 1000 * np.cumprod(np.maximum(1 + 0.01 * c, 1e-9))
    ax.plot(eq, lw=2.0, label=f"{name} -> USD {fin1:,.0f}, maxDD {dd1:.1f}%")
ax.set_yscale("log"); ax.grid(True, which="both", alpha=0.25)
ax.set_title("Crown candidates -- USD1000 @ f=1%/op (dashed = 6 segments)")
ax.set_xlabel("week"); ax.set_ylabel("equity USD (log)"); ax.legend(loc="upper left")
plt.tight_layout(); plt.savefig("out/pd2_crown_compare.png", dpi=110)
print("\nsaved out/pd2_crown_compare.png")
