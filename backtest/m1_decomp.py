"""Decompose the M1-engine vs tester gap, per leg, by matching ops on (dir, entry
price e0) -- the FINDINGS method. Splits the gap into matched-op R difference vs
entry-set differences (ops only one engine has). All R NBP-clamped (max -1)."""
import csv
import numpy as np
from m1_engine import run_m1_conc
from m1_validate import LEGS, TRUTH


def load_tester(leg):
    ops = []
    with open(f"out/ealog/{leg}.csv") as f:
        for r in csv.DictReader(f):
            ops.append((int(r["dir"]), float(r["e0"]), max(float(r["R"]), -1.0)))
    return ops


def match(a, b, tol=1e-4):
    """Greedy match a<->b on (dir, e0). Returns matched pairs, a-only, b-only."""
    b = sorted(b, key=lambda x: x[1]); used = [False] * len(b)
    pairs, a_only = [], []
    for da, ea, ra in a:
        best = -1; bd = 1e18
        for i, (db, eb, rb) in enumerate(b):
            if used[i] or db != da:
                continue
            d = abs(eb - ea) / max(abs(ea), 1)
            if d < bd:
                bd = d; best = i
        if best >= 0 and bd < tol:
            used[best] = True; pairs.append((ra, b[best][2]))
        else:
            a_only.append((da, ea, ra))
    b_only = [b[i] for i in range(len(b)) if not used[i]]
    return pairs, a_only, b_only


print(f"{'leg':<12}{'M1tot':>7}{'tst':>7}{'gap':>7} | {'matched':>8}{'mR_M1':>7}{'mR_tst':>7}{'mΔ':>6}"
      f" | {'M1only':>7}{'+R':>6} | {'tstonly':>8}{'+R':>6}")
for name, sym, tf, cfg in LEGS:
    res, *_ = run_m1_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    m1 = [(o[5]["dir"], o[5]["e0"], max(o[2], -1.0)) for o in res]
    tst = load_tester(name)
    pairs, m1_only, tst_only = match(m1, tst)
    mR_m1 = sum(p[0] for p in pairs); mR_t = sum(p[1] for p in pairs)
    tot_m1 = sum(x[2] for x in m1); tot_t = sum(x[2] for x in tst)
    print(f"{name:<12}{tot_m1:>7.1f}{tot_t:>7.1f}{tot_m1-tot_t:>+7.1f} | "
          f"{len(pairs):>8}{mR_m1:>7.1f}{mR_t:>7.1f}{mR_m1-mR_t:>+6.1f} | "
          f"{len(m1_only):>7}{sum(x[2] for x in m1_only):>+6.1f} | "
          f"{len(tst_only):>8}{sum(x[2] for x in tst_only):>+6.1f}")
print("\n  mΔ = matched-op R(M1)-R(tester); if ~0 the per-op physics agree and the gap is the entry set.")
