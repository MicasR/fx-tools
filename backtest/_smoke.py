"""Phase 2 knob smoke test: confirm the §3.6-REDUX inputs actually take effect through
the EA (the regression gate only exercised the default path). Each variant should
differ from the GoldS210 baseline (nbpR 157.4 / 383 ops) and be sane (ops>0, finite)."""
import opt_run

BASE = "GoldS210"  # geofloor gold, smaP5/slowP210/step1.7/tpR3, mtf=M15
VARIANTS = {
    "baseline":        {},
    "poscandle(F)":    {"addtrig": 1},
    "buffer0.5":       {"buffer": 0.5},
    "nback10(G)":      {"lineplace": 1, "nback": 10},
    "pinprev(G)":      {"lineplace": 2},
}
for name, fx in VARIANTS.items():
    r = opt_run.run_single(BASE, fixed=fx)
    print(f"{name:14s} nbpR={r.get('nbpR'):7.1f} ops={r.get('ops'):4d} "
          f"segpos={r.get('segpos')}/6 1op={r.get('oneop'):.0f}%  fixed={fx}")
