# VolumeSpikeBreakOut EA — Technical Specification

**Project:** FX Tools — MT5 Expert Advisor
**Version:** 1.00
**Status:** Active
**Author:** Dercio Micas
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation. Automates the **VolumeSpikeBreakOut** indicator: V-pattern (default) or Spike trigger → breakout-of-range entry → structural stop, 1:RR target. Self-contained (embedded detection) for the Strategy Tester. |

---

## 1. Overview & Design Intent

Automates the validated **VolumeSpikeBreakOut** setup (see the indicator spec §11).
Detection and breakout logic are **embedded** (mirroring the indicator) so the EA
runs self-contained in the Strategy Tester with no indicator dependency.

**What it trades (the validated edge):**
1. A **trigger** fires on a closed bar T — `V-pattern` (default) or `Spike`, using
   the selected method's line (default **Threshold** = `MA + Mult·StdDev`).
2. Over the next `InpBreakBars` closed bars, the **first** to break T's range gives
   the trade: break the high → **BUY**, break the low → **SELL**. Direction is
   confirmed by price, not candle colour. A bar breaking both (straddle) → no trade;
   no break within the window → the setup expires.
3. **Structural stop** at T's opposite extreme; **take-profit** at `1:InpRR` (default 3).

**Scope (important):** the edge is demonstrated on **gold and BTC, H1, V-pattern**.
On H4 the Spike trigger is better. Do **NOT** run on mean-reverting FX (e.g. EUR/AUD
crosses) — it is a net loser there. See indicator spec §11.

---

## 2. Entry / Stop / Target

| Element | Rule |
|---------|------|
| Signal eval | On each **new closed bar**; the just-closed bar (series idx 1) is tested as the breakout bar via the same backward scan as the indicator. |
| Entry | **Market**, at the breakout bar's close (bar-close tool). Buy at Ask, Sell at Bid. |
| Stop loss | Trigger bar T's **opposite extreme** (low for a buy, high for a sell); widened to the broker / `InpSLMinPoints` floor if too tight. |
| Take profit | `entry ± InpRR · |entry − SL|` (default 1:3). |
| Dedupe | One entry per breakout bar (`g_last_entry`); `InpMaxTrades` caps concurrent positions. |

### 2.1 Entry-timing note (expected performance)
The backtest entered at the **break level** (an intrabar stop) and measured avg R ≈
**0.21** (gold) / 0.20 (BTC) on H1. The EA enters at the **breakout bar's close**,
which is realistic for a bar-close tool but slightly worse — Python cross-check
(entry at close, structural 1:3, net of cost) gives avg R ≈ **0.155, PF ≈ 1.24** on
both gold and BTC. **That ~0.155 / PF 1.24 is the honest expectation for this EA**,
not 0.21. A future pending-stop-order entry at the break level would recover most of
the gap (see §6).

---

## 3. Trigger Detection (mirrors the indicator)

Per series-index `idx`, with `ma`/`std` = SMA/population-StdDev of `tick_volume` over
`InpMAPeriod`, the method's line `s` and spike test are:

| `InpMethod` | spike (Spike trigger) | line `s` (V-pattern trigger) |
|-------------|-----------------------|------------------------------|
| StdDev / Threshold | `vol > ma + Mult·std` | z-score / `ma+Mult·std` |
| Z-Score | `z > InpZThreshold` | z-score |
| Percentile | `rank > InpPctCutoff` | percentile rank |
| RVOL | `rvol > InpRvolThreshold` | rvol ratio |

**V-pattern** (idx = C1 rise, idx+1 = C2 trough, idx+2 = C3 pre-drop):
`s[C3] > s[C2]` AND `s[C1] > s[C2]` AND `(s[C1]−s[C2]) / |s[C2]| ≥ InpRisePct`.

EMA/SMMA MAs warm up from the oldest copied bar; SMA (and WMA→SMA) use a trailing sum.

---

## 4. Input Parameters

