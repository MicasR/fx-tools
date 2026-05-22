# VolumeSpike EA — Technical Specification

**Project:** FX Tools — MT5 Expert Advisor  
**Version:** 1.02  
**Status:** Development  
**Author:** Dercio Micas  
**Last updated:** 2026-05-22

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-05-21 | Initial implementation |
| 1.01 | 2026-05-21 | Embed detection logic; remove iCustom dependency (Strategy Tester compatibility) |
| 1.02 | 2026-05-22 | Dynamic SL/TP: structure-based (candle high/low), ATR, and fixed modes; minimum SL floor; R:R take profit |

---

## 1. Overview

A MetaTrader 5 Expert Advisor that automates trading based on signals from the **VolumeSpike** indicator. The EA loads the indicator internally via `iCustom`, reads the colour-index buffer to detect spike direction, and manages trades accordingly.

Design philosophy: keep the initial version minimal and backtestable. The indicator's own detection and time-filter logic is reused directly; no additional signal filtering is applied at this stage.

---

## 2. Signal Source

The detection logic is **embedded directly in the EA** (mirrors `VolumeSpike.mq5`), making the EA fully self-contained. The indicator file is not required for backtesting or live trading — `VolumeSpike.mq5` remains the charting tool; the EA runs its own identical copy of the algorithm.

A spike is declared when `is_spike = true` (detection method dependent) for a given bar. Direction is determined by `close >= open` (bullish) or `close < open` (bearish), exactly as in the indicator.

This architecture was chosen after the MT5 Strategy Tester failed to load the indicator via `iCustom` when the indicator folder was a directory junction (error 4002).

---

## 3. Trade Logic

### 3.1 Entry

On a BUY signal:
1. Close all open SELL positions for this EA / symbol.
2. Check total open trades against `InpMaxTrades`.
3. Compute SL via `CalcSL(true, idx, Ask)` — skip trade if insufficient history.
4. Compute TP via `CalcTP(true, Ask, sl, idx)` — skip trade if insufficient history.
5. Open a BUY at `Ask` with the computed SL and TP.

On a SELL signal:
1. Close all open BUY positions for this EA / symbol.
2. Check total open trades against `InpMaxTrades`.
3. Compute SL via `CalcSL(false, idx, Bid)` — skip trade if insufficient history.
4. Compute TP via `CalcTP(false, Bid, sl, idx)` — skip trade if insufficient history.
5. Open a SELL at `Bid` with the computed SL and TP.

### 3.2 Exit

Positions are closed by one of three events:
- **Contrary signal** — a spike of the opposite direction closes all positions of the prior type before the new trade is opened.
- **Take profit hit** — MT5 closes the position automatically.
- **Stop loss hit** — MT5 closes the position automatically.

### 3.3 Same-direction stacking

Consecutive signals of the same type each open a new trade, subject to `InpMaxTrades`. This allows the EA to pyramid into a move. Set `InpMaxTrades = 1` to disable stacking.

### 3.4 Per-bar deduplication

Regardless of bar-timing mode, the EA acts at most **once per spike bar per direction**. Two globals (`g_last_buy_bar`, `g_last_sell_bar`) store the open-time of the last bar that triggered each trade type. Subsequent ticks or bar-open events for the same bar are ignored.

---

## 4. Bar Timing Modes

Controlled by `InpUseBarClose`:

| Mode | Buffer index read | Guard | Purpose |
|------|------------------|-------|---------|
| `true` — bar close | 1 (just-closed bar) | Runs once on new-bar open | Trade on confirmed, fully-formed spike candle |
| `false` — tick | 0 (forming bar) | Per-bar dedup only | Enter as soon as the spike threshold is crossed mid-bar |

> Both modes are intended for backtesting comparison. The bar-close mode is the safer default for live trading.

---

## 5. Filters

### 5.1 Time filter

Mirrors `IsInTimeWindow()` from `VolumeSpike.mq5` exactly, including overnight range support. When `InpTimeFilter = true`, signals outside the configured window are silently skipped — no trade is opened and no position is closed. Applied to `TimeCurrent()` (MT5 server time).

### 5.2 Spread filter

When `InpMaxSpread != -1`, the EA checks `SYMBOL_SPREAD` before acting. If the current spread exceeds `InpMaxSpread` points, the tick is skipped entirely. Set `InpMaxSpread = -1` to disable.

---

## 6. Input Parameters

