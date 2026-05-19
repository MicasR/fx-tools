# SMC (Smart Money Concepts) Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 2.0  
**Status:** Release  
**Author:** Dercio Micas  
**Date:** 2026-05-19

---

## 1. Overview

A MetaTrader 5 custom indicator that maps the full Smart Money Concepts (SMC) framework
directly onto the price chart. It detects and visualises structural shifts, supply/demand
imbalances, institutional order flow zones, and liquidity events — giving traders a
clean, professional overlay without requiring manual drawing.

All objects are drawn on the **main price chart** (no sub-window required).

### Feature Summary

| # | Feature | Version |
|---|---------|---------|
| 1 | Break of Structure (BoS) | 1.0 |
| 2 | Change of Character (ChoCh) | 1.0 |
| 3 | Fair Value Gaps (FVG) with mitigation tracking | 1.0 |
| 4 | Order Blocks (OB) with mitigation tracking | 1.0 |
| 5 | Liquidity Sweeps | 1.0 |
| 6 | OTE Levels (61.8–79% Fibonacci retracement) | 1.0 |
| 7 | MTF Structure Overlay (HTF BoS/ChoCh on current chart) | 2.0 |
| 8 | Trend Bias Dashboard (multi-TF panel) | 2.0 |
| 9 | Premium / Discount Zones | 2.0 |
| 10 | Inducement Levels (IDM) | 2.0 |
| 11 | Equal Highs / Equal Lows (EQH / EQL) | 2.0 |

---

## 2. Feature Set

### 2.1 Break of Structure (BoS)

A BoS confirms trend continuation. It fires when price closes beyond the most recent
confirmed swing high (bullish BoS) or swing low (bearish BoS) in the direction of the
prevailing trend.

```
Bullish BoS : Close[i] > LastConfirmedSwingHigh  AND trend = UP
Bearish BoS : Close[i] < LastConfirmedSwingLow   AND trend = DOWN
```

Visual: horizontal dotted line from the broken swing to the break bar, labelled **"BOS"**.

---

### 2.2 Change of Character (ChoCh)

A ChoCh signals a potential trend reversal. It fires when price closes beyond the most
recent confirmed swing in the *opposite* direction to the prevailing trend.

```
Bullish ChoCh : Close[i] > LastConfirmedSwingHigh  AND trend = DOWN
Bearish ChoCh : Close[i] < LastConfirmedSwingLow   AND trend = UP
```

Visual: solid line from the broken swing to the break bar, labelled **"CHOCH"**.
Colour is distinct from BoS to make reversals immediately visible.

---

### 2.3 Fair Value Gap (FVG)

An FVG is a three-candle imbalance where candle[i-2].High < candle[i].Low (bullish) or
candle[i-2].Low > candle[i].High (bearish). Price is expected to return and partially
or fully fill the gap.

```
Bullish FVG : High[i-2] < Low[i]   → gap = [High[i-2], Low[i]]
Bearish FVG : Low[i-2]  > High[i]  → gap = [High[i],   Low[i-2]]
```

Visual: semi-transparent rectangle spanning the gap, extending rightward until price
fills it (mitigation tracking). A filled FVG is faded to grey and labelled `FVG+ ✓` /
`FVG- ✓`.

---

### 2.4 Order Blocks (OB)

An Order Block is the last opposing candle before a BoS or ChoCh. It represents the
candle where institutional orders were placed before the structural break.

```
Bullish OB : Last bearish candle (Close < Open) before a Bullish BoS/ChoCh
Bearish OB : Last bullish candle (Close >= Open) before a Bearish BoS/ChoCh
```

Visual: filled rectangle spanning the OB candle's full range, extending rightward until
price mitigates it (wicks into the body). Mitigated OBs are faded to grey and labelled
`OB+ ✓` / `OB- ✓`.

---

### 2.5 Liquidity Sweeps

A liquidity sweep occurs when price wicks beyond a prior swing high/low (taking out
stop-loss clusters) and then closes back inside the range, indicating a false breakout
and probable reversal.

