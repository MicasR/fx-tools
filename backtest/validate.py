"""
Out-of-sample validation for VolumeSpikeBreakOut across PERIOD and TIMEFRAME.

For a given timeframe, runs Spike vs V-pattern (breakout entry, structural 1:3,
NET of a round-trip cost) over the full cached history AND across N equal
segments, so robustness is judged over many sub-periods — not one split.

Run:  python validate.py --tf H1 --segments 6 --cost 0.40
"""
import argparse
import glob
import os
import numpy as np
import pandas as pd

import signals as sg
from experiments import evaluate_dir, stats

RR, WAIT = 3.0, 4


def row(df, sig, cost):
    d = sg.add_features(df.reset_index(drop=True), period=20, mult=2.0)
    sg2 = sig(d)
    r = evaluate_dir(d, sg2, mode="break", break_wait=WAIT, rr=RR, spread=cost)
    return stats(r["str_R"]), r["str_risk_px"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--symbol", default="", help="substring to pick the data file (e.g. XAG, EUR, BTC)")
    ap.add_argument("--segments", type=int, default=6)
    ap.add_argument("--cost", type=float, default=0.40)
    ap.add_argument("--from", dest="date_from", default="", help="ISO start date to slice from")
    args = ap.parse_args()

    path = glob.glob(f"data/*{args.symbol}*_{args.tf}.csv")
    if not path:
        raise SystemExit(f"No data/*{args.symbol}*_{args.tf}.csv — fetch it first.")
    fpath = sorted(path)[0]
    sym = os.path.basename(fpath).split("_")[0]
    full = pd.read_csv(fpath, parse_dates=["time"])
    if args.date_from:
        full = full[full["time"] >= pd.Timestamp(args.date_from)].reset_index(drop=True)
    spike = lambda d: sg.volumespike_signal(d, method="threshold")
    vpat = lambda d: sg.volumevpattern_signal(d, method="threshold", rise_pct=0.02)

    span = f"{full['time'].iloc[0]:%Y-%m-%d}..{full['time'].iloc[-1]:%Y-%m-%d}"
    print(f"\n{'='*86}")
    print(f"  {sym} {args.tf}   {span}   ({len(full):,} bars)   "
          f"breakout 1:3, struct stop, net cost ${args.cost:g}/round-trip")
    print(f"{'='*86}")

    def show(label, df):
        (sp, spr), (vp, vpr) = row(df, spike, args.cost), row(df, vpat, args.cost)
        print(f"{label:<22}"
              f"| Spike n{sp['n']:>4} avgR{sp['avgR']:>7.3f} totR{sp['totR']:>7.1f} PF{sp['pf']:>5.2f} "
              f"| Vpat n{vp['n']:>4} avgR{vp['avgR']:>7.3f} totR{vp['totR']:>7.1f} PF{vp['pf']:>5.2f}")
        return sp, vp

    sp_f, vp_f = show("FULL", full)
    sp_risk, vp_risk = row(full, spike, 0)[1], row(full, vpat, 0)[1]
    print(f"{'(avg $risk/trade)':<22}| Spike ${sp_risk:<10.5g}| Vpat ${vp_risk:<10.5g}"
          f"| cost = ${args.cost:g} ({100*args.cost/vp_risk:.1f}% of V risk)")
    print("-" * 86)

    n = len(full)
    seg = n // args.segments
    segs = []
    for k in range(args.segments):
        lo = k * seg
        hi = n if k == args.segments - 1 else (k + 1) * seg
        d = full.iloc[lo:hi]
        lab = f"  seg{k+1} {d['time'].iloc[0]:%Y-%m}.{d['time'].iloc[-1]:%m}"
        segs.append(show(lab, d))

    print("-" * 86)
    sp_pos = sum(1 for s, _ in segs if s["avgR"] > 0)
    vp_pos = sum(1 for _, v in segs if v["avgR"] > 0)
    sp_mean = np.mean([s["avgR"] for s, _ in segs])
    vp_mean = np.mean([v["avgR"] for _, v in segs])
    print(f"CONSISTENCY  (across {args.segments} segments, net struct avg R):")
    print(f"  Spike : positive {sp_pos}/{args.segments},  mean-segment avgR {sp_mean:+.3f},  full avgR {sp_f['avgR']:+.3f}")
    print(f"  Vpat  : positive {vp_pos}/{args.segments},  mean-segment avgR {vp_mean:+.3f},  full avgR {vp_f['avgR']:+.3f}")
    print(f"{'='*86}")


if __name__ == "__main__":
    main()
