"""
concurrent_geo.py — GEOMETRIC scale-to-DD test (2026-06-12).

concurrent_ops showed COMBO1 (geo1.7 + s210) beats both champions on RF (16.1)
at geo1.7-level DD, but its raw R-stream totR (213) is bounded below s210's 259.
Claim to verify: in the GEOMETRIC two-account model terminal wealth is governed
by RF, not raw totR (you size the risk fraction f to a DD budget) -> the combo's
RF headroom lets it run a bigger f at the same DD and OUT-GROW s210 in absolute
Main-account terms.

Method: take each strategy's stressed per-op R-stream as the edge; compound one
Main account where each op stakes f*(current C) at open and realizes f*C*R at
close (combo = two accounts, f/2 each, interleaved by time so one account's win
refills the other's drawdown).  Sweep f -> (growth x, realized %-equity maxDD).
Then read growth at matched DD budgets.  Loss floor = -1R, so C>0 for f<1.

ASSUMPTION: edge (R per op) is stable with scale (lots scale cleanly; ignores
VOL_MIN/VOL_MAX re-clamping as C compounds).  Isolates the RF->wealth question.
Stressed @ $0.40.
"""
import numpy as np
from concurrent_ops import stream, CFG

THR = 0.40
CAP0 = 1000.0


def geo_sim(legs, f, thr=THR):
    """legs = [(stream, m), ...]; each op stakes f*m*C at open, realizes f*m*C*R.
    Returns (growth_multiple, realized %-equity maxDD)."""
    ev = []
    for si, (s, m) in enumerate(legs):
        for oi, (t0, t1, R, gap) in enumerate(s):
            r = -1.0 if (R > 0 and gap is not None and gap < thr) else R
            ev.append((t0, 0, si, oi, m, r))   # open
            ev.append((t1, 1, si, oi, m, r))   # close
    ev.sort(key=lambda e: (e[0], e[1]))        # open(0) before close(1) at same ts
    C = CAP0; stakes = {}; peak = C; dd = 0.0
    for _, typ, si, oi, m, r in ev:
        if typ == 0:
            stakes[(si, oi)] = f * m * C
        else:
            C += stakes.pop((si, oi)) * r
            peak = max(peak, C); dd = max(dd, (peak - C) / peak)
    return C / CAP0, dd * 100


def at_dd(points, target):
    """Interpolate (growth, f) at a target DD% from points sorted by f (dd rising)."""
    for i in range(1, len(points)):
        f0, g0, d0 = points[i - 1]; f1, g1, d1 = points[i]
        if d0 <= target <= d1 and d1 > d0:
            w = (target - d0) / (d1 - d0)
            return g0 + w * (g1 - g0), f0 + w * (f1 - f0)
    return None


FGRID = [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]


if __name__ == "__main__":
    S1, S5 = {}, {}
    for nm in CFG:
        S1[nm], _, _ = stream(nm, 0.01)
        S5[nm], _, _ = stream(nm, 0.005)

    strats = {
        "geo1.7 @1R":           [(S1["geo1.7"], 1.0)],
        "f5/s210 1.5% @1R":     [(S1["f5/s210 1.5%"], 1.0)],
        "f5/s200 @1R":          [(S1["f5/s200"], 1.0)],
        "COMBO1 geo1.7+s210":   [(S5["geo1.7"], 0.5), (S5["f5/s210 1.5%"], 0.5)],
        "COMBO2 geo1.7+s200":   [(S5["geo1.7"], 0.5), (S5["f5/s200"], 0.5)],
    }

    curves = {}
    for nm, legs in strats.items():
        curves[nm] = [(f, *geo_sim(legs, f)) for f in FGRID]

    print("=== growth x (and realized %-equity maxDD) vs risk fraction f, stressed@$0.40 ===")
    print(f"{'f':>7} " + "".join(f"{nm[:18]:>22}" for nm in strats))
    for i, f in enumerate(FGRID):
        cells = "".join(f"{curves[nm][i][1]:>12.1f}x/{curves[nm][i][2]:>5.1f}%" for nm in strats)
        print(f"{f:>7.4f} {cells}")

    print("\n=== growth at MATCHED DD budget (interpolated f) ===")
    print(f"{'DD budget':>10}  " + "".join(f"{nm[:20]:>24}" for nm in strats))
    for tgt in (13.0, 18.0, 24.0, 30.0):
        cells = ""
        for nm in strats:
            r = at_dd(curves[nm], tgt)
            cells += (f"{r[0]:>16.1f}x @f{r[1]*100:>4.2f}%" if r else f"{'--':>24}")
        print(f"{tgt:>9.0f}%  {cells}")