```
Bullish sweep : Low[i]  < PriorSwingLow  AND Close[i] > PriorSwingLow
Bearish sweep : High[i] > PriorSwingHigh AND Close[i] < PriorSwingHigh
```

Visual: Wingdings arrow below/above the sweep candle with a **"Sweep"** text label.

---

### 2.6 OTE Levels (Optimal Trade Entry)

OTE is the 61.8%–79% Fibonacci retracement zone of the most recent impulse leg (origin
at the last ChoCh). Price returning to this zone in a pullback offers a high-probability
entry aligned with the new trend direction.

```
Impulse leg : from ChoCh origin to latest swing extreme
OTE zone    : 61.8% – 79.0% retracement of the leg
50% level   : equilibrium reference
```

Visual: shaded rectangle for the OTE zone + dashed horizontal lines labelled `50%`,
`61.8%`, and `79%`. Zone fires once per ChoCh; the alert triggers once when price enters
the zone.

---

### 2.7 MTF Structure Overlay *(v2.0)*

Runs the same BoS/ChoCh pivot detection on a configurable higher timeframe (default H4)
and draws those structural breaks as thicker, distinctly coloured lines on the current
chart. This lets traders see the HTF narrative without switching timeframes.

```
HTF BoS   : same logic as §2.1 but applied to g_htfRates[] (HTF bar cache)
HTF ChoCh : same logic as §2.2 but applied to g_htfRates[]
```

**Implementation details:**
- Uses `CopyRates(_Symbol, InpMTFTimeframe, 0, needed, tmp)` to fetch the last N HTF bars
- Self-throttled: only reprocesses when `tmp[0].time` changes (new HTF bar closed)
- Full HTF scan is run from scratch each refresh (small array, negligible cost)
- HTF must be strictly higher than the current chart timeframe (`InpMTFTimeframe > _Period`)

Visual: thicker trend lines labelled **"HTF-BoS"** / **"HTF-ChoCh"** in distinct colours.

---

### 2.8 Trend Bias Dashboard *(v2.0)*

A compact panel drawn in the top-left corner of the chart showing the current trend bias
across five fixed timeframes: M15, H1, H4, D1, W1.

Bias is determined by comparing the current close to the rolling range midpoint:

```
rangeHigh = Max(High, lookback=20)
rangeLow  = Min(Low,  lookback=20)
mid       = (rangeHigh + rangeLow) / 2

UP   : Close > mid  AND  Close > rangeLow  + range × 0.6
DOWN : Close < mid  AND  Close < rangeHigh − range × 0.6
NEUTRAL : otherwise
```

Visual: dark background panel with per-column TF labels and colour-coded badges:
- `▲ UP` in green
- `▼ DN` in red
- `◆ NT` in grey

The panel position is configurable via `InpDashX` / `InpDashY`. The current chart's
timeframe uses the live `g_trend` state machine result rather than the rolling-range
method for accuracy.

---

### 2.9 Premium / Discount Zones *(v2.0)*

Redrawn after every confirmed structural break (BoS or ChoCh) using the current
`g_lastSwHigh` / `g_lastSwLow` as the range boundaries.

```
Equilibrium (EQ) = (rangeHigh + rangeLow) / 2
Premium zone     = [EQ, rangeHigh]   → price is expensive, favour sells
Discount zone    = [rangeLow, EQ]    → price is cheap,     favour buys
```

Visual:
- Semi-transparent red rectangle for Premium
- Semi-transparent green rectangle for Discount
- Dashed yellow line at the equilibrium with `EQ 50%` label
- `PREMIUM` / `DISCOUNT` labels at zone midpoints

Zones extend 200 bars rightward from the break point. The previous zone is deleted when
a new structural break redraws it.

---

### 2.10 Inducement Levels (IDM) *(v2.0)*

An Inducement is a minor swing high/low that forms in the pullback between a structural
break and the most recent Order Block. It marks a liquidity target that price is likely
to sweep before returning to the OB zone and continuing in the impulse direction.

```
In uptrend   : minor swing LOW  (InpIDMSwingLen bars each side)
               that forms after the last BoS and above the last bullish OB bottom
In downtrend : minor swing HIGH (InpIDMSwingLen bars each side)
               that forms after the last BoS and below the last bearish OB top
```

