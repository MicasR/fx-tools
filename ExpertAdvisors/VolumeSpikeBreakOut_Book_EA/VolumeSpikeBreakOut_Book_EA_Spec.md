# VolumeSpikeBreakOut Book EA — Technical Specification

**Project:** FX Tools — MT5 Expert Advisor
**Version:** 1.00
**Status:** Active — **Strategy-Tester validation required before any use**
**Author:** Dercio Micas
**Last updated:** 2026-06-09

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-09 | Initial implementation of the **confB+trail** book strategy: pyramid into the trend on BE-gated confluent breakouts, trail the whole book out with one shared chandelier stop, **risk-% per-trade sizing**. The best mode in the `book_sim.py` study (gold & BTC). Separate from the single-setup `VolumeSpikeBreakOut_EA`, which is preserved. |
| 1.01 | 2026-06-09 | **Bug fixes from first tester run.** Moved order/position management (fill detection, sibling-OCO cancel, SL sync to all positions) out of the new-bar gate to run **every tick** — previously the un-taken twin leg lingered and SLs lagged up to a full bar. Pending-expiry now counts **actual bars via `iBarShift`** instead of `(time diff)/PeriodSeconds`, which over-counted across session/weekend gaps and expired setups too early. Trail ratchet + signal arming stay per-bar (match the bar-close backtest). |
| 1.02 | 2026-06-09 | **Lot sizing → embedded `CalculateSafeLotSize`** (from `SameRiskLotSizing.mqh`). Adds a **margin-call-safe cap** the prior sizing lacked — the lot is the *min* of the risk-% lot and the lot that keeps a losing book above the stop-out level (`totalLots` = current open book lots). Same loss-per-lot math as before (verified equivalent; POINT==TICK_SIZE for gold/BTC). Min-lot floor kept; margin-unsafe → skip. **Note:** sizes off **equity** (incl. floating P&L), so adds grow as the book profits — deviates from the sim's equal-weight units; switch to balance for true same-risk-per-add. |

---

## 1. Why this EA exists

`book_sim.py` swept five trade-management modes; **confB+trail dominated both gold and
BTC** on every metric, 6/6 segments (gold totR 103→186, BTC 133→203 vs the 3RR
baseline; PF 1.83 / 2.03; best risk-adjusted). This EA is that mode, made live, with
proper risk-% sizing. The other management modes (divergence, confluence-A,
confB+divergence) all underperformed and are *not* implemented.

---

## 2. Strategy (confB + trail)

1. **Trigger** on a closed bar — V-pattern (default) or Spike, selected method's line.
2. **Flat → arm an OCO breakout pair:** Buy Stop @ trigger high (SL = low), Sell Stop @
   trigger low (SL = high). First fill starts the book in that direction; the sibling is
   deleted next tick. (Idealised break-level entry.)
3. **In a book → confluent add (BE-gated):** a same-direction trigger arms one add Stop,
   **only if** its structural SL (the trigger's far extreme) locks **every** open
   position to break-even+ (long: trigger low ≥ max open entry). Contrary signals are
   ignored. **No reversals.**
4. **Shared exit — one chandelier stop for the whole book:**
   `stop = max( latest structure SL , running_extreme − InpTrailMult×latest_range )`,
   ratcheting up only, written to **every** position's broker SL each bar. The book
   exits together when price hits it. There is **no fixed take-profit**.
5. **Expiry:** an un-filled pair/add is deleted after `InpBreakBars` bars.

### 2.1 Risk-% sizing & the BE-gate property
Each entry is sized so its structural risk (`|entry − SL| = range`) equals
`InpRiskPct`% of account equity:
`lot = (equity × RiskPct%) / ((range / tickSize) × tickValue)`, floored to lot step
(min-lot may exceed RiskPct on tiny accounts). **Backtest-verified:** because the BE-gate
only adds once prior legs are locked, **total open book risk stays ≈ 1 unit
(`InpRiskPct`) no matter how many positions are stacked** (peak 6 on gold, still 1.00R).
So expected **max account drawdown ≈ maxDD_R × RiskPct** (≈ 8% at 0.5%, ≈ 16% at 1%,
in-sample). Residual tail = a **gap through the shared stop** hits all stacked legs
together (correlated) — size conservatively; 1R is the *normal*, not worst, case.

---

## 3. Inputs

```mql5
// Detection
InpTrigger=VPATTERN, InpBreakBars=4, InpMethod=THRESHOLD, InpMAPeriod=20, InpMAType=SMA,
InpMultiplier=2.0, InpZThreshold=2.5, InpPctPeriod=100, InpPctCutoff=95, InpRvolDays=10,
InpRvolThreshold=2.0, InpRisePct=0.02
// Risk / Book
InpRiskPct=0.5            // % equity risked per entry
InpTrailMult=2.5          // shared trail distance = mult x latest range
InpMinRangePts=100        // skip trigger if range below this
InpMaxPositions=0         // stack cap (0 = unlimited)
// Trade
InpMaxSpread=-1, InpMagicNumber=20260609, InpDeviation=30
// Time Filter (off by default)
```

---

## 4. Book state & control flow

State is **derived from live positions each bar** (count + direction) plus persisted
shared-stop globals (`g_bsl`, `g_bext`, `g_brng`, `g_bstop`) and the last-armed trigger
H/L/range. Fills/closes are detected by **count change** (no order→position ticket
mapping): count↑ from 0 = new book (seed stop from the fill's structure, kill sibling);
count↑ in-book = add filled (ratchet shared stop to the add's structure); count→0 =
book closed (reset, clear pendings). Each bar while in a book: extend the running
extreme, ratchet `g_bstop`, write it to all positions, cancel any contrary pendings,
expire stale adds, then arm a new BE-gated add if a confluent trigger closed.

One setup armed at a time (≤1 pending add, or the initial OCO pair). Trailing/protection
runs every new bar regardless of the time/spread filters; only *new entries* are gated.

---

## 5. Scope & limitations

- **Deploy on gold & BTC only** (validated). Do **not** run on mean-reverting FX — the
  underlying edge is a net loser there.
- **Default trigger = V-pattern** (best on H1). On H4, Spike is better (per indicator spec).
- **Per-bar trailing:** the shared SL ratchets at bar close, not intrabar — matches the
  bar-close backtest.
- **Correlated gap risk** (see §2.1) is the main tail; `InpMaxPositions` can cap exposure.
- **Rare double-fill** of the OCO pair on one fast bar → opposing positions; negligible
  on liquid gold/BTC H1.
- **Not yet forward-tested**, and all sizing analysis is in-sample on ~2.2y H1.

---

## 6. Acceptance criteria

- [x] Compiles clean in MetaEditor 5 (0 errors, 0 warnings)
- [ ] Strategy Tester (XAUUSD H1, "every tick"/"1-min OHLC"): book builds (multiple
      positions stack), all SLs ratchet up together, the book exits as one
- [ ] Confluent adds appear only when prior legs are locked to BE+
- [ ] Contrary signals never open a position; no reversals
- [ ] Per-trade risk ≈ `InpRiskPct`% of equity; account DD ≈ maxDD_R × RiskPct
- [ ] Result broadly tracks the book_sim benchmark (gold/BTC strongly positive)

---

## 7. File structure
```
fx_tools/ExpertAdvisors/VolumeSpikeBreakOut_Book_EA/
  ├── VolumeSpikeBreakOut_Book_EA.mq5
  └── VolumeSpikeBreakOut_Book_EA_Spec.md   ← this file
```

*Validation basis:* `backtest/book_sim.py` (confBtrail), indicator spec §11.

*End of specification.*
