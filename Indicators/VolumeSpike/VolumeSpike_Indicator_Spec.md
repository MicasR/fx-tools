# Volume Spike Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 1.03  
**Status:** Active  
**Author:** Dercio Micas  
**Last updated:** 2026-05-20

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-05-19 | Initial implementation |
| 1.01 | 2026-05-19 | Alert fires only once per candle; removed `InpAlertClose` |
| 1.02 | 2026-05-20 | Added optional time-of-day filter for alerts and arrows |
| 1.03 | 2026-05-20 | Default arrow size reduced from 2 to 1 |

---

## 1. Overview

A MetaTrader 5 custom indicator that identifies and visually highlights abnormal volume activity using statistical methods. The indicator operates across two chart panels: a **price panel overlay** (spike arrows and optional highlight zones drawn as chart objects) and a **volume sub-window** with a colour-coded histogram, volume MA, and dynamic threshold line.

The core premise is that volume significantly above its statistical norm precedes or accompanies high-probability price moves.

---

## 2. Detection Methods

### 2.1 Method 0 — MA + Standard Deviation *(Default, Recommended)*

```
Spike condition:  Volume[i] > MA_Volume[i] + (InpMultiplier × StdDev_Volume[i])
```

| Parameter | Input name | Default | Description |
|-----------|-----------|---------|-------------|
| MA period | `InpMAPeriod` | 20 | Lookback window for the volume MA |
| MA type | `InpMAType` | SMA | `SMA`, `EMA`, `WMA`, or `SMMA` |
| Multiplier | `InpMultiplier` | 2.0 | Sensitivity threshold (1.5 = aggressive, 3.0 = conservative) |

---

### 2.2 Method 1 — Z-Score Normalisation

```
Z[i] = (Volume[i] − MA_Volume[i]) / StdDev_Volume[i]
Spike condition: Z[i] > InpZThreshold
```

| Parameter | Input name | Default | Description |
|-----------|-----------|---------|-------------|
| Z threshold | `InpZThreshold` | 2.5 | Standard score above which a spike is declared |

---

### 2.3 Method 2 — Percentile Rank

```
Spike condition: Rank(Volume[i], lookback) > InpPctCutoff
```

| Parameter | Input name | Default | Description |
|-----------|-----------|---------|-------------|
| Lookback | `InpPctPeriod` | 100 | Historical window for ranking |
| Cutoff | `InpPctCutoff` | 95.0 | Top-N% threshold |

---

### 2.4 Method 3 — Relative Volume (RVOL)

Compares current volume to the average volume at the same session time-slot across the previous N days. Accounts for intraday volume seasonality (e.g. London open always has high volume).

```
RVOL[i] = Volume[i] / AvgVolume_SameSession[i]
Spike condition: RVOL[i] > InpRvolThreshold
```

| Parameter | Input name | Default | Description |
|-----------|-----------|---------|-------------|
| History days | `InpRvolDays` | 10 | Number of historical days to average |
| Threshold | `InpRvolThreshold` | 2.0 | Multiplier above session average |

---

## 3. Visual Design

### 3.1 Price Panel (Main Chart)

Spike markers are drawn as **chart objects** (not indicator buffers), allowing them to persist cleanly without requiring additional buffer slots.

| Element | Object type | Condition | Description |
|---------|------------|-----------|-------------|
| Spike arrow | `OBJ_ARROW` | `InpShowArrows = true` | Arrow above (bearish) or below (bullish) the spike bar |
| Highlight zone | `OBJ_RECTANGLE` | `InpShowZones = true` | Semi-transparent rectangle spanning the spike bar's high–low range |

On indicator load, objects are materialised for the most recent **500 bars** only to avoid flooding the chart on long histories (`MAX_OBJ_HIST = 500`).

### 3.2 Volume Sub-Window

| Element | Buffer | Description |
|---------|--------|-------------|
| Volume histogram | `g_vol` + `g_col` | Colour-coded bars: bull/bear normal and bull/bear spike |
| MA line | `g_ma` | Smooth line over the histogram |
| Threshold line | `g_thresh` | `MA + InpMultiplier × StdDev`, drawn as a dashed line |
| Z-score line *(optional)* | `g_z` | Z-score scaled to MA units; hidden unless `InpShowZScore = true` |

---

## 4. Input Parameters

