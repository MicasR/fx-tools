//+------------------------------------------------------------------+
//| GT_XAU_H1_don55_Signals.mq5 — where the GymTeam king would trade        |
//| Leg: XAU_H1_don55  ·  module: SIG_DONCHIAN  ·  entry TF: PERIOD_H1                |
//| Donchian-55 break: H1 close beyond the prior 55-bar extreme (fresh edge, either side)
//| Defaults = the live preset (presets/XAU_H1_don55.set). Attach to the    |
//| leg's chart on its entry TF. Docs: XAU_H1_don55_Signals.md              |
//| Engine: GT_Signals_Core.mqh (shared bar-level sim of the EA's     |
//| EntryCadence: trigger -> 4-bar OCO breakout -> -1R SL / +TpR TP). |
//+------------------------------------------------------------------+
#property copyright   "Dercio Micas"
#property version     "1.00"
#property description "XAU_H1_don55: Donchian-55 break: H1 close beyond the prior 55-bar extreme (fresh edge, either side)"
#property indicator_chart_window
#property indicator_buffers 8
#property indicator_plots   8
#property indicator_label1  "trigger"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrSilver
#property indicator_width1  1
#property indicator_label2  "armed buy-stop"
#property indicator_type2   DRAW_LINE
#property indicator_style2  STYLE_DOT
#property indicator_color2  clrCornflowerBlue
#property indicator_label3  "armed sell-stop"
#property indicator_type3   DRAW_LINE
#property indicator_style3  STYLE_DOT
#property indicator_color3  clrTomato
#property indicator_label4  "long entry"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrLime
#property indicator_width4  2
#property indicator_label5  "short entry"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrRed
#property indicator_width5  2
#property indicator_label6  "op SL (-1R)"
#property indicator_type6   DRAW_LINE
#property indicator_color6  clrCrimson
#property indicator_label7  "op TP (+TpR*R)"
#property indicator_type7   DRAW_LINE
#property indicator_color7  clrMediumSeaGreen
#property indicator_label8  "exit"
#property indicator_type8   DRAW_ARROW
#property indicator_color8  clrWhite

enum ENUM_GT_SIGNAL  { SIG_VPATTERN = 0, SIG_NR7 = 1, SIG_INSIDE = 2,
                       SIG_NR7_OR_INSIDE = 3, SIG_WARMHOURS = 4,
                       SIG_KELTNER = 5, SIG_ENGULF = 6,
                       SIG_DONCHIAN = 7, SIG_MA_ALIGN = 8 };

input string             InpLegName    = "XAU_H1_don55";     // Leg (stats panel label)
input ENUM_GT_SIGNAL     InpSignal     = SIG_DONCHIAN;       // Signal module (preset)
input ENUM_TIMEFRAMES    InpEntryTF    = PERIOD_H1;        // Preset entry TF (chart should match)
input int                InpBreakBars  = 4;            // Breakout OCO window (bars)
input int                InpMaxHoldBars = 240;         // Max op hold (bars; 0 = off)
input double             InpTpR        = 3.0;       // Fixed TP in R (0 = none)
input int                InpNRWindow   = 7;            // NR window (SIG_NR7*)
input int                InpMAPeriod   = 20;           // V-pattern: volume MA period
input double             InpMultiplier = 2.0;          // V-pattern: threshold multiplier
input double             InpRisePct    = 0.02;         // V-pattern: V rise leg
input string             InpWHHours    = "12,13,14,15,16"; // warm+hours: allowed hours
input double             InpWHLo       = 80.0;         // warm+hours: vol pct >
input double             InpWHHi       = 98.0;         // warm+hours: vol pct <=
input int                InpWHPctWin   = 100;          // warm+hours: percentile window
input int                InpKelP       = 20;           // Keltner: EMA period
input double             InpKelMult    = 2.0;          // Keltner: ATR multiple
input int                InpATRP       = 14;           // ATR period (Keltner / ma_align)
input int                InpDonP       = 55;           // Donchian lookback
input int                InpAlignFast  = 10;           // ma_align: fast SMA
input int                InpAlignSlow  = 50;           // ma_align: slow SMA
input double             InpAlignImp   = 1.2;          // ma_align: impulse rng > x*ATR
input bool               InpShowStats  = true;         // Show the on-chart stats panel

#include "GT_Signals_Core.mqh"
