//+------------------------------------------------------------------+
//|                                                 VolumeSpike.mq5  |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Statistical volume anomaly detection for MetaTrader 5.          |
//|  Sub-window : colour-coded histogram + MA + threshold line.      |
//|  Price chart: spike arrows and optional highlight zones.         |
//|                                                                   |
//|  Detection methods:                                              |
//|    0 – MA + Standard Deviation  (default, recommended)          |
//|    1 – Z-Score Normalisation                                     |
//|    2 – Percentile Rank                                           |
//|    3 – Relative Volume / RVOL  (session-aware)                  |
//+------------------------------------------------------------------+
#property copyright    "Dercio Micas"
#property version      "1.00"
#property description  "Volume Spike – four detection methods: StdDev · Z-Score · Percentile · RVOL"
#property indicator_separate_window
#property indicator_buffers  5
#property indicator_plots    4

//--- Plot 0: colour-coded volume histogram (occupies buffer index 0 + 1)
#property indicator_label1   "Volume"
#property indicator_type1    DRAW_COLOR_HISTOGRAM
#property indicator_color1   clrSteelBlue, clrDimGray, clrDodgerBlue, clrOrangeRed
#property indicator_style1   STYLE_SOLID
#property indicator_width1   1

//--- Plot 1: volume moving average
#property indicator_label2   "MA Volume"
#property indicator_type2    DRAW_LINE
#property indicator_color2   clrWhite
#property indicator_style2   STYLE_SOLID
#property indicator_width2   2

//--- Plot 2: spike threshold line
#property indicator_label3   "Threshold"
#property indicator_type3    DRAW_LINE
#property indicator_color3   clrYellow
#property indicator_style3   STYLE_DASH
#property indicator_width3   1

//--- Plot 3: Z-score scaled to MA units (optional – hidden by default)
#property indicator_label4   "Z-Score (scaled)"
#property indicator_type4    DRAW_LINE
#property indicator_color4   clrAqua
#property indicator_style4   STYLE_DOT
#property indicator_width4   1

//+------------------------------------------------------------------+
//| Enumeration                                                      |
//+------------------------------------------------------------------+
enum ENUM_DETECT_METHOD
{
   METHOD_STDDEV     = 0,   //  MA + Standard Deviation  (recommended)
   METHOD_ZSCORE     = 1,   //  Z-Score Normalisation
   METHOD_PERCENTILE = 2,   //  Percentile Rank
   METHOD_RVOL       = 3    //  Relative Volume – session-aware
};

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group              "── Detection ──────────────────────────────";
input ENUM_DETECT_METHOD InpMethod        = METHOD_STDDEV;  // Detection method
input int                InpMAPeriod      = 20;             // MA period (bars)
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;       // MA type
input double             InpMultiplier    = 2.0;            // Std Dev multiplier
input double             InpZThreshold    = 2.5;            // Z-score threshold
input int                InpPctPeriod     = 100;            // Percentile lookback (bars)
input double             InpPctCutoff     = 95.0;           // Percentile cutoff  (%)
input int                InpRvolDays      = 10;             // RVOL history (days)
input double             InpRvolThreshold = 2.0;            // RVOL multiplier

input group              "── Price Chart ─────────────────────────────";
input bool               InpShowArrows    = true;           // Draw spike arrows
input bool               InpShowZones     = false;          // Draw highlight zones
input color              InpBullColor     = clrDodgerBlue;  // Bullish spike colour
input color              InpBearColor     = clrOrangeRed;   // Bearish spike colour
input color              InpZoneColor     = clrGold;        // Zone fill colour
input int                InpArrowSize     = 2;              // Arrow size  (1–5)

input group              "── Sub-Window ──────────────────────────────";
input color              InpBarBull       = clrSteelBlue;   // Normal bull bar
input color              InpBarBear       = clrDimGray;     // Normal bear bar
input color              InpSpikeBull     = clrDodgerBlue;  // Spike bull bar
input color              InpSpikeBear     = clrOrangeRed;   // Spike bear bar
input bool               InpShowZScore    = false;          // Show Z-score line

