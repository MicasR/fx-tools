# Volume V-Pattern Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 1.01  
**Status:** Active  
**Author:** Dercio Micas  
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation — V-pattern in the volume z-score |
| 1.01 | 2026-06-08 | Selectable source line (`InpSource`); plot only that single line; rise leg expressed as a percentage (`InpRisePct`) so it is scale-independent across sources |

---

## 1. Overview

A MetaTrader 5 custom indicator inspired by **VolumeSpike**, but signalling on a
different idea. VolumeSpike is *level*-based: it fires when volume is **high**
relative to its statistical norm. VolumeVPattern is *shape*-based: it fires when
a chosen **volume-derived line** traces a **V** across three consecutive bars —
the line drops into a short trough and then **rises sharply** back out.

The trader chooses **one source line** (`InpSource`). That single line is the
only thing plotted in the sub-window (it auto-scales to its own range), and the V
is detected on it. This mirrors how the idea was found: by watching the dashed
`Threshold` line on VolumeSpike trace a V.

---

## 2. The Source Line (`InpSource`)

Exactly one line is computed, plotted, and tested. All four are derived from the
same rolling MA and population StdDev of volume over `InpZPeriod` bars:

| `InpSource` | Line | Formula | Units |
|-------------|------|---------|-------|
| **Threshold** *(default)* | the VolumeSpike dashed line | `MA + InpMultiplier × StdDev` | volume |
| Z-Score | per-bar extremity | `(Volume − MA) / StdDev` | σ |
| MA Volume | the average | `MA(Volume)` | volume |
| Volume | raw bars | `Volume` | volume |

Because only one line is drawn, the sub-window auto-scales to it — no unit
juggling, no scaling hacks. The line is plotted with `DRAW_COLOR_LINE` and tinted
at the signal bar (green = buy, red = sell by default).

---

## 3. Detection Logic

Let `s[]` be the chosen source series. Using MT5 series indexing (`[0]` = current
forming bar, `[1]` = last closed bar), the indicator treats **C1 = `[1]`** as the
*rise bar*, **C2 = `[2]`** as the *trough*, and **C3 = `[3]`** as the *pre-drop*:

```
Signal when ALL hold:
   s[3] > s[2]                          drop into the trough   (C3 → C2 down)
   s[1] > s[2]                          rise out of the trough (C2 → C1 up)
   (s[1] − s[2]) / |s[2]| >= InpRisePct rise leg steep enough  (percentage)
```

`s[3] > s[2]` and `s[1] > s[2]` together make **C2 a strict local minimum** — the
bottom of the V. The rise leg is measured as a **fraction of the trough's
magnitude**, so the *same* `InpRisePct` works regardless of which source line (and
its scale) is selected. `|s[2]|` is floored at `1e-10` to avoid division blow-ups
near zero.

```
  selected source line

   s[3] ●                       ● s[1]   ← rise leg ≥ InpRisePct
         \                     /
          \                   /
           ● s[2]  (trough = strict local minimum)

   → arrow on C1, direction from C1's candle colour, enter at C0 open
```

### 3.1 Direction

| C1 candle | Signal | Arrow | Line tint |
|-----------|--------|-------|-----------|
| Bullish (`close ≥ open`) | **BUY** | below the bar (Wingdings 233) | `InpSigBull` |
| Bearish (`close < open`) | **SELL** | above the bar (Wingdings 234) | `InpSigBear` |

### 3.2 Timing / non-repainting

The V is only evaluated on **closed bars** — a marker is committed for bar `i`
only while `i < rates_total − 1`. The forming bar never receives an arrow, so a
signal cannot appear and then vanish intrabar. The arrow for C1 appears the moment
C1 closes (i.e. when C0 opens); the trader enters at C0's open.

---

## 4. Input Parameters

