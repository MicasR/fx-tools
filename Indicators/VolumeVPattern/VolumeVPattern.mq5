//+------------------------------------------------------------------+
//|                                              VolumeVPattern.mq5  |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Volume "V" pattern detector for MetaTrader 5.                   |
//|                                                                   |
//|  Works on the VOLUME Z-SCORE series. A signal fires when the     |
//|  z-score traces a V across three consecutive bars:               |
//|                                                                   |
//|        z[3] ●                       ● z[1]   ← sharp RISE leg     |
//|              \                     /          (slope ≥ InpSlope)  |
//|               \                   /                                |
//|                \                 /                                 |
//|                 ● z[2]  (trough, strict local minimum)            |
//|                                                                   |
//|  Signal conditions (MT5 series indexing, [1] = last closed bar): |
//|     z[3] > z[2]                  drop into the trough             |
//|     z[1] > z[2]                  rise out of the trough           |
//|     z[1] - z[2] >= InpSlope      the rise leg is steep enough     |
//|                                                                   |
//|  Arrow is drawn on C1 (the rise bar) at its close. Direction is  |
//|  taken from C1's candle colour. The trader enters at C0 open.    |
//|                                                                   |
//|  Sub-window: colour-coded volume histogram + MA + (scaled)       |
//|  z-score line so the V is visible.                               |
//+------------------------------------------------------------------+
#property copyright    "Dercio Micas"
#property version      "1.00"
#property description  "Volume V-Pattern – fires on a V in the volume z-score (drop into a trough, then a sharp rise)"
#property indicator_separate_window
#property indicator_buffers  4
#property indicator_plots    3

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

//--- Plot 2: volume z-score, scaled to MA units so it overlays the histogram
#property indicator_label3   "Z-Score (scaled)"
#property indicator_type3    DRAW_LINE
#property indicator_color3   clrYellow
#property indicator_style3   STYLE_DOT
#property indicator_width3   1

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group              "── Detection ──────────────────────────────";
input int                InpZPeriod       = 20;             // Z-score MA period (bars)
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;       // MA type
input double             InpSlope         = 2.0;            // Min rise-leg slope  (z[1] − z[2])

input group              "── Price Chart ─────────────────────────────";
input bool               InpShowArrows    = true;           // Draw signal arrows
input color              InpBullColor     = clrDodgerBlue;  // Buy (bullish C1) colour
input color              InpBearColor     = clrOrangeRed;   // Sell (bearish C1) colour
input int                InpArrowSize     = 1;              // Arrow size  (1–5)

input group              "── Sub-Window ──────────────────────────────";
input color              InpBarBull       = clrSteelBlue;   // Normal bull bar
input color              InpBarBear       = clrDimGray;     // Normal bear bar
input color              InpSigBull       = clrDodgerBlue;  // Signal bull bar (V + buy)
input color              InpSigBear       = clrOrangeRed;   // Signal bear bar (V + sell)
input bool               InpShowZScore    = true;           // Show z-score line

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
double g_col[];       // [1] histogram colour index (0=bull, 1=bear, 2=sig-bull, 3=sig-bear)
double g_ma[];        // [2] MA line
double g_zplot[];     // [3] z-score × MA  (scaled to be visible in the same window)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define OBJ_PFX       "VolumeVPattern_"
#define MAX_OBJ_HIST  5000     // max past bars to materialise chart objects on first load

