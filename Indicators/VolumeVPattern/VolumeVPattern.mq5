//+------------------------------------------------------------------+
//|                                              VolumeVPattern.mq5  |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Volume "V" pattern detector for MetaTrader 5.                   |
//|                                                                   |
//|  The trader picks ONE source line (InpSource); that single line  |
//|  is plotted in the sub-window and the V is detected on it:        |
//|                                                                   |
//|     Threshold : MA + Multiplier × StdDev   (the dashed line)     |
//|     Z-Score   : (Volume − MA) / StdDev                           |
//|     MA Volume : MA(Volume)                                        |
//|     Volume    : raw tick volume                                   |
//|                                                                   |
//|        s[3] ●                       ● s[1]   ← RISE leg           |
//|              \                     /          (rise % ≥ InpRisePct)|
//|               \                   /                                |
//|                ● s[2]  (trough, strict local minimum)            |
//|                                                                   |
//|  Signal conditions (MT5 series indexing, [1] = last closed bar): |
//|     s[3] > s[2]                          drop into the trough     |
//|     s[1] > s[2]                          rise out of the trough   |
//|     (s[1] − s[2]) / |s[2]| >= InpRisePct rise leg steep enough    |
//|                                                                   |
//|  Arrow is drawn on C1 (the rise bar) at its close. Direction is  |
//|  taken from C1's candle colour. The trader enters at C0 open.    |
//+------------------------------------------------------------------+
#property copyright    "Dercio Micas"
#property version      "1.01"
#property description  "Volume V-Pattern – detects a V (trough then sharp rise) on a user-selected volume line"
#property indicator_separate_window
#property indicator_buffers  2
#property indicator_plots    1

//--- Plot 0: the single selected source line (colour-highlighted at signals)
#property indicator_label1   "Source"
#property indicator_type1    DRAW_COLOR_LINE
#property indicator_color1   clrYellow, clrLime, clrRed
#property indicator_style1   STYLE_SOLID
#property indicator_width1   2

//+------------------------------------------------------------------+
//| Source-line selector                                             |
//+------------------------------------------------------------------+
enum ENUM_VSOURCE
{
   VSRC_THRESHOLD = 0,   //  Threshold: MA + Multiplier × StdDev
   VSRC_ZSCORE    = 1,   //  Z-Score: (Volume − MA) / StdDev
   VSRC_MA        = 2,   //  MA of Volume
   VSRC_VOLUME    = 3    //  Raw Volume
};

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group              "── Detection ──────────────────────────────";
input ENUM_VSOURCE       InpSource        = VSRC_THRESHOLD;  // Source line for the V
input int                InpZPeriod       = 20;             // MA / StdDev period (bars)
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;       // MA type
input double             InpMultiplier    = 2.0;            // StdDev multiplier (Threshold source)
input double             InpRisePct       = 0.20;           // Min rise leg  (fraction, 0.20 = 20%)

input group              "── Price Chart ─────────────────────────────";
input bool               InpShowArrows    = true;           // Draw signal arrows
input color              InpBullColor     = clrDodgerBlue;  // Buy (bullish C1) colour
input color              InpBearColor     = clrOrangeRed;   // Sell (bearish C1) colour
input int                InpArrowSize     = 1;              // Arrow size  (1–5)

input group              "── Sub-Window Line ─────────────────────────";
input color              InpLineColor     = clrYellow;      // Source line colour
input color              InpSigBull       = clrLime;        // Signal highlight – buy
input color              InpSigBear       = clrRed;         // Signal highlight – sell

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
double g_src[];       // [0] selected source line (also read back for the V test)
double g_srccol[];    // [1] colour index (0=normal, 1=signal-buy, 2=signal-sell)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
#define OBJ_PFX       "VolumeVPattern_"
#define MAX_OBJ_HIST  5000     // max past bars to materialise chart objects on first load