input group              "── Alerts ──────────────────────────────────";
input bool               InpAlert         = true;           // Pop-up alert
input bool               InpPush          = false;          // Push notification
input bool               InpEmail         = false;          // Email alert

//+------------------------------------------------------------------+
//| Indicator buffers                                                |
//+------------------------------------------------------------------+
double g_vol[];       // [0] histogram bar height
double g_col[];       // [1] histogram colour index  (0=bull, 1=bear, 2=spike-bull, 3=spike-bear)
double g_ma[];        // [2] MA line
double g_thresh[];    // [3] threshold  =  MA + Multiplier × StdDev
double g_z[];         // [4] Z-score × MA  (scaled to be visible in the same window)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define OBJ_PFX       "VolumeSpike_"
#define MAX_OBJ_HIST  500     // max past bars to materialise chart objects on first load

double   g_dvol[];          // double copy of tick_volume[], rebuilt each call
int      g_min_bars;        // minimum bars required before calculation starts
datetime g_last_alert_bar;  // open-time of the last bar that fired an alert

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_min_bars = MathMax(InpMAPeriod, InpPctPeriod) + 1;

   //--- bind buffers
   SetIndexBuffer(0, g_vol,    INDICATOR_DATA);
   SetIndexBuffer(1, g_col,    INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2, g_ma,     INDICATOR_DATA);
   SetIndexBuffer(3, g_thresh, INDICATOR_DATA);
   SetIndexBuffer(4, g_z,      INDICATOR_DATA);

   //--- histogram colour palette  (indices 0-3 map to the four colours)
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, InpBarBull);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 1, InpBarBear);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 2, InpSpikeBull);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 3, InpSpikeBear);
   PlotIndexSetDouble (0, PLOT_EMPTY_VALUE, 0.0);

   //--- hide Z-score line unless explicitly enabled
   if(!InpShowZScore)
      PlotIndexSetInteger(3, PLOT_DRAW_TYPE, DRAW_NONE);

   //--- sub-window label
   string meth[] = {"StdDev", "Z-Score", "Pct", "RVOL"};
   IndicatorSetString(INDICATOR_SHORTNAME,
      "VolumeSpike[" + meth[InpMethod] + "," + (string)InpMAPeriod + "]");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DeleteAllObjects();
   ArrayFree(g_dvol);
}

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
//+------------------------------------------------------------------+
int OnCalculate(const int      rates_total,
                const int      prev_calculated,
                const datetime &time[],
                const double   &open[],
                const double   &high[],
                const double   &low[],
                const double   &close[],
                const long     &tick_volume[],
                const long     &volume[],
                const int      &spread[])
{
   if(rates_total < g_min_bars)
      return 0;

   //--- keep g_dvol in sync with tick_volume
   if(ArraySize(g_dvol) < rates_total)
      ArrayResize(g_dvol, rates_total);

   int update_from = (prev_calculated <= 0) ? 0 : MathMax(0, prev_calculated - 1);
   for(int j = update_from; j < rates_total; j++)
      g_dvol[j] = (double)tick_volume[j];

   //--- on full recalculation remove stale chart objects
   if(prev_calculated <= 0)
      DeleteAllObjects();

   int start = (prev_calculated <= 0) ? g_min_bars - 1 : prev_calculated - 1;

   //--- initialise exponential-style MA seed
   double ema_prev = 0.0;
   if(InpMAType == MODE_EMA || InpMAType == MODE_SMMA)
   {
      if(prev_calculated <= 0)
      {
         // seed = SMA of the first InpMAPeriod bars ending at `start`
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++)
            seed += g_dvol[start - k];
         ema_prev = seed / InpMAPeriod;
      }
      else
         ema_prev = g_ma[start - 1];
   }

   const double ema_k  = 2.0 / (InpMAPeriod + 1.0);   // EMA smoothing factor
   const double smma_k = 1.0 / InpMAPeriod;            // SMMA smoothing factor

   //--- ─────────────── main calculation loop ───────────────────────
   for(int i = start; i < rates_total; i++)
   {
      double vol = g_dvol[i];

      // ── Moving average ──────────────────────────────────────────
      double ma_vol;
      switch(InpMAType)
      {
         case MODE_EMA:
            ma_vol   = (i == start && prev_calculated <= 0)
                        ? ema_prev
                        : vol * ema_k + ema_prev * (1.0 - ema_k);
            ema_prev = ma_vol;
            break;

         case MODE_SMMA:
            ma_vol   = (i == start && prev_calculated <= 0)
                        ? ema_prev
                        : vol * smma_k + ema_prev * (1.0 - smma_k);
            ema_prev = ma_vol;
            break;

         default:  // MODE_SMA (WMA falls back to SMA)
         {
            int    cnt = MathMin(i + 1, InpMAPeriod);
            double sum = 0;
            for(int k = 0; k < cnt; k++) sum += g_dvol[i - k];
            ma_vol = sum / cnt;
            break;
         }
      }

      // ── Standard deviation (population) ─────────────────────────
      double std_vol = 0.0;
      {
         int cnt = MathMin(i + 1, InpMAPeriod);
         if(cnt > 1)
         {
            double sq = 0;
            for(int k = 0; k < cnt; k++)
            {
               double d = g_dvol[i - k] - ma_vol;
               sq += d * d;
            }
            std_vol = MathSqrt(sq / cnt);
         }
      }

      double z_score = (std_vol > 1e-10) ? (vol - ma_vol) / std_vol : 0.0;

      // ── Spike detection ──────────────────────────────────────────
      bool is_spike = false;
      switch(InpMethod)
      {
         case METHOD_STDDEV:
            is_spike = (vol > ma_vol + InpMultiplier * std_vol);
            break;

         case METHOD_ZSCORE:
            is_spike = (z_score > InpZThreshold);
            break;

         case METHOD_PERCENTILE:
         {
            int below = 0;
            int cnt   = MathMin(i, InpPctPeriod);
            for(int k = 1; k <= cnt; k++)
               if(g_dvol[i - k] < vol) below++;
            double rank = (cnt > 0) ? 100.0 * below / cnt : 0.0;
            is_spike = (rank > InpPctCutoff);
            break;
         }

         case METHOD_RVOL:
         {
            double avg_sess = SessionAvgVol(tick_volume, time, i, InpRvolDays);
            if(avg_sess > 0)
               is_spike = (vol / avg_sess > InpRvolThreshold);
            break;
         }
      }

      bool bullish = (close[i] >= open[i]);

      // ── Sub-window buffers ───────────────────────────────────────
      g_vol[i]    = vol;
      g_ma[i]     = ma_vol;
      g_thresh[i] = ma_vol + InpMultiplier * std_vol;
      g_z[i]      = InpShowZScore ? (z_score * ma_vol) : EMPTY_VALUE;
      g_col[i]    = (double)(is_spike ? (bullish ? 2 : 3) : (bullish ? 0 : 1));

      // ── Price-chart objects ──────────────────────────────────────
      // On init only materialise objects for the most recent MAX_OBJ_HIST bars
      // so we don't flood the chart with thousands of objects on long histories.
      bool draw_obj = (prev_calculated <= 0)
                      ? (i >= rates_total - MAX_OBJ_HIST)
                      : true;

      if(is_spike && draw_obj)
      {
         string key = OBJ_PFX + (string)(int)time[i];
         if(InpShowArrows)
            DrawArrow(key + "A", time[i], bullish ? low[i] : high[i], bullish);
         if(InpShowZones)
            DrawZone (key + "Z", time[i], high[i], low[i]);
      }

      // ── Alert – fires once per candle (first spike tick only) ────
      if(is_spike && i == rates_total - 1 && time[i] != g_last_alert_bar)
      {
         g_last_alert_bar = time[i];
         TriggerAlert(vol, ma_vol, z_score);
      }
   }

   return rates_total;
}

