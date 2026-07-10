# GT_XAU_H4_engulf_Signals — engulfing bar (T2 · #161611606 · XAUUSDc H4)

Chart indicator reproducing where the live **GymTeam king with the `XAU_H4_engulf` preset**
would trade. Attach to the **XAUUSDc H4** chart in the T2 terminal (Navigator → Indicators →
GymTeam). Defaults are the live preset.

## The signal

A closed H4 bar is a **trigger** when its real body **engulfs the previous bar's opposite
body** (exact `signals2` formula, both directions):

- **Bullish**: this bar closes up, the prior bar closed down, this close is above the prior
  open AND this open is below the prior close — the up-body completely swallows the
  down-body.
- **Bearish**: the mirror image.

No trend filter, no size filter — the pattern itself is the whole trigger.

## Theory

The engulfing bar is a classic **two-bar reversal/absorption pattern**: one side pushes
price to a new short-term extreme, then the other side absorbs the entire move and closes
beyond where the first bar even started. On a 4-hour gold bar that means a session-scale
shift in control (Asia → London → NY handovers frequently print exactly this shape at
turning points). Note the subtlety of how the king uses it: the engulfing bar does **not**
pick a direction — it only marks the *battle bar*. The OCO breakout pair lets the market
choose the side; an engulf followed by continuation fills the with-body stop, an engulf that
gets faded fills the other. What the pattern contributes is a bar whose **range is a
meaningful 1R unit** — a fought-over range whose break tends to travel.

## From signal to trade (what the EA then does)

- OCO pair: Buy Stop @ trigger high, Sell Stop @ trigger low; alive **4 H4 bars**, first
  fill cancels the sibling.
- **1R = the trigger bar's range**; stop at the opposite extreme (whole-account −1R by the
  equity-0 pinning). TP **+3R**, max-hold **240 H4 bars**, no stacking.

## What is drawn

| Mark | Meaning |
|---|---|
| ◆ grey diamond | engulfing trigger bar |
| blue / red dotted levels | armed Buy-Stop / Sell-Stop while the pair is alive |
| ▲ / ▼ arrows | breakout fill — **the trade occurs here** |
| crimson / green lines | −1R stop and +3R target while the op runs |
| × white cross | exit (TP / SL / END) |

## General stats

On-chart panel (top-left): **triggers, fills (L/S), exit mix TP/SL/END, sum R, avg R/op**
over loaded history (TP = +3, SL = −1, END = mark-to-market, NBP-clamped). Breakeven TP rate
at 3R/−1R is **25 %** of resolved (TP/SL) ops.

Reading guidance for this leg specifically:
- Engulfing bars are more frequent than the align/keltner triggers, but the 4-bar breakout
  window rejects the ones that stall — expect a visibly lower fill/trigger ratio than T1.
- Both directions fire; a healthy sample should show a roughly balanced L/S fill split on
  gold H4.

**Caveats:** bar-level simulation — bar-extreme fills, open-proximity choice when one bar
touches both OCO levels, SL-first on bars spanning stop and target; no spread/slippage/
margin/stops-level modeling. Slightly pessimistic vs tester/live by construction. The
validation oracle is the Strategy Tester vs `backtest/out/shadow/<leg>.csv`.
