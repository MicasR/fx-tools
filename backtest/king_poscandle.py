"""
king_poscandle.py — swap/add the poscandle component into the King (2026-06-12).
Growth-at-matched-DD vs the baseline king (32.0x @24%DD).  Consistent engine +
stress@$0.40.  Moves suggested by the segment plot:
  - swap s210 -> g1.3 (tamer seg3 sword, RF 13.9 vs 10.8, 1op 19% vs 53%)
  - swap/add g1.1/g1.2 (shield-shaped smoother that dodges seg3, more return)
"""
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd

A = lambda g: dict(trig="poscandle", smaP=7, slowP=0, sizing="proggeo", unit="base",
                   mult=0.01, prog_step=g, tp_R=3.0, stack=True)
CFG = {
    "geo1.7": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
    "g1.1": A(1.1), "g1.2": A(1.2), "g1.3": A(1.3),
}
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
BUD = (13.0, 18.0, 24.0, 30.0)

S = {}
for nm, c in CFG.items():
    res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
    S[nm] = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]

VARIANTS = {
    "KING geo1.7/s210/shield":  [("geo1.7", .45), ("s210", .45), ("shield", .10)],
    "swap s210->g1.3":          [("geo1.7", .45), ("g1.3", .45), ("shield", .10)],
    "swap shield->g1.2":        [("geo1.7", .45), ("s210", .45), ("g1.2", .10)],
    "swap shield->g1.1":        [("geo1.7", .45), ("s210", .45), ("g1.1", .10)],
    "add g1.2 (4th leg)":       [("geo1.7", .40), ("s210", .40), ("shield", .10), ("g1.2", .10)],
    "add g1.1 (4th leg)":       [("geo1.7", .40), ("s210", .40), ("shield", .10), ("g1.1", .10)],
    "swap s210->g1.3 +add g1.1":[("geo1.7", .40), ("g1.3", .40), ("shield", .10), ("g1.1", .10)],
}

def growth(legs):
    cur = [(f, *geo_sim([(S[nm], w) for nm, w in legs], f)) for f in FG]
    return "".join(f"{at_dd(cur, x)[0]:>9.1f}x" if at_dd(cur, x) else f"{'--':>10}" for x in BUD)


print(f"{'king variant':<28}" + "".join(f"{f'@{int(b)}%':>10}" for b in BUD))
for lbl, legs in VARIANTS.items():
    print(f"{lbl:<28}{growth(legs)}")

print(f"\n--- g1.2 4th-leg weight sweep (shield .10, geo=s210=(.90-pc)/2) ---")
for pc in (0.0, 0.05, 0.075, 0.10, 0.15, 0.20):
    half = (0.90 - pc) / 2
    legs = [("geo1.7", half), ("s210", half), ("shield", .10)] + ([("g1.2", pc)] if pc > 0 else [])
    print(f"{f'g1.2 add {int(pc*100)}%':<28}{growth(legs)}")
