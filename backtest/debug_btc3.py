import glob, numpy as np, pandas as pd
from conc_engine import run_tf_conc
from pyramid_engine import margin_line, SPECS, lot_to_pin

for sym in ("XAU", "BTC"):
    res, tm, H, L, n = run_tf_conc(sym=sym, stack=False, tp_R=2.0, max_conc=1, conc_dir="same")
    R = np.array([o[2] for o in res])
    win = 100 * np.mean(R > 0)
    reasons = {}
    for o in res:
        reasons[o[4]] = reasons.get(o[4], 0) + 1
    print(f"\n{sym}: run_tf_conc shield  win={win:.1f}%  totR={R.sum():.1f}  n={len(R)}  reasons={reasons}")
    # inspect first 5 ops: entry lot, margin line vs structural stop
    sp = SPECS[sym]; TR, MPL = sp["TR"], sp["MPL"] * 400 / 2000
    for o in res[:5]:
        info = o[5]; e0 = info["e0"]; r0 = info["r0"]; dd = info["dir"]; E0 = info["E0"]
        log = info["log"]; entry, lot = log[0][1], log[0][2]
        ml = margin_line([(entry, lot)], dd, E0, TR, MPL)
        print(f"   op k0={o[0]} k1={o[1]} R={o[2]:+.2f} {o[4]}  e0={e0:.1f} r0={r0:.1f} lot={lot}"
              f"  ml={ml:.1f}  structural={e0 - dd*r0:.1f}  tp={e0 + dd*2*r0:.1f}")
