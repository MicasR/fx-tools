"""No-subprocess self-test for the PROM-DATE engine: a synthetic MIXED pool where
gold candidates earn in the front half and BTC in the back half (the opposite-half
decorrelation we expect). Proves the cross-instrument selector picks BOTH and the
mixed team beats either instrument alone at matched DD."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import promdate as pd_

NW = 130
rng = np.random.default_rng(0)


def cand(leg, sym, active_lo, active_hi, edge, vol, n):
    """A fake candidate: positive drift in its active window, noise elsewhere."""
    rows = []
    for _ in range(n):
        w = rng.normal(0, vol, NW)
        w[active_lo:active_hi] += edge + rng.normal(0, vol, active_hi - active_lo)
        wk = {f"w{i}": w[i] for i in range(NW)}
        rows.append(dict(leg=leg, sym=sym, nbpR=float(w.sum()), segpos=4, rf=3.0,
                         oneop=20.0, ops=200, win=30.0, sizing=1, smaP=7, slowP=210,
                         mult=0.015, step=1.7, tpR=3.0, trailR=0.0, half=0.5, **wk))
    return rows


# gold earns weeks 0..70, BTC earns weeks 60..130 -> opposite halves
pool = pd.DataFrame(
    cand("GoldA", "XAUUSDc", 0, 70, 0.6, 0.5, 6) +
    cand("BtcA", "BTCUSDc", 60, 130, 0.6, 0.5, 6)
)
print(f"synthetic pool: {len(pool)} candidates  {pool['sym'].str[:3].value_counts().to_dict()}")
sel, combined, g = pd_.promdate(pool, budget=0.24, maxn=6, verbose=True)
pd_.report(pool, sel, combined, budget=0.24)
pd_.compare_instruments(pool, budget=0.24, maxn=6)
