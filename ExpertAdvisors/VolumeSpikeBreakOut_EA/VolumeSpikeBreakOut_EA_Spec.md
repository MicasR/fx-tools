# VolumeSpikeBreakOut EA — Technical Specification

**Project:** FX Tools — MT5 Expert Advisor
**Version:** 1.01
**Status:** Active
**Author:** Dercio Micas
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation. Automates the **VolumeSpikeBreakOut** indicator: V-pattern (default) or Spike trigger → breakout-of-range entry → structural stop, 1:RR target. Self-contained (embedded detection) for the Strategy Tester. Entry at the breakout bar's *close*. |
| 1.01 | 2026-06-08 | **Idealized break-level entry via an OCO pending-stop pair.** On a trigger bar, arm a Buy Stop @ high and Sell Stop @ low (structural SL, 1:RR TP); the first fill cancels the other; the pair expires after `InpBreakBars` bars. Recovers the ~0.05 R/trade that the v1.00 close-entry gave up — expected avg R ≈ 0.21 (gold), matching the backtest. |

---

## 1. Overview & Design Intent

Automates the validated **VolumeSpikeBreakOut** setup (see the indicator spec §11).
Detection and breakout logic are **embedded** (mirroring the indicator) so the EA
runs self-contained in the Strategy Tester with no indicator dependency.

**What it trades (the validated edge):**
1. A **trigger** fires on a closed bar T — `V-pattern` (default) or `Spike`, using
   the selected method's line (default **Threshold** = `MA + Mult·StdDev`).
2. An **OCO pending pair** is armed at T's range — a **Buy Stop @ T.high** and a
   **Sell Stop @ T.low**. The first to fill is the trade (direction confirmed by
   price); the other is **cancelled** on the next tick. If neither fills within
   `InpBreakBars` bars, the pair is deleted (expires).
3. **Structural stop** at T's opposite extreme; **take-profit** at `1:InpRR` (default 3).

**Scope (important):** the edge is demonstrated on **gold and BTC, H1, V-pattern**.
On H4 the Spike trigger is better. Do **NOT** run on mean-reverting FX (e.g. EUR/AUD
crosses) — it is a net loser there. See indicator spec §11.

---

## 2. Entry / Stop / Target

| Element | Rule |
|---------|------|
| Signal eval | On each **new closed bar**, the just-closed bar (series idx 1) is tested as a trigger. |
| Arming | If it's a trigger and we are flat with no pending pair: place **Buy Stop @ high[1]** and **Sell Stop @ low[1]** (GTC). |
| Entry | The **break level** itself — whichever stop the market reaches first fills. |
| OCO | On the next tick after a fill, the opposite pending order is **deleted**. |
| Expiry | Managed per-bar: if the pair is unfilled after `InpBreakBars` bars, both are deleted. |
| Stop loss | Trigger bar T's **opposite extreme** (low for the buy leg, high for the sell leg). |
| Take profit | break level `± InpRR · range` where `range = high[1] − low[1]` (so 1:`InpRR` on the structural risk). |
| Sizing / cap | Fixed `InpLotSize`; **one setup at a time** (`InpMaxTrades = 1`). |

### 2.1 Expected performance
Entry is now the **idealized break-level fill** the backtest measured. On H1,
V-pattern, structural 1:3, net of cost: **gold ≈ 0.21 avg R (PF 1.32, 6/6 segments),
BTC ≈ 0.20 (PF 1.31, 6/6)** — see indicator spec §11. (v1.00 entered at the bar
*close* and gave ≈ 0.155; v1.01's pending-stop pair recovers that gap.)

A setup is **skipped** if the trigger-bar range is below `InpMinRangePts`, or if a
break level is not a valid stop-order distance from the current market (e.g. an open
gap already through the level) — we never place a one-sided or invalid pair.

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
input double InpRR = 3.0;         input int InpMinRangePts = 100;   // skip if trigger range < this
```

> `InpMaxSpread = -1` (disabled) by default — gold's spread (~280 points at 3-digit
> pricing) would otherwise block trades; enable with a symbol-appropriate value.

---

## 5. Execution Flow

```
OnTick (EVERY tick):
  if a position is open AND a pending order remains → DeleteAllPendings()   // OCO

OnTick (first tick of a NEW bar only):
  if pending pair unfilled and (bars since arm) > InpBreakBars → DeleteAllPendings()  // expiry
  if outside time window / spread too high                    → return
  if any position OR any pending of ours exists               → return       // one setup at a time
  if IsTriggerBar(index 1):
     range = high[1] - low[1]
     if range >= InpMinRangePts and both levels a valid stop distance from market:
        BuyStop  @ high[1]  SL=low[1]   TP=high[1]+InpRR*range
        SellStop @ low[1]   SL=high[1]  TP=low[1] -InpRR*range
        remember arm time
```

OCO is enforced two ways: the per-tick check cancels the surviving leg right after a
fill, and *one-setup-at-a-time* guarantees only the current pair's orders exist, so
"delete all our pendings when a position is open" is unambiguous.

---

## 6. Limitations & Future Work

- **One setup at a time** (`InpMaxTrades=1`). The backtest took overlapping signals
  independently; the EA is more conservative, so live trade count ≤ backtest. This is
  also what makes the simple "delete-all-pendings" OCO unambiguous.
- **Fixed lot** sizing. *Future:* risk-% sizing off the structural stop distance.
- **No swap/financing** modelled here (multi-bar holds).
- **Rare double-fill:** if one fast tick trades through *both* break levels before the
  per-tick OCO runs, two opposing positions could open. Negligible on liquid gold/BTC
  H1; `OnTradeTransaction`-based instant OCO is a possible hardening.
- **Gap skips:** if price has already passed a break level when the bar opens, that
  pair is skipped (no valid stop-order distance) — matches the backtest's straddle/
  no-trade handling.

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
      roughly in line with avg R ≈ 0.21 / PF ≈ 1.3 (modulo the tester fill model)
- [ ] On a trigger bar, a Buy Stop @ high and Sell Stop @ low are placed
- [ ] First fill cancels the opposite pending order (OCO)
- [ ] Unfilled pairs disappear after `InpBreakBars` bars
- [ ] Filled trade direction = break side; SL at opposite extreme; TP at 1:InpRR
- [ ] Only one setup (pair or position) active at a time
- [ ] `InpTrigger` switches V-pattern/Spike; `InpMethod` selectable; closed bars only

---

## 9. Validation Basis

Indicator spec §11: gold +0.21 / BTC +0.20 avg R on H1 (6/6 segments, net of cost),
**break-level entry — which v1.01's OCO pending-stop pair reproduces.** (The v1.00
bar-close entry measured ≈ 0.155 avg R via `experiments.py break_entry="close"`; the
~0.05 R gap is what the pending-stop entry recovers.) Strategy-Tester confirmation on
XAUUSD H1 is the recommended next step before any live/demo use.

---

*End of specification.*