double   g_dvol[];          // double copy of tick_volume[], rebuilt each call
double   g_zsc[];           // raw volume z-score per bar (persists across calls)
int      g_zstart;          // first bar index with a meaningful z-score
int      g_min_bars;        // minimum bars required before detection starts
datetime g_last_alert_bar;  // open-time of the last bar that fired an alert

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_zstart   = InpZPeriod - 1;     // earliest bar with a full z-score window
   g_min_bars = InpZPeriod + 2;     // +2 so z[i-1] and z[i-2] exist for the V test

   //--- bind buffers
   SetIndexBuffer(0, g_vol,   INDICATOR_DATA);
   SetIndexBuffer(1, g_col,   INDICATOR_COLOR_INDEX);
   SetIndexBuffer(2, g_ma,    INDICATOR_DATA);
   SetIndexBuffer(3, g_zplot, INDICATOR_DATA);

   //--- histogram colour palette  (indices 0-3 map to the four colours)
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, InpBarBull);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 1, InpBarBear);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 2, InpSigBull);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 3, InpSigBear);
   PlotIndexSetDouble (0, PLOT_EMPTY_VALUE, 0.0);

   //--- hide z-score line unless enabled
   if(!InpShowZScore)
      PlotIndexSetInteger(2, PLOT_DRAW_TYPE, DRAW_NONE);

   //--- sub-window label
   IndicatorSetString(INDICATOR_SHORTNAME,
      "VolumeVPattern[" + (string)InpZPeriod + ", slope " +
      DoubleToString(InpSlope, 1) + "]");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DeleteAllObjects();
   ArrayFree(g_dvol);
   ArrayFree(g_zsc);
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

   //--- keep working arrays sized to history
   if(ArraySize(g_dvol) < rates_total)
   {
      ArrayResize(g_dvol, rates_total);
      ArrayResize(g_zsc,  rates_total);
   }
   if(prev_calculated <= 0)
      ArrayInitialize(g_zsc, 0.0);

   //--- refresh the double volume copy for the affected range
   int update_from = (prev_calculated <= 0) ? 0 : MathMax(0, prev_calculated - 1);
   for(int j = update_from; j < rates_total; j++)
      g_dvol[j] = (double)tick_volume[j];

   //--- on full recalculation remove stale chart objects
   if(prev_calculated <= 0)
      DeleteAllObjects();

   int start = (prev_calculated <= 0) ? g_zstart : prev_calculated - 1;

   //--- initialise exponential-style MA seed
   double ema_prev = 0.0;
   if(InpMAType == MODE_EMA || InpMAType == MODE_SMMA)
   {
      if(prev_calculated <= 0)
      {
         double seed = 0;
         for(int k = 0; k < InpZPeriod; k++)
            seed += g_dvol[start - k];
         ema_prev = seed / InpZPeriod;
      }
      else
         ema_prev = g_ma[start - 1];
   }

   const double ema_k  = 2.0 / (InpZPeriod + 1.0);   // EMA smoothing factor
   const double smma_k = 1.0 / InpZPeriod;           // SMMA smoothing factor

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
            int    cnt = MathMin(i + 1, InpZPeriod);
            double sum = 0;
            for(int k = 0; k < cnt; k++) sum += g_dvol[i - k];
            ma_vol = sum / cnt;
            break;
         }
      }

      // ── Standard deviation (population) ─────────────────────────
      double std_vol = 0.0;
      {
         int cnt = MathMin(i + 1, InpZPeriod);
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

      double z = (std_vol > 1e-10) ? (vol - ma_vol) / std_vol : 0.0;
      g_zsc[i] = z;

      bool bullish = (close[i] >= open[i]);

      // ── V-pattern detection ─────────────────────────────────────
      // Treat bar i as C1 (the rise bar). C2 = i-1 (trough), C3 = i-2.
      //   z[i-2] > z[i-1]            drop into the trough
      //   z[i]   > z[i-1]            rise out of the trough
      //   z[i] - z[i-1] >= InpSlope  the rise leg is steep enough
      bool is_signal = false;
      if(i >= g_zstart + 2)
      {
         double z_c2 = g_zsc[i - 1];   // trough
         double z_c3 = g_zsc[i - 2];   // pre-drop
         is_signal = (z_c3 > z_c2) && (z > z_c2) && ((z - z_c2) >= InpSlope);
      }

      // A signal is only valid on a CLOSED bar; the forming bar (last
      // index) can still change, so we never commit a marker there.
      bool closed = (i < rates_total - 1);
      bool fire   = is_signal && closed;

      // ── Sub-window buffers ───────────────────────────────────────
      g_vol[i]   = vol;
      g_ma[i]    = ma_vol;
      g_zplot[i] = InpShowZScore ? (z * ma_vol) : EMPTY_VALUE;
      g_col[i]   = (double)(fire ? (bullish ? 2 : 3) : (bullish ? 0 : 1));

      // ── Price-chart arrow on C1 ──────────────────────────────────
      // On init only materialise objects for the most recent MAX_OBJ_HIST bars.
      bool draw_obj = (prev_calculated <= 0)
                      ? (i >= rates_total - MAX_OBJ_HIST)
                      : true;

      // On H4+ the bar open time is not meaningful for intraday filtering;
      // bypass so higher-TF signals are always drawn regardless of the window.
      bool in_window = (PeriodSeconds(_Period) >= PeriodSeconds(PERIOD_H4))
                       ? true
                       : IsInTimeWindow(time[i]);

      if(fire && draw_obj && in_window && InpShowArrows)
      {
         string key = OBJ_PFX + (string)(int)time[i];
         DrawArrow(key + "A", time[i], bullish ? low[i] : high[i], bullish);
      }

      // ── Alert – fires once when C1 (the newest closed bar) closes ─
      if(fire && i == rates_total - 2 && time[i] != g_last_alert_bar
         && IsInTimeWindow(TimeCurrent()))
      {
         g_last_alert_bar = time[i];
         TriggerAlert(vol, ma_vol, z, z - g_zsc[i - 1], bullish);
      }
   }

   return rates_total;
}

//+------------------------------------------------------------------+
//| Draw a signal arrow on the main price chart                      |
//+------------------------------------------------------------------+
void DrawArrow(const string name, datetime t, double price, bool bullish)
{
   if(ObjectFind(0, name) >= 0) return;   // already drawn for this bar

   // offset arrow away from the bar so it doesn't overlap the wick
   double offset = _Point * 15.0 * InpArrowSize;
   double y      = bullish ? price - offset : price + offset;
   int    code   = bullish ? 233 : 234;   // Wingdings solid up/down arrows

   ObjectCreate     (0, name, OBJ_ARROW, 0, t, y);
   ObjectSetInteger (0, name, OBJPROP_ARROWCODE,  code);
   ObjectSetInteger (0, name, OBJPROP_COLOR,      bullish ? InpBullColor : InpBearColor);
   ObjectSetInteger (0, name, OBJPROP_WIDTH,      InpArrowSize);
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
void TriggerAlert(double vol, double ma, double z, double slope, bool bullish)
{
   string dir = bullish ? "BUY" : "SELL";
   string msg = StringFormat(
      "[VolumeVPattern] %s %s | %s | Vol: %.0f | MA: %.0f | Z: %.2f | Slope: %.2f | %s",
      _Symbol,
      EnumToString(_Period),
      dir, vol, ma, z, slope,
      TimeToString(TimeCurrent(), TIME_DATE | TIME_MINUTES));

   if(InpAlert)   Alert(msg);
   if(InpPush)    SendNotification(msg);
   if(InpEmail)   SendMail("[VolumeVPattern] " + _Symbol, msg);
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

   // Escape backslashes then double-quotes so the JSON body stays valid
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
      Print("VolumeVPattern | WhatsApp WebRequest error ", GetLastError(),
            " – whitelist https://api.maytapi.com in Tools > Options > Expert Advisors");
}
//+------------------------------------------------------------------+
