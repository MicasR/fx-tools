"""
cross_margin.py — MARGIN FEASIBILITY of running BOTH kings on one account (2026-06-13).
The last unchecked assumption before the cross-instrument portfolio is bankable: do
the two stacking books' COMBINED simultaneously-open positions ever demand more margin
than the shared account has?

Mechanic: the engine caps each op's lots so (total_lots * MPL_eff) <= op equity, and
the whole book scales LINEARLY with the equity stake.  So per op:
   margin_ratio = peak_lots * MPL_eff / E0_engine      (peak margin as a multiple of risk stake)
In the geometric Main account an op of weight w stakes f*w*bal at open and needs
real_margin = margin_ratio * stake.  Sum the real margins of all concurrently-OPEN ops,
divide by account equity -> peak margin utilization.  Utilization is a RATIO (scale-
invariant -> immune to the VOL_MAX idealization).  Conservative equity = realized
balance only (floating gains that actually fund a winner's adds are NOT credited ->
OVERstates utilization).  lev=2000 (MPL_eff = MPL*0.2).  Stress baked per instrument.
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap
from concurrent_geo import geo_sim, at_dd
from pyramid_engine import SPECS

CAP0 = 1000.0; LEV = 2000.0; E0_ENG = 0.01 * CAP0      # engine's per-op equity slice ($10)
FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]


def legs_of(sym, tf, thr, cfgw):
    """Return [(stream, weight)] where each op = (t_open, t_close, R_stressed, margin_ratio)."""
    sp = SPECS[sym]; TR, MPL = sp["TR"], sp["MPL"]; MPL_eff = MPL * 400.0 / LEV
    out = []
    for cfg, w in cfgw:
        res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
        s = []
        for o in res:
            g = op_gap(o, H, L, TR) if o[2] > 0 else None
            R = -1.0 if (o[2] > 0 and g is not None and g < thr) else o[2]
            peak_lots = sum(l for _, _, l in o[5]["log"])           # all adds stay open till op close
            mratio = peak_lots * MPL_eff / o[5]["E0"]               # peak margin / risk stake
            s.append((tm[o[0]], tm[o[1]], R, mratio))
        out.append((s, w))
    return out


GOLD = legs_of("XAU", "M15", 0.40, [
    (dict(smaP=7, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True), 0.500),
    (dict(smaP=5, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True), 0.375),
    (dict(stack=False, tp_R=2.0), 0.125)])
BTC = legs_of("BTC", "H1", 18.0, [
    (dict(smaP=15, slowP=210, sizing="geofloor", unit="base", mult=0.015, prog_step=1.2, tp_R=0.0, trail_R=2.5, stack=True), 0.552),
    (dict(smaP=15, slowP=0,   sizing="proggeo",  unit="base", mult=0.01,  prog_step=1.2, tp_R=3.0, stack=True), 0.248),
    (dict(stack=False, tp_R=1.25), 0.200)])
BOTH = GOLD + BTC


def f_at_dd(legs, b):
    cur = [(f, *geo_sim([(s, w) for s, w in legs], f, 0.0)) for f in FG]
    r = at_dd(cur, b); return r[1] if r else None


def margin_sim(legs, f):
    """Geometric Main account; track peak combined margin utilization (% of balance)."""
    ev = []
    for si, (s, w) in enumerate(legs):
        for oi, (to, tc, R, mr) in enumerate(s):
            ev.append((to, 0, si, oi, w, R, mr)); ev.append((tc, 1, si, oi, w, R, mr))
    ev.sort(key=lambda e: (e[0], e[1]))
    bal = CAP0; openm = {}; stake = {}
    peak_util = 0.0; peak_t = None; peak_nop = 0
    util_series = []
    for t, typ, si, oi, w, R, mr in ev:
        if typ == 0:
            st = f * w * bal
            stake[(si, oi)] = st; openm[(si, oi)] = mr * st
        else:
            st = stake.pop((si, oi)); openm.pop((si, oi), None)
            bal += st * R
        tot_m = sum(openm.values())
        util = tot_m / bal * 100 if bal > 0 else 9e9
        util_series.append(util)
        if util > peak_util:
            peak_util = util; peak_t = t; peak_nop = len(openm)
    return peak_util, peak_t, peak_nop, np.array(util_series)


if __name__ == "__main__":
    # per-op margin-ratio profile
    print("=== per-op peak margin / risk-stake ratio (how many x its stake an op locks in margin) ===")
    for nm, legs in (("GOLD", GOLD), ("BTC", BTC)):
        for s, w in legs:
            mrs = np.array([o[3] for o in s])
            print(f"  {nm:<5} w{w:<6}: ops {len(s):>4}  margin/stake  mean {mrs.mean():>4.1f}x  median {np.median(mrs):>4.1f}x  max {mrs.max():>5.1f}x")

    f24 = f_at_dd(BOTH, 24.0)
    print(f"\n=== peak COMBINED margin utilization (% of account balance), lev 1:2000 ===")
    print(f"    (conservative: floating gains NOT credited to equity -> overstates utilization)\n")
    print(f"{'risk dial f':>14}{'peak util':>11}{'#ops open':>11}   at")
    for lbl, f in [("1.0%/op", 0.01), (f"@24%DD ({f24*100:.2f}%)", f24), ("2.0%/op", 0.02), ("3.0%/op", 0.03)]:
        pu, pt, nop, ser = margin_sim(BOTH, f)
        print(f"{lbl:>14}{pu:>10.1f}%{nop:>11}   {str(pt)[:10]}   (median {np.median(ser):.2f}%, 99pct {np.percentile(ser,99):.1f}%)")

    print("\n  free-margin headroom at 1:2000: an account is liquidated near 100% utilization (margin call ~ margin level<100%).")
    print("  GOLD-alone and BTC-alone for reference:")
    for nm, legs in (("GOLD only", GOLD), ("BTC only", BTC)):
        pu, pt, nop, _ = margin_sim(legs, 0.02)
        print(f"    {nm:<10} @2%/op: peak util {pu:.1f}%  ({nop} ops, {str(pt)[:10]})")
