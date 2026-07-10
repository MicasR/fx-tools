# GT_BTC_wh_shield_Signals — warm-volume hours (T3 · #161611603 · BTCUSDc H1)

Chart indicator reproducing where the live **GymTeam king with the `BTC_wh_shield` preset**
would trade. Attach to the **BTCUSDc H1** chart in the T3 terminal (Navigator → Indicators →
GymTeam). Defaults are the live preset.

## The signal

A closed H1 bar is a **trigger** when three volume-regime conditions coincide (the frozen
`warm_fires` rule from fxgym `run_revalidate`):

1. **Warming volume** — tick volume rose two bars in a row (`vol[t] > vol[t−1] > vol[t−2]`).
2. **Warm, not blow-off** — the bar's tick volume ranks in the **(80, 98] percentile** of the
   last 100 bars (rank vs the 99 predecessors, pandas-matched). Above the 98th percentile is
   excluded on purpose: climax volume is where breakouts *fail*.
3. **Liquid hours only** — the bar's server-time hour is in **{12…16}**, the London/NY
   overlap, where BTC's move-through liquidity is deepest.

## Theory

This is a **volume-regime** entry rather than a price-pattern one: rising-but-not-climactic
participation during the deepest liquidity window is the signature of a move that is being
*accumulated into*, not exhausted. The percentile ceiling (≤98) encodes the classic
volume-analysis asymmetry — expansion attracts follow-through, climax marks reversal — and
the hour gate avoids the thin-tape breakouts that dominate BTC outside the overlap. The
"shield" in the name is its team role: its fires are time-decorrelated from the gold legs
(different asset, different driver), so it earns on weeks the gold book bleeds — that is
what the prom-date weekly-vector selection optimized for.

## From signal to trade (what the EA then does)

- OCO pair: Buy Stop @ trigger high, Sell Stop @ trigger low; alive **4 H1 bars**.
- **1R = trigger bar range**, stop at the opposite extreme (equity-0 pinned). TP **+2R**
  (this leg runs the tighter bracket), max-hold **240 H1 bars** (~10 days), no stacking.

## What is drawn

| Mark | Meaning |
|---|---|
| ◆ grey diamond | warm-hours trigger bar |
| blue / red dotted levels | armed Buy-Stop / Sell-Stop while the pair is alive |
| ▲ / ▼ arrows | breakout fill — **the trade occurs here** |
| crimson / green lines | −1R stop and +2R target while the op runs |
| × white cross | exit (TP / SL / END) |

## General stats

On-chart panel (top-left): **triggers, fills (L/S), exit mix TP/SL/END, sum R, avg R/op**
over loaded history (TP = +2, SL = −1, END = mark-to-market, NBP-clamped). Breakeven TP rate
at 2R/−1R is **33 %** of resolved ops — this leg trades a higher hit-rate/lower-payoff
bracket than the gold legs.

Reading guidance:
- Triggers cluster inside the 12:00–16:00 server window by construction — an even spread
  across the day means the chart's server timezone does not match the preset's assumption.
- H1 + a 5-hour window makes this the highest-frequency leg of the book; expect several
  triggers per week.

**Caveats:** bar-level simulation — bar-extreme fills, open-proximity choice when a bar
touches both OCO levels, SL-first on bars spanning stop and target; no spread/slippage/
margin/stops-level modeling. Tick-volume history must be real broker data — a freshly
downloaded chart with thin history skews the percentile rank; load full history first.
Validation oracle: Strategy Tester vs `backtest/out/shadow/<leg>.csv`.
