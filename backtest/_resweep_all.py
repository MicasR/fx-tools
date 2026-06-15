"""Definitive re-sweep: regenerate the FULL championship pool on the current EA so every
candidate carries the R2/R3 metrics (segpos_ex3, h1R, h2R). =
  incumbent base (pool_gen, 8) + incumbent dense (pool_dense, 8) + 6 archetype sweeps.
Density now matches the original champion pool; archetypes compete under R1-R3. One pass.
-> out/opt/*.csv (overwrites). Then: python _tournament.py"""
import time
import opt_run as o
import pool_gen
import pool_dense

ARCH = [
    ("gold_poscandle", "GoldS210", dict(step=(1.1, 0.3, 2.0), buffer=(0.0, 0.25, 0.75),
        tpR=(1.0, 0.5, 3.0), slowP=(150, 60, 270)),
        dict(addtrig=1, sizing=1, smaP=5, half=0.5, trailR=0.0)),
    ("gold_nback", "GoldS210", dict(step=(1.1, 0.3, 2.0), buffer=(0.0, 0.25, 0.75),
        tpR=(1.0, 0.5, 3.0), nback=(5, 5, 20)),
        dict(addtrig=0, lineplace=1, sizing=1, smaP=5, slowP=0, half=0.5, trailR=0.0)),
    ("gold_pinprev", "GoldS210", dict(buffer=(0.0, 0.2, 0.8), tpR=(1.0, 0.5, 3.0),
        smaP=(5, 2, 11), half=(0.0, 0.5, 1.0)),
        dict(addtrig=0, lineplace=2, sizing=1, slowP=0, trailR=0.0, step=1.1, mult=0.01)),
    ("btc_poscandle", "BtcGF", dict(step=(1.1, 0.3, 2.0), buffer=(0.0, 0.25, 0.75),
        tpR=(1.0, 0.5, 3.0), slowP=(150, 60, 270)),
        dict(addtrig=1, sizing=1, smaP=15, half=0.5, trailR=0.0)),
    ("btc_nback", "BtcGF", dict(step=(1.1, 0.3, 2.0), buffer=(0.0, 0.25, 0.75),
        tpR=(1.0, 0.5, 3.0), nback=(5, 5, 20)),
        dict(addtrig=0, lineplace=1, sizing=1, smaP=15, slowP=0, half=0.5, trailR=0.0)),
    ("btc_pinprev", "BtcGF", dict(buffer=(0.0, 0.2, 0.8), tpR=(1.0, 0.5, 3.0),
        smaP=(11, 2, 17), half=(0.0, 0.5, 1.0)),
        dict(addtrig=0, lineplace=2, sizing=1, slowP=0, trailR=0.0, step=1.1, mult=0.01)),
]

ALL = pool_gen.SWEEPS + pool_dense.SWEEPS + ARCH
print(f"re-sweeping {len(ALL)} grids on the current EA (R2/R3 metrics)...", flush=True)
for tag, leg, opt, fixed in ALL:
    t0 = time.time()
    df = o.run_opt(tag, leg, opt=opt, fixed=fixed, mode=1, timeout=6000)
    print(f"{tag:<15}{leg:<11} passes={len(df):4d} best={df['score'].max():7.1f} "
          f"({time.time()-t0:.0f}s)", flush=True)
print("RESWEEP ALL DONE")
