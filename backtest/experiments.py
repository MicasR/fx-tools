"""
Direction-logic experiments for VolumeVPattern.

The baseline indicator decides trade direction from C1's candle colour — the
weakest part of the signal. This script tests alternative direction/entry rules
and filters, judging each on the OUT-OF-SAMPLE SPLIT (first half / second half)
so a "win" has to survive both regimes, not just flatter the full-period average.

Run:  python experiments.py
"""
import glob
import numpy as np
import pandas as pd

import signals as sg

METHOD = "threshold"
RISE = 0.02
RR = 3.0
ATR_MULT = 1.5
MAX_HOLD = 64
MFE_WIN = 16


def _direction(df, i, mode, ema, disp_lb):
    """Return +1 / -1 / 0 (skip) for signal bar i under a direction rule.
    'break' is handled in the evaluator (it depends on future bars)."""
    o, c = df["open"].iat[i], df["close"].iat[i]
    if mode == "candle":
        return 1 if c >= o else -1
    if mode == "displacement":
        if i - disp_lb < 0:
            return 0
        prev = df["close"].iat[i - disp_lb]
        if c > prev:
            return 1
        if c < prev:
            return -1
        return 0
    raise ValueError(mode)


def evaluate_dir(df, sig, *, mode="candle", rr=RR, atr_mult=ATR_MULT,
                 trend_ema=0, decisive=False, break_wait=8, disp_lb=2,
                 spread=0.0, slippage=0.0, invert=False, break_entry="level"):
    """Evaluate signals with a configurable direction/entry rule + filters.
    Returns dict with n, fwd win%@8, and avg R for ATR and structural brackets.

    Costs: `spread` and `slippage` are in PRICE units. Round-trip cost
    = spread + 2*slippage is charged once per trade and deducted from the R
    multiple as cost / risk_distance (so a wider stop dilutes the cost in R)."""
    cost = spread + 2.0 * slippage
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(df)
    ema = df["close"].ewm(span=trend_ema, adjust=False).mean().to_numpy() if trend_ema else None

    idx = np.flatnonzero(sig.to_numpy())
    idx = idx[(idx + 1 < n) & ~np.isnan(atr[idx])]

    fwd_wins, atr_R, str_R = [], [], []
    atr_risk_px, str_risk_px = [], []
    skipped = 0

    for i in idx:
        # ---- decisive-candle filter (direction-agnostic) ----
        if decisive:
            rng = h[i] - l[i]
            if rng <= 0:
                skipped += 1; continue
            body = abs(c[i] - o[i])
            top_third = (c[i] - l[i]) / rng
            if body < 0.5 * rng or (0.333 < top_third < 0.667):
                skipped += 1; continue

        # ---- direction + entry ----
        if mode == "break":
            hi, lo = h[i], l[i]
            d, entry, entry_j = 0, None, None
            end_w = min(i + break_wait, n - 1)
            for j in range(i + 1, end_w + 1):
                up = h[j] >= hi
                dn = l[j] <= lo
                if up and dn:           # straddle bar → ambiguous, skip
                    break
                if up:
                    d, entry, entry_j = 1, (c[j] if break_entry == "close" else hi), j; break
                if dn:
                    d, entry, entry_j = -1, (c[j] if break_entry == "close" else lo), j; break
            if d == 0:
                skipped += 1; continue
        else:
            d = _direction(df, i, mode, ema, disp_lb)
            if d == 0:
                skipped += 1; continue
            entry, entry_j = o[i + 1], i + 1

        if invert:                      # fade the signal (test mean-reversion)
            d = -d

        # ---- trend filter ----
        if trend_ema:
            bias = 1 if c[i] > ema[i] else -1
            if d != bias:
                skipped += 1; continue

        # ---- forward win @ 8 (from entry bar) ----
        jf = entry_j + 8
        if jf < n:
            fwd_wins.append(1 if d * (c[jf] - entry) > 0 else 0)

        a = atr[i]
        end_b = min(entry_j + MAX_HOLD, n - 1)

        # ---- ATR bracket ----
        sl = entry - d * atr_mult * a
        tp = entry + d * rr * atr_mult * a
        out = _walk(h, l, c, entry_j, end_b, d, sl, tp, rr, atr_mult * a, cost)
        atr_R.append(out)
        atr_risk_px.append(atr_mult * a)

        # ---- structural bracket (stop at C1 extreme) ----
        sl_s = h[i] if d == -1 else l[i]
        risk = d * (entry - sl_s)
        if risk > 0:
            tp_s = entry + d * rr * risk
            str_R.append(_walk(h, l, c, entry_j, end_b, d, sl_s, tp_s, rr, risk, cost))
            str_risk_px.append(risk)

    atr_R = np.array(atr_R) if atr_R else np.array([0.0])
    str_R = np.array(str_R) if str_R else np.array([0.0])
    return {
        "n": int(len(atr_R)) if atr_R.any() or skipped < len(idx) else 0,
        "n_trades": len(idx) - skipped,
        "skipped": skipped,
        "win8": 100 * np.mean(fwd_wins) if fwd_wins else 0.0,
        "atr_avgR": float(np.mean(atr_R)),
        "atr_totR": float(np.sum(atr_R)),
        "str_avgR": float(np.mean(str_R)),
        "str_totR": float(np.sum(str_R)),
        "atr_R": atr_R,
        "str_R": str_R,
        "atr_risk_px": float(np.mean(atr_risk_px)) if atr_risk_px else 0.0,
        "str_risk_px": float(np.mean(str_risk_px)) if str_risk_px else 0.0,
    }


