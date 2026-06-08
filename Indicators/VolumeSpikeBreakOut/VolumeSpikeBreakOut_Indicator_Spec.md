# Volume Spike BreakOut Indicator — Technical Specification

**Project:** FX Tools — MT5 Custom Indicator  
**Version:** 1.01  
**Status:** Active  
**Author:** Dercio Micas  
**Last updated:** 2026-06-08

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.00 | 2026-06-08 | Initial implementation. Fork of VolumeVPattern. Adds a **trigger selector** (Spike or V-pattern) and replaces the immediate trigger-bar arrow with a **breakout-of-range entry**: the first of the next `InpBreakBars` closed bars to break the trigger bar's high/low decides the direction. Backtest-driven (see §11). |
| 1.01 | 2026-06-08 | **Default trigger changed to `V-pattern`** after 2.2-year validation (§11): on H1 it is positive net-of-cost in 6/6 segments and beats Spike. NB — on **H4 the Spike trigger is better**; keep the switch in mind per timeframe. |

---

## 1. Overview & Design Intent

VolumeSpikeBreakOut is a **fork of VolumeVPattern** (itself a fork of VolumeSpike).
Loaded with the same settings, all three produce an **identical sub-window** — same
colour-coded histogram, MA, threshold and z-score lines, driven by the same
`is_spike` logic and the same inputs — so they can be compared side by side.

The behavioural change addresses the **weakest part of the parent indicators: the
trade direction.** VolumeSpike and VolumeVPattern both infer direction from the
**candle colour** of the trigger bar — close to a coin flip on a spike/doji. This
indicator instead lets **price confirm direction** via a range breakout:

- **VolumeSpike** — acts on the trigger bar immediately (arrow on the spike bar).
- **VolumeVPattern** — acts on the trigger bar immediately (arrow on C1).
- **VolumeSpikeBreakOut** — *waits* for price to break the trigger bar's high or
  low, and takes the **breakout direction**.

> The threshold-style parameters (`InpMultiplier`, `InpZThreshold`, `InpPctCutoff`,
> `InpRvolThreshold`) still drive the histogram colouring and the threshold line
> exactly as in VolumeSpike. What they gate depends on the trigger:
> Spike → they define the spike; V-pattern → the V shape plus `InpRisePct` does.

---

## 2. The Trigger (two types, selectable)

`InpTrigger` selects what arms a setup on a closed bar **T**:

| `InpTrigger` | Condition on bar T | Notes |
|--------------|--------------------|-------|
| **Spike** *(default)* | `is_spike` — volume crosses the spike level for `InpMethod` | Identical to VolumeSpike's detection |
| **V-pattern** | the selected method's line traces a V (see §3) | Identical to VolumeVPattern's detection; uses `InpRisePct` |

`InpMethod` works exactly as in the parents — it selects both the histogram
colouring and (for the V-pattern trigger) the line `s[]` the V is detected on:

| `InpMethod` | `is_spike` (Spike trigger) | V line `s[]` (V-pattern trigger) |
|-------------|----------------------------|----------------------------------|
| StdDev | `vol > MA + Mult·StdDev` | z-score `(vol−MA)/std` |
| Z-Score | `z > InpZThreshold` | z-score `(vol−MA)/std` |
| Percentile | `rank > InpPctCutoff` | percentile rank (0–100) |
| RVOL | `rvol > InpRvolThreshold` | RVOL ratio `vol / session-avg` |
| **Threshold** *(default)* | `vol > MA + Mult·StdDev` | `MA + Mult·StdDev` (the dashed line) |

The V-pattern condition (when `InpTrigger = V-pattern`), MT5 series indexing
`[1]`=last closed bar = C1 (rise), `[2]`=C2 (trough), `[3]`=C3 (pre-drop):

```
   s[3] > s[2]                          drop into the trough
   s[1] > s[2]                          rise out of the trough (C2 strict local min)
   (s[1] − s[2]) / |s[2]| >= InpRisePct rise leg steep enough
```

---

## 3. Breakout Entry Logic (the signal change)

A trigger on closed bar **T** records its range `[low[T], high[T]]`. Over the next
**`InpBreakBars`** closed bars, the **first** bar to break the range decides:

```
For entry bar i (the first closed bar after T to break T's range):
   high[i] >= high[T]  AND  low[i] > low[T]   → BULL breakout  → up arrow on i
   low[i]  <= low[T]   AND  high[i] < high[T] → BEAR breakout  → down arrow on i

   high[i] >= high[T] AND low[i] <= low[T]    → STRADDLE → ambiguous, NO entry
   neither broken within InpBreakBars bars    → setup EXPIRES, no entry
```

Direction is the **breakout side**, decided by the market — not the candle colour.
This is the whole point of the indicator.

