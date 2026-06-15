"""Phase 2 sweep #2 — GOLD archetype G (structural / grid-SL line placement).
Two flavors, SMA-bounce trigger:
  nback   : geofloor anchored to the structural low/high N bars back (step/ramp matter)
  pinprev : pin each add's liquidation to the prior bounce extreme (no ramp; buffer/TP/smaP matter)
-> out/opt/gold_nback.csv , out/opt/gold_pinprev.csv"""
import opt_run

print("=== GOLD nback (G) ===")
df1 = opt_run.run_opt(
    "gold_nback", "GoldS210",
    opt={"step": (1.1, 0.3, 2.0), "buffer": (0.0, 0.25, 0.75),
         "tpR": (1.0, 0.5, 3.0), "nback": (5, 5, 20)},   # 5,10,15,20
    fixed={"addtrig": 0, "lineplace": 1, "sizing": 1, "smaP": 5, "slowP": 0,
           "half": 0.5, "trailR": 0.0},
    mode=1, timeout=18000)
print(f"passes: {len(df1)}  positive: {len(df1[df1['nbpR']>0])}/{len(df1)}")
opt_run.show(df1, 12)

print("\n=== GOLD pinprev (G) ===")
df2 = opt_run.run_opt(
    "gold_pinprev", "GoldS210",
    opt={"buffer": (0.0, 0.2, 0.8), "tpR": (1.0, 0.5, 3.0),
         "smaP": (5, 2, 11), "half": (0.0, 0.5, 1.0)},
    fixed={"addtrig": 0, "lineplace": 2, "sizing": 1, "slowP": 0,
           "trailR": 0.0, "step": 1.1, "mult": 0.01},
    mode=1, timeout=18000)
print(f"passes: {len(df2)}  positive: {len(df2[df2['nbpR']>0])}/{len(df2)}")
opt_run.show(df2, 12)
