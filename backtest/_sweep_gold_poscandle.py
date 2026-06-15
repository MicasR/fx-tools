"""Phase 2 sweep #1 — GOLD poscandle (archetype F) across the aggression knobs.
geofloor sizing (where buffer/anchor matter); sweep step x buffer x slowP x TP(low->high).
Probe grid (4x4x5x3 = 240). If a viable corner exists (positive nbpR, monsters), densify;
if uniformly dead, archetype F is rejected cheaply. -> out/opt/gold_poscandle.csv"""
import opt_run

df = opt_run.run_opt(
    "gold_poscandle", "GoldS210",
    opt={"step": (1.1, 0.3, 2.0),     # 1.1,1.4,1.7,2.0
         "buffer": (0.0, 0.25, 0.75), # 0,0.25,0.5,0.75  (aggression dial)
         "tpR": (1.0, 0.5, 3.0),      # 1,1.5,2,2.5,3    (low TP for aggressors)
         "slowP": (150, 60, 270)},    # 150,210,270      (anchor distance)
    fixed={"addtrig": 1, "sizing": 1, "smaP": 5, "half": 0.5, "trailR": 0.0},
    mode=1, timeout=14400)

print(f"passes: {len(df)}")
opt_run.show(df, 20)
pos = df[df["nbpR"] > 0]
print(f"\npositive nbpR: {len(pos)}/{len(df)}")
if len(pos):
    print(f"best nbpR={pos['nbpR'].max():.1f}  best score={df['score'].max():.1f}")
    if "nmonster" in df.columns:
        print(f"max nmonster={int(df['nmonster'].max())}  "
              f"max extop1R={df['extop1R'].max():.1f}")