```mql5
// ── Detection ──
input ENUM_BO_TRIGGER InpTrigger     = BO_TRIGGER_VPATTERN; // V-pattern (H1) | Spike (H4)
input int             InpBreakBars   = 4;                   // breakout confirm window (bars)
input ENUM_BO_METHOD  InpMethod      = BO_METHOD_THRESHOLD;
input int             InpMAPeriod    = 20;     input ENUM_MA_METHOD InpMAType = MODE_SMA;
input double          InpMultiplier  = 2.0;    input double InpZThreshold = 2.5;
input int             InpPctPeriod   = 100;    input double InpPctCutoff  = 95.0;
input int             InpRvolDays    = 10;     input double InpRvolThreshold = 2.0;
input double          InpRisePct     = 0.02;   // only if trigger = V-pattern
// ── Time Filter ──  (InpTimeFilter, From/To hour/min)
// ── Trade ──
input double InpLotSize = 0.01;  input int InpMaxTrades = 1;   input int InpMaxSpread = -1;
input long   InpMagicNumber = 20260608;  input int InpDeviation = 30;
// ── Risk ──
input double InpRR = 3.0;         input int InpSLMinPoints = 100;
```

> `InpMaxSpread = -1` (disabled) by default — gold's spread (~280 points at 3-digit
> pricing) would otherwise block trades; enable with a symbol-appropriate value.

---

## 5. Execution Flow (per new bar)

```
OnTick (first tick of a new bar only):
  if outside time window / spread too high / at InpMaxTrades  → return
  DetectBreakout():
     for back = 1..InpBreakBars:
        T = 1 + back
        if not TriggerFired(T):                       continue
        if any bar in (T, 1) already broke [low[T],high[T]]: continue
        up = high[1] >= high[T];  dn = low[1] <= low[T]
        if up and dn (straddle) or neither:           continue
        → entry on bar 1, direction = up ? BUY : SELL ; trig = T ; break
  if entry: SL = T's opposite extreme (floored); TP = 1:InpRR; market order
```

---

## 6. Limitations & Future Work

- **One setup at a time** (`InpMaxTrades=1` default). The backtest took overlapping
  signals independently; the EA is more conservative, so live trade count ≤ backtest.
- **Market entry at bar close**, not the break level → ~0.05 R/trade below the
  idealized backtest (§2.1). *Future:* place **Buy/Sell Stop OCO pending orders** at
  T's extremes (expiry = `InpBreakBars` bars) to fill at the break level and recover
  the gap.
- **Fixed lot** sizing. *Future:* risk-% sizing off the structural stop distance.
- **No swap/financing** modelled here (multi-bar holds).
- Rare: a single fast bar gapping through **both** extremes could open opposing
  positions before dedupe; negligible on liquid gold/BTC H1.

---

## 7. File Structure

```
fx_tools/
└── ExpertAdvisors/
    └── VolumeSpikeBreakOut_EA/
        ├── VolumeSpikeBreakOut_EA.mq5
        └── VolumeSpikeBreakOut_EA_Spec.md   ← this file
```

---

## 8. Acceptance Criteria

- [ ] Compiles without warnings in MetaEditor 5 *(done: 0 errors, 0 warnings)*
- [ ] On XAUUSD H1 with defaults, Strategy Tester shows a **positive** result
      roughly in line with avg R ≈ 0.155 / PF ≈ 1.24 (modulo the tester fill model)
- [ ] Trade direction = breakout side (buy on high break, sell on low break)
- [ ] Stop sits at the trigger bar's opposite extreme; TP at 1:InpRR
- [ ] One entry per breakout bar; respects `InpMaxTrades`, spread, time filter
- [ ] `InpTrigger` switches between V-pattern and Spike; `InpMethod` selectable
- [ ] No trades on the forming bar (acts only on closed bars)

---

## 9. Validation Basis

Indicator spec §11: gold +0.21 / BTC +0.20 avg R on H1 (6/6 segments, net of cost),
break-level entry. EA entry-at-close cross-check (Python, `experiments.py`
`break_entry="close"`): gold/BTC ≈ 0.155 avg R, PF 1.24. Strategy-Tester
confirmation on XAUUSD H1 is the recommended next step before any live/demo use.

---

*End of specification.*
