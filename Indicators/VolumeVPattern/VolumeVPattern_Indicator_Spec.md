# Volume V-Pattern Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 2.01  
**Status:** Active  
**Author:** Dercio Micas  
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation — V-pattern in the volume z-score |
| 1.01 | 2026-06-08 | Selectable source line; plotted only that single line; rise leg as a percentage |
| 2.00 | 2026-06-08 | **Re-forked from VolumeSpike.** Sub-window analytics now IDENTICAL to VolumeSpike (same histogram, MA, threshold, z-score lines and inputs). The ONLY change vs VolumeSpike is the price-chart signal: arrows/zones fire on a V-pattern in the selected method's line instead of a level cross. Added `METHOD_THRESHOLD` and `InpRisePct`. |
| 2.01 | 2026-06-08 | Default `InpRisePct` lowered to `0.02` (2%). Live testing showed the fork beats VolumeSpike — closer to the optimal entry zone and catches setups the original missed. |

---

## 1. Overview & Design Intent

VolumeVPattern is a **fork of VolumeSpike** built for direct, apples-to-apples
comparison. Loaded with the same settings, the two indicators produce an
**identical sub-window** — same colour-coded histogram, same MA, threshold and
z-score lines, all driven by the same `is_spike` logic and the same inputs.

The **only behavioural difference** is how the price-chart signal is produced:

- **VolumeSpike** marks a bar when volume **crosses a level** (StdDev / Z / Pct / RVOL threshold).
- **VolumeVPattern** marks a bar when the **selected method's line traces a V** —
  a drop into a trough followed by a sharp rise out.

This means a trader can run both indicators side by side and the *only* visible
difference on the chart is **where the arrows appear**.

> **Note:** the threshold-style parameters (`InpMultiplier`, `InpZThreshold`,
> `InpPctCutoff`, `InpRvolThreshold`) still drive the histogram colouring and the
> threshold line exactly as in VolumeSpike, but they **no longer gate the signal**
> — the V shape plus `InpRisePct` decides that now.

---

## 2. The Source Line per Method

`InpMethod` selects both the histogram colouring (as in VolumeSpike) **and** which
continuous line the V is detected on:

| `InpMethod` | Histogram `is_spike` (unchanged) | V line `s[]` |
|-------------|----------------------------------|--------------|
| StdDev | `vol > MA + Mult·StdDev` | z-score `(vol−MA)/std` |
| Z-Score | `z > InpZThreshold` | z-score `(vol−MA)/std` |
| Percentile | `rank > InpPctCutoff` | percentile rank (0–100) |
| RVOL | `rvol > InpRvolThreshold` | RVOL ratio `vol / session-avg` |
| **Threshold** *(new)* | `vol > MA + Mult·StdDev` (same as StdDev) | `MA + Mult·StdDev` (the dashed line) |

StdDev and Z-Score share the same z-score line, so their V signals are identical
(they differ only in how VolumeSpike's histogram is coloured).

---

## 3. Detection Logic (the signal change)

Let `s[]` be the chosen method's line. Using MT5 series indexing (`[0]` = current
forming bar, `[1]` = last closed bar), **C1 = `[1]`** is the *rise bar*,
**C2 = `[2]`** the *trough*, **C3 = `[3]`** the *pre-drop*:

```
Signal when ALL hold:
   s[3] > s[2]                          drop into the trough   (C3 → C2 down)
   s[1] > s[2]                          rise out of the trough (C2 → C1 up)
   (s[1] − s[2]) / |s[2]| >= InpRisePct rise leg steep enough  (percentage)
```

`s[3] > s[2]` and `s[1] > s[2]` make **C2 a strict local minimum**. The rise leg
is a **fraction of the trough's magnitude**, so the same `InpRisePct` works across
all method lines regardless of scale. `|s[2]|` is floored at `1e-10`.