double   g_dvol[];          // double copy of tick_volume[], rebuilt each call
int      g_zstart;          // first bar index with a meaningful source value
int      g_min_bars;        // minimum bars required before detection starts
datetime g_last_alert_bar;  // open-time of the last bar that fired an alert

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_zstart   = InpZPeriod - 1;     // earliest bar with a full window
   g_min_bars = InpZPeriod + 2;     // +2 so s[i-1] and s[i-2] exist for the V test

   //--- bind buffers
   SetIndexBuffer(0, g_src,    INDICATOR_DATA);
   SetIndexBuffer(1, g_srccol, INDICATOR_COLOR_INDEX);

   //--- line colour palette  (0=normal, 1=signal-buy, 2=signal-sell)
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 0, InpLineColor);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 1, InpSigBull);
   PlotIndexSetInteger(0, PLOT_LINE_COLOR, 2, InpSigBear);
   PlotIndexSetDouble (0, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   //--- sub-window label
   string src[] = {"Threshold", "Z-Score", "MA", "Volume"};
   IndicatorSetString(INDICATOR_SHORTNAME,
      "VolumeVPattern[" + src[InpSource] + ", " + (string)InpZPeriod +
      ", " + DoubleToString(InpRisePct * 100.0, 0) + "%]");

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

   //--- keep the double volume copy sized to history
   if(ArraySize(g_dvol) < rates_total)
      ArrayResize(g_dvol, rates_total);

   int update_from = (prev_calculated <= 0) ? 0 : MathMax(0, prev_calculated - 1);
   for(int j = update_from; j < rates_total; j++)
      g_dvol[j] = (double)tick_volume[j];

   //--- on full recalculation remove stale chart objects and blank the early line
   if(prev_calculated <= 0)
   {
      DeleteAllObjects();
      for(int j = 0; j < g_zstart && j < rates_total; j++)
      {
         g_src[j]    = EMPTY_VALUE;
         g_srccol[j] = 0.0;
      }
   }

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
      {
         // recover the MA used on the previous bar from the stored source value
         ema_prev = RecoverMA(start - 1);
      }
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

      // ── Selected source value ───────────────────────────────────
      double s;
      switch(InpSource)
      {
         case VSRC_ZSCORE:  s = (std_vol > 1e-10) ? (vol - ma_vol) / std_vol : 0.0; break;
         case VSRC_MA:      s = ma_vol;                                             break;
         case VSRC_VOLUME:  s = vol;                                                break;
         default:           s = ma_vol + InpMultiplier * std_vol;                   break; // Threshold
      }
      g_src[i] = s;

      bool bullish = (close[i] >= open[i]);

      // ── V-pattern detection ─────────────────────────────────────
      // Treat bar i as C1 (rise bar). C2 = i-1 (trough), C3 = i-2 (pre-drop).
      //   s[i-2] > s[i-1]                       drop into the trough
      //   s[i]   > s[i-1]                       rise out of the trough
      //   (s[i]-s[i-1]) / |s[i-1]| >= InpRisePct  rise leg steep enough
      bool   is_signal = false;
      double rise_frac = 0.0;
      if(i >= g_zstart + 2)
      {
         double s2 = g_src[i - 1];   // trough
         double s3 = g_src[i - 2];   // pre-drop
         if(s3 > s2 && s > s2)
         {
            double denom = MathMax(MathAbs(s2), 1e-10);
            rise_frac = (s - s2) / denom;
            is_signal = (rise_frac >= InpRisePct);
         }
      }

      // A signal is only valid on a CLOSED bar; the forming bar (last
      // index) can still change, so we never commit a marker there.
      bool closed = (i < rates_total - 1);
      bool fire   = is_signal && closed;

      // ── Line colour: highlight the C1 bar on a signal ────────────
      g_srccol[i] = (double)(fire ? (bullish ? 1 : 2) : 0);

      // ── Price-chart arrow on C1 ──────────────────────────────────
      bool draw_obj = (prev_calculated <= 0)
                      ? (i >= rates_total - MAX_OBJ_HIST)
                      : true;

      // On H4+ the bar open time is not meaningful for intraday filtering.
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
         TriggerAlert(s, rise_frac, bullish);
      }
   }

   return rates_total;
}

//+------------------------------------------------------------------+
//| Recover the MA value at bar idx from the stored source value.    |
//| Only needed to reseed EMA/SMMA on incremental recalculation.     |
//+------------------------------------------------------------------+
double RecoverMA(int idx)
{
   if(idx < 0) return 0.0;
   double s = g_src[idx];
   // For MA/Threshold the stored value is derived from the MA; for the
   // other sources we just recompute the SMA so the seed stays sensible.
   if(InpSource == VSRC_MA)
      return s;

   int    cnt = MathMin(idx + 1, InpZPeriod);
   double sum = 0;
   for(int k = 0; k < cnt; k++) sum += g_dvol[idx - k];
   return sum / cnt;
}

//+------------------------------------------------------------------+
//| Draw a signal arrow on the main price chart                      |
//+------------------------------------------------------------------+
void DrawArrow(const string name, datetime t, double price, bool bullish)
{
   if(ObjectFind(0, name) >= 0) return;   // already drawn for this bar

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
void TriggerAlert(double s, double rise_frac, bool bullish)
{
   string src[] = {"Threshold", "Z-Score", "MA", "Volume"};
   string dir   = bullish ? "BUY" : "SELL";
   string msg = StringFormat(
      "[VolumeVPattern] %s %s | %s | %s: %.2f | Rise: %.0f%% | %s",
      _Symbol,
      EnumToString(_Period),
      dir, src[InpSource], s, rise_frac * 100.0,
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
