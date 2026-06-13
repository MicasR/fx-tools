"""
cross_mt5.py — MT5-style report + equity image for GOLD alone / BTC alone / BOTH (2026-06-13).
Geometric $1000 Main account: each operation stakes f*weight*current-balance at open,
realizes that * R at close (one op = one "trade", shares one -1R floor).  Gold king
(.50/.375/.125, M15, stress $0.40) and BTC king v3 (.552/.248/.200, H1, stress $18);
BOTH = all 6 legs, 1R each.  Image: 3 equity curves (log) + drawdown, with the 6
time-segments marked by vertical dividers.
"""
import numpy as np
from conc_engine import run_tf_conc
from stress_audit import op_gap
from pyramid_engine import SPECS

CAP0 = 1000.0


def legs_of(sym, tf, thr, cfgw):
    sp = SPECS[sym]; TR = sp["TR"]
    out = []
    for cfg, w in cfgw:
        res, tm, H, L, n = run_tf_conc(sym=sym, tf=tf, **cfg, max_conc=1, conc_dir="same")
        s = []
        for o in res:
            g = op_gap(o, H, L, TR) if o[2] > 0 else None
            R = -1.0 if (o[2] > 0 and g is not None and g < thr) else o[2]
            s.append((tm[o[0]], tm[o[1]], R))
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
PORTS = {"GOLD alone": GOLD, "BTC alone": BTC, "BOTH (1R each)": BOTH}


def simulate(legs, f):
    ev = []
    for si, (s, w) in enumerate(legs):
        for oi, (to, tc, R) in enumerate(s):
            ev.append((to, 0, si, oi, w, R)); ev.append((tc, 1, si, oi, w, R))
    ev.sort(key=lambda e: (e[0], e[1]))
    bal = CAP0; stake = {}; trades = []; peak = bal; ddmax = ddpct = 0.0
    for t, typ, si, oi, w, R in ev:
        if typ == 0:
            stake[(si, oi)] = f * w * bal
        else:
            pnl = stake.pop((si, oi)) * R; ret = pnl / bal; bal += pnl
            peak = max(peak, bal); ddmax = max(ddmax, peak - bal); ddpct = max(ddpct, (peak - bal) / peak * 100)
            trades.append((t, pnl, bal, ret))
    t0 = min(min(o[0] for o in s) for s, _ in legs)
    t1 = max(max(o[1] for o in s) for s, _ in legs)
    years = (t1 - t0) / np.timedelta64(365, "D")
    return trades, bal, ddmax, ddpct, years, t0, t1


def report(name, legs, f):
    trades, bal, ddmax, ddpct, years, t0, t1 = simulate(legs, f)
    pnl = np.array([x[1] for x in trades]); rets = np.array([x[3] for x in trades])
    n = len(pnl); wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gp, gl = wins.sum(), -losses.sum(); net = bal - CAP0
    mcw = mcl = cw = cl = 0
    for p in pnl:
        if p > 0: cw += 1; cl = 0; mcw = max(mcw, cw)
        else: cl += 1; cw = 0; mcl = max(mcl, cl)
    cagr = (bal / CAP0) ** (1 / years) - 1
    print(f"\n===========  {name}  —  f = {f*100:.0f}%/op   ({str(t0)[:10]}->{str(t1)[:10]}, {years:.2f}y)  ===========")
    print(f"  Ending balance     ${bal:>12,.2f}   ({bal/CAP0:>6.1f}x)        Total Net Profit  ${net:>12,.2f}  ({net/CAP0*100:>6,.0f}%)")
    print(f"  CAGR               {cagr*100:>11,.1f}%                          Profit Factor     {gp/gl:>12.2f}")
    print(f"  Balance DD max     ${ddmax:>12,.2f}   ({ddpct:>5.1f}%)        Recovery Factor   {net/ddmax:>12.2f}")
    print(f"  Trades (ops)       {n:>12}                          Win rate          {len(wins)/n*100:>11.1f}%")
    print(f"  Largest win        ${wins.max():>12,.2f}                  Largest loss     ${losses.min():>12,.2f}")
    print(f"  Avg win            ${wins.mean():>12,.2f}                  Avg loss         ${losses.mean():>12,.2f}")
    print(f"  Max consec wins    {mcw:>12}                          Max consec losses {mcl:>11}")