```
  selected method's line

   s[3] ●                       ● s[1]   ← rise leg ≥ InpRisePct
         \                     /
          \                   /
           ● s[2]  (trough = strict local minimum)

   → arrow/zone on C1, direction from C1's candle colour, enter at C0 open
```

### 3.1 Direction & markers
Direction comes from **C1's candle colour** — bullish (`close ≥ open`) → **BUY**
arrow below the bar (Wingdings 233); bearish → **SELL** arrow above (234). Zones
(when `InpShowZones`) span C1's high–low. Both arrows and zones are now V-driven
(VolumeSpike drew them on the spike bar).

### 3.2 Timing / non-repainting
The V is evaluated on **closed bars** only — a marker is committed for bar `i`
only while `i < rates_total − 1`. The arrow for C1 appears the moment C1 closes
(when C0 opens); the trader enters at C0's open.

---

## 4. Input Parameters

Identical to VolumeSpike **except** the additions marked **(new)**.

```mql5
// ── Detection ───────────────────────────────────────────────────────
input ENUM_DETECT_METHOD InpMethod     = METHOD_STDDEV; // incl. METHOD_THRESHOLD (new)
input int                InpMAPeriod   = 20;
input ENUM_MA_METHOD     InpMAType     = MODE_SMA;
input double             InpMultiplier = 2.0;
input double             InpZThreshold = 2.5;
input int                InpPctPeriod  = 100;
input double             InpPctCutoff  = 95.0;
input int                InpRvolDays   = 10;
input double             InpRvolThreshold = 2.0;
input double             InpRisePct    = 0.02;           // V rise leg, fraction (new; 0.02 = 2%)

// ── Price Chart ──────────────────────────────────────────────────────
input bool   InpShowArrows = true;   input bool  InpShowZones = false;
input color  InpBullColor  = clrDodgerBlue; input color InpBearColor = clrOrangeRed;
input color  InpZoneColor  = clrGold;       input int   InpArrowSize = 1;

// ── Sub-Window ───────────────────────────────────────────────────────
input color  InpBarBull = clrSteelBlue;  input color InpBarBear   = clrDimGray;
input color  InpSpikeBull = clrDodgerBlue; input color InpSpikeBear = clrOrangeRed;
input bool   InpShowZScore = false;

// ── Alerts ──── (InpAlert, InpPush, InpEmail, InpWhatsApp + Maytapi fields) ──
// ── Time Filter ──── (InpTimeFilter, From/To hour/min) ──
```

---

## 5. Indicator Buffers — IDENTICAL to VolumeSpike

| Index | Variable | Plot type | Description |
|-------|----------|-----------|-------------|
| 0 | `g_vol` | `DRAW_COLOR_HISTOGRAM` | Volume bar heights |
| 1 | `g_col` | colour index | 0=bull, 1=bear, 2=spike-bull, 3=spike-bear |
| 2 | `g_ma` | `DRAW_LINE` | Volume moving average |
| 3 | `g_thresh` | `DRAW_LINE` (dashed) | `MA + Multiplier × StdDev` |
| 4 | `g_z` | `DRAW_LINE` (dotted) | Z-score × MA (hidden unless `InpShowZScore`) |

> 4 plots, 5 buffers — same as VolumeSpike, so the sub-window renders identically.
> Internally, `g_sig[]` holds the selected method's line so the V test can read
> `s[i-1]` / `s[i-2]` across calls. Arrows/zones are chart objects prefixed
> `VolumeVPattern_`.

---

## 6. Alert Behaviour

Same mechanics as VolumeSpike (pop-up / push / email / WhatsApp-Maytapi, once per
candle via `g_last_alert_bar`, time-of-day filter with overnight support, H4+
arrows bypass the intraday window). The only difference: the alert fires on the
**V signal** when C1 becomes the newest closed bar (`i == rates_total − 2`),
rather than on a spike.

---

## 7. Calculation Logic (Pseudocode)