**Detection conditions:**
- Active trend required (`g_trend ≠ NEUTRAL`)
- At least one active OB must exist
- IDM pivot must be newer than the most recent OB's `timeStart`
- Duplicate IDMs within `2 × _Point` are suppressed

Visual: dashed orange horizontal line at the IDM price, labelled `IDM`. Marked `IDM ✓`
when price touches the level.

---

### 2.11 Equal Highs / Equal Lows (EQH / EQL) *(v2.0)*

Equal Highs and Equal Lows form when two swing pivots of the same type (both highs or
both lows) are within a configurable tolerance of each other. They represent liquidity
pools where stop-loss orders are clustered and are prime sweep targets.

```
EQH : |SwingHigh[a] − SwingHigh[b]| ≤ InpEQTolerance × _Point
EQL : |SwingLow[a]  − SwingLow[b]|  ≤ InpEQTolerance × _Point
```

The most recent confirmed swing is compared against all prior swings of the same type
within `InpEQLookback` bars. One match per new swing is drawn.

Visual: dashed line connecting the two matching swings, labelled **"EQH"** (yellow) or
**"EQL"** (cyan). Up to 30 active EQ pairs are tracked; oldest is evicted at capacity.

---

## 3. Input Parameters

```mql5
// ── Structure ──────────────────────────────────────────────────────────────
input int              InpSwingLen        = 5;              // Swing pivot look-left/right (bars)
input bool             InpShowBoS         = true;           // Show Break of Structure
input bool             InpShowChoCh       = true;           // Show Change of Character
input color            InpBoSColor        = clrDodgerBlue;  // BoS line colour
input color            InpChoCHColor      = clrOrangeRed;   // ChoCh line colour
input int              InpStructLineWidth = 1;              // Structure line width

// ── Fair Value Gaps ────────────────────────────────────────────────────────
input bool             InpShowFVG         = true;           // Show Fair Value Gaps
input bool             InpFVGMitigation   = true;           // Extend FVG until mitigated
input color            InpFVGBullColor    = clrLimeGreen;   // Bullish FVG colour
input color            InpFVGBearColor    = clrTomato;      // Bearish FVG colour
input int              InpFVGAlpha        = 40;             // FVG transparency (0–255)
input int              InpMaxFVGs         = 20;             // Max active FVGs tracked

// ── Order Blocks ───────────────────────────────────────────────────────────
input bool             InpShowOB          = true;           // Show Order Blocks
input bool             InpOBMitigation    = true;           // Fade mitigated OBs
input color            InpOBBullColor     = clrDeepSkyBlue; // Bullish OB colour
input color            InpOBBearColor     = clrCrimson;     // Bearish OB colour
input int              InpOBAlpha         = 50;             // OB transparency (0–255)
input int              InpMaxOBs          = 10;             // Max active OBs tracked

// ── Liquidity Sweeps ───────────────────────────────────────────────────────
input bool             InpShowSweeps      = true;           // Show Liquidity Sweeps
input color            InpSweepBullColor  = clrAqua;        // Bullish sweep colour
input color            InpSweepBearColor  = clrMagenta;     // Bearish sweep colour
input int              InpSweepArrowSize  = 2;              // Sweep arrow size (1–5)

// ── OTE ────────────────────────────────────────────────────────────────────
input bool             InpShowOTE         = true;           // Show OTE zone
input color            InpOTEColor        = clrGold;        // OTE zone colour
input int              InpOTEAlpha        = 35;             // OTE transparency (0–255)

// ── MTF Structure Overlay ─────────────────────────────────────────────────
input bool             InpShowMTF         = true;           // Show HTF structure overlay
input ENUM_TIMEFRAMES  InpMTFTimeframe    = PERIOD_H4;      // Higher timeframe
input color            InpMTFBoSColor     = clrSteelBlue;   // HTF BoS colour
input color            InpMTFChoCHColor   = clrSalmon;      // HTF ChoCh colour
input int              InpMTFLineWidth    = 2;              // HTF line width
input int              InpMTFSwingLen     = 5;              // HTF swing look-left/right

// ── Trend Bias Dashboard ──────────────────────────────────────────────────
input bool             InpShowDashboard   = true;           // Show trend bias dashboard
input color            InpDashBgColor     = C'20,20,30';    // Dashboard background
input color            InpDashTextColor   = clrWhite;       // Dashboard text colour
input color            InpDashUpColor     = clrLimeGreen;   // Uptrend badge colour
input color            InpDashDownColor   = clrTomato;      // Downtrend badge colour
input color            InpDashNeutColor   = clrDimGray;     // Neutral badge colour
input int              InpDashX           = 20;             // Dashboard X position (pixels)
input int              InpDashY           = 30;             // Dashboard Y position (pixels)

// ── Premium / Discount ────────────────────────────────────────────────────
input bool             InpShowPD          = true;           // Show Premium/Discount zones
input color            InpPremiumColor    = clrTomato;      // Premium zone colour
input color            InpDiscountColor   = clrLimeGreen;   // Discount zone colour
input color            InpEqColor         = clrYellow;      // Equilibrium line colour
input int              InpPDAlpha         = 20;             // P/D transparency (0–255)

// ── Inducement ────────────────────────────────────────────────────────────
input bool             InpShowIDM         = true;           // Show Inducement levels
input color            InpIDMColor        = clrOrange;      // Inducement line colour
input int              InpIDMSwingLen     = 2;              // IDM swing sensitivity (bars)

// ── Equal Highs / Equal Lows ──────────────────────────────────────────────
input bool             InpShowEQ          = true;           // Show Equal Highs/Lows
input double           InpEQTolerance     = 5.0;            // Tolerance in points (pips × 10)
input color            InpEQHColor        = clrYellow;      // EQH colour
input color            InpEQLColor        = clrCyan;        // EQL colour
input int              InpEQLookback      = 100;            // Bars to look back for EQ matches

// ── Alerts ─────────────────────────────────────────────────────────────────
input bool             InpAlertBoS        = true;           // Alert on BoS
input bool             InpAlertChoCh      = true;           // Alert on ChoCh
input bool             InpAlertFVG        = false;          // Alert on new FVG
input bool             InpAlertSweep      = false;          // Alert on Liquidity Sweep
input bool             InpAlertOTE        = false;          // Alert when price enters OTE
input bool             InpPush            = false;          // Push notification
input bool             InpEmail           = false;          // Email alert
input bool             InpAlertBarClose   = true;           // Alert only at bar close
```

