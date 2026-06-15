"""Phase 2 sweep #3 — BTC archetypes F + G (poscandle, nback, pinprev). H1 mgmt.
Base = BtcGF (BTCUSDc, mtf=H1, mpl=0.318). TP-exit probes (trail style already covered
by the incumbent BtcGF). _val now force-disables fixed knobs -> clean grid sizes.
-> out/opt/btc_poscandle.csv , btc_nback.csv , btc_pinprev.csv"""
import opt_run

print("=== BTC poscandle (F) ===")
d1 = opt_run.run_opt(
    "btc_poscandle", "BtcGF",
    opt={"step": (1.1, 0.3, 2.0), "buffer": (0.0, 0.25, 0.75),
         "tpR": (1.0, 0.5, 3.0), "slowP": (150, 60, 270)},
    fixed={"addtrig": 1, "sizing": 1, "smaP": 15, "half": 0.5, "trailR": 0.0},
    mode=1, timeout=18000)
print(f"passes: {len(d1)}  positive: {len(d1[d1['nbpR']>0])}/{len(d1)}")
opt_run.show(d1, 10)

print("\n=== BTC nback (G) ===")
d2 = opt_run.run_opt(
    "btc_nback", "BtcGF",
    opt={"step": (1.1, 0.3, 2.0), "buffer": (0.0, 0.25, 0.75),
         "tpR": (1.0, 0.5, 3.0), "nback": (5, 5, 20)},
    fixed={"addtrig": 0, "lineplace": 1, "sizing": 1, "smaP": 15, "slowP": 0,
           "half": 0.5, "trailR": 0.0},
    mode=1, timeout=18000)
print(f"passes: {len(d2)}  positive: {len(d2[d2['nbpR']>0])}/{len(d2)}")
opt_run.show(d2, 10)

print("\n=== BTC pinprev (G) ===")
d3 = opt_run.run_opt(
    "btc_pinprev", "BtcGF",
    opt={"buffer": (0.0, 0.2, 0.8), "tpR": (1.0, 0.5, 3.0),
         "smaP": (11, 2, 17), "half": (0.0, 0.5, 1.0)},
    fixed={"addtrig": 0, "lineplace": 2, "sizing": 1, "slowP": 0,
           "trailR": 0.0, "step": 1.1, "mult": 0.01},
    mode=1, timeout=18000)
print(f"passes: {len(d3)}  positive: {len(d3[d3['nbpR']>0])}/{len(d3)}")
opt_run.show(d3, 10)