```mql5
// ── Detection ───────────────────────────────────────────────────────
input ENUM_VSOURCE    InpSource     = VSRC_THRESHOLD; // Source line for the V
input int             InpZPeriod    = 20;             // MA / StdDev period (bars)
input ENUM_MA_METHOD  InpMAType     = MODE_SMA;       // MA type (SMA/EMA/SMMA; WMA→SMA)
input double          InpMultiplier = 2.0;            // StdDev multiplier (Threshold source)
input double          InpRisePct    = 0.20;           // Min rise leg (fraction, 0.20 = 20%)

// ── Price Chart ──────────────────────────────────────────────────────
input bool            InpShowArrows = true;           // Draw signal arrows
input color           InpBullColor  = clrDodgerBlue;  // Buy (bullish C1) colour
input color           InpBearColor  = clrOrangeRed;   // Sell (bearish C1) colour
input int             InpArrowSize  = 1;              // Arrow size (1–5)

// ── Sub-Window Line ──────────────────────────────────────────────────
input color           InpLineColor  = clrYellow;      // Source line colour
input color           InpSigBull    = clrLime;        // Signal highlight – buy
input color           InpSigBear    = clrRed;         // Signal highlight – sell

// ── Alerts ───────────────────────────────────────────────────────────
input bool            InpAlert            = true;     // Pop-up alert
input bool            InpPush             = false;    // Push notification
input bool            InpEmail            = false;    // Email alert
input bool            InpWhatsApp         = false;    // WhatsApp (Maytapi)
input string          InpMaytapiProductId = "";       // Maytapi product ID
input string          InpMaytapiPhoneId   = "";       // Maytapi phone ID
input string          InpMaytapiKey       = "";       // Maytapi API key
input string          InpWhatsAppTo       = "";       // Recipient (+XXXXXXXXXXX)

// ── Time Filter ──────────────────────────────────────────────────────
input bool            InpTimeFilter   = false;        // Enable time-of-day filter
input int             InpTimeFromHour = 9;            // From – hour   (0-23)
input int             InpTimeFromMin  = 0;            // From – minute (0-59)
input int             InpTimeToHour   = 23;           // To   – hour   (0-23)
input int             InpTimeToMin    = 59;           // To   – minute (0-59)
```

---

## 5. Indicator Buffers

| Index | Variable | Plot type | Description |
|-------|----------|-----------|-------------|
| 0 | `g_src` | `DRAW_COLOR_LINE` | The selected source line (also read back for the V test) |
| 1 | `g_srccol` | colour index | 0 = normal, 1 = signal-buy, 2 = signal-sell |

> 1 plot, 2 buffers. The source buffer doubles as detection storage — since
> indicator buffers persist across `OnCalculate` calls, the V test reads
> `g_src[i-1]` and `g_src[i-2]` directly. Arrows are chart objects (`OBJ_ARROW`)
> prefixed `VolumeVPattern_`, not buffers.

---

## 6. Alert Behaviour

### Once-per-candle guard
Alerts fire **at most once per candle**. `g_last_alert_bar` records the open-time
of the C1 bar that last triggered; the alert is raised when C1 becomes the newest
closed bar (`i == rates_total − 2`).

### Time-of-day filter
When `InpTimeFilter = true`:
- **Alerts** are gated by `TimeCurrent()` (MT5 server time).
- **Arrows** on intraday timeframes (< H4) are gated by the bar's open time.
- **Arrows on H4 and above** bypass the filter (a daily bar opens at 00:00).

Overnight ranges (e.g. 22:00 → 06:00) are supported. All times are **MT5 broker
server time**.

### WhatsApp (Maytapi)
Identical mechanism to VolumeSpike: a POST to the Maytapi REST API on every alert.
`https://api.maytapi.com` must be whitelisted in **Tools → Options → Expert
Advisors → Allow WebRequest for listed URL**. If any of the four Maytapi fields
are empty, no request is made.

---

## 7. Calculation Logic (Pseudocode)

