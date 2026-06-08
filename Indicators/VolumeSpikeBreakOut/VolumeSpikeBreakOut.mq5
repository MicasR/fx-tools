//+------------------------------------------------------------------+
//|                                          VolumeSpikeBreakOut.mq5  |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  A fork of VolumeVPattern. The sub-window analytics are IDENTICAL |
//|  to VolumeSpike / VolumeVPattern (same colour-coded histogram,    |
//|  MA, threshold and z-score lines, same inputs) so all three can   |
//|  be compared side by side with the same settings.                 |
//|                                                                   |
//|  The behavioural change is the price-chart SIGNAL. Instead of     |
//|  acting on the trigger bar immediately (spike arrow / V arrow),   |
//|  this indicator waits for a BREAKOUT of the trigger bar's range:  |
//|                                                                   |
//|    1. A TRIGGER fires on a closed bar T. Two trigger types:       |
//|         Spike     – volume crosses the spike level (is_spike)      |
//|         V-pattern – the selected line traces a V (VolumeVPattern)  |
//|    2. Over the next InpBreakBars closed bars, the first bar to     |
//|         break above T's high  → BULL entry arrow on that bar       |
//|         break below T's low   → BEAR entry arrow on that bar       |
//|       Direction is decided by the market, not the candle colour.  |
//|    3. A bar that breaks BOTH sides (straddle) is ambiguous → no    |
//|       trade. If no break occurs within the window, the setup       |
//|       expires. Non-repainting: only closed bars are evaluated.     |
//|                                                                   |
//|  Backtest basis (XAUUSDc H1, threshold method, 1:3 target):       |
//|  the breakout entry flips the adverse-regime expectancy from       |
//|  negative to positive vs the candle-colour direction, and was      |
//|  positive across all four time quarters with the Spike trigger.    |
//+------------------------------------------------------------------+
#property copyright    "Dercio Micas"
#property version      "1.01"
#property description  "Volume Spike / V-pattern trigger + breakout-of-range entry (direction confirmed by price)"
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
//| Enumerations                                                     |
//+------------------------------------------------------------------+
enum ENUM_DETECT_METHOD
{
   METHOD_STDDEV     = 0,   //  MA + Standard Deviation  (recommended)
   METHOD_ZSCORE     = 1,   //  Z-Score Normalisation
   METHOD_PERCENTILE = 2,   //  Percentile Rank
   METHOD_RVOL       = 3,   //  Relative Volume – session-aware
   METHOD_THRESHOLD  = 4    //  Threshold line  (MA + Multiplier*StdDev)
};

enum ENUM_BREAKOUT_TRIGGER
{
   TRIGGER_SPIKE     = 0,   //  Spike      (volume crosses the level)
   TRIGGER_VPATTERN  = 1    //  V-pattern  (selected line traces a V)
};

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group              "── Detection ──────────────────────────────";
input ENUM_BREAKOUT_TRIGGER InpTrigger    = TRIGGER_VPATTERN;// Setup trigger (V-pattern best on H1; Spike better on H4)
input int                InpBreakBars     = 4;               // Breakout window (bars to confirm)
input ENUM_DETECT_METHOD InpMethod        = METHOD_THRESHOLD;// Detection method
input int                InpMAPeriod      = 20;             // MA period (bars)
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;       // MA type
input double             InpMultiplier    = 2.0;            // Std Dev multiplier
input double             InpZThreshold    = 2.5;            // Z-score threshold
input int                InpPctPeriod     = 100;            // Percentile lookback (bars)
input double             InpPctCutoff     = 95.0;           // Percentile cutoff  (%)
input int                InpRvolDays      = 10;             // RVOL history (days)
input double             InpRvolThreshold = 2.0;            // RVOL multiplier
input double             InpRisePct       = 0.02;           // V rise leg (only if trigger = V-pattern)

input group              "── Price Chart ─────────────────────────────";
input bool               InpShowArrows    = true;           // Draw breakout entry arrows
input bool               InpShowZones     = true;           // Draw the breakout-range box
input color              InpBullColor     = clrDodgerBlue;  // Bullish breakout colour
input color              InpBearColor     = clrOrangeRed;   // Bearish breakout colour
input color              InpZoneColor     = clrGold;        // Range box colour
input int                InpArrowSize     = 1;              // Arrow size  (1–5)

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
input bool               InpWhatsApp      = false;          // WhatsApp notification (Maytapi)
input string             InpMaytapiProductId = "";          // Maytapi product ID
input string             InpMaytapiPhoneId   = "";          // Maytapi phone ID
input string             InpMaytapiKey       = "";          // Maytapi API key
input string             InpWhatsAppTo       = "";          // Recipient number (+XXXXXXXXXXX)

input group              "── Time Filter ─────────────────────────────";
input bool               InpTimeFilter    = false;          // Enable time-of-day filter
input int                InpTimeFromHour  = 9;              // From – hour   (0-23)
input int                InpTimeFromMin   = 0;              // From – minute (0-59)
input int                InpTimeToHour    = 23;             // To   – hour   (0-23)
input int                InpTimeToMin     = 59;             // To   – minute (0-59)

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
#define OBJ_PFX       "VolumeSpikeBreakOut_"
#define MAX_OBJ_HIST  5000     // max past bars to materialise chart objects on first load