```mql5
// ── Detection ───────────────────────────────────────────────────────
input ENUM_DETECT_METHOD  InpMethod        = METHOD_STDDEV; // Detection method (0–3)
input int                 InpMAPeriod      = 20;            // MA period (bars)
input ENUM_MA_METHOD      InpMAType        = MODE_SMA;      // MA type
input double              InpMultiplier    = 2.0;           // Std Dev multiplier
input double              InpZThreshold    = 2.5;           // Z-score threshold
input int                 InpPctPeriod     = 100;           // Percentile lookback (bars)
input double              InpPctCutoff     = 95.0;          // Percentile cutoff (%)
input int                 InpRvolDays      = 10;            // RVOL history (days)
input double              InpRvolThreshold = 2.0;           // RVOL multiplier

// ── Price Chart ──────────────────────────────────────────────────────
input bool                InpShowArrows    = true;          // Draw spike arrows
input bool                InpShowZones     = false;         // Draw highlight zones
input color               InpBullColor     = clrDodgerBlue; // Bullish spike colour
input color               InpBearColor     = clrOrangeRed;  // Bearish spike colour
input color               InpZoneColor     = clrGold;       // Zone fill colour
input int                 InpArrowSize     = 1;             // Arrow size (1–5)

// ── Sub-Window ───────────────────────────────────────────────────────
input color               InpBarBull       = clrSteelBlue;  // Normal bull bar
input color               InpBarBear       = clrDimGray;    // Normal bear bar
input color               InpSpikeBull     = clrDodgerBlue; // Spike bull bar
input color               InpSpikeBear     = clrOrangeRed;  // Spike bear bar
input bool                InpShowZScore    = false;         // Show Z-score line

// ── Alerts ───────────────────────────────────────────────────────────
input bool                InpAlert         = true;          // Pop-up alert
input bool                InpPush          = false;         // Push notification
input bool                InpEmail         = false;         // Email alert

// ── Time Filter ──────────────────────────────────────────────────────
input bool                InpTimeFilter    = false;         // Enable time-of-day filter
input int                 InpTimeFromHour  = 9;             // From – hour   (0-23)
input int                 InpTimeFromMin   = 0;             // From – minute (0-59)
input int                 InpTimeToHour    = 23;            // To   – hour   (0-23)
input int                 InpTimeToMin     = 59;            // To   – minute (0-59)
```

---

## 5. Indicator Buffers

| Index | Variable | Plot type | Description |
|-------|----------|-----------|-------------|
| 0 | `g_vol` | `DRAW_COLOR_HISTOGRAM` | Volume bar heights |
| 1 | `g_col` | colour index | Histogram colour selector (0=bull, 1=bear, 2=spike-bull, 3=spike-bear) |
| 2 | `g_ma` | `DRAW_LINE` | Volume moving average |
| 3 | `g_thresh` | `DRAW_LINE` (dashed) | Spike threshold = MA + Multiplier × StdDev |
| 4 | `g_z` | `DRAW_LINE` (dotted) | Z-score scaled to MA units; hidden by default |

> Arrows and zones are chart objects (`OBJ_ARROW`, `OBJ_RECTANGLE`), not buffers. Object names are prefixed with `VolumeSpike_` for clean removal on deinit.

---

## 6. Alert Behaviour

### Once-per-candle guard
Alerts fire **at most once per candle**. A `datetime` global (`g_last_alert_bar`) records the open-time of the last bar that triggered an alert. Any subsequent tick on the same candle is suppressed, whether the bar is still open or has already closed.

### Time-of-day filter
When `InpTimeFilter = true`:

- **Alerts** are gated by `TimeCurrent()` (MT5 server time, not local time).
- **Arrows / zones** on intraday timeframes (< H4) are gated by the bar's open time.
- **Arrows / zones on H4 and above** bypass the filter entirely — a daily bar opens at 00:00 server time, so filtering by its open time is meaningless. All higher-TF spikes are always drawn; alerts on those timeframes are still filtered by wall-clock time.

Overnight ranges are supported (e.g. From `22:00` To `06:00`).

> **Time reference:** All times are **MT5 broker server time**. If your broker is UTC+2 and you want a 09:00 local (UTC+1) window, set `InpTimeFromHour = 8`.

---

## 7. Calculation Logic (Pseudocode)

