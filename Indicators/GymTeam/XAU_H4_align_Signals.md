# GT_XAU_H4_align_Signals — MA-alignment impulse (T1 · #161611609 · XAUUSDc H4)

Chart indicator that reproduces, bar for bar, where the live **GymTeam king with the
`XAU_H4_align` preset** would trade. Attach to the **XAUUSDc H4** chart in the T1 terminal
(Navigator → Indicators → GymTeam). Defaults are the live preset — change nothing to see
what the EA sees.

## The signal

A closed H4 bar is a **trigger** when trend and impulse line up (`AlignCond`, ported from
`signals2` via GymTeam_EA):

1. **Trend filter** — close is beyond the SMA-50, and the SMA-50 itself is *moving that
   way* (rising for longs, falling for shorts), and the SMA-10 agrees (also rising/falling).
2. **Impulse filter** — the bar's range exceeds **1.2 × ATR(14)** (ATR = SMA of true range,
   pandas-matched). An aligned but sleepy bar does not fire.
3. **Fresh edge only** — the condition must be newly true vs the previous bar, so a
   trending market fires once per thrust, not every bar.

## Theory

This is a **momentum-continuation** entry: when a mature trend (slow MA direction) produces
an outsized expansion bar (range ≫ typical volatility), the odds favour follow-through —
institutional flow that moves gold 1.2×ATR in 4 hours rarely completes in one bar. The MA
alignment keeps it out of chop; the ATR gate keeps it out of drift. It is the "fat-bar
family" survivor of the thread-36/37 tester-true selection (the fxgym generator search),
picked for time-decorrelation against the breakout/compression legs, not in isolation.

## From signal to trade (what the EA then does)

- Arms an **OCO breakout pair**: Buy Stop at the trigger bar's high, Sell Stop at its low.
- Pair lives **4 H4 bars** (`InpBreakBars`), then stale-cancels. First fill wins, sibling dies.
- **1R = the trigger bar's range**; the stop sits at the opposite extreme. The base lot pins
  the account's equity-0 line onto that stop (whole-account sizing: full stop = −1R = −account).
- Exit: fixed **TP at +3R**, stop at **−1R**, or **END** (market close) after **240 H4 bars** (~40
  trading days). No stacking on this leg (`InpStack=false`).

## What is drawn

| Mark | Meaning |
|---|---|
| ◆ grey diamond | trigger bar (signal fired at its close) |
| blue / red dotted levels | armed Buy-Stop / Sell-Stop lines while the OCO pair is alive |
| ▲ green / ▼ red arrow | where the breakout stop fills — **the trade occurs here** |
| crimson line | the op's −1R stop while the trade runs |
| green line | the +3R take-profit |
| × white cross | exit (TP / SL / max-hold END) |

## General stats

The indicator computes its own stats over the loaded chart history and prints them in the
top-left corner: **triggers, fills (long/short), exit mix (TP/SL/END), sum R and avg R/op**
(R accounting: TP = +3, SL = −1, END = mark-to-market, losses NBP-clamped at −1 like the
EA's OnTester). Load more history (Home key) to grow the sample.

Structural expectations to read them against:
- With a +3R target and a −1R stop, the leg is profitable above a **25 % TP rate** (ignoring
  END exits, which land anywhere in between).
- Fill rate is well below trigger rate by design — the 4-bar breakout window filters
  triggers that never get momentum confirmation.
- This is a low-frequency H4 leg: a few triggers per month is normal. The live weight (0.33,
  the book's largest) reflects its tester-true robustness score, not its frequency.

**Caveats (bar-level simulation):** fills and exits are evaluated on bar extremes, not tick
sequence — when one bar touches both OCO levels the side nearer the open fills, and when a
bar spans both SL and TP the SL is counted (conservative). Spread, slippage, margin caps and
the live stops-level skip are not modeled. Expect the panel to be slightly pessimistic vs
the tester and the live book. The oracle for validation remains the Strategy Tester against
`backtest/out/shadow/<leg>.csv` (see the EA header).