double   g_dvol[];          // double copy of tick_volume[], rebuilt each call
double   g_sig[];           // the selected method's line (the V test reads it)
double   g_trig[];          // 1.0 on a trigger bar, else 0.0 (persists across calls)
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
   string meth[] = {"StdDev", "Z-Score", "Pct", "RVOL", "Threshold"};
   string trig   = (InpTrigger == TRIGGER_VPATTERN) ? "Vpat" : "Spike";
   IndicatorSetString(INDICATOR_SHORTNAME,
      "VolSpikeBO[" + trig + "," + meth[InpMethod] + ",brk" + (string)InpBreakBars + "]");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DeleteAllObjects();
   ArrayFree(g_dvol);
   ArrayFree(g_sig);
   ArrayFree(g_trig);
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

   //--- keep working arrays in sync with history
   if(ArraySize(g_dvol) < rates_total)
   {
      ArrayResize(g_dvol, rates_total);
      ArrayResize(g_sig,  rates_total);
      ArrayResize(g_trig, rates_total);
   }

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
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++)
            seed += g_dvol[start - k];
         ema_prev = seed / InpMAPeriod;
      }
      else
         ema_prev = g_ma[start - 1];
   }

   const double ema_k  = 2.0 / (InpMAPeriod + 1.0);   // EMA smoothing factor
   const double smma_k = 1.0 / InpMAPeriod;           // SMMA smoothing factor

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
      double thresh  = ma_vol + InpMultiplier * std_vol;

      // ── Percentile rank & RVOL (computed for the selected method) ─
      double rank = 0.0;
      if(InpMethod == METHOD_PERCENTILE)
      {
         int below = 0;
         int cnt   = MathMin(i, InpPctPeriod);
         for(int k = 1; k <= cnt; k++)
            if(g_dvol[i - k] < vol) below++;
         rank = (cnt > 0) ? 100.0 * below / cnt : 0.0;
      }

      double rvol = 0.0;
      if(InpMethod == METHOD_RVOL)
      {
         double avg_sess = SessionAvgVol(tick_volume, time, i, InpRvolDays);
         rvol = (avg_sess > 0) ? vol / avg_sess : 0.0;
      }

      // ── is_spike  (drives the histogram colour – IDENTICAL to VolumeSpike) ─
      bool is_spike = false;
      switch(InpMethod)
      {
         case METHOD_ZSCORE:     is_spike = (z_score > InpZThreshold);       break;
         case METHOD_PERCENTILE: is_spike = (rank    > InpPctCutoff);        break;
         case METHOD_RVOL:       is_spike = (rvol    > InpRvolThreshold);    break;
         default:                is_spike = (vol     > thresh);              break; // STDDEV & THRESHOLD
      }

      // ── V source line for the selected method ────────────────────
      double sig;
      switch(InpMethod)
      {
         case METHOD_PERCENTILE: sig = rank;   break;
         case METHOD_RVOL:       sig = rvol;   break;
         case METHOD_THRESHOLD:  sig = thresh; break;
         default:                sig = z_score; break; // STDDEV & ZSCORE
      }
      g_sig[i] = sig;

      bool bullish = (close[i] >= open[i]);

      // ── Sub-window buffers (IDENTICAL to VolumeSpike) ────────────
      g_vol[i]    = vol;
      g_ma[i]     = ma_vol;
      g_thresh[i] = thresh;
      g_z[i]      = InpShowZScore ? (z_score * ma_vol) : EMPTY_VALUE;
      g_col[i]    = (double)(is_spike ? (bullish ? 2 : 3) : (bullish ? 0 : 1));

      // ── Trigger detection ────────────────────────────────────────
      // V-pattern: bar i is C1 (rise bar); i-1 trough; i-2 pre-drop.
      bool v_signal = false;
      if(i >= g_min_bars + 1)
      {
         double s2 = g_sig[i - 1];
         double s3 = g_sig[i - 2];
         if(s3 > s2 && sig > s2)
         {
            double denom = MathMax(MathAbs(s2), 1e-10);
            v_signal = ((sig - s2) / denom >= InpRisePct);
         }
      }
      bool trig = (InpTrigger == TRIGGER_VPATTERN) ? v_signal : is_spike;
      g_trig[i] = trig ? 1.0 : 0.0;

      // ── Breakout-entry detection on the CLOSED bar i ─────────────
      // Find the most recent un-broken trigger within InpBreakBars and
      // check whether bar i is the first bar to break its range.
      bool closed = (i < rates_total - 1);
      if(closed && i > g_min_bars && InpBreakBars > 0)
      {
         int maxlook = MathMin(InpBreakBars, i - 1);
         for(int back = 1; back <= maxlook; back++)
         {
            int T = i - back;
            if(T < g_min_bars)         break;
            if(g_trig[T] == 0.0)       continue;   // not a trigger bar

            double hiT = high[T];
            double loT = low[T];

            // skip if any bar strictly between T and i already broke the range
            bool resolved = false;
            for(int j = T + 1; j < i; j++)
               if(high[j] >= hiT || low[j] <= loT) { resolved = true; break; }
            if(resolved)               continue;

            bool up = (high[i] >= hiT);
            bool dn = (low[i]  <= loT);
            if(up && dn)               continue;   // straddle → ambiguous, no entry
            if(!up && !dn)             continue;   // i doesn't break this pending trigger

            // ── ENTRY confirmed on bar i ──
            bool draw_obj = (prev_calculated <= 0)
                            ? (i >= rates_total - MAX_OBJ_HIST)
                            : true;
            bool in_window = (PeriodSeconds(_Period) >= PeriodSeconds(PERIOD_H4))
                             ? true
                             : IsInTimeWindow(time[i]);

            if(draw_obj && in_window)
            {
               string key = OBJ_PFX + (string)(int)time[i];
               if(InpShowArrows)
                  DrawArrow(key + "A", time[i], up ? low[i] : high[i], up);
               if(InpShowZones)
                  DrawZone(key + "Z", time[T], hiT, time[i], loT);
            }

            // ── Alert when the entry is the newest closed bar ──
            if(i == rates_total - 2 && time[i] != g_last_alert_bar
               && IsInTimeWindow(TimeCurrent()))
            {
               g_last_alert_bar = time[i];
               TriggerAlert(up, up ? hiT : loT, back, vol);
            }
            break;   // one entry per bar
         }
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
//| Draw the breakout-range box (trigger bar → breakout bar)         |
//+------------------------------------------------------------------+
void DrawZone(const string name, datetime t1, double hi, datetime t2, double lo)
{
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate     (0, name, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
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
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, OBJ_PFX) == 0)
         ObjectDelete(0, name);
   }
}

