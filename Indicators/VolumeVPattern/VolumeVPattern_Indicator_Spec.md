# Volume V-Pattern Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 1.00  
**Status:** Active  
**Author:** Dercio Micas  
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation — V-pattern in the volume z-score |

---

## 1. Overview

A MetaTrader 5 custom indicator inspired by **VolumeSpike**, but signalling on a
different idea. VolumeSpike is *level*-based: it fires when volume is **high**
relative to its statistical norm. VolumeVPattern is *shape*-based: it fires when
the **volume z-score** traces a **V** across three consecutive bars — volume
drops into a short trough and then **rises sharply** back out.

The premise: a sharp rise in participation *immediately after a lull* marks the
moment conviction returns to the market — often closer to the actual entry
trigger than a bar that is merely high-volume.

The indicator runs in a **separate sub-window** (colour-coded volume histogram +
MA + scaled z-score line) and draws **buy/sell arrows** on the price chart.

---

## 2. Detection Logic

All detection happens on the **volume z-score** series:

```
ma   = MA(volume, InpZPeriod, InpMAType)
std  = PopulationStdDev(volume, InpZPeriod)
z    = (volume − ma) / std          // 0 when std ≈ 0
```

### 2.1 The V test

Using MT5 series indexing (`[0]` = current forming bar, `[1]` = last closed bar),
the indicator treats **C1 = `[1]`** as the *rise bar*, **C2 = `[2]`** as the
*trough*, and **C3 = `[3]`** as the *pre-drop* bar:

```
Signal when ALL hold:
   z[3] > z[2]                 drop into the trough  (C3 → C2 down)
   z[1] > z[2]                 rise out of the trough (C2 → C1 up)
   z[1] − z[2] >= InpSlope     the rise leg is steep enough
```

`z[3] > z[2]` and `z[1] > z[2]` together make **C2 a strict local minimum** —
the bottom of the V. `InpSlope` controls how aggressive the right-hand (rise) arm
must be.

```
  z-score

   z[3] ●                       ● z[1]   ← rise leg, slope = z[1]−z[2] ≥ InpSlope
         \                     /
          \                   /
           \                 /
            ● z[2]  (trough = strict local minimum)

   → arrow on C1, direction from C1's candle colour, enter at C0 open
```

### 2.2 Direction

Direction comes from **C1's candle colour**:

| C1 candle | Signal | Arrow |
|-----------|--------|-------|
| Bullish (`close ≥ open`) | **BUY** | below the bar (Wingdings 233) |
| Bearish (`close < open`) | **SELL** | above the bar (Wingdings 234) |

### 2.3 Timing / non-repainting

The V is only evaluated on **closed bars** — the marker is committed for bar `i`
only while `i < rates_total − 1`. The currently forming bar never receives an
arrow, so a signal cannot appear and then vanish intrabar. In practice the arrow
for C1 appears the moment C1 closes (i.e. when C0 opens), and the trader enters
at C0's open.

---

## 3. Input Parameters

```mql5
// ── Detection ───────────────────────────────────────────────────────
input int             InpZPeriod   = 20;          // Z-score MA period (bars)
input ENUM_MA_METHOD  InpMAType    = MODE_SMA;     // MA type (SMA/EMA/SMMA; WMA→SMA)
input double          InpSlope     = 2.0;          // Min rise-leg slope (z[1] − z[2])

// ── Price Chart ──────────────────────────────────────────────────────
input bool            InpShowArrows = true;        // Draw signal arrows
input color           InpBullColor  = clrDodgerBlue; // Buy (bullish C1) colour
input color           InpBearColor  = clrOrangeRed;  // Sell (bearish C1) colour
input int             InpArrowSize  = 1;           // Arrow size (1–5)

// ── Sub-Window ───────────────────────────────────────────────────────
input color           InpBarBull    = clrSteelBlue;  // Normal bull bar
input color           InpBarBear    = clrDimGray;     // Normal bear bar
input color           InpSigBull    = clrDodgerBlue;  // Signal bull bar (V + buy)
input color           InpSigBear    = clrOrangeRed;   // Signal bear bar (V + sell)
input bool            InpShowZScore = true;         // Show scaled z-score line

// ── Alerts ───────────────────────────────────────────────────────────
input bool            InpAlert            = true;   // Pop-up alert
input bool            InpPush             = false;  // Push notification
input bool            InpEmail            = false;  // Email alert
input bool            InpWhatsApp         = false;  // WhatsApp (Maytapi)
input string          InpMaytapiProductId = "";     // Maytapi product ID
input string          InpMaytapiPhoneId   = "";     // Maytapi phone ID
input string          InpMaytapiKey       = "";     // Maytapi API key
input string          InpWhatsAppTo       = "";     // Recipient (+XXXXXXXXXXX)

// ── Time Filter ──────────────────────────────────────────────────────
input bool            InpTimeFilter   = false;      // Enable time-of-day filter
input int             InpTimeFromHour = 9;          // From – hour   (0-23)
input int             InpTimeFromMin  = 0;          // From – minute (0-59)
input int             InpTimeToHour   = 23;         // To   – hour   (0-23)
input int             InpTimeToMin    = 59;         // To   – minute (0-59)
```

---

## 4. Indicator Buffers

| Index | Variable | Plot type | Description |
|-------|----------|-----------|-------------|
| 0 | `g_vol` | `DRAW_COLOR_HISTOGRAM` | Volume bar heights |
| 1 | `g_col` | colour index | 0=bull, 1=bear, 2=signal-bull, 3=signal-bear |
| 2 | `g_ma` | `DRAW_LINE` | Volume moving average |
| 3 | `g_zplot` | `DRAW_LINE` (dotted) | Volume z-score × MA (scaled to overlay) |