```
min_bars = MAX(InpMAPeriod, InpPctPeriod) + 1

FOR each bar i FROM min_bars-1 TO rates_total-1:

    vol    = tick_volume[i]
    ma     = MA(vol, i, InpMAPeriod, InpMAType)
    std    = PopulationStdDev(vol, i, InpMAPeriod)
    z      = (std>0) ? (vol-ma)/std : 0
    thresh = ma + InpMultiplier*std
    rank   = PercentileRank(vol, i, InpPctPeriod)     // if Percentile
    rvol   = vol / SessionAvg(i, InpRvolDays)          // if RVOL

    // Histogram colour – IDENTICAL to VolumeSpike
    is_spike = SELECT InpMethod:
        ZSCORE: z>InpZThreshold; PERCENTILE: rank>InpPctCutoff;
        RVOL: rvol>InpRvolThreshold; else: vol>thresh
    g_vol[i]=vol; g_ma[i]=ma; g_thresh[i]=thresh
    g_z[i]= InpShowZScore ? z*ma : EMPTY_VALUE
    g_col[i]= is_spike ? (bullish?2:3) : (bullish?0:1)

    // V line for the selected method
    s = SELECT InpMethod: PERCENTILE:rank; RVOL:rvol; THRESHOLD:thresh; else:z
    g_sig[i] = s

    // V-pattern: bar i is C1, i-1 is C2 (trough), i-2 is C3
    v_signal = false
    IF i >= min_bars+1 AND g_sig[i-2] > g_sig[i-1] AND s > g_sig[i-1]:
        rise_frac = (s - g_sig[i-1]) / max(|g_sig[i-1]|, 1e-10)
        v_signal  = (rise_frac >= InpRisePct)

    fire = v_signal AND (i < rates_total-1)   // closed bars only

    IF fire AND within_obj_history AND IsInTimeWindow(time[i]):
        IF InpShowArrows: DrawArrow(time[i], bullish?low[i]:high[i], bullish)
        IF InpShowZones:  DrawZone(time[i], high[i], low[i])

    IF fire AND i == rates_total-2 AND time[i] != g_last_alert_bar
       AND IsInTimeWindow(TimeCurrent()):
        g_last_alert_bar = time[i]; TriggerAlert(...)
```

---

## 8. Performance Notes

- `OnCalculate()` uses `prev_calculated` to skip processed bars.
- `tick_volume[]` copied once to `g_dvol[]`; the selected line cached in `g_sig[]`.
- EMA/SMMA seed computed once; reseeded from `g_ma[]` on incremental calls.
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
- [ ] Sub-window is pixel-identical to VolumeSpike with the same settings
- [ ] All 5 methods selectable (StdDev, Z-Score, Percentile, RVOL, Threshold)
- [ ] Only the price-chart arrows/zones differ from VolumeSpike (V vs level cross)
- [ ] V test matches: `s[3] > s[2]`, `s[1] > s[2]`, `(s[1]−s[2])/|s[2]| ≥ InpRisePct`
- [ ] Arrow on C1 only after C1 closes (no intrabar repaint)
- [ ] Buy arrow below a bullish C1; sell arrow above a bearish C1
- [ ] Alert fires at most once per candle
- [ ] Time-of-day filter and H4+ bypass behave as in VolumeSpike

---

## 11. Comparison Workflow (intended use)

1. Open the same chart twice (or attach both indicators).
2. Attach **VolumeSpike** and **VolumeVPattern** with **identical** detection
   settings (`InpMethod`, `InpMAPeriod`, multipliers, etc.).
3. The volume sub-windows should look the same; compare **only the arrows**.
4. Tune `InpRisePct` on the fork; evaluate which signal set performs better.

---

## 12. Roadmap / Future Improvements

- **Configurable trough width** — let the dip span more than one bar.
- **Drop-leg minimum** — require the `s[3] → s[2]` drop to exceed a threshold.
- **Signal strength rating** — grade by how far `rise_frac` exceeds `InpRisePct`.
- **WMA support** — VolumeSpike currently falls back to SMA for WMA; carry over.

---

*End of specification.*
