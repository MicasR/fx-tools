"""Run prom-date at several 1-op concentration caps to see the robust team."""
import promdate as pd_

for cap in (100, 50, 40, 30):
    pool = pd_.load_pool(max_oneop=cap)
    comp = pool["sym"].astype(str).str[:3].value_counts().to_dict()
    print(f"\n############ max 1op = {cap}%  (pool {len(pool)} cands {comp}) ############")
    sel, combined, g = pd_.promdate(pool, budget=0.24, maxn=6)
    pd_.report(pool, sel, combined, budget=0.24)
