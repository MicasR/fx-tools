"""
Compare VolumeSpike vs VolumeVPattern on cached XAU/USD data.

Loads data/<symbol>_<tf>.csv, computes both signal sets, evaluates them, prints
a comparison table, and writes charts to out/ that can be inspected directly.

Usage:
    python compare.py --tf M15 --method stddev --rise 0.02
"""
import argparse
import glob
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import signals as sg


def load(tf: str) -> tuple[pd.DataFrame, str]:
    files = glob.glob(f"data/*_{tf}.csv")
    if not files:
        raise SystemExit(f"No data/*_{tf}.csv — run fetch_data.py --tf {tf} first.")
    path = files[0]
    df = pd.read_csv(path, parse_dates=["time"])
    sym = path.split("\\")[-1].split("/")[-1].replace(f"_{tf}.csv", "")
    return df, sym


def fmt_row(name, r):
    return (f"{name:<16} {r['n_signals']:>7} "
            f"{r['fwd_winrate'][8]*100:>8.1f} "
            f"{r['fwd_mean_bps'][8]:>9.1f} "
            f"{r['avg_mfe_pct']:>8.2f} {r['avg_mae_pct']:>8.2f} {r['mfe_mae_ratio']:>7.2f} "
            f"{r['bracket_winrate']*100:>8.1f} {r['bracket_avg_R']:>8.3f} {r['bracket_total_R']:>9.1f} "
            f"{r['struct_winrate']*100:>8.1f} {r['struct_avg_R']:>8.3f} {r['struct_total_R']:>9.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M15")
    ap.add_argument("--method", default="stddev",
                    choices=["stddev", "zscore", "percentile", "threshold"])
    ap.add_argument("--rise", type=float, default=0.02)
    ap.add_argument("--mult", type=float, default=2.0)
    ap.add_argument("--rr", type=float, default=1.5)
    ap.add_argument("--atr-mult", type=float, default=1.5)
    args = ap.parse_args()

    df, sym = load(args.tf)
    df = sg.add_features(df, mult=args.mult)

    vs_sig = sg.volumespike_signal(df, method=args.method)
    vp_sig = sg.volumevpattern_signal(df, method=args.method, rise_pct=args.rise)

    ev = dict(horizons=(4, 8, 16), atr_mult=args.atr_mult, rr=args.rr, struct_rr=args.rr)
    vs = sg.evaluate(df, vs_sig, **ev)
    vp = sg.evaluate(df, vp_sig, **ev)

    span = f"{df['time'].iloc[0]:%Y-%m-%d} -> {df['time'].iloc[-1]:%Y-%m-%d}"
    print("=" * 130)
    print(f"  {sym}  {args.tf}   {span}   ({len(df):,} bars)   method={args.method}  "
          f"rise={args.rise:.0%}  ATR bracket={args.atr_mult}xATR @ 1:{args.rr}  "
          f"struct bracket=C1 extreme @ 1:{args.rr}")
    print("=" * 130)
    print(f"{'':<54}|{'  ATR bracket  ':^27}|{'  struct bracket (C1 stop)  ':^27}")
    hdr = (f"{'indicator':<16} {'signals':>7} {'win%@8':>8} {'ret@8bps':>9} "
           f"{'MFE%':>8} {'MAE%':>8} {'MFE/MAE':>7} {'brkWin%':>8} {'avgR':>8} {'totR':>9} "
           f"{'sWin%':>8} {'savgR':>8} {'stotR':>9}")
    print(hdr)
    print("-" * len(hdr))
    print(fmt_row("VolumeSpike", vs))
    print(fmt_row("VolumeVPattern", vp))
    if vs["struct_skipped"] or vp["struct_skipped"]:
        print(f"  (struct trades skipped on entry gaps — "
              f"VS:{vs['struct_skipped']}  VP:{vp['struct_skipped']})")
    print("=" * 130)

    _plots(df, sym, args, vs_sig, vp_sig, vs, vp)


def _plots(df, sym, args, vs_sig, vp_sig, vs, vp):
    t = df["time"]

    # 1) Equity curves (cumulative R) — ATR bracket (solid) vs struct bracket (dashed)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(np.cumsum(vs["rmults"]), color="#888", lw=1.8,
            label=f"VolumeSpike · ATR (n={vs['n_signals']})")
    ax.plot(np.cumsum(vp["rmults"]), color="#1f77b4", lw=1.8,
            label=f"VolumeVPattern · ATR (n={vp['n_signals']})")
    ax.plot(np.cumsum(vs["srmults"]), color="#888", lw=1.5, ls="--",
            label=f"VolumeSpike · struct (n={vs['struct_n']})")
    ax.plot(np.cumsum(vp["srmults"]), color="#1f77b4", lw=1.5, ls="--",
            label=f"VolumeVPattern · struct (n={vp['struct_n']})")
    ax.axhline(0, color="k", lw=.6, alpha=.5)
    ax.set_title(f"{sym} {args.tf} — cumulative R  (method={args.method}, "
                 f"rise={args.rise:.0%}, 1:{args.rr})")
    ax.set_xlabel("signal #"); ax.set_ylabel("cumulative R"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig("out/equity.png", dpi=110); plt.close(fig)

    # 2) Metric bars
    metrics = [
        ("signals", vs["n_signals"], vp["n_signals"]),
        ("win%@8", vs["fwd_winrate"][8] * 100, vp["fwd_winrate"][8] * 100),
        ("MFE/MAE", vs["mfe_mae_ratio"], vp["mfe_mae_ratio"]),
        ("ATR avg R", vs["bracket_avg_R"], vp["bracket_avg_R"]),
        ("struct avg R", vs["struct_avg_R"], vp["struct_avg_R"]),
    ]
    fig, axes = plt.subplots(1, len(metrics), figsize=(15, 3.5))
    for ax, (name, a, b) in zip(axes, metrics):
        ax.bar(["VS", "VP"], [a, b], color=["#888", "#1f77b4"])
        ax.set_title(name, fontsize=10)
        for x, val in enumerate([a, b]):
            ax.text(x, val, f"{val:.2f}", ha="center", va="bottom", fontsize=8)
        ax.grid(alpha=.3, axis="y")
    fig.suptitle(f"{sym} {args.tf} — VolumeSpike vs VolumeVPattern", y=1.04)
    fig.tight_layout(); fig.savefig("out/metrics.png", dpi=110, bbox_inches="tight"); plt.close(fig)

    # 3) Zoomed price with both signal sets (last ~400 bars)
    w = df.iloc[-400:]
    wv = vs_sig.iloc[-400:]
    wp = vp_sig.iloc[-400:]
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(w["time"], w["close"], color="#333", lw=.9, label="close")
    ax.scatter(w["time"][wv], w["low"][wv] * 0.999, marker="^", color="#d62728",
               s=42, label="VolumeSpike", zorder=5)
    ax.scatter(w["time"][wp], w["high"][wp] * 1.001, marker="v", color="#1f77b4",
               s=42, label="VolumeVPattern", zorder=5)
    ax.set_title(f"{sym} {args.tf} — signal placement (last {len(w)} bars)")
    ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig("out/signals_zoom.png", dpi=110); plt.close(fig)

    print("Charts written: out/equity.png  out/metrics.png  out/signals_zoom.png")


if __name__ == "__main__":
    main()