```
        trigger bar T (volume spike / V)
        ┌───────────┐  high[T] ─────────────────  ← break up  → BUY
        │           │
        │   range   │   …watch next InpBreakBars bars…
        │           │
        └───────────┘  low[T]  ─────────────────  ← break down → SELL
```

### 3.1 Resolution rule (non-repainting, recalculation-safe)
Entry detection is a **backward scan** from each closed bar `i`: find the most
recent trigger `T` in `[i−InpBreakBars, i−1]` whose range was **not** broken by any
bar strictly between `T` and `i`; if bar `i` breaks it (and is not a straddle),
bar `i` is the entry. This is stateless per bar and deterministic on closed bars,
so it never repaints and survives `prev_calculated` incremental recompute. At most
**one arrow per bar** (the most recent qualifying trigger wins).

### 3.2 Markers
- **Arrow** (`InpShowArrows`) on the **breakout bar**: Wingdings 233 below the bar
  for a bull breakout, 234 above for a bear breakout, coloured `InpBullColor` /
  `InpBearColor`.
- **Range box** (`InpShowZones`, on by default): a rectangle from `time[T]` to
  `time[i]` spanning `[low[T], high[T]]` — visualises the level that was broken.

### 3.3 Timing
Only **closed bars** are evaluated (`i < rates_total − 1`); the trigger bar and all
bars in the breakout window are closed. The arrow appears when the breakout bar
closes. (Backtests entered at that bar's break level — a stop order at the trigger
extreme — with the structural stop at the opposite extreme.)

---

## 4. Input Parameters

Superset of VolumeVPattern. **(new)** marks additions; `InpMethod` default changed
to `THRESHOLD` (the backtested method).

```mql5
// ── Detection ───────────────────────────────────────────────────────
input ENUM_BREAKOUT_TRIGGER InpTrigger    = TRIGGER_VPATTERN; // Spike | V-pattern   (default V; Spike better on H4)
input int                InpBreakBars      = 4;               // breakout window, bars  (new)
input ENUM_DETECT_METHOD InpMethod         = METHOD_THRESHOLD;// default changed to Threshold
input int                InpMAPeriod       = 20;
input ENUM_MA_METHOD     InpMAType         = MODE_SMA;
input double             InpMultiplier     = 2.0;
input double             InpZThreshold     = 2.5;
input int                InpPctPeriod      = 100;
input double             InpPctCutoff      = 95.0;
input int                InpRvolDays       = 10;
input double             InpRvolThreshold  = 2.0;
input double             InpRisePct        = 0.02;            // only if InpTrigger = V-pattern

// ── Price Chart ──────────────────────────────────────────────────────
input bool   InpShowArrows = true;   input bool  InpShowZones = true;  // box ON by default
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

## 5. Indicator Buffers — IDENTICAL to VolumeSpike / VolumeVPattern

| Index | Variable | Plot type | Description |
|-------|----------|-----------|-------------|
| 0 | `g_vol` | `DRAW_COLOR_HISTOGRAM` | Volume bar heights |
| 1 | `g_col` | colour index | 0=bull, 1=bear, 2=spike-bull, 3=spike-bear |
| 2 | `g_ma` | `DRAW_LINE` | Volume moving average |
| 3 | `g_thresh` | `DRAW_LINE` (dashed) | `MA + Multiplier × StdDev` |
| 4 | `g_z` | `DRAW_LINE` (dotted) | Z-score × MA (hidden unless `InpShowZScore`) |

> 4 plots, 5 buffers — same as the parents, so the sub-window renders identically.
> Internally `g_sig[]` caches the selected line (for the V test) and `g_trig[]`
> caches the per-bar trigger flag so the breakout scan can read earlier triggers
> across calls. Arrows/boxes are chart objects prefixed `VolumeSpikeBreakOut_`.

---

## 6. Alert Behaviour

Same mechanics as the parents (pop-up / push / email / WhatsApp-Maytapi, once per
candle via `g_last_alert_bar`, time-of-day filter with overnight support, H4+
bypasses the intraday window). The alert fires on the **breakout entry** when the
breakout bar becomes the newest closed bar (`i == rates_total − 2`), and reports the
direction, trigger type, broken level, and how many bars the breakout took.

---

## 7. Calculation Logic (Pseudocode)

```
min_bars = MAX(InpMAPeriod, InpPctPeriod) + 1

