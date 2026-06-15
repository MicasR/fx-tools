"""Evaluate the CURRENT CROWNED 3-dancer champion under the SAME engine + robust lens as
the challengers. Run each leg single-combo (1 pass) to get its weekly vector, equal-weight
combine, and report raw growth@DD (should reproduce ~57.5x) AND robust/ex-top3 growth +
the team-robustness backstop. Apples-to-apples vs the tournament's robust-selected team."""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import opt_run as o
import promdate as p

LEGS = {  # exact PD_*.set configs; opt = a trivial 1-value sweep so it runs as one pass
    "PD_BtcGF":      ("BtcGF",      dict(sizing=1, smaP=18, slowP=270, mult=0.015, step=1.1, tpR=0.0, trailR=2.5, half=0.5)),
    "PD_GoldShield": ("GoldShield", dict(sizing=0, smaP=7,  slowP=0,   mult=0.01,  step=1.7, tpR=2.0, trailR=0.0, half=0.3)),
    "PD_BtcPG":      ("BtcPG",      dict(sizing=0, smaP=12, slowP=0,   mult=0.01,  step=1.5, tpR=2.0, trailR=0.0, half=0.3)),
}
WCOLS = [f"w{i}" for i in range(130)]
vecs = []
for tag, (base, fx) in LEGS.items():
    # MT5 needs a non-degenerate range -> sweep smaP over 2 points, then pick the target row
    df = o.run_opt(f"champ_{tag}", base, opt={"smaP": (fx["smaP"], 1, fx["smaP"] + 1)},
                   fixed=fx, mode=1, timeout=900)
    df = df[df["smaP"] == fx["smaP"]]
    row = df.sort_values("nbpR", ascending=False).iloc[0]
    vecs.append(np.array([row[c] for c in WCOLS], dtype=float))
    print(f"{tag:14s} nbpR={row['nbpR']:6.1f} segpos={int(row['segpos'])}/6 "
          f"extop1R={row['extop1R']:6.1f} 1op={row['oneop']:.0f}%")

combined = np.sum(vecs, axis=0)          # equal weight (the crowned team is equal-weight)
raw = p.growth_at_dd(combined, 0.24)[0]
rob = p.robust_growth(combined, 0.24, 3)[0]
print(f"\n=== CHAMPION 3-dancer (equal weight), same engine ===")
print(f"  raw growth@24%DD = {raw:.1f}x   robust/ex-top3 = {rob:.1f}x")
p.print_robustness(combined, budget=0.24, drop=5)
