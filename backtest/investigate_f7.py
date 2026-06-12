"""
investigate_f7.py — closest-gap audit of f7/s200's top ops (M15 replay).
M15 lows ARE the exact intrabar minima, so a replay against M15 bars yields
the exact closest-approach of price to the liquidation line for ANY op,
including the 2024 ops the M5 cache can't cover.  Audit f7's top 8 the same
way f5 was audited.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import run_tf
from investigate_f5 import replay_m5, frame15

if __name__ == "__main__":
    f7 = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=7, sizing="geofloor",
                slowP=200, unit="base", mult=0.01, prog_step=1.7, lev=2000.0)
    m = frame15(7)
    t15 = m["time"].to_numpy()
    q = f7[3] // 6
    print(f"--- f7/s200 top 8 ops, closest-$ to line (M15-exact) ---")
    print(f"{'open':>17}{'close':>17}{'R':>9}{'nPos':>6}{'maxLot':>8}{'seg':>5}  exit"
          f"   closest gap")
    for o in sorted(f7[0], key=lambda x: -x[2])[:8]:
        info = o[5]
        t0, t1 = m["time"].iloc[o[0]], m["time"].iloc[min(o[1], len(m) - 1)]
        mx = max(l for _, _, l in info["log"])
        sg = min(o[0] // q + 1, 6)
        res, mg, mgt = replay_m5(info, t15, m)
        extra = (f"{res}, gap {mg:.2f}$ at {mgt}" if mg is not None else res)
        print(f"{str(t0):>17}{str(t1):>17}{o[2]:>9.1f}{o[3]:>6}{mx:>8.2f}{sg:>5}  {o[4]}"
              f"   {extra}")