```
z_start  = InpZPeriod − 1          // first bar with a full window
min_bars = InpZPeriod + 2          // +2 so s[i-1] and s[i-2] exist

FOR each bar i FROM z_start TO rates_total-1:

    vol = tick_volume[i]
    ma  = MA(vol, i, InpZPeriod, InpMAType)
    std = PopulationStdDev(vol, i, InpZPeriod)

    s = SELECT InpSource:
          THRESHOLD: ma + InpMultiplier*std
          ZSCORE:    (std>0) ? (vol-ma)/std : 0
          MA:        ma
          VOLUME:    vol
    g_src[i] = s

    // V-pattern: bar i is C1, i-1 is C2 (trough), i-2 is C3
    is_signal = false
    IF i >= z_start+2 AND g_src[i-2] > g_src[i-1] AND s > g_src[i-1]:
        rise_frac = (s - g_src[i-1]) / max(|g_src[i-1]|, 1e-10)
        is_signal = (rise_frac >= InpRisePct)

    closed = (i < rates_total-1)    // never commit on the forming bar
    fire   = is_signal AND closed

    g_srccol[i] = fire ? (bullish?1:2) : 0

    IF fire AND within_obj_history AND IsInTimeWindow(time[i]) AND InpShowArrows:
        DrawArrow(time[i], bullish ? low[i] : high[i], bullish)

    IF fire AND i == rates_total-2 AND time[i] != g_last_alert_bar
       AND IsInTimeWindow(TimeCurrent()):
        g_last_alert_bar = time[i]
        TriggerAlert(...)
```

---

## 8. Performance Notes

- `OnCalculate()` uses `prev_calculated` to skip processed bars.
- `tick_volume[]` is copied once to `g_dvol[]`; the source line is cached in the
  `g_src` buffer and read back for the V test without recomputation.
- EMA/SMMA seed is computed once; on incremental recalculation it is recovered via
  `RecoverMA()`.
- Chart objects capped at the most recent `MAX_OBJ_HIST` (5000) bars on first load.

---

## 9. File Structure

```
fx_tools/
└── Indicators/
    └── VolumeVPattern/
        ├── VolumeVPattern.mq5                 ← indicator source
        └── VolumeVPattern_Indicator_Spec.md   ← this file
```

---

## 10. Acceptance Criteria

- [ ] Compiles without warnings in MetaEditor 5
- [ ] Sub-window plots exactly one line — the selected source — and nothing else
- [ ] Switching `InpSource` changes both the plotted line and the detection series
- [ ] Line tints green/red at the C1 signal bar
- [ ] Arrow appears on C1 only after C1 closes (no intrabar repaint)
- [ ] Buy arrow below a bullish C1; sell arrow above a bearish C1
- [ ] V test matches: `s[3] > s[2]`, `s[1] > s[2]`, `(s[1]−s[2])/|s[2]| ≥ InpRisePct`
- [ ] Same `InpRisePct` behaves sensibly across all four sources
- [ ] Alert fires at most once per candle
- [ ] Time-of-day filter suppresses alerts and intraday arrows outside the window
- [ ] H4/D1/W1/MN: arrows always drawn; alert still respects time window

---

## 11. Relationship to VolumeSpike

| | VolumeSpike | VolumeVPattern |
|--|-------------|----------------|
| Signal basis | Volume **level** above norm | **V shape** on a chosen volume line |
| Fires on | Any high-volume bar | Trough then sharp rise only |
| Source line | fixed (volume histogram) | selectable: Threshold / Z-Score / MA / Volume |
| Direction | Candle colour of spike bar | Candle colour of C1 (rise bar) |
| Marker bar | Spike bar | C1 (rise bar), confirmed at close |
| Shared | — | alerts/push/email, WhatsApp/Maytapi, time filter |

---

## 12. Roadmap / Future Improvements

- **Configurable trough width** — let the dip span more than one bar (variable
  floor) instead of the strict single-bar local minimum.
- **Drop-leg minimum** — require the `s[3] → s[2]` drop to exceed a threshold.
- **Signal strength rating** — grade by how far `rise_frac` exceeds `InpRisePct`.
- **MQL5 Market listing** — once validated across instruments.

---

*End of specification.*
