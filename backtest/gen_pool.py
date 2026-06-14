"""Generate the cross-instrument PROM-DATE candidate pool on the tester (Path A).
Diverse families on BOTH instruments so gold and BTC can complement each other:
gold stacker + gold shield + BTC trailer + BTC shield + BTC proggeo.
Each -> out/opt/pool_<leg>.csv with weekly perf vectors. Run: python gen_pool.py
"""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # run from backtest/ (relative out/ paths)
import opt_run as o

SWEEPS = [
    ("pool_GoldS210",   "GoldS210",   dict(step=(1.4, 0.2, 2.0), slowP=(150, 90, 330), smaP=(5, 4, 13))),
    ("pool_GoldShield", "GoldShield", dict(tpR=(1.5, 0.5, 3.5))),
    ("pool_BtcGF",      "BtcGF",      dict(step=(1.1, 0.1, 1.5), slowP=(150, 90, 330), trailR=(2.0, 0.5, 3.5))),
    ("pool_BtcShield",  "BtcShield",  dict(tpR=(0.75, 0.25, 2.0))),
    ("pool_BtcPG",      "BtcPG",      dict(step=(1.1, 0.1, 1.5), smaP=(9, 6, 21))),
]

for tag, leg, opt in SWEEPS:
    n = 1
    for v in opt.values():
        lo, st, hi = v
        n *= int(round((hi - lo) / st)) + 1
    print(f">>> {tag} ({leg}): ~{n} combos ...", flush=True)
    df = o.run_opt(tag, leg, opt=opt, mode=1, timeout=1200)
    print(f"    done: {len(df)} passes, best score {df['score'].iloc[0]:.1f} "
          f"(nbpR {df['nbpR'].iloc[0]:.1f}, {int(df['segpos'].iloc[0])}/6)", flush=True)
print("POOL READY")