---

## 4. Indicator Buffers

This indicator uses **chart objects only** (no plotted buffers). All drawings are
`OBJ_TREND`, `OBJ_RECTANGLE`, `OBJ_RECTANGLE_LABEL`, `OBJ_ARROW`, `OBJ_LABEL`, and
`OBJ_TEXT` objects managed via `ObjectCreate` / `ObjectDelete`.

One hidden buffer (index 0, `DRAW_NONE`) is declared to satisfy the MT5 requirement that
`indicator_buffers >= 1`.

---

## 5. Internal Data Structures

```mql5
struct SwingPoint {
    datetime time;
    double   price;
    bool     isHigh;       // true = swing high, false = swing low
    bool     confirmed;    // true once look-right bars have closed
};

struct FVGZone {
    datetime timeStart;
    datetime timeEnd;      // extends rightward each bar until mitigated
    double   top;
    double   bottom;
    bool     bullish;
    bool     mitigated;
    string   objName;
};

struct OrderBlock {
    datetime timeStart;
    datetime timeEnd;
    double   top;          // candle High
    double   bottom;       // candle Low
    double   bodyTop;      // max(Open, Close)
    double   bodyBottom;   // min(Open, Close)
    bool     bullish;
    bool     mitigated;
    string   objName;
};

struct OTEState {
    double   legHigh;
    double   legLow;
    double   ote61;        // 61.8% retracement level
    double   ote79;        // 79.0% retracement level
    double   eq50;         // 50.0% equilibrium
    bool     bullish;
    bool     active;
    datetime originTime;
};

// ── v2.0 additions ──────────────────────────────────────────────────────────

struct MTFState {
    ENUM_TREND_STATE trend;
    double           lastSwHigh;
    double           lastSwLow;
    datetime         lastSwHighTime;
    datetime         lastSwLowTime;
    int              obCandidateIdx;
};

struct PDState {
    double   rangeHigh;
    double   rangeLow;
    double   eq50;
    bool     active;
    datetime originTime;
};

struct IDMLevel {
    datetime time;
    double   price;
    bool     isHigh;       // true = IDM above price (bearish context)
    bool     hit;
    string   objName;
};

struct EQLevel {
    datetime time1;
    datetime time2;
    double   price;        // average of the two matched swing prices
    bool     isHigh;
    string   objName;
};
```