> 3 plots, 4 buffers (the colour histogram uses two buffers). Arrows are chart
> objects (`OBJ_ARROW`) prefixed `VolumeVPattern_`, not buffers. The raw z-score
> is also held in an internal `g_zsc[]` array so the V test can read `z[i-1]` and
> `z[i-2]` cheaply across calls.

---

## 5. Alert Behaviour

### Once-per-candle guard
Alerts fire **at most once per candle**. `g_last_alert_bar` records the open-time
of the C1 bar that last triggered; the alert is raised when C1 becomes the newest
closed bar (`i == rates_total − 2`).

### Time-of-day filter
When `InpTimeFilter = true`:
- **Alerts** are gated by `TimeCurrent()` (MT5 server time).
- **Arrows** on intraday timeframes (< H4) are gated by the bar's open time.
- **Arrows on H4 and above** bypass the filter (a daily bar opens at 00:00, so
  filtering by its open time is meaningless).

Overnight ranges (e.g. 22:00 → 06:00) are supported. All times are **MT5 broker
server time**.

### WhatsApp (Maytapi)
Identical mechanism to VolumeSpike: a POST to the Maytapi REST API on every
alert. `https://api.maytapi.com` must be whitelisted in **Tools → Options →
Expert Advisors → Allow WebRequest for listed URL**. If any of the four Maytapi
fields are empty, no request is made.

---

## 6. Calculation Logic (Pseudocode)

```
z_start  = InpZPeriod − 1          // first bar with a full z-score window
min_bars = InpZPeriod + 2          // +2 so z[i-1] and z[i-2] exist

FOR each bar i FROM z_start TO rates_total-1:

    vol  = tick_volume[i]
    ma   = MA(vol, i, InpZPeriod, InpMAType)
    std  = PopulationStdDev(vol, i, InpZPeriod)
    z    = (vol - ma) / std        // 0 if std ≈ 0
    g_zsc[i] = z

    // V-pattern: bar i is C1, i-1 is C2 (trough), i-2 is C3
    is_signal = (i >= z_start+2)
                AND g_zsc[i-2] > g_zsc[i-1]          // drop into trough
                AND z          > g_zsc[i-1]          // rise out of trough
                AND (z - g_zsc[i-1]) >= InpSlope     // rise leg steep enough

    closed = (i < rates_total-1)   // never commit on the forming bar
    fire   = is_signal AND closed

    // Sub-window
    g_vol[i]   = vol
    g_ma[i]    = ma
    g_zplot[i] = InpShowZScore ? z * ma : EMPTY_VALUE
    g_col[i]   = fire ? (bullish?2:3) : (bullish?0:1)

    // Arrow on C1
    IF fire AND within_obj_history AND IsInTimeWindow(time[i]) AND InpShowArrows:
        DrawArrow(time[i], bullish ? low[i] : high[i], bullish)

    // Alert – once per candle when C1 is the newest closed bar
    IF fire AND i == rates_total-2 AND time[i] != g_last_alert_bar
       AND IsInTimeWindow(TimeCurrent()):
        g_last_alert_bar = time[i]
        TriggerAlert(...)
```

---

## 7. Performance Notes

- `OnCalculate()` uses `prev_calculated` to skip processed bars; only new bars
  are recalculated per tick.
- `tick_volume[]` is copied once to `g_dvol[]`; raw z-scores cached in `g_zsc[]`
  so the V test reads neighbours without recomputation.
- EMA/SMMA seed is computed once from the SMA of the first `InpZPeriod` bars.
- Chart objects capped at the most recent `MAX_OBJ_HIST` (5000) bars on first load.

---

## 8. File Structure

```
fx_tools/
└── Indicators/
    └── VolumeVPattern/
        ├── VolumeVPattern.mq5                 ← indicator source
        └── VolumeVPattern_Indicator_Spec.md   ← this file
```

---

## 9. Acceptance Criteria

- [ ] Compiles without warnings in MetaEditor 5
- [ ] Sub-window shows colour-coded histogram, MA line, and (optional) z-score line
- [ ] Arrow appears on C1 only after C1 closes (no intrabar repaint)
- [ ] Buy arrow below a bullish C1; sell arrow above a bearish C1
- [ ] V test matches: `z[3] > z[2]`, `z[1] > z[2]`, `z[1] − z[2] ≥ InpSlope`
- [ ] Alert fires at most once per candle
- [ ] Time-of-day filter suppresses alerts and intraday arrows outside the window
- [ ] H4/D1/W1/MN: arrows always drawn; alert still respects time window
- [ ] No performance degradation on long M1 history

---

## 10. Relationship to VolumeSpike

| | VolumeSpike | VolumeVPattern |
|--|-------------|----------------|
| Signal basis | Volume **level** above norm (StdDev/Z/Pct/RVOL) | **V shape** in the volume z-score |
| Fires on | Any high-volume bar | Trough then sharp rise only |
| Direction | Candle colour of spike bar | Candle colour of C1 (rise bar) |
| Marker bar | Spike bar | C1 (rise bar), confirmed at close |
| Shared | Sub-window histogram, alerts/push/email, WhatsApp/Maytapi, time filter | same |

---

## 11. Roadmap / Future Improvements

- **Configurable trough width** — allow the dip to span more than one bar
  (variable-length floor) instead of the strict single-bar local minimum.
- **Rise-leg floor** — optional `z[1] ≥ floor` so the rise must reach a real
  level, not just be steep within below-average volume.
- **Drop-leg minimum** — require the `z[3] → z[2]` drop to exceed a threshold,
  not merely be negative.
- **Signal strength rating** — grade by how far the rise slope exceeds `InpSlope`.
- **MQL5 Market listing** — once validated across instruments.

---

*End of specification.*