def streak_stats(legs):
    """Win% and consecutive-win/loss run lengths, ops ordered by close time (dial-independent)."""
    from itertools import groupby
    ops = sorted(((tc, R) for s, _ in legs for (to, tc, R) in s), key=lambda x: x[0])
    signs = [1 if R > 0 else 0 for _, R in ops]
    n = len(signs); wins = sum(signs)
    runs_w = [sum(1 for _ in g) for k, g in groupby(signs) if k == 1]
    runs_l = [sum(1 for _ in g) for k, g in groupby(signs) if k == 0]
    avg = lambda r: (sum(r) / len(r)) if r else 0.0
    return dict(n=n, win=wins / n * 100,
                avg_w=avg(runs_w), max_w=max(runs_w) if runs_w else 0, n_w=len(runs_w),
                avg_l=avg(runs_l), max_l=max(runs_l) if runs_l else 0, n_l=len(runs_l))


def streak_report():
    print("\n=== consecutive WIN / LOSS streaks per operation (dial-independent) ===")
    print(f"{'portfolio':<16}{'ops':>6}{'win%':>7}{'avg cWin':>10}{'max cWin':>10}{'#Wstreaks':>11}"
          f"{'avg cLoss':>11}{'max cLoss':>11}")
    for name, legs in PORTS.items():
        s = streak_stats(legs)
        print(f"{name:<16}{s['n']:>6}{s['win']:>6.1f}%{s['avg_w']:>10.2f}{s['max_w']:>10}{s['n_w']:>11}"
              f"{s['avg_l']:>11.2f}{s['max_l']:>11}")


def plot(f=0.02):
    import os, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    os.makedirs("out", exist_ok=True)
    colors = {"GOLD alone": "#D4A017", "BTC alone": "#1f77b4", "BOTH (1R each)": "#2ca02c"}

    # union timeline + 6 segment dividers
    T0 = min(simulate(l, f)[5] for l in PORTS.values())
    T1 = max(simulate(l, f)[6] for l in PORTS.values())
    bounds = [T0 + (T1 - T0) * i / 6 for i in range(7)]
    bnp = [np.datetime64(b, "s").astype("datetime64[ms]").astype("O") for b in bounds]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    for name, legs in PORTS.items():
        trades, bal, ddmax, ddpct, years, t0, t1 = simulate(legs, f)
        t = np.array([t0] + [x[0] for x in trades], dtype="datetime64[s]").astype("datetime64[ms]").astype("O")
        b = np.array([CAP0] + [x[2] for x in trades])
        peak = np.maximum.accumulate(b); dd = (peak - b) / peak * 100
        lbl = f"{name}:  ${b[-1]:,.0f}  ({b[-1]/CAP0:.0f}x, DD {ddpct:.0f}%)"
        ax1.plot(t, b, color=colors[name], lw=1.8, label=lbl)
        ax2.fill_between(t, dd, 0, color=colors[name], alpha=0.30, lw=0)

    for i, x in enumerate(bnp):
        for ax in (ax1, ax2):
            ax.axvline(x, color="0.55", ls="--", lw=0.9, alpha=0.8)
    ymid = None
    for i in range(6):
        xmid = bnp[i] + (bnp[i + 1] - bnp[i]) / 2
        ax1.annotate(f"seg{i+1}", xy=(xmid, 0.965), xycoords=("data", "axes fraction"),
                     ha="center", va="top", fontsize=9, color="0.4")

    ax1.set_yscale("log"); ax1.set_ylabel("Balance  $  (log)")
    ax1.set_title(f"Cross-instrument portfolio — $1000 Main, geometric, {int(f*100)}%/op, stress-baked "
                  f"(gold @$0.40 / BTC @$18).  Vertical = 6 time-segments.")
    ax1.legend(loc="upper left", framealpha=0.92, fontsize=10)
    ax1.grid(True, which="both", alpha=0.22)
    ax2.set_ylabel("Drawdown %"); ax2.invert_yaxis(); ax2.grid(True, alpha=0.22)
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(); fig.tight_layout()
    out = "out/cross_kings_equity.png"; fig.savefig(out, dpi=120)
    print(f"\nsaved {out}")


if __name__ == "__main__":
    for dial in (0.01, 0.02):
        print(f"\n################################  RISK DIAL {int(dial*100)}%/op  ################################")
        for name, legs in PORTS.items():
            report(name, legs, dial)
    plot(0.02)
