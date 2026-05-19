# Volume Spike Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 1.0  
**Status:** Draft  
**Author:** Dercio Micas  
**Date:** 2026-05-19

---

## 1. Overview

A MetaTrader 5 custom indicator that identifies and visually highlights abnormal volume activity using statistical methods. The indicator operates across two chart panels: a **price panel overlay** (candle highlighting, arrows, or zones) and a **volume sub-window** with a stylized volume histogram and dynamic threshold lines.

The core premise is that volume significantly above its statistical norm precedes or accompanies high-probability price moves. The indicator makes these events immediately visible without cluttering the chart.

---

## 2. Detection Methods

### 2.1 Method A — Moving Average + Standard Deviation *(Primary, Recommended)*

The baseline method. Volume is considered a spike when it exceeds the rolling mean by a configurable number of standard deviations.

```
Spike condition:  Volume[i] > MA_Volume[i] + (Multiplier × StdDev_Volume[i])
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MA_Period` | 20 | Lookback window for the volume MA |
| `MA_Type` | SMA | `SMA`, `EMA`, `WMA`, or `SMMA` |
| `StdDev_Multiplier` | 2.0 | Sensitivity threshold (1.5 = aggressive, 3.0 = conservative) |

**Strengths:** Statistically rigorous, self-adapting to the instrument's volatility regime, easy to tune.

---

### 2.2 Method B — Z-Score Normalization *(Alternative)*

Normalises volume into standard units, making the threshold instrument-agnostic. Useful when comparing across multiple pairs.

```
Z[i] = (Volume[i] − MA_Volume[i]) / StdDev_Volume[i]
Spike condition: Z[i] > Z_Threshold
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Z_Threshold` | 2.5 | Standard score above which a spike is declared |

**Strengths:** Produces a normalised output buffer (useful for dashboards or multi-pair scanners).

---

### 2.3 Method C — Percentile Rank *(Alternative)*

Ranks the current bar's volume against the previous N bars. A spike is declared when volume is in the top P% of the distribution.

```
Spike condition: Rank(Volume[i], lookback) > Percentile_Threshold
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Percentile_Period` | 100 | Historical window for ranking |
| `Percentile_Threshold` | 95 | Top-N% cutoff |

**Strengths:** No assumption about distribution shape; robust to extreme outliers.

---

### 2.4 Method D — Relative Volume (RVOL) *(Supplementary)*

Compares current volume to the average volume of the same session time-slot across previous days. Accounts for intraday volume seasonality (e.g., London open always has high volume).

```
RVOL[i] = Volume[i] / AvgVolume_SameSession[i]
Spike condition: RVOL[i] > RVOL_Threshold
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RVOL_Days` | 10 | Number of historical days to average |
| `RVOL_Threshold` | 2.0 | Multiplier above session average |

**Strengths:** Best for intraday traders. Removes the "always high at 09:30" noise.

---

## 3. Visual Design

### 3.1 Price Panel (Main Chart)

| Element | Spike Type | Description |
|---------|-----------|-------------|
| Candle highlight | Bullish spike | Candle body and wicks recoloured to `Bullish_Spike_Color` |
| Candle highlight | Bearish spike | Candle body and wicks recoloured to `Bearish_Spike_Color` |
| Arrow marker | Any spike | Optional arrow above/below the bar for quick scanning |
| Background zone | Optional | Semi-transparent rectangle spanning the spike bar |

### 3.2 Volume Sub-Window

| Element | Description |
|---------|-------------|
| Volume histogram | Standard bars, coloured by candle direction (bull/bear) |
| MA line | Smooth line over the volume histogram |
| Upper threshold band | MA + Multiplier × StdDev drawn as a dashed line |
| Spike bars | Histogram bar recoloured to `Spike_Bar_Color` when threshold is exceeded |
| Z-Score line *(optional)* | Secondary buffer showing Z-score as a normalised oscillator |

---

## 4. Input Parameters

```mql5
// --- Detection ---
input ENUM_DETECTION_METHOD  DetectionMethod    = METHOD_STDDEV;  // Detection method
input int                    MA_Period          = 20;              // MA period (volume)
input ENUM_MA_METHOD         MA_Type            = MODE_SMA;       // MA type
input double                 StdDev_Multiplier  = 2.0;            // Std Dev multiplier
input double                 Z_Threshold        = 2.5;            // Z-score threshold
input int                    Percentile_Period  = 100;            // Percentile lookback
input double                 Percentile_Cutoff  = 95.0;           // Percentile threshold (%)
input int                    RVOL_Days          = 10;             // RVOL session days
input double                 RVOL_Threshold     = 2.0;            // RVOL spike multiplier

// --- Visuals (Price Panel) ---
input bool                   HighlightCandles   = true;           // Recolour spike candles
input bool                   ShowArrows         = true;           // Show arrow markers
input bool                   ShowZones          = false;          // Show background zones
input color                  Bullish_Spike_Color = clrDodgerBlue; // Bullish spike colour
input color                  Bearish_Spike_Color = clrOrangeRed;  // Bearish spike colour
input color                  Arrow_Color        = clrGold;        // Arrow colour
input int                    Arrow_Size         = 2;              // Arrow size (1–5)

// --- Visuals (Sub-Window) ---
input color                  Spike_Bar_Color    = clrMagenta;     // Spike histogram colour
input color                  MA_Line_Color      = clrWhite;       // MA line colour
input color                  Threshold_Color    = clrYellow;      // Threshold line colour
input bool                   ShowZScore         = false;          // Show Z-score buffer
input color                  ZScore_Color       = clrAqua;        // Z-score line colour

// --- Alerts ---
input bool                   AlertOnSpike       = true;           // Pop-up alert
input bool                   PushNotification   = false;          // Push to mobile
input bool                   EmailAlert         = false;          // Send email
input bool                   AlertOnNewBarOnly  = true;           // Limit alerts to bar close
```