**Fixed-size limits (compile-time defines):**

| Constant | Value | Purpose |
|----------|-------|---------|
| `SWING_HIST` | 200 | Swing ring-buffer capacity |
| `MAX_OBJ_HIST` | 300 | Max bars back to draw objects on first load |
| `MAX_IDM` | 20 | Max active Inducement levels tracked |
| `MAX_EQ` | 30 | Max active EQH/EQL pairs tracked |

---

## 6. Swing Detection Algorithm

A swing high at bar `i` is confirmed when:
- `High[i]` is strictly the highest high within `[i − SwingLen, i + SwingLen]`
- All `SwingLen` bars to the right have already closed (look-right confirmation)

This introduces a `SwingLen`-bar lag, which is the standard SMC approach to avoid false
pivots on live bars.

The same algorithm runs independently on:
1. **LTF (current chart)** — with `InpSwingLen`, drives all primary features
2. **HTF (MTF overlay)** — with `InpMTFSwingLen`, operates on `g_htfRates[]`
3. **IDM micro-pivots** — with `InpIDMSwingLen` (default 2), finer resolution

---

## 7. Structure State Machine

Applies identically to both the LTF (`g_trend`) and HTF (`g_mtf.trend`) contexts.

```
States:   TREND_NEUTRAL (0) → TREND_UP (1) ↔ TREND_DOWN (2)

Transitions:
  NEUTRAL    + bull break → TREND_UP    (first break, no label — establishes bias)
  NEUTRAL    + bear break → TREND_DOWN
  TREND_UP   + bull break → TREND_UP    → draws BoS
  TREND_UP   + bear break → TREND_DOWN  → draws ChoCh
  TREND_DOWN + bear break → TREND_DOWN  → draws BoS
  TREND_DOWN + bull break → TREND_UP    → draws ChoCh
```

A "break" is a candle closing beyond the most recent confirmed opposite swing.

---

## 8. Object Naming Convention

All indicator objects use the prefix `"SMC_"` for LTF objects or `"SMC_DASH_"` for
dashboard UI objects. Bulk deletion on `OnDeinit` scans for these prefixes.

| Object | Name pattern |
|--------|-------------|
| BoS line | `SMC_BOS_<timestamp>` |
| ChoCh line | `SMC_CHOCH_<timestamp>` |
| Structure label | `SMC_BOS_<ts>_L` / `SMC_CHOCH_<ts>_L` |
| FVG rectangle | `SMC_FVG_<B\|R>_<timestamp>` |
| FVG label | `SMC_FVG_<B\|R>_<ts>_L` |
| OB rectangle | `SMC_OB_<B\|R>_<timestamp>` |
| OB label | `SMC_OB_<B\|R>_<ts>_L` |
| Sweep arrow | `SMC_SWP_<B\|R>_<timestamp>` |
| Sweep label | `SMC_SWP_<B\|R>_<ts>_L` |
| OTE zone | `SMC_OTE_<timestamp>` |
| OTE Fib lines | `SMC_OTE_50_<ts>`, `SMC_OTE_618_<ts>`, `SMC_OTE_79_<ts>` |
| HTF BoS line | `SMC_MTF_HTF-BoS_<timestamp>` |
| HTF ChoCh line | `SMC_MTF_HTF-ChoCh_<timestamp>` |
| Premium zone | `SMC_PD_PREM_<timestamp>` |
| Discount zone | `SMC_PD_DISC_<timestamp>` |
| Equilibrium line | `SMC_PD_EQ_<timestamp>` |
| IDM level | `SMC_IDM_<timestamp>` |
| EQH/EQL line | `SMC_EQ_<ts1>_<ts2>` |
| Dashboard panel | `SMC_DASH_BG` |
| Dashboard labels | `SMC_DASH_TITLE`, `SMC_DASH_TF_<n>`, `SMC_DASH_BIAS_<n>` |

