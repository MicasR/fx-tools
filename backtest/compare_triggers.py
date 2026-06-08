"""
Head-to-head: which TRIGGER pairs best with the breakout entry?

  A) Spike trigger     (VolumeSpike: volume > threshold)  + break(wait=4)
  B) V-pattern trigger (VolumeVPattern)                   + break(wait=4)

Judged on the structural bracket (the strictest, stop = trigger-bar extreme),
across the full sample AND four time quarters, with profit factor and R-curve
max drawdown — so the winner is the one that is most CONSISTENTLY positive, not
just the one with the best full-period average.

Run:  python compare_triggers.py
"""
import glob
import numpy as np
import pandas as pd

import signals as sg
from experiments import evaluate_dir, stats

RR, WAIT = 3.0, 4


def metrics_for(df):
    df = sg.add_features(df.reset_index(drop=True), period=20, mult=2.0)
    spike = sg.volumespike_signal(df, method="threshold")
    vpat = sg.volumevpattern_signal(df, method="threshold", rise_pct=0.02)
    a = evaluate_dir(df, spike, mode="break", break_wait=WAIT, rr=RR)
    b = evaluate_dir(df, vpat, mode="break", break_wait=WAIT, rr=RR)
    return a, b


def show(label, df):
    a, b = metrics_for(df)
    sa, sb = stats(a["str_R"]), stats(b["str_R"])
    print(f"\n=== {label}  ({df['time'].iloc[0]:%Y-%m-%d}..{df['time'].iloc[-1]:%Y-%m-%d}, {len(df):,} bars) ===")
    print(f"{'trigger+break(w4)':<22}{'n':>5}{'win%':>7}{'avgR':>8}{'totR':>8}{'PF':>7}{'maxDD':>8}{'maxLoss':>8}")
    print("-" * 73)
    for nm, s in [("A) Spike + break", sa), ("B) Vpattern + break", sb)]:
        print(f"{nm:<22}{s['n']:>5}{s['win']:>7.1f}{s['avgR']:>8.3f}{s['totR']:>8.1f}"
              f"{s['pf']:>7.2f}{s['maxdd']:>8.1f}{s['maxloss']:>8}")
    return sa, sb


if __name__ == "__main__":
    full = pd.read_csv(glob.glob("data/*_H1.csv")[0], parse_dates=["time"])
    n = len(full)
    q = n // 4

    print("STRUCTURAL BRACKET (stop = trigger-bar extreme, target 1:3, break confirm = 4 bars)")
    show("FULL", full)
    qstats = []
    for k in range(4):
        lo = k * q
        hi = n if k == 3 else (k + 1) * q
        sa, sb = show(f"Q{k+1}", full.iloc[lo:hi])
        qstats.append((sa, sb))

    # consistency scorecard
    a_pos = sum(1 for sa, _ in qstats if sa["avgR"] > 0)
    b_pos = sum(1 for _, sb in qstats if sb["avgR"] > 0)
    a_avg = np.mean([sa["avgR"] for sa, _ in qstats])
    b_avg = np.mean([sb["avgR"] for _, sb in qstats])
    print("\n" + "=" * 73)
    print("CONSISTENCY SCORECARD  (across 4 quarters, structural avg R)")
    print(f"  A) Spike + break    : positive in {a_pos}/4 quarters, mean-of-quarter avgR = {a_avg:+.3f}")
    print(f"  B) Vpattern + break : positive in {b_pos}/4 quarters, mean-of-quarter avgR = {b_avg:+.3f}")
    print("=" * 73)