---

## 5. Indicator Buffers

| Index | Name | Type | Panel | Description |
|-------|------|------|-------|-------------|
| 0 | `VolBuffer` | `DRAW_HISTOGRAM` | Sub-window | Raw volume bars |
| 1 | `MABuffer` | `DRAW_LINE` | Sub-window | Rolling volume MA |
| 2 | `ThresholdBuffer` | `DRAW_LINE` | Sub-window | Upper spike threshold line |
| 3 | `SpikeVolBuffer` | `DRAW_HISTOGRAM` | Sub-window | Recoloured spike bars |
| 4 | `ZScoreBuffer` | `DRAW_LINE` | Sub-window | Normalised Z-score (optional) |
| 5 | `ArrowUpBuffer` | `DRAW_ARROW` | Price | Spike arrow above candle |
| 6 | `ArrowDownBuffer` | `DRAW_ARROW` | Price | Spike arrow below candle |
| 7 | `BullCandleBuffer` | `DRAW_CANDLES` | Price | Recoloured bullish spike candles |
| 8 | `BearCandleBuffer` | `DRAW_CANDLES` | Price | Recoloured bearish spike candles |

> **Note:** MT5 supports `DRAW_CANDLES` for candle recolouring via a colour index buffer — no separate indicator window needed for the candle overlay.

---

## 6. Calculation Logic (Pseudocode)

```
FOR each bar i FROM MA_Period TO total_bars:

    vol = iVolume(symbol, timeframe, i)

    // Step 1: Rolling statistics
    ma_vol  = Mean(volume, i, MA_Period)
    std_vol = StdDev(volume, i, MA_Period)
    z_score = (vol - ma_vol) / std_vol  // guard: divide by zero if std_vol = 0

    // Step 2: Spike detection (selected method)
    IF method = STDDEV:
        is_spike = vol > (ma_vol + Multiplier * std_vol)

    ELSE IF method = ZSCORE:
        is_spike = z_score > Z_Threshold

    ELSE IF method = PERCENTILE:
        rank = CountBarsBelow(vol, i, Percentile_Period) / Percentile_Period * 100
        is_spike = rank > Percentile_Cutoff

    ELSE IF method = RVOL:
        avg_session_vol = AvgVolumeAtSameTime(i, RVOL_Days)
        rvol = vol / avg_session_vol
        is_spike = rvol > RVOL_Threshold

    // Step 3: Populate buffers
    MABuffer[i]        = ma_vol
    ThresholdBuffer[i] = ma_vol + Multiplier * std_vol
    ZScoreBuffer[i]    = z_score

    IF is_spike:
        SpikeVolBuffer[i] = vol
        is_bullish = Close[i] >= Open[i]
        IF ShowArrows:
            IF is_bullish: ArrowUpBuffer[i]  = Low[i]  - offset
            ELSE:          ArrowDownBuffer[i] = High[i] + offset
        IF HighlightCandles:
            set candle colour buffers for bar i

    // Step 4: Alerts (new bar only if enabled)
    IF is_spike AND AlertOnNewBarOnly AND i = 0:
        TriggerAlert(...)
```

---

## 7. Performance Considerations

- Use `OnCalculate()` with `prev_calculated` to avoid recalculating the entire history on every tick.
- Cache rolling mean and standard deviation using incremental updates (Welford's algorithm) for O(1) per bar rather than O(N).
- Avoid calling `iVolume()` in a loop — copy the full volume array once with `CopyTickVolume()` at the start of `OnCalculate()`.
- Sub-window with `DRAW_CANDLES` in the price panel requires `indicator_chart_window` to be set to `false` and using the colour buffer approach.

---

## 8. Alerts & Notifications

| Trigger | Condition |
|---------|-----------|
| Pop-up alert | `AlertOnSpike = true` |
| Push notification | `PushNotification = true` (requires MT5 mobile linked) |
| Email | `EmailAlert = true` (requires SMTP in MT5 settings) |

Alert message format:
```
[VolumeSpike] EURUSD H1 — Spike detected | Vol: 12,450 | MA: 5,230 | Z: 2.87 | 2026.05.19 14:00
```

---

## 9. File Structure

```
fx_tools/
├── VolumeSpike_Indicator_Spec.md       ← this file
└── Indicators/
    ├── VolumeSpike.mq5                 ← main indicator source
    └── VolumeSpike.ex5                 ← compiled binary (MT5)
```

---

## 10. Acceptance Criteria

- [ ] Indicator compiles without warnings in MetaEditor 5
- [ ] Spike candles are correctly coloured on the price chart
- [ ] Sub-window shows volume histogram, MA line, and threshold line
- [ ] All 4 detection methods selectable via input dropdown
- [ ] Alerts fire only on bar close when `AlertOnNewBarOnly = true`
- [ ] No performance degradation on 10-year history on M1
- [ ] Works on Forex, Indices, and Crypto instruments (tick volume)

---

## 11. Open Questions

| # | Question | Owner |
|---|---------- |-------|
| 1 | Should spike zones extend across multiple bars if volume stays above threshold? | Dercio |
| 2 | Should the Z-score buffer be normalised to a fixed scale (e.g., 0–100) for readability? | Dercio |
| 3 | Is RVOL (Method D) required for the v1 release or is it a v2 feature? | Dercio |
| 4 | Target timeframes: all, or restrict RVOL to M1–H1 only? | Dercio |

---

*End of specification.*
