# GT_XAU_H1_keltner_Signals — Keltner channel break (T6 · #161557528 · XAUUSDc H1)

Chart indicator reproducing where the live **GymTeam king with the `XAU_H1_keltner` preset**
would trade. Attach to the **XAUUSDc H1** chart in the T6 terminal (Navigator → Indicators →
GymTeam). Defaults are the live preset.

## The signal

Identical rule to the T4 leg, one timeframe down: a closed **H1** bar triggers when the
close **crosses out of EMA(20) ± 2.0 × ATR(14)** — outside now, inside on the previous bar,
either side. EMA is pandas `ewm(adjust=False)`, ATR is the SMA of true range, both ported
exactly from the EA.

## Theory

Same volatility-regime logic as the H4 version (see `XAU_H4_keltner_Signals.md` for the full
argument): a 2-ATR excursion from the 20-EMA marks the statistical end of normal oscillation
and the start of a directional regime, and the edge-only condition makes it a one-shot
breakout detector rather than a mean-reversion band. **Why run it twice?** Timeframe
diversification of the *same* edge: H1 excursions resolve in hours and catch intraday
regime shifts (news bars, session opens) that have already come and gone before an H4 bar
even closes. In the prom-date weekly vectors the two keltner legs earn in different weeks —
which is why both made the team, at small weights (T6 = 0.04, the book's smallest), instead
of one at a large weight.

## From signal to trade (what the EA then does)

- OCO pair: Buy Stop @ trigger high, Sell Stop @ trigger low; alive **4 H1 bars**.
- **1R = trigger bar range**, stop at the opposite extreme (equity-0 pinned). TP **+3R**,
  max-hold **240 H1 bars** (~10 days), no stacking.

## What is drawn

| Mark | Meaning |
|---|---|
| ◆ grey diamond | band-exit trigger bar |
| blue / red dotted levels | armed Buy-Stop / Sell-Stop while the pair is alive |
| ▲ / ▼ arrows | breakout fill — **the trade occurs here** |
| crimson / green lines | −1R stop and +3R target while the op runs |
| × white cross | exit (TP / SL / END) |

## General stats

On-chart panel (top-left): **triggers, fills (L/S), exit mix TP/SL/END, sum R, avg R/op**
over loaded history (TP = +3, SL = −1, END = mark-to-market, NBP-clamped). Breakeven TP rate
at 3R/−1R: **25 %** of resolved ops.

Reading guidance:
- H1 fires several times more often than the H4 twin, with smaller 1R units — more trades,
  each worth less, same underlying edge. Compare the two panels side by side to see the
  timeframe trade-off directly.
- Around scheduled news, H1 gold prints band exits that snap straight back; the 4-bar OCO
  window is what filters most of those out of the fill count.

**Caveats:** bar-level simulation — bar-extreme fills, open-proximity choice on double-touch
bars, SL-first on bars spanning stop and target; no spread/slippage/margin/stops-level
modeling. EMA warms from loaded history start — load full history before judging early
signals. Validation oracle: Strategy Tester vs `backtest/out/shadow/<leg>.csv`.