FOR each bar i FROM min_bars-1 TO rates_total-1:

    // ── identical sub-window maths to VolumeSpike ──
    vol, ma, std, z, thresh, rank, rvol = … (as VolumeSpike)
    is_spike = method-specific level cross
    g_vol/g_ma/g_thresh/g_z/g_col[i] = … (as VolumeSpike)
    s = method line (THRESHOLD→thresh, PCT→rank, RVOL→rvol, else z); g_sig[i]=s

    // ── trigger ──
    v_signal = (i>=min_bars+1) AND s[i-2]>s[i-1] AND s>s[i-1]
               AND (s-s[i-1])/max(|s[i-1]|,1e-10) >= InpRisePct
    trig = (InpTrigger==V_PATTERN) ? v_signal : is_spike
    g_trig[i] = trig ? 1 : 0

    // ── breakout entry on closed bar i ──
    IF i < rates_total-1 AND InpBreakBars>0:
        FOR back = 1 .. MIN(InpBreakBars, i-1):
            T = i - back
            IF g_trig[T] == 0: continue
            IF any bar in (T, i) broke [low[T], high[T]]: continue   // already resolved
            up = high[i] >= high[T];  dn = low[i] <= low[T]
            IF up AND dn: continue          // straddle, ambiguous
            IF NOT up AND NOT dn: continue  // i didn't break this pending trigger
            // ENTRY on bar i, direction = up ? BUY : SELL
            IF within_obj_history AND IsInTimeWindow(time[i]):
                DrawArrow(time[i], up?low[i]:high[i], up)
                DrawZone (time[T], high[T], time[i], low[T])
            IF i == rates_total-2 AND new bar AND IsInTimeWindow(now):
                TriggerAlert(up, level, back, vol)
            BREAK   // one entry per bar
```

---

## 8. Performance Notes

- `OnCalculate()` uses `prev_calculated` to skip processed bars.
- `tick_volume[]` copied to `g_dvol[]`; the line cached in `g_sig[]`; triggers in
  `g_trig[]` so the backward breakout scan is O(`InpBreakBars²`) per bar.
- EMA/SMMA seed computed once; reseeded from `g_ma[]` on incremental calls.
- Chart objects capped at the most recent `MAX_OBJ_HIST` (5000) bars on first load.

---

## 9. File Structure

```
fx_tools/
└── Indicators/
    └── VolumeSpikeBreakOut/
        ├── VolumeSpikeBreakOut.mq5                 ← indicator source
        └── VolumeSpikeBreakOut_Indicator_Spec.md   ← this file
```

---

## 10. Acceptance Criteria

- [ ] Compiles without warnings in MetaEditor 5
- [ ] Sub-window is identical to VolumeSpike with the same settings
- [ ] `InpTrigger` switches the setup between Spike and V-pattern
- [ ] Arrow appears on the **breakout** bar, not the trigger bar
- [ ] Bull arrow on an up-break, bear arrow on a down-break (direction = price, not candle)
- [ ] Straddle bars produce no entry; setups expire after `InpBreakBars` bars
- [ ] No intrabar repaint — entries only on closed bars, stable across recompute
- [ ] Range box (when enabled) spans the trigger bar's high/low to the breakout bar
- [ ] Alert fires at most once per candle, on the breakout bar
- [ ] Time-of-day filter and H4+ bypass behave as in the parents

---

## 11. Backtest Basis (why this exists)

Python harness `backtest/` on XAUUSDc, threshold method, 1:3 target, judged on the
structural bracket (stop = trigger-bar extreme), **net of a $0.40 round-trip cost**.

**Why breakout entry:** the parents infer direction from C1's candle colour, which
went **negative in the adverse regime**. Breakout entry (window = 4 bars) flips it
positive and beats candle direction on every metric — direction confirmed by price.
The breakout stop is the spike bar's opposite extreme (a wide, high-range bar), so
spread is <2% of risk; the edge is robust to costs (avg R barely moves to $1.50/RT).

**2.2-year validation** (XAUUSDc, 2024-03 → 2026-06, full cached history):

| Timeframe | V-pattern (full avgR / consistency) | Spike (full avgR / consistency) | Best |
|-----------|-------------------------------------|---------------------------------|------|
| **H1** | **+0.219**, PF 1.33, **6/6 segments** | +0.179, PF 1.27, 5/6 | **V-pattern** |
| M15 | +0.053, PF 1.07, 6/8 | +0.082, PF 1.12, 5/8 | both thin |
| H4 | +0.048, PF 1.07, 3/5 | **+0.291**, PF 1.48, 3/5 | **Spike** |

- The V-pattern edge is **strongest on H1** (positive every sub-period) → the default.
- On **H4 prefer the Spike trigger**; on **M15 both are marginal** (PF ≈ 1, costs bite
  more on small-range bars). The trigger switch exists for exactly this reason.
- The long-run edge (avg R ≈ 0.2 on H1) is **more modest than the recent 5-month
  window** (≈ 0.4) suggested — that window was an unusually strong gold regime.

> Caveat: still one symbol, gross of swap/financing for multi-day holds. Validated
> across period and timeframe; not yet across symbols.

---

## 12. Roadmap / Future Improvements

- **Trend/regime filter** — only take breakouts aligned with a higher-TF bias.
- **Volatility-scaled break window** — adapt `InpBreakBars` to ATR/session.
- **Retest entry** — optional entry on a pullback to the broken level.
- **Multi-symbol / multi-regime validation** before fixing the default trigger.

---

*End of specification.*
