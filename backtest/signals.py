"""
Faithful Python ports of the VolumeSpike and VolumeVPattern signal logic,
plus a simple trade evaluator.

Both indicators operate on tick_volume with a rolling MA + population StdDev
(matching the MQL5 default: SMA, period 20, population std / ddof=0).

VolumeSpike  : signal on bar i when volume crosses a level (level cross).
VolumeVPattern: signal on bar i (= C1) when the selected method's line s[]
                traces a V:  s[i-2] > s[i-1]  AND  s[i] > s[i-1]
                AND (s[i]-s[i-1]) / |s[i-1]| >= rise_pct.

Both enter at the NEXT bar's open; direction = signal bar's candle colour
(bullish if close >= open).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────────
# Features
# ──────────────────────────────────────────────────────────────────────────
def add_features(df: pd.DataFrame, period: int = 20, mult: float = 2.0,
                 pct_period: int = 100, atr_period: int = 14) -> pd.DataFrame:
    df = df.copy()
    v = df["tick_volume"].astype(float)

    ma = v.rolling(period, min_periods=period).mean()
    std = v.rolling(period, min_periods=period).std(ddof=0)   # population std
    df["ma"] = ma
    df["std"] = std
    df["z"] = np.where(std > 1e-10, (v - ma) / std, 0.0)
    df["threshold"] = ma + mult * std

    # percentile rank of current vol within the trailing window (excl. current)
    def _rank(x):
        cur = x[-1]
        prev = x[:-1]
        return 100.0 * (prev < cur).sum() / len(prev) if len(prev) else 0.0
    df["pct_rank"] = v.rolling(pct_period, min_periods=pct_period).apply(_rank, raw=True)

    # ATR (Wilder-ish via simple rolling mean of true range) for the bracket test
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_period, min_periods=atr_period).mean()

    df["bull"] = (df["close"] >= df["open"]).astype(int)
    return df


def _source_series(df: pd.DataFrame, method: str) -> pd.Series:
    method = method.lower()
    if method in ("stddev", "zscore"):
        return df["z"]
    if method == "threshold":
        return df["threshold"]
    if method == "percentile":
        return df["pct_rank"]
    raise ValueError(f"unsupported method for V source: {method}")


# ──────────────────────────────────────────────────────────────────────────
# Signal generators  → boolean Series aligned to df.index
# ──────────────────────────────────────────────────────────────────────────
def volumespike_signal(df: pd.DataFrame, method: str = "stddev",
                       z_threshold: float = 2.5, pct_cutoff: float = 95.0) -> pd.Series:
    method = method.lower()
    v = df["tick_volume"].astype(float)
    if method in ("stddev", "threshold"):
        sig = v > df["threshold"]
    elif method == "zscore":
        sig = df["z"] > z_threshold
    elif method == "percentile":
        sig = df["pct_rank"] > pct_cutoff
    else:
        raise ValueError(method)
    return sig.fillna(False)


def volumevpattern_signal(df: pd.DataFrame, method: str = "stddev",
                          rise_pct: float = 0.02) -> pd.Series:
    s = _source_series(df, method)
    s2 = s.shift(1)   # trough  (C2)
    s3 = s.shift(2)   # pre-drop (C3)
    denom = s2.abs().clip(lower=1e-10)
    rise = (s - s2) / denom
    sig = (s3 > s2) & (s > s2) & (rise >= rise_pct)
    return sig.fillna(False)


# ──────────────────────────────────────────────────────────────────────────
# Evaluation
# ──────────────────────────────────────────────────────────────────────────
def evaluate(df: pd.DataFrame, sig: pd.Series, *, horizons=(4, 8, 16),
             mfe_window: int = 16, atr_mult: float = 1.5, rr: float = 1.5,
             max_hold: int = 64) -> dict:
    """Simulate each signal: enter next bar open, dir = signal bar candle colour."""
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    bull = df["bull"].to_numpy(int)
    n = len(df)
    idx = np.flatnonzero(sig.to_numpy())
    idx = idx[(idx + 1 < n) & ~np.isnan(atr[idx])]   # need a next-bar open + valid ATR

    fwd = {hz: [] for hz in horizons}
    mfe_l, mae_l, rmults = [], [], []

    for i in idx:
        d = 1 if bull[i] else -1
        entry = o[i + 1]
        # forward returns (price %), direction-adjusted
        for hz in horizons:
            j = i + hz
            if j < n:
                fwd[hz].append(d * (c[j] - entry) / entry)
        # MFE / MAE over the window
        end = min(i + mfe_window, n - 1)
        win_h = h[i + 1:end + 1]
        win_l = l[i + 1:end + 1]
        if len(win_h):
            if d == 1:
                mfe_l.append((win_h.max() - entry) / entry)
                mae_l.append((win_l.min() - entry) / entry)
            else:
                mfe_l.append((entry - win_l.min()) / entry)
                mae_l.append((entry - win_h.max()) / entry)
        # ATR bracket → outcome in R multiples
        a = atr[i]
        sl = entry - d * atr_mult * a
        tp = entry + d * rr * atr_mult * a
        outcome = None
        end_b = min(i + max_hold, n - 1)
        for j in range(i + 1, end_b + 1):
            hit_sl = (l[j] <= sl) if d == 1 else (h[j] >= sl)
            hit_tp = (h[j] >= tp) if d == 1 else (l[j] <= tp)
            if hit_sl and hit_tp:
                outcome = -1.0          # ambiguous bar → assume stop first
                break
            if hit_sl:
                outcome = -1.0
                break
            if hit_tp:
                outcome = rr
                break
        if outcome is None:             # timed out → mark to market in R
            outcome = d * (c[end_b] - entry) / (atr_mult * a)
        rmults.append(outcome)

    rmults = np.array(rmults) if rmults else np.array([0.0])
    wins = rmults[rmults > 0]
    res = {
        "n_signals": int(len(idx)),
        "fwd_mean_bps": {hz: float(np.mean(fwd[hz]) * 1e4) if fwd[hz] else 0.0 for hz in horizons},
        "fwd_winrate": {hz: float(np.mean(np.array(fwd[hz]) > 0)) if fwd[hz] else 0.0 for hz in horizons},
        "avg_mfe_pct": float(np.mean(mfe_l) * 100) if mfe_l else 0.0,
        "avg_mae_pct": float(np.mean(mae_l) * 100) if mae_l else 0.0,
        "mfe_mae_ratio": float(np.mean(mfe_l) / abs(np.mean(mae_l))) if mae_l and np.mean(mae_l) != 0 else 0.0,
        "bracket_winrate": float(np.mean(rmults > 0)),
        "bracket_avg_R": float(np.mean(rmults)),
        "bracket_total_R": float(np.sum(rmults)),
        "bracket_rr": rr,
        "idx": idx,
        "rmults": rmults,
    }
    return res
