"""
btc_monster_audit.py — is the smaP18/s360 "124x" monster REAL or a pin jackpot? (2026-06-12)
The structural sweep threw a spike: smaP18/slowP360 = 124x solo / 90x blend, and the
slowP surface EXPLODES monotonically (s210 9.5 -> s280 32.7 -> s360 90.5) — the exact
signature of the gold geofloor-s200 pin-monster (one melt-up op, margin-maxed lot on a
far slow-SMA line, curve-fit spike).  Apply the gold playbook:
  - full stats: 6 segs, 1-op concentration, ex-top-1 totR
  - STRESS SENSITIVITY: totR & g@24 as the flip-threshold widens $18 -> $120.  A
    margin-maxed lot that grazed liquidation DIES as the gap widens; a real edge holds.
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from concurrent_ops import stats
from pyramid_engine import SPECS

SYM = "BTC"; TR = SPECS[SYM]["TR"]; TF = "H1"
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
CANDS = [("smaP18/s360", 18, 360), ("smaP15/s360", 15, 360), ("smaP18/s280", 18, 280),
         ("smaP10/s210", 10, 210), ("smaP15/s210 (incumbent)", 15, 210)]


def build(smaP, slowP):
    res, tm, H, L, n = run_tf_conc(sym=SYM, tf=TF, smaP=smaP, slowP=slowP, sizing="geofloor",
                                   unit="base", mult=0.015, prog_step=1.2, tp_R=0.0,
                                   trail_R=2.5, stack=True, max_conc=1, conc_dir="same")
    return [(tm[o[0]], tm[o[1]], o[2], op_gap(o, H, L, TR) if o[2] > 0 else None) for o in res], tm[0], tm[-1]


def extop1(s, thr):
    """totR and ex-largest-op totR under stress thr (own-stake R units)."""
    cs = [(-1.0 if (R > 0 and g is not None and g < thr) else R) for _, _, R, g in s]
    tot = sum(cs); mx = max(cs) if cs else 0.0
    return tot, tot - mx, mx


def g24(s, thr):
    r = at_dd([(f, *geo_sim([(s, 1.0)], f, thr)) for f in FG], 24.0); return r[0] if r else 0.0


if __name__ == "__main__":
    print("=== BTC H1 monster-candidate AUDIT (stress @ $18 unless noted) ===\n")
    print(f"{'monster':<24}{'ops':>5}{'totR':>8}{'win%':>6}{'maxDD':>7}{'RF':>6}{'1op':>6}{'exTop1':>8}{'g@24':>7}  segs / per-seg")
    S = {}
    for lbl, smaP, slowP in CANDS:
        s, t0, t1 = build(smaP, slowP); S[lbl] = (s, t0, t1)
        st = stats([(s, 1.0)], 18.0, t0, t1)
        tot, ex, mx = extop1(s, 18.0)
        segs = " ".join(f"{x:+5.0f}" for x in st["seg"])
        print(f"{lbl:<24}{st['n']:>5}{st['tot']:>8.1f}{st['win']:>6.1f}{st['dd']:>7.1f}{st['rf']:>6.1f}"
              f"{st['oneop']:>5.0f}%{ex:>8.1f}{g24(s,18.0):>6.1f}x  {st['rob']}/6 {segs}")

    print("\n=== STRESS SENSITIVITY — totR (and g@24) as flip-threshold widens ===")
    print(f"{'monster':<24}" + "".join(f"{'$'+str(t):>16}" for t in (18, 40, 60, 90, 120)))
    for lbl, *_ in CANDS:
        s, t0, t1 = S[lbl]
        cells = ""
        for thr in (18, 40, 60, 90, 120):
            tot, ex, mx = extop1(s, float(thr))
            cells += f"{tot:>8.0f}/{g24(s,float(thr)):>5.1f}x"
        print(f"{lbl:<24}{cells}")
