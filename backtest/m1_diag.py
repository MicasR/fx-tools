"""Pinpoint diagnostics: GoldS210 monster op + BtcGF extra-op clustering."""
import csv
import numpy as np
from m1_engine import run_m1_conc
from m1_validate import LEGS


def run(name):
    cfg = next(c for n, s, t, c in LEGS if n == name)
    sym, tf = next((s, t) for n, s, t, c in LEGS if n == name)
    res, tm1, *_ = run_m1_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
    out = []
    for o in res:
        k0, k1, R, npos, reason, info = o
        out.append((info["dir"], info["e0"], max(R, -1.0), npos, reason,
                    str(tm1[k0])[:16], str(tm1[k1])[:16]))
    return out


def tester(name):
    ops = []
    with open(f"out/ealog/{name}.csv") as f:
        for r in csv.DictReader(f):
            ops.append((int(r["dir"]), float(r["e0"]), max(float(r["R"]), -1.0), int(r["depth"])))
    return ops


print("===== GoldS210: my biggest ops (entry, R, depth) =====")
mine = run("GoldS210"); tst = tester("GoldS210")
for d, e0, R, npos, rsn, t0, t1 in sorted(mine, key=lambda x: -x[2])[:8]:
    # nearest tester op by entry price
    cand = [o for o in tst if o[0] == d]
    near = min(cand, key=lambda o: abs(o[1] - e0)) if cand else None
    nd = f"tst e0={near[1]:.1f} R={near[2]:+.1f} dep={near[3]}" if near and abs(near[1]-e0)/e0 < 1e-3 else "NO TESTER MATCH"
    print(f"  dir{d:+d} e0={e0:8.1f} R={R:+7.1f} dep={npos:2d} {rsn:3} {t0}->{t1}  | {nd}")

print("\n===== BtcGF: extra ops (mine not in tester), by time =====")
mine = run("BtcGF"); tst = tester("BtcGF")
tstkeys = sorted(tst, key=lambda o: o[1])
used = [False] * len(tstkeys)
extra = []
for d, e0, R, npos, rsn, t0, t1 in mine:
    best, bd = -1, 1e18
    for i, o in enumerate(tstkeys):
        if used[i] or o[0] != d:
            continue
        rr = abs(o[1] - e0) / max(e0, 1)
        if rr < bd:
            bd, best = rr, i
    if best >= 0 and bd < 1e-4:
        used[best] = True
    else:
        extra.append((R, t0, npos, rsn))
print(f"  {len(extra)} extra ops, sumR={sum(e[0] for e in extra):+.1f}")
# bucket by year-month
from collections import Counter
cnt = Counter(t[1][:7] for t in extra)
rsum = {}
for R, t0, npos, rsn in extra:
    rsum[t0[:7]] = rsum.get(t0[:7], 0) + R
for ym in sorted(cnt):
    print(f"    {ym}: {cnt[ym]:2d} ops  sumR={rsum[ym]:+7.1f}")