def stats(R):
    """Richer per-strategy stats from an array of R multiples."""
    R = np.asarray(R, float)
    if R.size == 0:
        return dict(n=0, win=0.0, avgR=0.0, totR=0.0, pf=0.0, maxdd=0.0, maxloss=0)
    wins, losses = R[R > 0], R[R <= 0]
    gp, gl = wins.sum(), -losses.sum()
    eq = np.cumsum(R)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size else 0.0
    # longest losing streak
    streak = mx = 0
    for r in R:
        streak = streak + 1 if r <= 0 else 0
        mx = max(mx, streak)
    return dict(n=int(R.size), win=100 * np.mean(R > 0), avgR=float(R.mean()),
                totR=float(R.sum()), pf=float(gp / gl) if gl > 0 else float("inf"),
                maxdd=dd, maxloss=int(mx))


def _walk(h, l, c, start_j, end_b, d, sl, tp, rr, risk_px, cost=0.0):
    """First-touch walk forward → R multiple, net of round-trip cost.
    Pessimistic on straddle bars. `cost` (price) is deducted as cost/risk_px."""
    pen = cost / risk_px
    for j in range(start_j, end_b + 1):
        hit_sl = (l[j] <= sl) if d == 1 else (h[j] >= sl)
        hit_tp = (h[j] >= tp) if d == 1 else (l[j] <= tp)
        if hit_sl and hit_tp:
            return -1.0 - pen
        if hit_sl:
            return -1.0 - pen
        if hit_tp:
            return rr - pen
    return d * (c[end_b] - (sl + d * risk_px)) / risk_px - pen  # mark-to-market in R


def run(df, label, variants):
    df = sg.add_features(df.reset_index(drop=True), period=20, mult=2.0)
    sig = sg.volumevpattern_signal(df, method=METHOD, rise_pct=RISE)
    vs = sg.volumespike_signal(df, method=METHOD)
    print(f"\n=== {label}  ({df['time'].iloc[0]:%Y-%m-%d}..{df['time'].iloc[-1]:%Y-%m-%d}, {len(df):,} bars) ===")
    print(f"{'variant':<28}{'trades':>7}{'win%@8':>8}{'ATRavgR':>9}{'ATRtotR':>9}{'strAvgR':>9}{'strTotR':>9}")
    print("-" * 78)
    r = evaluate_dir(df, vs, mode="candle")
    print(f"{'VolumeSpike (baseline ref)':<28}{r['n_trades']:>7}{r['win8']:>8.1f}{r['atr_avgR']:>9.3f}{r['atr_totR']:>9.1f}{r['str_avgR']:>9.3f}{r['str_totR']:>9.1f}")
    for name, kw in variants:
        r = evaluate_dir(df, sig, **kw)
        print(f"{name:<28}{r['n_trades']:>7}{r['win8']:>8.1f}{r['atr_avgR']:>9.3f}{r['atr_totR']:>9.1f}{r['str_avgR']:>9.3f}{r['str_totR']:>9.1f}")


if __name__ == "__main__":
    full = pd.read_csv(glob.glob("data/*_H1.csv")[0], parse_dates=["time"])
    mid = len(full) // 2

    variants = [
        ("VP candle (BASELINE)",        dict(mode="candle")),
        ("VP break wait=4",             dict(mode="break", break_wait=4)),
        ("VP break wait=6",             dict(mode="break", break_wait=6)),
        ("VP break wait=8",             dict(mode="break", break_wait=8)),
        ("VP break wait=12",            dict(mode="break", break_wait=12)),
        ("VP break wait=16",            dict(mode="break", break_wait=16)),
        ("VP break+decisive w=8",       dict(mode="break", break_wait=8, decisive=True)),
    ]

    for label, d in [("FULL", full), ("FIRST HALF", full.iloc[:mid]), ("SECOND HALF", full.iloc[mid:])]:
        run(d, label, variants)