---

## 9. Performance Notes

- `OnCalculate` uses `prev_calculated` to only loop over new bars on each tick.
- On full recalculation (chart attach / timeframe change), object drawing is limited to
  the most recent `MAX_OBJ_HIST` (300) bars to prevent flooding long histories.
- FVG, OB, IDM, and EQ arrays are all hard-capped; oldest entries are evicted (FIFO)
  when each respective cap is reached.
- All swing history is stored in a fixed-size ring buffer (`SWING_HIST = 200`) — no
  unbounded memory growth.
- **MTF overlay** calls `CopyRates` once per `OnCalculate` tick but short-circuits
  immediately if the HTF bar timestamp has not changed — effectively O(1) on most ticks.
- **Dashboard** redraws every tick using `ObjectSetString`/`ObjectSetInteger` updates
  on existing objects, which is faster than delete-and-recreate.
- EQH/EQL scan is bounded by `InpEQLookback` comparisons per new swing — worst case
  `O(InpEQLookback)` but typically exits after the first match.

---

## 10. File Structure

```
fx_tools/
└── Indicators/
    ├── VolumeSpike/
    │   ├── VolumeSpike.mq5
    │   └── VolumeSpike_Indicator_Spec.md
    └── SMC/
        ├── SMC.mq5                  ← main indicator source (v2.0, ~1 400 lines)
        └── SMC_Indicator_Spec.md    ← this file
```

---

## 11. Remaining Improvement Opportunities

Features 1–5 from the original list are now implemented. The following remain:

| # | Feature | Priority |
|---|---------|----------|
| 1 | ChoCh confirmation filter (require FVG or OB confluence before flipping trend) | Medium |
| 2 | Session-based liquidity lines (NY open high/low, London, Asian range) | Low |
| 3 | Breaker blocks (mitigated OB that flips polarity and acts as opposing zone) | Low |
| 4 | Dashboard: configurable TF list instead of fixed M15/H1/H4/D1/W1 | Low |
| 5 | MTF FVG display (show HTF FVGs as faint background zones on LTF chart) | Medium |
| 6 | Alerts for IDM hit and EQH/EQL sweep | Low |

---

## 12. Acceptance Criteria

### v1.0 (original)
- [x] Indicator compiles without warnings in MetaEditor 5
- [x] BoS and ChoCh lines drawn correctly with labels
- [x] FVG rectangles extend rightward until mitigated
- [x] Order Blocks faded after price touches the zone
- [x] Liquidity sweeps detected and marked with arrows
- [x] OTE zone drawn after each ChoCh with correct Fib levels
- [x] All objects deleted cleanly on `OnDeinit`
- [x] Alerts fire at bar close when `InpAlertBarClose = true`

### v2.0 (new features)
- [ ] HTF BoS/ChoCh lines appear on the chart when `InpShowMTF = true`
- [ ] HTF lines do not redraw on every tick (throttled to new HTF bars only)
- [ ] Dashboard panel shows correct UP/DN/NT bias for all 5 timeframes
- [ ] Dashboard updates colour on bias change without flickering
- [ ] Premium/Discount zones redraw on every new structural break
- [ ] Equilibrium line sits exactly at the 50% midpoint of the swing range
- [ ] IDM levels only appear when trend is active and an OB exists
- [ ] IDM marked as hit when price touches the level
- [ ] EQH/EQL pairs connected by dashed line within tolerance
- [ ] No performance degradation on 5-year M15 history with all features enabled

---

*End of specification.*
