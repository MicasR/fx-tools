"""Backtest-grade performance metrics over the immutable op R-stream — the war-room
'strategy tester report'. Pure functions (no I/O), unit-testable like capital.py.

Unit is R (risk multiples), the system's native P&L unit: each closed op records realized_r.
This mirrors the MT5 strategy-tester metric set (profit factor, expected payoff, recovery
factor, Sharpe, max drawdown, consecutive wins/losses, ...) in R rather than $ — exact per-op
$ is not stored (only R + the live equity curve in /status)."""
from math import sqrt


def _stats(rs):
    """Compute the full metric set for an ORDERED list of per-op realized_r."""
    n = len(rs)
    if n == 0:
        return dict(trades=0, wins=0, losses=0, scratches=0, win_rate=0.0, net_r=0.0,
                    gross_win_r=0.0, gross_loss_r=0.0, profit_factor=None, expectancy_r=0.0,
                    avg_win_r=0.0, avg_loss_r=0.0, payoff_ratio=None, largest_win_r=0.0,
                    largest_loss_r=0.0, max_consec_wins=0, max_consec_losses=0,
                    max_dd_r=0.0, recovery_factor=None, sharpe=0.0)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r < 0]
    scratches = n - len(wins) - len(losses)
    gross_win = sum(wins)
    gross_loss = sum(losses)                 # <= 0
    net = sum(rs)
    avg_win = gross_win / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    # consecutive streaks
    mcw = mcl = cw = cl = 0
    for r in rs:
        if r > 0:
            cw += 1; cl = 0; mcw = max(mcw, cw)
        elif r < 0:
            cl += 1; cw = 0; mcl = max(mcl, cl)
        else:
            cw = cl = 0
    # cumulative equity curve -> max peak-to-valley drawdown (in R)
    cum = peak = 0.0
    max_dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    # Sharpe: mean / sample-stdev of per-op R (per-trade, not annualized)
    mean = net / n
    if n > 1:
        var = sum((r - mean) ** 2 for r in rs) / (n - 1)
        sd = sqrt(var)
        sharpe = mean / sd if sd > 0 else 0.0
    else:
        sharpe = 0.0
    return dict(
        trades=n, wins=len(wins), losses=len(losses), scratches=scratches,
        win_rate=len(wins) / n,
        net_r=round(net, 4), gross_win_r=round(gross_win, 4), gross_loss_r=round(gross_loss, 4),
        profit_factor=(round(gross_win / -gross_loss, 4) if gross_loss < 0 else None),
        expectancy_r=round(mean, 4),
        avg_win_r=round(avg_win, 4), avg_loss_r=round(avg_loss, 4),
        payoff_ratio=(round(avg_win / -avg_loss, 4) if avg_loss < 0 else None),
        largest_win_r=round(max(rs), 4), largest_loss_r=round(min(rs), 4),
        max_consec_wins=mcw, max_consec_losses=mcl,
        max_dd_r=round(max_dd, 4),
        recovery_factor=(round(net / max_dd, 4) if max_dd > 0 else None),
        sharpe=round(sharpe, 4),
    )


def compute(ops):
    """ops: list of dicts (db.ops_all order = by close_time) with 'account' + 'realized_r'.
    Returns {combined, per_leg:{account: stats}} — each value is a full _stats() dict."""
    combined = _stats([o["realized_r"] for o in ops])
    per_leg = {}
    order = []
    buckets = {}
    for o in ops:
        a = o["account"]
        if a not in buckets:
            buckets[a] = []
            order.append(a)
        buckets[a].append(o["realized_r"])
    for a in order:
        per_leg[a] = _stats(buckets[a])
    return dict(combined=combined, per_leg=per_leg)
