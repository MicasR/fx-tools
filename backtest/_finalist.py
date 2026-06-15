"""Finalist validation of the crowned robust team:
  1. extract the 6 selected legs' exact params from the pool,
  2. single-pass REPRODUCE each standalone (drift check vs the optimizer pool value),
  3. recombine the reproduced weekly vectors and report team growth@24%DD
     WITH monsters (raw, full upside) AND WITHOUT (robust = ex-top-3 weeks) + bootstrap.
Writes the reproduced legs' configs for PD2_*.set generation."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import opt_run as o
import promdate as p

WCOLS = [f"w{i}" for i in range(130)]
PARAMS = ["sizing", "smaP", "slowP", "mult", "step", "tpR", "trailR", "half",
          "addtrig", "lineplace", "nback", "buffer"]

pool = p.load_pool()
sel, combined_pool, _ = p.promdate(pool, budget=0.24, maxn=6, max_corr=1.0, drop_top=3, verbose=False)
team = pool.iloc[sel].reset_index(drop=True)
print(f"crowned team: {len(team)} legs\n")

rep_vecs, pool_vecs = [], []
for i, row in team.iterrows():
    base = "GoldS210" if str(row["sym"]).startswith("XAU") else "BtcGF"
    fx = {k: (int(row[k]) if k in ("sizing", "smaP", "slowP", "addtrig", "lineplace", "nback")
              else float(row[k])) for k in PARAMS}
    smaP = fx["smaP"]
    df = o.run_opt(f"fin_{i}", base, opt={"smaP": (smaP, 1, smaP + 1)}, fixed=fx, mode=1, timeout=900)
    df = df[df["smaP"] == smaP]
    r = df.sort_values("nbpR", ascending=False).iloc[0]
    rep_vecs.append(np.array([r[c] for c in WCOLS], float))
    pool_vecs.append(np.array([row[c] for c in WCOLS], float))
    drift = (r["nbpR"] - row["nbpR"]) / row["nbpR"] * 100 if row["nbpR"] else 0.0
    print(f"  leg{i} {str(row['sym'])[:3]} {p.arch_tag(row):<10} sma{smaP} slow{int(row['slowP'])} "
          f"step{row['step']:.2f} tp{row['tpR']:.2f} tr{row['trailR']:.2f} | pool nbpR={row['nbpR']:6.1f} "
          f"-> repro {r['nbpR']:6.1f} ({drift:+.1f}%) seg{int(r['segpos'])}/6")

rep = np.sum(rep_vecs, axis=0)
poolc = np.sum(pool_vecs, axis=0)
print("\n=== CROWNED TEAM (reproduced, equal weight) ===")
for tag, c in [("pool weekly vectors", poolc), ("REPRODUCED weekly vectors", rep)]:
    raw = p.growth_at_dd(c, 0.24)[0]
    rob = p.robust_growth(c, 0.24, 3)[0]
    print(f"  [{tag}]  WITH monsters (raw) = {raw:.1f}x   |   WITHOUT (ex-top3wk) = {rob:.1f}x")
p.print_robustness(rep, budget=0.24, drop=5)
