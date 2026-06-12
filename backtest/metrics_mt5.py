"""
metrics_mt5.py — MT5-style backtest report for the KING (2026-06-12).

Main account $1000, geometric: each operation stakes f * weight * current balance
at open, realizes that * R at close.  King = geo1.7/s210/shield at 45/45/10, so
at f=1% a sword op risks 0.45% and a shield op 0.10% of the live balance ("1% per
operation-cycle" dialed across the crowned mix).  Each OPERATION = one "trade"
(the joint book shares one -1R floor + TP).  Consistent engine (run_tf_conc,
all legs -1R floor) + stress@$0.40.  Reports standard MT5 Strategy-Tester metrics.
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap

CFG = {
    "geo1.7": dict(smaP=7, slowP=0,   sizing="proggeo",  mult=0.01,  prog_step=1.7, tp_R=3.0, stack=True),
    "s210":   dict(smaP=5, slowP=210, sizing="geofloor", mult=0.015, prog_step=1.7, tp_R=3.0, stack=True),
    "shield": dict(stack=False, tp_R=2.0),
}
WEIGHT = {"geo1.7": 0.50, "s210": 0.375, "shield": 0.125}   # crowned rounded-plateau king
CAP0 = 1000.0
THR = 0.40


def streams():
    out = {}
    t0g = t1g = None
    for nm, c in CFG.items():
        res, tm, H, L, n = run_tf_conc(**c, max_conc=1, conc_dir="same")
        s = []
        for o in res:
            g = op_gap(o, H, L) if o[2] > 0 else None
            R = -1.0 if (o[2] > 0 and g is not None and g < THR) else o[2]   # stress flip
            s.append((tm[o[0]], tm[o[1]], R))
        out[nm] = s
        t0g = tm[0] if t0g is None else min(t0g, tm[0])
        t1g = tm[-1] if t1g is None else max(t1g, tm[-1])
    return out, t0g, t1g


def simulate(f):
    S, t0, t1 = streams()
    ev = []
    for nm, s in S.items():
        w = WEIGHT[nm]
        for i, (to, tc, R) in enumerate(s):
            ev.append((to, 0, nm, i, w, R))
            ev.append((tc, 1, nm, i, w, R))
    ev.sort(key=lambda e: (e[0], e[1]))
    bal = CAP0; stake = {}; trades = []          # (close_time, pnl, bal_after, ret)
    peak = bal; ddmax = 0.0; ddmax_pct = 0.0
    for t, typ, nm, i, w, R in ev:
        if typ == 0:
            stake[(nm, i)] = f * w * bal
        else:
            st = stake.pop((nm, i)); pnl = st * R
            ret = pnl / bal
            bal += pnl
            peak = max(peak, bal)
            ddmax = max(ddmax, peak - bal); ddmax_pct = max(ddmax_pct, (peak - bal) / peak * 100)
            trades.append((t, pnl, bal, ret))
    years = (t1 - t0) / np.timedelta64(365, "D")
    return trades, bal, ddmax, ddmax_pct, years, t0, t1


def report(f):
    trades, bal, ddmax, ddmax_pct, years, t0, t1 = simulate(f)
    pnl = np.array([x[1] for x in trades])
    rets = np.array([x[3] for x in trades])
    n = len(pnl)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gp, gl = wins.sum(), -losses.sum()
    net = bal - CAP0
    # consecutive streaks
    mcw = mcl = cw = cl = 0
    for p in pnl:
        if p > 0:
            cw += 1; cl = 0; mcw = max(mcw, cw)
        else:
            cl += 1; cw = 0; mcl = max(mcl, cl)
    sharpe = rets.mean() / rets.std() if rets.std() > 0 else 0
    cagr = (bal / CAP0) ** (1 / years) - 1

    print(f"\n================  KING — MT5-style report  (risk dial f = {f*100:.0f}%/op-cycle) ================")
    print(f"  Period                 {str(t0)[:10]} -> {str(t1)[:10]}   ({years:.2f} years)")
    print(f"  Initial deposit        ${CAP0:,.2f}")
    print(f"  Ending balance         ${bal:,.2f}        ({bal/CAP0:.1f}x)")
    print(f"  Total Net Profit       ${net:,.2f}        ({net/CAP0*100:,.0f}%)")
    print(f"  CAGR (annualized)      {cagr*100:,.1f}%")
    print(f"  Gross Profit           ${gp:,.2f}")
    print(f"  Gross Loss            -${gl:,.2f}")
    print(f"  Profit Factor          {gp/gl:.2f}")
    print(f"  Expected Payoff        ${net/n:,.2f}  per trade")
    print(f"  Recovery Factor        {net/ddmax:.2f}")
    print(f"  Sharpe Ratio           {sharpe:.2f}  (per-trade)")
    print(f"  Balance DD Maximal     ${ddmax:,.2f}   ({ddmax_pct:.1f}%)")
    print(f"  -------------------------------------------------------------")
    print(f"  Total Trades (ops)     {n}")
    print(f"  Profit Trades          {len(wins)}  ({len(wins)/n*100:.1f}%)")
    print(f"  Loss Trades            {len(losses)}  ({len(losses)/n*100:.1f}%)")
    print(f"  Largest profit trade   ${wins.max():,.2f}")
    print(f"  Largest loss trade     ${losses.min():,.2f}")
    print(f"  Average profit trade   ${wins.mean():,.2f}")
    print(f"  Average loss trade     ${losses.mean():,.2f}")
    print(f"  Max consecutive wins   {mcw}")
    print(f"  Max consecutive losses {mcl}")


def plot(fs=(0.01, 0.02)):
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    os.makedirs("out", exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    colors = {0.01: "#1f77b4", 0.02: "#d62728"}
    for f in fs:
        trades, bal, ddmax, ddmax_pct, years, t0, t1 = simulate(f)
        t = [t0] + [x[0] for x in trades]
        b = [CAP0] + [x[2] for x in trades]
        t = np.array(t, dtype="datetime64[s]").astype("datetime64[ms]").astype("O")
        b = np.array(b)
        peak = np.maximum.accumulate(b)
        dd = (peak - b) / peak * 100
        lbl = f"{int(f*100)}%/op   ${b[-1]:,.0f}  ({b[-1]/CAP0:.1f}x, DD {ddmax_pct:.0f}%)"
        ax1.plot(t, b, color=colors.get(f), lw=1.6, label=lbl)
        ax2.fill_between(t, dd, 0, color=colors.get(f), alpha=0.35, lw=0)

    ax1.set_yscale("log")
    ax1.set_ylabel("Balance  $  (log)")
    ax1.set_title("KING (geo1.7 / s210 / TP2.0-shield  50/37.5/12.5) — $1000 Main, geometric, stress@$0.40")
    ax1.legend(loc="upper left", framealpha=0.9)
    ax1.grid(True, which="both", alpha=0.25)
    ax2.set_ylabel("Drawdown %"); ax2.invert_yaxis()
    ax2.grid(True, alpha=0.25)
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig("out/king_equity.png", dpi=110)
    print("saved out/king_equity.png")


def growth_at_dd():
    from concurrent_geo import geo_sim, at_dd
    S, t0, t1 = streams()                       # already stress-flipped (3-tuples)
    legs = [([(a, b, R, None) for a, b, R in S[nm]], WEIGHT[nm]) for nm in CFG]
    FG = [0.0005, 0.001, 0.0015, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.03, 0.05]
    cur = [(f, *geo_sim(legs, f)) for f in FG]
    print("\n  growth-at-matched-DD (crown metric): " +
          "  ".join(f"@{b}%={at_dd(cur, b)[0]:.1f}x" for b in (13, 18, 24, 30)))


if __name__ == "__main__":
    report(0.01)
    report(0.02)
    growth_at_dd()
    plot()
