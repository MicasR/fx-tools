"""Densify the prom-date pool around the winning regions -> more genuinely-distinct
strong dancers (so the selector doesn't reach for near-twins). Tags pool_*2 so they
join the pool_*.csv glob."""
import time
import opt_run as o

SWEEPS = [
    ("pool_btcgf2", "BtcGF",      dict(slowP=(180, 30, 300), smaP=(12, 3, 18), step=(1.1, 0.1, 1.5), trailR=(2.0, 0.5, 3.0)), {}),
    ("pool_s2102",  "GoldS210",   dict(step=(1.4, 0.1, 1.8), slowP=(210, 40, 290), smaP=(7, 2, 11), half=(0.3, 0.2, 0.5)),    {}),
    ("pool_geo172", "GoldGeo17",  dict(step=(1.5, 0.1, 2.0), smaP=(5, 2, 9), half=(0.3, 0.2, 0.5), tpR=(2.0, 1.0, 3.0)),      {}),
    ("pool_gsh2",   "GoldShield", dict(tpR=(1.5, 0.25, 3.0), half=(0.3, 0.2, 0.5)),                                          {"trailR": 0.0}),
    ("pool_gshtr2", "GoldShield", dict(trailR=(2.0, 0.5, 3.5), half=(0.3, 0.2, 0.5)),                                        {"tpR": 0.0}),
    ("pool_btcpg2", "BtcPG",      dict(step=(1.2, 0.1, 1.6), smaP=(12, 3, 18), half=(0.3, 0.2, 0.5), tpR=(2.0, 1.0, 3.0)),   {}),
    ("pool_bsh2",   "BtcShield",  dict(tpR=(0.75, 0.25, 2.0), half=(0.3, 0.2, 0.5)),                                         {"trailR": 0.0}),
    ("pool_bshtr2", "BtcShield",  dict(trailR=(1.5, 0.5, 3.0), half=(0.3, 0.2, 0.5)),                                        {"tpR": 0.0}),
]

if __name__ == "__main__":
    for tag, leg, opt, fixed in SWEEPS:
        t0 = time.time()
        df = o.run_opt(tag, leg, opt=opt, fixed=fixed, mode=1, timeout=3000)
        print(f"{tag:<13} {leg:<11} passes={len(df):4d}  best score={df['score'].max():7.1f}  "
              f"({time.time()-t0:.0f}s)", flush=True)
    print("DENSE POOL DONE")
