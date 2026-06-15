"""Densify the LIVE robust archetype corners (low-TP, where recurring non-jackpot edges
live, + the nback/pinprev regions that earned team seats) so the robust greedy has more
decorrelated options. Tags end in '2' -> join the gold_*/btc_* glob. -> out/opt/*2.csv"""
import time
import opt_run as o

SWEEPS = [
    # gold nback low-TP (the standout standalone corner: nback5/TP1.0)
    ("gold_nback2", "GoldS210",
        dict(nback=(3, 2, 9), tpR=(0.5, 0.25, 1.75), buffer=(0.0, 0.25, 0.5), step=(1.7, 0.3, 2.3)),
        dict(addtrig=0, lineplace=1, sizing=1, smaP=5, slowP=0, half=0.5, trailR=0.0)),
    # gold poscandle low-TP
    ("gold_poscandle2", "GoldS210",
        dict(tpR=(1.0, 0.25, 2.0), buffer=(0.1, 0.15, 0.4), step=(1.7, 0.3, 2.3), slowP=(150, 60, 270)),
        dict(addtrig=1, sizing=1, smaP=5, half=0.5, trailR=0.0)),
    # BTC nback (team-member region: nback15/buf0.5)
    ("btc_nback2", "BtcGF",
        dict(nback=(10, 5, 20), tpR=(0.75, 0.25, 2.0), buffer=(0.3, 0.2, 0.7), step=(1.5, 0.5, 2.0)),
        dict(addtrig=0, lineplace=1, sizing=1, smaP=15, slowP=0, half=0.5, trailR=0.0)),
    # BTC pinprev (team-member region)
    ("btc_pinprev2", "BtcGF",
        dict(buffer=(0.0, 0.2, 0.6), tpR=(1.0, 0.25, 2.0), smaP=(9, 2, 15), half=(0.5, 0.5, 1.0)),
        dict(addtrig=0, lineplace=2, sizing=1, slowP=0, trailR=0.0, step=1.1, mult=0.01)),
    # BTC poscandle low-TP
    ("btc_poscandle2", "BtcGF",
        dict(tpR=(1.0, 0.25, 2.0), buffer=(0.0, 0.2, 0.6), step=(1.5, 0.3, 2.1), slowP=(180, 60, 300)),
        dict(addtrig=1, sizing=1, smaP=15, half=0.5, trailR=0.0)),
]

print(f"densifying {len(SWEEPS)} archetype corners...", flush=True)
for tag, leg, opt, fixed in SWEEPS:
    t0 = time.time()
    df = o.run_opt(tag, leg, opt=opt, fixed=fixed, mode=1, timeout=6000)
    print(f"{tag:<16}{leg:<11} passes={len(df):4d} best={df['score'].max():7.1f} "
          f"({time.time()-t0:.0f}s)", flush=True)
print("DENSIFY ARCH DONE")
