# GT_XAU_H4_keltner_Signals — Keltner channel break (T4 · #161611597 · XAUUSDc H4)

Chart indicator reproducing where the live **GymTeam king with the `XAU_H4_keltner` preset**
would trade. Attach to the **XAUUSDc H4** chart in the T4 terminal (Navigator → Indicators →
GymTeam). Defaults are the live preset. (T6 runs the same rule on H1 — see
`XAU_H1_keltner_Signals.md`.)

## The signal

A closed H4 bar is a **trigger** when the close **crosses out of the Keltner channel**:

- Channel: **EMA(20) ± 2.0 × ATR(14)** (EMA = pandas `ewm(span=20, adjust=False)`; ATR = SMA
  of true range — both ported exactly from the EA so the lines match the tester).
- **Fresh edge only** — close outside the band now, was *inside* on the previous bar.
  Either side fires; a market camping outside the band does not re-fire.

## Theory

The Keltner channel frames price in units of its own average volatility around its average
level. A close beyond **2 ATR from the 20-EMA** is a >2-sigma-equivalent excursion — the
point where "normal oscillation around value" statistically ends and **regime change**
begins. Unlike Bollinger bands (standard deviation of price), the ATR envelope doesn't
inflate during the very expansion it is trying to measure, which makes the band-exit a
cleaner breakout statement. The edge-only condition converts the channel from a
mean-reversion tool into a **volatility-breakout detector**: it fires exactly once, at the
moment the excursion becomes abnormal — and then hands the direction decision to the OCO
pair, so a false excursion that snaps back can still fill the *reverting* side.

## From signal to trade (what the EA then does)

- OCO pair: Buy Stop @ trigger high, Sell Stop @ trigger low; alive **4 H4 bars**.
- **1R = trigger bar range**, stop at the opposite extreme (equity-0 pinned). TP **+3R**,
  max-hold **240 H4 bars**, no stacking.

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
- Band exits on H4 gold are uncommon — this is a patient leg (weight 0.10). A long quiet
  stretch on the panel is normal behaviour, not a broken indicator.
- Trigger bars are usually *large* (they closed 2 ATR out), so 1R here tends to be a wide
  unit — one reason the +3R bracket still gets hit at a useful rate.

**Caveats:** bar-level simulation — bar-extreme fills, open-proximity choice on double-touch
bars, SL-first on bars spanning stop and target; no spread/slippage/margin/stops-level
modeling. The EMA warms up from the start of loaded history (the EA warms 300 bars) — the
first ~60 bars of a fresh chart can differ; load full history. Validation oracle: Strategy
Tester vs `backtest/out/shadow/<leg>.csv`.
