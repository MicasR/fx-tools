"""
margin_buffer.py — MIN-BUFFER on the margin line (user's idea, 2026-06-12).

The geofloor pin sizes each add to push the book's liquidation line up to the
slow SMA.  When the slow SMA hugs price, lot_to_pin explodes (lot ~ 1/(P-S)) ->
the margin-maxed "monster" ops.  This sweep clamps the line so it can never sit
closer than `buf` to price: a slow SMA inside the buffer gets pinned AT the
buffer instead, capping the lot.  Does the floor kill the monster but keep the
ordinary stacking — or is it a net improvement?

Gold M15, point = 0.001 (3-decimal feed) -> buffer in $ = points * 0.001.
Sweep: spread (400pt = $0.40) then 3000..10000pt ($3..$10), per the user.
Judged on the SPREAD-STRESS@$0.40 exam (heads row = thr 0).  Champion +
buf=0 leading candidate included as benchmarks.
"""
import numpy as np
from pyramid_engine import run_tf
from stress_audit import op_gap, frame
from sweep_candidate import HDR, stats, row

POINT = 0.001  # gold: 3-decimal feed -> 1 point = $0.001
CFG = dict(tf="M15", triggers=("bounce",), sizing="geofloor", unit="base",
           prog_step=1.7, lev=2000.0)


def audit(lbl, smaP, slowP, mult, buf, H, L):
    ops, _, _, n = run_tf("XAU", smaP=smaP, slowP=slowP, mult=mult, buf=buf, **CFG)
    gaps = [op_gap(o, H, L) if o[2] > 0 else None for o in ops]
    row(lbl, 0.0, stats(ops, gaps, n, 0.0))     # heads (as recorded)
    s4 = stats(ops, gaps, n, 0.40)
    row(lbl, 0.40, s4)                           # stressed @ $0.40
    return s4


def sweep(title, slowP, mult, H, L):
    print(f"\n=== {title} (points -> $) ===")
    res = {}
    for pts in [0, 400, 1000, 2000, 3000, 4000, 5000, 6000, 8000, 10000]:
        buf = pts * POINT
        lbl = "buf 0 (no floor)" if pts == 0 else f"buf {pts}pt (${buf:.2f})"
        res[pts] = audit(lbl, 5, slowP, mult, buf, H, L)
    ok = {p: s for p, s in res.items() if s["rob"] == 6}
    pool = ok if ok else res
    bp = max(pool, key=lambda p: pool[p]["tot"])
    print(f"--> best buffer (stressed, 6/6 if any) = {bp}pt (${bp*POINT:.2f}), "
          f"totR {res[bp]['tot']:.1f}, avgR {res[bp]['avg']:.2f}, 1op {res[bp]['oneop']:.0f}%")
    return res


if __name__ == "__main__":
    print(HDR)

    # benchmarks
    m = frame(7, 0); H7, L7 = m["high"].to_numpy(), m["low"].to_numpy()
    ops, _, _, n = run_tf("XAU", smaP=7, sizing="proggeo", unit="base",
                          mult=0.01, prog_step=1.7, lev=2000.0, tf="M15",
                          triggers=("bounce",))
    gaps = [op_gap(o, H7, L7) if o[2] > 0 else None for o in ops]
    row("champion geo1.7", 0.0, stats(ops, gaps, n, 0.0))
    row("champion geo1.7", 0.40, stats(ops, gaps, n, 0.40))

    m = frame(5, 200); H2, L2 = m["high"].to_numpy(), m["low"].to_numpy()
    sweep("buffer sweep: geofloor f5/s200 g1.7 1% (deploy lead)", 200, 0.01, H2, L2)

    m = frame(5, 210); H3, L3 = m["high"].to_numpy(), m["low"].to_numpy()
    sweep("buffer sweep: geofloor f5/s210 g1.7 1.5% (research ceiling)", 210, 0.015, H3, L3)