```mql5
// ── Detection ────────────────────────────────────────────────────────
input ENUM_VS_DETECT_METHOD InpMethod        = VS_METHOD_STDDEV; // Detection method
input int                   InpMAPeriod      = 20;               // MA period (bars)
input ENUM_MA_METHOD        InpMAType        = MODE_SMA;         // MA type
input double                InpMultiplier    = 2.0;              // Std Dev multiplier
input double                InpZThreshold    = 2.5;              // Z-score threshold
input int                   InpPctPeriod     = 100;              // Percentile lookback (bars)
input double                InpPctCutoff     = 95.0;             // Percentile cutoff (%)
input int                   InpRvolDays      = 10;               // RVOL history (days)
input double                InpRvolThreshold = 2.0;              // RVOL multiplier

// ── Time Filter ──────────────────────────────────────────────────────
input bool                  InpTimeFilter    = false;            // Enable time-of-day filter
input int                   InpTimeFromHour  = 9;                // From – hour   (0-23)
input int                   InpTimeFromMin   = 0;                // From – minute (0-59)
input int                   InpTimeToHour    = 23;               // To   – hour   (0-23)
input int                   InpTimeToMin     = 59;               // To   – minute (0-59)

// ── Trade ────────────────────────────────────────────────────────────
input double                InpLotSize       = 0.01;             // Lot size
input int                   InpMaxTrades     = 3;                // Max open trades (-1 = unlimited)
input int                   InpMaxSpread     = 50;               // Max spread in points (-1 = disabled)
input long                  InpMagicNumber   = 20260521;         // Magic number
input int                   InpDeviation     = 10;               // Max slippage (points)
input bool                  InpUseBarClose   = true;             // true = bar close, false = tick

// ── Stop Loss ─────────────────────────────────────────────────────────
input ENUM_VS_SL_METHOD     InpSLMethod      = VS_SL_STRUCTURE;  // Stop loss method
input int                   InpSLLookback    = 3;                // Structure: bars before spike to scan
input int                   InpATRPeriod     = 14;               // ATR period (shared by SL and TP)
input double                InpSLATRMult     = 1.5;              // ATR multiplier for SL
input int                   InpSLFixed       = 1000;             // Fixed SL (points)
input int                   InpSLMinPoints   = 200;              // Minimum SL floor (points)

// ── Take Profit ───────────────────────────────────────────────────────
input ENUM_VS_TP_METHOD     InpTPMethod      = VS_TP_RR;         // Take profit method
input double                InpTPRR          = 2.0;              // R:R ratio
input double                InpTPATRMult     = 3.0;              // ATR multiplier for TP
input int                   InpTPFixed       = 3000;             // Fixed TP (points)
```

### SL methods

| Method | Description |
|--------|-------------|
| `VS_SL_STRUCTURE` | Scans `InpSLLookback` bars **before** the spike (excludes spike candle). For buys: lowest low. For sells: highest high. |
| `VS_SL_ATR` | `entry ± ATR(InpATRPeriod) × InpSLATRMult` |
| `VS_SL_FIXED` | `entry ± InpSLFixed × point` |

`InpSLMinPoints` and the broker's `SYMBOL_TRADE_STOPS_LEVEL` are always applied as a floor — the larger of the two wins.

### TP methods

| Method | Description |
|--------|-------------|
| `VS_TP_RR` | `TP_distance = SL_distance × InpTPRR`. Scales with the computed SL. |
| `VS_TP_ATR` | `entry ± ATR(InpATRPeriod) × InpTPATRMult` |
| `VS_TP_FIXED` | `entry ± InpTPFixed × point` |

---

## 7. Global State

| Variable | Type | Description |
|----------|------|-------------|
| `g_last_bar` | `datetime` | Open time of the last processed bar (bar-close mode guard) |
| `g_last_buy_bar` | `datetime` | Open time of the bar that last triggered a BUY |
| `g_last_sell_bar` | `datetime` | Open time of the bar that last triggered a SELL |
| `g_trade` | `CTrade` | MT5 trade execution object |

---

## 8. Execution Logic (Pseudocode)