```
min_bars = MAX(InpMAPeriod, InpPctPeriod) + 1

FOR each bar i FROM min_bars TO rates_total:

    vol = tick_volume[i]

    // Rolling statistics
    ma_vol  = MA(vol, i, InpMAPeriod, InpMAType)
    std_vol = PopulationStdDev(vol, i, InpMAPeriod)
    z_score = (vol - ma_vol) / std_vol   // 0 if std_vol ≈ 0

    // Spike detection
    SWITCH InpMethod:
        STDDEV:     is_spike = vol > ma_vol + InpMultiplier * std_vol
        ZSCORE:     is_spike = z_score > InpZThreshold
        PERCENTILE: is_spike = PercentileRank(vol, i, InpPctPeriod) > InpPctCutoff
        RVOL:       is_spike = vol / SessionAvg(i, InpRvolDays) > InpRvolThreshold

    // Populate sub-window buffers
    g_vol[i]    = vol
    g_col[i]    = spike ? (bullish ? 2 : 3) : (bullish ? 0 : 1)
    g_ma[i]     = ma_vol
    g_thresh[i] = ma_vol + InpMultiplier * std_vol
    g_z[i]      = InpShowZScore ? z_score * ma_vol : EMPTY_VALUE

    // Draw price-chart objects (intraday TF: filter by bar time; H4+: always draw)
    IF is_spike AND within_obj_history AND IsInTimeWindow(time[i]):
        IF InpShowArrows: DrawArrow(...)
        IF InpShowZones:  DrawZone(...)

    // Alert – once per candle, wall-clock time filter
    IF is_spike AND i == rates_total-1
       AND time[i] != g_last_alert_bar
       AND IsInTimeWindow(TimeCurrent()):
        g_last_alert_bar = time[i]
        TriggerAlert(vol, ma_vol, z_score)
```

---

## 8. Performance Notes

- `OnCalculate()` uses `prev_calculated` to skip already-processed bars — only the last bar is recalculated on each tick.
- `tick_volume[]` is copied to a local `double` array (`g_dvol`) once per call to avoid repeated casting in the inner loop.
- Chart objects are capped at the most recent 500 bars on first load (`MAX_OBJ_HIST`) to prevent lag on long histories.
- EMA/SMMA seed is computed once from the SMA of the first `InpMAPeriod` bars, not recalculated per tick.

---

## 9. File Structure

```
fx_tools/
└── Indicators/
    └── VolumeSpike/
        ├── VolumeSpike.mq5                 ← indicator source
        └── VolumeSpike_Indicator_Spec.md   ← this file
```

---

## 10. Acceptance Criteria

- [x] Compiles without warnings in MetaEditor 5
- [x] Sub-window shows colour-coded histogram, MA line, and threshold line
- [x] All 4 detection methods selectable via input dropdown
- [x] Spike arrows and zones drawn as chart objects on the price panel
- [x] Alert fires at most once per candle regardless of tick rate
- [x] Time-of-day filter correctly suppresses alerts and intraday arrows outside the window
- [x] H4/D1/W1/MN: arrows always drawn; alert still respects time window
- [x] Overnight time ranges (e.g. 22:00–06:00) handled correctly
- [ ] No performance degradation on 10-year M1 history
- [ ] Confirmed working on Forex, Indices, and Crypto instruments

---

## 11. Roadmap / Future Improvements

Items identified for future development, roughly in priority order.

### Polish & UX
- **Settings presets** — save/load input profiles per instrument or session (e.g. "Forex scalping", "Index daily")
- **RVOL visual feedback** — display the computed session-average volume on the sub-window so the user can see what the spike is being compared against
- **Cleaner arrow style** — explore custom bitmap arrows or larger Wingdings codes for a more premium look
- **On-chart info label** — small corner label showing current method, threshold, and last spike time

### Functionality
- **Multi-pair / multi-timeframe scanner panel** — a separate EA or indicator window listing all watched symbols and their spike status in real time; biggest differentiator for commercial value
- **Spike strength rating** — classify spikes as Weak / Medium / Strong based on how far above threshold they are, with colour coding to match
- **Consecutive spike detection** — flag when two or more consecutive bars are spikes (sustained volume surge)
- **Divergence signal** — alert when volume spikes but price barely moves (potential reversal setup)

### Commercial readiness
- **End-user guide** — trader-facing documentation separate from this spec; no code, just "how to use it"
- **Demo video / GIF** — short screen recording showing the indicator in action across different instruments
- **MQL5 Market listing** — product page copy, screenshots, and pricing strategy ($20–$50 range)
- **Performance test** — verify no lag on 10-year M1 history before publishing

---

*End of specification.*
