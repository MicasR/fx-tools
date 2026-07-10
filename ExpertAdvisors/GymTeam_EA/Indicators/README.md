# GymTeam per-leg signal indicators

One chart indicator per live leg, reproducing **where the king EA would trade** — the leg's
signal module with its live preset baked in as defaults, run through a bar-level simulation
of the EA's entry engine (trigger → 4-bar OCO breakout → single op with −1R structural stop,
+TpR target, 240-bar max-hold, one op at a time).

| Leg | Indicator | Module | Chart | Doc |
|---|---|---|---|---|
| T1 #161611609 | `GT_XAU_H4_align_Signals` | MA-alignment impulse | XAUUSDc H4 | [doc](XAU_H4_align_Signals.md) |
| T2 #161611606 | `GT_XAU_H4_engulf_Signals` | Engulfing bar | XAUUSDc H4 | [doc](XAU_H4_engulf_Signals.md) |
| T3 #161611603 | `GT_BTC_wh_shield_Signals` | Warm-volume hours | BTCUSDc H1 | [doc](BTC_wh_shield_Signals.md) |
| T4 #161611597 | `GT_XAU_H4_keltner_Signals` | Keltner break | XAUUSDc H4 | [doc](XAU_H4_keltner_Signals.md) |
| T5 #161611593 | `GT_XAU_H1_don55_Signals` | Donchian-55 break | XAUUSDc H1 | [doc](XAU_H1_don55_Signals.md) |
| T6 #161557528 | `GT_XAU_H1_keltner_Signals` | Keltner break | XAUUSDc H1 | [doc](XAU_H1_keltner_Signals.md) |

**Deployed to:** each leg terminal's data folder, `MQL5\Indicators\GymTeam\` (right-click →
Refresh in the Navigator if it doesn't show, then drag onto the chart named above).

**Architecture:** `GT_Signals_Core.mqh` holds the whole engine (signal detectors ported
verbatim from `GymTeam_EA.mq5`, entry state machine, drawing, stats panel); each
`GT_<leg>_Signals.mq5` is a thin wrapper declaring the preset defaults. Recompile any leg
file with MetaEditor after editing the core.

**Stats panel** (top-left of the chart): triggers, fills (L/S), exit mix (TP/SL/END), sum R
and avg R/op over the loaded history — R accounted like the EA's OnTester (TP = +TpR,
SL = −1, END = mark-to-market, NBP-clamped). Bar-level approximations and their bias are
listed in each doc's Caveats section; the tester vs `backtest/out/shadow/<leg>.csv` remains
the validation oracle.