//+------------------------------------------------------------------+
//| Compute average tick volume for the same session time-slot over  |
//| the previous N calendar days.  Handles gaps (weekends/holidays). |
//+------------------------------------------------------------------+
double SessionAvgVol(const long &tv[], const datetime &t[], int pos, int days)
{
   MqlDateTime cur;
   TimeToStruct(t[pos], cur);

   double sum   = 0;
   int    count = 0;

   for(int j = pos - 1; j >= 0 && count < days; j--)
   {
      MqlDateTime bar;
      TimeToStruct(t[j], bar);
      if(bar.hour == cur.hour && bar.min == cur.min)
      {
         sum += (double)tv[j];
         count++;
      }
   }

   return (count > 0) ? sum / count : 0.0;
}

//+------------------------------------------------------------------+
//| Draw an arrow on the main price chart                            |
//+------------------------------------------------------------------+
void DrawArrow(const string name, datetime t, double price, bool bullish)
{
   if(ObjectFind(0, name) >= 0) return;   // already drawn for this bar

   // offset arrow away from the bar so it doesn't overlap the wick
   double offset = _Point * 15.0 * InpArrowSize;
   double y      = bullish ? price - offset : price + offset;
   int    code   = bullish ? 233 : 234;   // Wingdings solid up/down arrows

   ObjectCreate       (0, name, OBJ_ARROW, 0, t, y);
   ObjectSetInteger   (0, name, OBJPROP_ARROWCODE,  code);
   ObjectSetInteger   (0, name, OBJPROP_COLOR,      bullish ? InpBullColor : InpBearColor);
   ObjectSetInteger   (0, name, OBJPROP_WIDTH,      InpArrowSize);
   ObjectSetInteger   (0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger   (0, name, OBJPROP_HIDDEN,     true);
}

//+------------------------------------------------------------------+
//| Draw a background highlight zone on the main price chart         |
//+------------------------------------------------------------------+
void DrawZone(const string name, datetime t, double hi, double lo)
{
   if(ObjectFind(0, name) >= 0) return;

   datetime t2 = t + (datetime)PeriodSeconds(_Period);

   ObjectCreate     (0, name, OBJ_RECTANGLE, 0, t, hi, t2, lo);
   ObjectSetInteger (0, name, OBJPROP_COLOR,      InpZoneColor);
   ObjectSetInteger (0, name, OBJPROP_FILL,       true);
   ObjectSetInteger (0, name, OBJPROP_BACK,       true);    // draw behind price bars
   ObjectSetInteger (0, name, OBJPROP_STYLE,      STYLE_SOLID);
   ObjectSetInteger (0, name, OBJPROP_WIDTH,      1);
   ObjectSetInteger (0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger (0, name, OBJPROP_HIDDEN,     true);
}

//+------------------------------------------------------------------+
//| Remove all chart objects created by this indicator               |
//+------------------------------------------------------------------+
void DeleteAllObjects()
{
   // iterate backwards so deletion doesn't shift positions
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, OBJ_PFX) == 0)
         ObjectDelete(0, name);
   }
}

//+------------------------------------------------------------------+
//| Fire alert / push / email                                        |
//+------------------------------------------------------------------+
void TriggerAlert(double vol, double ma, double z)
{
   string msg = StringFormat(
      "[VolumeSpike] %s %s | Vol: %.0f | MA: %.0f | Z: %.2f | %s",
      _Symbol,
      EnumToString(_Period),
      vol, ma, z,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES));

   if(InpAlert) Alert(msg);
   if(InpPush)  SendNotification(msg);
   if(InpEmail) SendMail("[VolumeSpike] " + _Symbol, msg);
}
//+------------------------------------------------------------------+
