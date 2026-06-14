"""Generate the PROM-DATE candidate pool: sweep every leg family on the tester,
each pass carrying its weekly performance vector -> out/opt/pool_*.csv."""
import time
import opt_run as o

SWEEPS = [
    # tag,          leg,          opt ranges,                                                    fixed
    ("pool_s210",   "GoldS210",   dict(step=(1.4, 0.2, 2.0), slowP=(150, 50, 300), smaP=(5, 4, 9), half=(0.3, 0.2, 0.5)), {}),
    ("pool_geo17",  "GoldGeo17",  dict(step=(1.4, 0.2, 2.0), smaP=(3, 2, 9), half=(0.3, 0.2, 0.5), tpR=(2.0, 1.0, 4.0)),  {}),
    ("pool_gshTP",  "GoldShield", dict(tpR=(1.5, 0.5, 4.0), half=(0.3, 0.2, 0.7)),                                        {"trailR": 0.0}),
    ("pool_gshTR",  "GoldShield", dict(trailR=(1.5, 0.5, 3.0), half=(0.3, 0.2, 0.7)),                                     {"tpR": 0.0}),
    ("pool_btcgf",  "BtcGF",      dict(step=(1.1, 0.2, 1.5), slowP=(150, 60, 300), smaP=(9, 6, 21), trailR=(2.0, 0.5, 3.5)), {}),
    ("pool_btcpg",  "BtcPG",      dict(step=(1.1, 0.2, 1.5), smaP=(9, 6, 21), half=(0.3, 0.2, 0.5), tpR=(2.0, 1.0, 4.0)),  {}),
    ("pool_bshTP",  "BtcShield",  dict(tpR=(0.75, 0.25, 2.0), half=(0.3, 0.2, 0.7)),                                      {"trailR": 0.0}),
    ("pool_bshTR",  "BtcShield",  dict(trailR=(1.5, 0.5, 3.0), half=(0.3, 0.2, 0.7)),                                     {"tpR": 0.0}),
]

if __name__ == "__main__":
    for tag, leg, opt, fixed in SWEEPS:
        t0 = time.time()
        df = o.run_opt(tag, leg, opt=opt, fixed=fixed, mode=1, timeout=3000)
        print(f"{tag:<12} {leg:<11} passes={len(df):4d}  best score={df['score'].max():7.1f}  "
              f"({time.time()-t0:.0f}s)", flush=True)
    print("POOL DONE")
