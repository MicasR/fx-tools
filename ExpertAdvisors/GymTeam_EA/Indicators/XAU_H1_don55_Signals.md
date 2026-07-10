# GT_XAU_H1_don55_Signals — Donchian-55 break (T5 · #161611593 · XAUUSDc H1)

Chart indicator reproducing where the live **GymTeam king with the `XAU_H1_don55` preset**
would trade. Attach to the **XAUUSDc H1** chart in the T5 terminal (Navigator → Indicators →
GymTeam). Defaults are the live preset.

## The signal

A closed H1 bar is a **trigger** when its close breaks the **55-bar Donchian channel**:

- close above the **highest high of the prior 55 bars** (excluding the bar itself), or
  below the lowest low — either side fires.
- **Fresh edge only** — the same condition must have been false on the previous bar, so a
  runaway trend fires at the moment of breakout, not on every new extreme.

## Theory

The Donchian channel break is the oldest systematic trend entry there is — the rule behind
Richard Donchian's 4-week system and the Turtles' System Two (55-day). The premise:
**price making a multi-week extreme is itself the signal** — no indicator smoothing, no
volatility estimate, just the fact that every buyer/seller of the last 55 hours-of-trading
is now underwater on one side. 55 H1 bars ≈ 2.5 trading days of gold, so this leg hunts the
short-cycle trends that H4 legs are too slow for. Its known weakness — whipsaw at
long-consolidation edges — is exactly what the king's OCO wrapper mitigates: the *break bar*
only arms the pair, and price must then take out that bar's extreme within 4 bars to fill.
A one-bar false poke that immediately dies never becomes a trade.

## From signal to trade (what the EA then does)

- OCO pair: Buy Stop @ trigger high, Sell Stop @ trigger low; alive **4 H1 bars**.
- **1R = trigger bar range**, stop at the opposite extreme (equity-0 pinned). TP **+3R**,
  max-hold **240 H1 bars** (~10 days), no stacking.

## What is drawn

| Mark | Meaning |
|---|---|
| ◆ grey diamond | Donchian-break trigger bar |
| blue / red dotted levels | armed Buy-Stop / Sell-Stop while the pair is alive |
| ▲ / ▼ arrows | breakout fill — **the trade occurs here** |
| crimson / green lines | −1R stop and +3R target while the op runs |
| × white cross | exit (TP / SL / END) |

## General stats

On-chart panel (top-left): **triggers, fills (L/S), exit mix TP/SL/END, sum R, avg R/op**
over loaded history (TP = +3, SL = −1, END = mark-to-market, NBP-clamped). Breakeven TP rate
at 3R/−1R: **25 %** of resolved ops.

Reading guidance:
- Classic trend-following distribution: expect a **sub-50 % hit rate carried by the +3R
  winners** — long SL streaks between TP hits are the normal cost of the style, which is why
  this leg carries a small weight (0.06) inside a decorrelated team.
- Trigger clusters mark regime shifts; in strong gold trends the leg re-fires as each
  55-bar high gives way, in ranges it goes silent.

**Caveats:** bar-level simulation — bar-extreme fills, open-proximity choice on double-touch
bars, SL-first on bars spanning stop and target; no spread/slippage/margin/stops-level
modeling. Validation oracle: Strategy Tester vs `backtest/out/shadow/<leg>.csv`.
