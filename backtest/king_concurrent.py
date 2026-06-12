"""
king_concurrent.py — concurrent operations on the KING (2026-06-12).

Apply concurrency to all three king accounts (geo1.7 / s210 / shield): new H1
breakouts open NEW ops while existing ops keep stacking.  Sweep the concurrency
cap (1/2/3/5/inf) x direction policy (same/opp/both).  Compare the concurrent
king vs the one-at-a-time king on geometric growth-at-matched-DD.

Regression: run_tf_conc(max_conc=1) must reproduce run_tf for the stacking
configs -- asserted up top before any concurrent result is trusted.
"""
import numpy as np
from conc_engine import run_tf_conc
from pyramid_engine import run_tf
from concurrent_geo import geo_sim, at_dd
from stress_audit import op_gap

CFG = {
    "geo1.7": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
}
WEIGHT = {"geo1.7": 0.45, "s210": 0.45, "shield": 0.10}
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
BUD = (13.0, 18.0, 24.0, 30.0)


def conc_ops(name, mc, cd):
    res, tm, H, L, n = run_tf_conc(**CFG[name], max_conc=mc, conc_dir=cd)
    stream = [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L) if o[2] > 0 else None) for o in res]
    return stream, len(res)


def king_row(label, streams):
    legs = [(streams[nm][0], WEIGHT[nm]) for nm in CFG]
    cur = [(f, *geo_sim(legs, f)) for f in FG]
    cells, nops = "", sum(streams[nm][1] for nm in CFG)
    for b in BUD:
        r = at_dd(cur, b)
        cells += (f"{r[0]:>10.1f}x" if r else f"{'--':>11}")
    print(f"{label:<26}{nops:>6}{cells}")


if __name__ == "__main__":
    # ---- regression: conc(max_conc=1) == run_tf for the stacking configs ----
    for nm in ("geo1.7", "s210"):
        c = CFG[nm]
        r1, *_ = run_tf_conc(**c, max_conc=1, conc_dir="same")
        r2, _, _, _ = run_tf("XAU", tf="M15", triggers=("bounce",), smaP=c["smaP"],
                             slowP=c["slowP"], sizing=c["sizing"], unit="base",
                             mult=c["mult"], prog_step=c["prog_step"], tp_R=c["tp_R"], lev=2000.0)
        a, b = sum(o[2] for o in r1), sum(o[2] for o in r2)
        print(f"  regression {nm:<8} conc={a:8.2f}  run_tf={b:8.2f}  "
              f"{'OK' if abs(a-b) < 1e-6 and len(r1) == len(r2) else 'MISMATCH'}  (ops {len(r1)}/{len(r2)})")

    print(f"\n{'king (cap, dir)':<26}{'ops':>6}" + "".join(f"{f'@{int(b)}%':>11}" for b in BUD))
    base = {nm: conc_ops(nm, 1, "same") for nm in CFG}
    king_row("BASELINE one-at-a-time", base)

    for cd in ("same", "opp", "both"):
        print(f"--- direction policy: {cd} ---")
        for mc in (2, 3, 5, 999):
            streams = {nm: conc_ops(nm, mc, cd) for nm in CFG}
            tag = "inf" if mc == 999 else str(mc)
            king_row(f"cap {tag} / {cd}", streams)