//+------------------------------------------------------------------+
//| Returns true if t falls inside the configured time window.       |
//| Handles overnight ranges (e.g. 22:00 – 06:00).                  |
//| Always returns true when InpTimeFilter is disabled.              |
//+------------------------------------------------------------------+
bool IsInTimeWindow(datetime t)
{
   if(!InpTimeFilter) return true;

   MqlDateTime dt;
   TimeToStruct(t, dt);
   int cur  = dt.hour * 60 + dt.min;
   int from = InpTimeFromHour * 60 + InpTimeFromMin;
   int to   = InpTimeToHour  * 60 + InpTimeToMin;

   if(from <= to)
      return (cur >= from && cur <= to);
   else   // overnight wrap – e.g. 22:00 → 06:00
      return (cur >= from || cur <= to);
}

//+------------------------------------------------------------------+
//| Fire alert / push / email / WhatsApp                             |
//+------------------------------------------------------------------+
void TriggerAlert(bool bullish, double level, int bars_to_break, double vol)
{
   string trig = (InpTrigger == TRIGGER_VPATTERN) ? "Vpat" : "Spike";
   string dir  = bullish ? "BUY break" : "SELL break";
   string msg = StringFormat(
      "[VolumeSpikeBreakOut] %s %s | %s | trigger: %s | level: %s | confirmed in %d bar(s) | Vol: %.0f | %s",
      _Symbol,
      EnumToString(_Period),
      dir, trig, DoubleToString(level, _Digits), bars_to_break, vol,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES));

   if(InpAlert)   Alert(msg);
   if(InpPush)    SendNotification(msg);
   if(InpEmail)   SendMail("[VolumeSpikeBreakOut] " + _Symbol, msg);
   SendWhatsApp(msg);
}

//+------------------------------------------------------------------+
//| Send a WhatsApp message via the Maytapi REST API                 |
//| Requires https://api.maytapi.com whitelisted in MT5 Options      |
//+------------------------------------------------------------------+
void SendWhatsApp(const string msg)
{
   if(!InpWhatsApp) return;
   if(InpMaytapiProductId == "" || InpMaytapiPhoneId == "" ||
      InpMaytapiKey == "" || InpWhatsAppTo == "") return;

   string url = "https://api.maytapi.com/api/"
                + InpMaytapiProductId + "/"
                + InpMaytapiPhoneId  + "/sendMessage";

   string headers = "Content-Type: application/json\r\nx-maytapi-key: " + InpMaytapiKey;

   string safe = msg;
   StringReplace(safe, "\\", "\\\\");
   StringReplace(safe, "\"", "\\\"");

   string json = StringFormat(
      "{\"to_number\":\"%s\",\"type\":\"text\",\"message\":\"%s\",\"text\":\"\"}",
      InpWhatsAppTo, safe);

   char   post[];
   char   result[];
   string result_headers;
   StringToCharArray(json, post, 0, StringLen(json));

   int res = WebRequest("POST", url, headers, 5000, post, result, result_headers);
   if(res == -1)
      Print("VolumeSpikeBreakOut | WhatsApp WebRequest error ", GetLastError(),
            " – whitelist https://api.maytapi.com in Tools > Options > Expert Advisors");
}
//+------------------------------------------------------------------+