```
OnInit:
    g_trade.SetMagicNumber(InpMagicNumber)
    g_trade.SetDeviation(InpDeviation)

OnTick:
    IF InpUseBarClose:
        IF iTime(0) == g_last_bar: return     // same bar, skip
        g_last_bar = iTime(0)

    IF NOT IsInTimeWindow(TimeCurrent()): return
    IF InpMaxSpread != -1 AND spread > InpMaxSpread: return

    idx = InpUseBarClose ? 1 : 0
    DetectSpike(idx) → is_spike, bullish
    IF NOT is_spike: return
    signal_bar = iTime(idx)

    IF bullish spike AND signal_bar != g_last_buy_bar:
        CloseAllByType(SELL)
        IF MaxTrades == -1 OR CountOpenTrades() < MaxTrades:
            sl = CalcSL(buy=true,  idx, Ask);  IF sl == 0: return
            tp = CalcTP(buy=true,  Ask, sl, idx); IF tp == 0: return
            g_last_buy_bar = signal_bar
            BUY at Ask with sl, tp

    IF bearish spike AND signal_bar != g_last_sell_bar:
        CloseAllByType(BUY)
        IF MaxTrades == -1 OR CountOpenTrades() < MaxTrades:
            sl = CalcSL(buy=false, idx, Bid);  IF sl == 0: return
            tp = CalcTP(buy=false, Bid, sl, idx); IF tp == 0: return
            g_last_sell_bar = signal_bar
            SELL at Bid with sl, tp
```

---

## 9. File Structure

```
fx_tools/
├── Indicators/
│   └── VolumeSpike/
│       ├── VolumeSpike.mq5
│       └── VolumeSpike_Indicator_Spec.md
└── ExpertAdvisors/
    └── VolumeSpike_EA/
        ├── VolumeSpike_EA.mq5              ← EA source
        └── VolumeSpike_EA_Spec.md          ← this file
```

---

## 10. Acceptance Criteria

- [ ] Compiles without warnings in MetaEditor 5
- [ ] EA loads the VolumeSpike indicator successfully (`INIT_SUCCEEDED`)
- [ ] BUY trade opens on bullish spike bar
- [ ] SELL trade opens on bearish spike bar
- [ ] Contrary signal closes opposite positions before opening a new one
- [ ] Same-direction signals stack trades up to `InpMaxTrades`
- [ ] `InpMaxTrades = -1` opens unlimited trades
- [ ] `InpMaxSpread = -1` disables spread filter
- [ ] Bar-close mode (`InpUseBarClose = true`) acts only once per new bar
- [ ] Tick mode (`InpUseBarClose = false`) acts on first qualifying tick per bar
- [ ] Time filter correctly blocks trades outside the configured window
- [ ] Overnight time ranges (e.g. 22:00–06:00) handled correctly
- [ ] No duplicate trades on the same spike bar in either timing mode
- [ ] Structure SL places stop below lowest low (buy) / above highest high (sell) of N candles before spike
- [ ] ATR SL places stop at entry ± ATR × multiplier
- [ ] Fixed SL places stop at entry ± points
- [ ] Minimum SL floor (`InpSLMinPoints`) is always respected, broker stop level honoured
- [ ] R:R TP scales correctly with the computed SL distance
- [ ] ATR TP and Fixed TP produce correct prices for both BUY and SELL
- [ ] Trade skipped gracefully when insufficient history for SL/TP calculation
- [ ] Backtester runs cleanly with no off-quotes or invalid price errors
- [ ] Confirmed working on Forex, Indices, and Crypto instruments

---

## 11. Roadmap / Future Improvements

Items identified for future development, roughly in priority order.

### Backtesting & Tuning
- **Optimisation pass** — systematic parameter sweep over `InpSL`, `InpTP`, `InpMultiplier`, `InpMAPeriod` using the MT5 Strategy Tester optimiser
- **Bar-close vs tick comparison** — run identical backtest with both `InpUseBarClose` values and compare equity curves to quantify the difference
- **Walk-forward analysis** — split history into in-sample / out-of-sample periods to detect overfitting early

### Risk Management
- **Account equity risk sizing** — calculate lot size as a percentage of account equity (e.g. 1% risk per trade) instead of a fixed lot
- **Trailing stop** — follow price after a certain number of points in profit
- **Break-even stop** — move SL to entry once TP is 50% reached

### Signal Filtering
- **Trend filter** — only take trades in the direction of a higher-timeframe MA or trend indicator
- **Minimum spike strength** — ignore spikes that barely exceed the threshold; add an `InpMinSpikeRatio` multiplier (e.g. spike must be 1.5× the threshold, not just above it)
- **Session filter** — separate from the time-of-day filter; allow selecting specific trading sessions (London, New York, Asian) by name

### Operational
- **Trade comment** — tag each opened position with a comment string (e.g. `VS_BUY_v1.00`) for easy identification in the trade history
- **Dashboard panel** — on-chart label showing EA status, open trade count, last signal, and current filter state
- **Notifications** — optional push/email/WhatsApp alert when a trade is opened or closed (mirrors indicator alert infrastructure)

---

*End of specification.*
