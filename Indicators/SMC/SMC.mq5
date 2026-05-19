//+------------------------------------------------------------------+
//|                                                          SMC.mq5 |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Smart Money Concepts overlay for MetaTrader 5.                  |
//|  Price chart only (no sub-window).                               |
//|                                                                   |
//|  Features:                                                        |
//|    · Break of Structure  (BoS)                                   |
//|    · Change of Character (ChoCh)                                 |
//|    · Fair Value Gaps     (FVG)  – with mitigation tracking       |
//|    · Order Blocks        (OB)   – with mitigation tracking       |
//|    · Liquidity Sweeps                                            |
//|    · OTE Levels          (61.8 – 79 % Fibonacci retracement)    |
//|    · MTF Structure Overlay (HTF BoS/ChoCh on current chart)     |
//|    · Trend Bias Dashboard (multi-TF bias panel)                  |
//|    · Premium / Discount Zones                                    |
//|    · Inducement Levels (IDM)                                     |
//|    · Equal Highs / Equal Lows (EQH / EQL)                       |
//+------------------------------------------------------------------+
#property copyright    "Dercio Micas"
#property version      "2.00"
#property description  "SMC – Full Smart Money Concepts suite v2"
#property indicator_chart_window
#property indicator_buffers  1
#property indicator_plots    0

//+------------------------------------------------------------------+
//| Enumerations                                                     |
//+------------------------------------------------------------------+
enum ENUM_TREND_STATE
{
   TREND_NEUTRAL   = 0,
   TREND_UP        = 1,
   TREND_DOWN      = 2
};

//+------------------------------------------------------------------+
//| Input parameters                                                 |
//+------------------------------------------------------------------+
input group "── Structure ──────────────────────────────────────────";
input int   InpSwingLen        = 5;              // Swing pivot look-left/right (bars)
input bool  InpShowBoS         = true;           // Show Break of Structure
input bool  InpShowChoCh       = true;           // Show Change of Character
input color InpBoSColor        = clrDodgerBlue;  // BoS line colour
input color InpChoCHColor      = clrOrangeRed;   // ChoCh line colour
input int   InpStructLineWidth = 1;              // Structure line width

input group "── Fair Value Gaps ─────────────────────────────────────";
input bool  InpShowFVG         = true;           // Show Fair Value Gaps
input bool  InpFVGMitigation   = true;           // Extend FVG until mitigated
input color InpFVGBullColor    = clrLimeGreen;   // Bullish FVG colour
input color InpFVGBearColor    = clrTomato;      // Bearish FVG colour
input int   InpFVGAlpha        = 40;             // FVG transparency (0–255)
input int   InpMaxFVGs         = 20;             // Max active FVGs tracked

input group "── Order Blocks ────────────────────────────────────────";
input bool  InpShowOB          = true;           // Show Order Blocks
input bool  InpOBMitigation    = true;           // Fade mitigated OBs
input color InpOBBullColor     = clrDeepSkyBlue; // Bullish OB colour
input color InpOBBearColor     = clrCrimson;     // Bearish OB colour
input int   InpOBAlpha         = 50;             // OB transparency (0–255)
input int   InpMaxOBs          = 10;             // Max active OBs tracked

input group "── Liquidity Sweeps ────────────────────────────────────";
input bool  InpShowSweeps      = true;           // Show Liquidity Sweeps
input color InpSweepBullColor  = clrAqua;        // Bullish sweep colour
input color InpSweepBearColor  = clrMagenta;     // Bearish sweep colour
input int   InpSweepArrowSize  = 2;              // Sweep arrow size (1–5)

input group "── OTE ─────────────────────────────────────────────────";
input bool  InpShowOTE         = true;           // Show OTE zone
input color InpOTEColor        = clrGold;        // OTE zone colour
input int   InpOTEAlpha        = 35;             // OTE transparency (0–255)

input group "── MTF Structure Overlay ────────────────────────────────";
input bool             InpShowMTF        = true;             // Show HTF structure overlay
input ENUM_TIMEFRAMES  InpMTFTimeframe   = PERIOD_H4;        // Higher timeframe
input color            InpMTFBoSColor    = clrSteelBlue;     // HTF BoS colour
input color            InpMTFChoCHColor  = clrSalmon;        // HTF ChoCh colour
input int              InpMTFLineWidth   = 2;                // HTF line width
input int              InpMTFSwingLen    = 5;                // HTF swing look-left/right

input group "── Trend Bias Dashboard ─────────────────────────────────";
input bool   InpShowDashboard  = true;           // Show trend bias dashboard
input color  InpDashBgColor    = C'20,20,30';    // Dashboard background
input color  InpDashTextColor  = clrWhite;       // Dashboard text colour
input color  InpDashUpColor    = clrLimeGreen;   // Uptrend badge colour
input color  InpDashDownColor  = clrTomato;      // Downtrend badge colour
input color  InpDashNeutColor  = clrDimGray;     // Neutral badge colour
input int    InpDashX          = 20;             // Dashboard X position (pixels)
input int    InpDashY          = 30;             // Dashboard Y position (pixels)

input group "── Premium / Discount ──────────────────────────────────";
input bool   InpShowPD         = true;           // Show Premium/Discount zones
input color  InpPremiumColor   = clrTomato;      // Premium zone colour
input color  InpDiscountColor  = clrLimeGreen;   // Discount zone colour
input color  InpEqColor        = clrYellow;      // Equilibrium line colour
input int    InpPDAlpha        = 20;             // P/D zone transparency (0–255)

input group "── Inducement ──────────────────────────────────────────";
input bool   InpShowIDM        = true;           // Show Inducement levels
input color  InpIDMColor       = clrOrange;      // Inducement line colour
input int    InpIDMSwingLen    = 2;              // IDM swing sensitivity (bars)

input group "── Equal Highs / Equal Lows ─────────────────────────────";
input bool   InpShowEQ         = true;           // Show Equal Highs/Lows
input double InpEQTolerance    = 5.0;            // Tolerance in points (pips × 10)
input color  InpEQHColor       = clrYellow;      // EQH colour
input color  InpEQLColor       = clrCyan;        // EQL colour
input int    InpEQLookback     = 100;            // Bars to look back for EQ matches

input group "── Alerts ──────────────────────────────────────────────";
input bool  InpAlertBoS        = true;           // Alert on BoS
input bool  InpAlertChoCh      = true;           // Alert on ChoCh
input bool  InpAlertFVG        = false;          // Alert on new FVG
input bool  InpAlertSweep      = false;          // Alert on Liquidity Sweep
input bool  InpAlertOTE        = false;          // Alert when price enters OTE
input bool  InpPush            = false;          // Push notification
input bool  InpEmail           = false;          // Email alert
input bool  InpAlertBarClose   = true;           // Alert only at bar close

//+------------------------------------------------------------------+
//| Internal structures                                              |
//+------------------------------------------------------------------+
struct SwingPoint
{
   datetime time;
   double   price;
   bool     isHigh;
   bool     confirmed;
};

struct FVGZone
{
   datetime timeStart;
   datetime timeEnd;
   double   top;
   double   bottom;
   bool     bullish;
   bool     mitigated;
   string   objName;
};

struct OrderBlock
{
   datetime timeStart;
   datetime timeEnd;
   double   top;
   double   bottom;
   double   bodyTop;
   double   bodyBottom;
   bool     bullish;
   bool     mitigated;
   string   objName;
};

struct OTEState
{
   double   legHigh;
   double   legLow;
   double   ote61;
   double   ote79;
   double   eq50;
   bool     bullish;
   bool     active;
   datetime originTime;
};

// MTF swing state (mirrors SwingPoint logic but on HTF data)
struct MTFState
{
   ENUM_TREND_STATE trend;
   double           lastSwHigh;
   double           lastSwLow;
   datetime         lastSwHighTime;
   datetime         lastSwLowTime;
   int              obCandidateIdx;  // index into htf arrays
};

// Premium/Discount zone state (one active at a time, redrawn on each ChoCh)
struct PDState
{
   double   rangeHigh;
   double   rangeLow;
   double   eq50;
   bool     active;
   datetime originTime;
};

// Inducement level
struct IDMLevel
{
   datetime time;
   double   price;
   bool     isHigh;   // true = IDM above price (before bearish OB)
   bool     hit;
   string   objName;
};

// Equal High / Equal Low
struct EQLevel
{
   datetime time1;
   datetime time2;
   double   price;
   bool     isHigh;
   string   objName;
};

//+------------------------------------------------------------------+
//| Object prefix & limits                                           |
//+------------------------------------------------------------------+
#define OBJ_PFX        "SMC_"
#define MAX_OBJ_HIST   300     // max bars materialised on first load
#define SWING_HIST     200     // swing ring-buffer size
#define MAX_IDM        20
#define MAX_EQ         30

//+------------------------------------------------------------------+
//| Indicator buffer (dummy – satisfies indicator_buffers >= 1)      |
//+------------------------------------------------------------------+
double g_dummy[];

//+------------------------------------------------------------------+
//| Global state                                                     |
//+------------------------------------------------------------------+
ENUM_TREND_STATE g_trend;

// Swing ring-buffers
SwingPoint g_swings[];
int        g_swingHead;
int        g_swingCount;

// Latest confirmed swing high / low tracked for structure
double   g_lastSwHigh;
double   g_lastSwLow;
datetime g_lastSwHighTime;
datetime g_lastSwLowTime;

// Pending OB candidate (last opposing candle before next structure break)
int      g_obCandidateBar;   // bar index of the OB candidate (-1 = none)

// Active zone arrays
FVGZone    g_fvg[];
int        g_fvgCount;

OrderBlock g_ob[];
int        g_obCount;

OTEState   g_ote;

// MTF
MTFState   g_mtf;
MqlRates   g_htfRates[];         // HTF OHLC cache
int        g_htfCount;
datetime   g_htfLastTime;        // last HTF bar time seen (change detection)

// Premium / Discount
PDState    g_pd;

// Inducement
IDMLevel   g_idm[];
int        g_idmCount;

// Equal Highs / Lows
EQLevel    g_eq[];
int        g_eqCount;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, g_dummy, INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, DRAW_NONE);

   IndicatorSetString(INDICATOR_SHORTNAME,
      "SMC[" + (string)InpSwingLen + "]");

   ArrayResize(g_swings,  SWING_HIST);
   ArrayResize(g_fvg,     InpMaxFVGs);
   ArrayResize(g_ob,      InpMaxOBs);
   ArrayResize(g_idm,     MAX_IDM);
   ArrayResize(g_eq,      MAX_EQ);
   ArraySetAsSeries(g_htfRates, false);

   g_trend          = TREND_NEUTRAL;
   g_swingHead      = 0;
   g_swingCount     = 0;
   g_lastSwHigh     = 0.0;
   g_lastSwLow      = DBL_MAX;
   g_lastSwHighTime = 0;
   g_lastSwLowTime  = 0;
   g_obCandidateBar = -1;
   g_fvgCount       = 0;
   g_obCount        = 0;
   g_ote.active     = false;

   // MTF init
   g_mtf.trend            = TREND_NEUTRAL;
   g_mtf.lastSwHigh       = 0.0;
   g_mtf.lastSwLow        = DBL_MAX;
   g_mtf.lastSwHighTime   = 0;
   g_mtf.lastSwLowTime    = 0;
   g_mtf.obCandidateIdx   = -1;
   g_htfCount             = 0;
   g_htfLastTime          = 0;

   // Premium/Discount init
   g_pd.active     = false;

   // IDM / EQ init
   g_idmCount = 0;
   g_eqCount  = 0;

   // Dashboard timeframes (fixed 5-entry list covering common MTF views)
   DashTFs[0] = PERIOD_M15;
   DashTFs[1] = PERIOD_H1;
   DashTFs[2] = PERIOD_H4;
   DashTFs[3] = PERIOD_D1;
   DashTFs[4] = PERIOD_W1;

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DeleteAllObjects();
   DeleteDashboard();
   ArrayFree(g_swings);
   ArrayFree(g_fvg);
   ArrayFree(g_ob);
   ArrayFree(g_idm);
   ArrayFree(g_eq);
   ArrayFree(g_htfRates);
   ArrayFree(g_dummy);
}

//+------------------------------------------------------------------+
//| Remove every chart object whose name starts with OBJ_PFX        |
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
//| Thin helpers used across phases                                  |
//+------------------------------------------------------------------+

// Unique key string from a timestamp
string Key(datetime t) { return (string)(int)t; }

// Blend colour with alpha for fill (MT5 uses ARGB)
color AlphaColor(color c, int alpha)
{
   return (color)(((alpha & 0xFF) << 24) | (c & 0x00FFFFFF));
}

// Fire alert / push / email
void TriggerAlert(const string tag, const string detail)
{
   string msg = StringFormat("[SMC] %s %s | %s | %s",
      _Symbol,
      EnumToString(_Period),
      tag,
      detail);

   Alert(msg);
   if(InpPush)  SendNotification(msg);
   if(InpEmail) SendMail("[SMC] " + _Symbol + " " + tag, msg);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dashboard helpers
// ─────────────────────────────────────────────────────────────────────────────

// All dashboard object names
#define DASH_PFX  "SMC_DASH_"

// Timeframes shown in the dashboard — populated in OnInit
ENUM_TIMEFRAMES DashTFs[5];

string TFName(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return "M1";
      case PERIOD_M5:  return "M5";
      case PERIOD_M15: return "M15";
      case PERIOD_M30: return "M30";
      case PERIOD_H1:  return "H1";
      case PERIOD_H4:  return "H4";
      case PERIOD_D1:  return "D1";
      case PERIOD_W1:  return "W1";
      case PERIOD_MN1: return "MN";
      default:         return "?";
   }
}

// Determine trend on any timeframe using a simple swing-based method:
// compare current price to a rolling N-bar high/low.
ENUM_TREND_STATE GetTFTrend(ENUM_TIMEFRAMES tf, int lookback = 20)
{
   double hi[], lo[], cl[];
   if(CopyHigh (_Symbol, tf, 0, lookback + 1, hi) < lookback + 1) return TREND_NEUTRAL;
   if(CopyLow  (_Symbol, tf, 0, lookback + 1, lo) < lookback + 1) return TREND_NEUTRAL;
   if(CopyClose(_Symbol, tf, 0, 1, cl)             < 1)           return TREND_NEUTRAL;

   double rangeHigh = hi[ArrayMaximum(hi, 1, lookback)];
   double rangeLow  = lo[ArrayMinimum(lo, 1, lookback)];
   double mid       = (rangeHigh + rangeLow) * 0.5;

   if(cl[0] > mid && cl[0] > rangeLow  + (rangeHigh - rangeLow) * 0.6) return TREND_UP;
   if(cl[0] < mid && cl[0] < rangeHigh - (rangeHigh - rangeLow) * 0.6) return TREND_DOWN;
   return TREND_NEUTRAL;
}

// Delete all dashboard objects
void DeleteDashboard()
{
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
   {
      string n = ObjectName(0, i, 0, -1);
      if(StringFind(n, DASH_PFX) == 0) ObjectDelete(0, n);
   }
}

// Draw or refresh the dashboard panel
void DrawDashboard()
{
   if(!InpShowDashboard) return;

   int tfCount  = 5;
   int rowH     = 22;
   int colW     = 58;
   int padX     = 8;
   int padY     = 6;
   int panelW   = padX * 2 + tfCount * colW;
   int panelH   = padY * 2 + rowH * 2 + 4;
   int x        = InpDashX;
   int y        = InpDashY;

   // Background panel
   string bg = DASH_PFX + "BG";
   if(ObjectFind(0, bg) < 0)
   {
      ObjectCreate    (0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, bg, OBJPROP_XSIZE,     panelW);
      ObjectSetInteger(0, bg, OBJPROP_YSIZE,     panelH);
      ObjectSetInteger(0, bg, OBJPROP_BGCOLOR,   InpDashBgColor);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_COLOR,     C'50,50,70');
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, bg, OBJPROP_HIDDEN,    true);
   }

   // Title label
   string title = DASH_PFX + "TITLE";
   if(ObjectFind(0, title) < 0)
   {
      ObjectCreate    (0, title, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, title, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, title, OBJPROP_XDISTANCE, x + padX);
      ObjectSetInteger(0, title, OBJPROP_YDISTANCE, y + padY);
      ObjectSetString (0, title, OBJPROP_TEXT,      "SMC BIAS");
      ObjectSetString (0, title, OBJPROP_FONT,      "Arial Bold");
      ObjectSetInteger(0, title, OBJPROP_FONTSIZE,  8);
      ObjectSetInteger(0, title, OBJPROP_COLOR,     InpDashTextColor);
      ObjectSetInteger(0, title, OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, title, OBJPROP_HIDDEN,    true);
   }

   // Per-TF columns
   for(int col = 0; col < tfCount; col++)
   {
      ENUM_TIMEFRAMES  tf     = DashTFs[col];
      ENUM_TREND_STATE trend  = (tf == _Period) ? g_trend : GetTFTrend(tf);

      string trendStr = (trend == TREND_UP)   ? "▲ UP"
                      : (trend == TREND_DOWN) ? "▼ DN"
                      :                         "◆ NT";
      color  trendClr = (trend == TREND_UP)   ? InpDashUpColor
                      : (trend == TREND_DOWN) ? InpDashDownColor
                      :                         InpDashNeutColor;

      int cx = x + padX + col * colW;
      int ty = y + padY + rowH;

      // TF label
      string tfLbl = DASH_PFX + "TF_" + (string)col;
      if(ObjectFind(0, tfLbl) < 0)
         ObjectCreate(0, tfLbl, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, tfLbl, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, tfLbl, OBJPROP_XDISTANCE, cx);
      ObjectSetInteger(0, tfLbl, OBJPROP_YDISTANCE, ty);
      ObjectSetString (0, tfLbl, OBJPROP_TEXT,      TFName(tf));
      ObjectSetString (0, tfLbl, OBJPROP_FONT,      "Arial");
      ObjectSetInteger(0, tfLbl, OBJPROP_FONTSIZE,  8);
      ObjectSetInteger(0, tfLbl, OBJPROP_COLOR,     InpDashTextColor);
      ObjectSetInteger(0, tfLbl, OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, tfLbl, OBJPROP_HIDDEN,    true);

      // Trend badge
      string badge = DASH_PFX + "BIAS_" + (string)col;
      if(ObjectFind(0, badge) < 0)
         ObjectCreate(0, badge, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, badge, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, badge, OBJPROP_XDISTANCE, cx);
      ObjectSetInteger(0, badge, OBJPROP_YDISTANCE, ty + rowH - 4);
      ObjectSetString (0, badge, OBJPROP_TEXT,      trendStr);
      ObjectSetString (0, badge, OBJPROP_FONT,      "Arial Bold");
      ObjectSetInteger(0, badge, OBJPROP_FONTSIZE,  8);
      ObjectSetInteger(0, badge, OBJPROP_COLOR,     trendClr);
      ObjectSetInteger(0, badge, OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, badge, OBJPROP_HIDDEN,    true);
   }

   ChartRedraw(0);
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
   // Require enough bars to detect a confirmed swing
   if(rates_total < InpSwingLen * 2 + 1)
      return 0;

   // On full recalc, wipe all objects and reset state
   if(prev_calculated <= 0)
   {
      DeleteAllObjects();
      DeleteDashboard();

      g_trend          = TREND_NEUTRAL;
      g_swingHead      = 0;
      g_swingCount     = 0;
      g_lastSwHigh     = 0.0;
      g_lastSwLow      = DBL_MAX;
      g_lastSwHighTime = 0;
      g_lastSwLowTime  = 0;
      g_obCandidateBar = -1;
      g_fvgCount       = 0;
      g_obCount        = 0;
      g_ote.active     = false;
      g_pd.active      = false;
      g_idmCount       = 0;
      g_eqCount        = 0;

      g_mtf.trend          = TREND_NEUTRAL;
      g_mtf.lastSwHigh     = 0.0;
      g_mtf.lastSwLow      = DBL_MAX;
      g_mtf.lastSwHighTime = 0;
      g_mtf.lastSwLowTime  = 0;
      g_mtf.obCandidateIdx = -1;
      g_htfCount           = 0;
      g_htfLastTime        = 0;
   }

   // Lower bound: need InpSwingLen bars on each side for pivot confirmation
   //              and at least 2 bars back for 3-candle FVG check.
   int minStart = MathMax(InpSwingLen, 2);
   int start    = (prev_calculated <= 0)
                  ? minStart
                  : MathMax(minStart, prev_calculated - InpSwingLen - 1);

   // Upper bound: confirmed pivots only available up to this bar
   int limit = rates_total - 1 - InpSwingLen;

   for(int i = start; i <= limit; i++)
   {
      ProcessSwings   (i, rates_total, time, open, high, low, close, prev_calculated);
      ProcessFVG      (i, time, high, low);
      UpdateFVGMitigation(i, time, high, low, close);
      UpdateOBMitigation (i, time, high, low);
      ProcessIDM      (i, time, high, low);
      UpdateIDMMitigation(i, high, low);
      ProcessEqualHighsLows(i, time, high, low);
      ProcessSweeps   (i, time, high, low, close);
      ProcessOTE      (i, time, high, low, close);
   }

   // MTF overlay runs once per tick (self-throttled by HTF bar change check)
   ProcessMTF();

   // Dashboard redraws every tick (cheap label updates)
   DrawDashboard();

   return rates_total;
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessMTF
//   Fetches the latest HTF bars, then runs pivot + BoS/ChoCh detection on them.
//   Called once per OnCalculate tick (outside the per-LTF-bar loop).
//   Only reprocesses when a new HTF bar has closed.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessMTF()
{
   if(!InpShowMTF) return;
   if(InpMTFTimeframe <= _Period) return;   // HTF must be higher than current TF

   // Fetch HTF bars (newest first from CopyRates, then flip to oldest-first)
   int needed = InpMTFSwingLen * 2 + 50;
   MqlRates tmp[];
   int copied = CopyRates(_Symbol, InpMTFTimeframe, 0, needed, tmp);
   if(copied < InpMTFSwingLen * 2 + 1) return;

   // Check if HTF has a new bar since last run
   datetime newTime = tmp[0].time;
   if(newTime == g_htfLastTime && g_htfCount > 0) return;
   g_htfLastTime = newTime;

   // Reverse into chronological order (index 0 = oldest)
   int n = copied;
   ArrayResize(g_htfRates, n);
   for(int k = 0; k < n; k++)
      g_htfRates[k] = tmp[n - 1 - k];
   g_htfCount = n;

   // Re-run full HTF structure scan from scratch each time (small array, cheap)
   g_mtf.trend          = TREND_NEUTRAL;
   g_mtf.lastSwHigh     = 0.0;
   g_mtf.lastSwLow      = DBL_MAX;
   g_mtf.lastSwHighTime = 0;
   g_mtf.lastSwLowTime  = 0;
   g_mtf.obCandidateIdx = -1;

   int htfLimit = n - 1 - InpMTFSwingLen;

   for(int i = InpMTFSwingLen; i <= htfLimit; i++)
      CheckMTFPivot(i, n);
}

// ─────────────────────────────────────────────────────────────────────────────
// CheckMTFPivot  –  mirrors ProcessSwings logic but operates on g_htfRates[]
// ─────────────────────────────────────────────────────────────────────────────
void CheckMTFPivot(int i, int total)
{
   bool isPivotHigh = true;
   bool isPivotLow  = true;

   for(int k = 1; k <= InpMTFSwingLen; k++)
   {
      if(g_htfRates[i-k].high >= g_htfRates[i].high) isPivotHigh = false;
      if(g_htfRates[i-k].low  <= g_htfRates[i].low)  isPivotLow  = false;
      if(g_htfRates[i+k].high >= g_htfRates[i].high) isPivotHigh = false;
      if(g_htfRates[i+k].low  <= g_htfRates[i].low)  isPivotLow  = false;
      if(!isPivotHigh && !isPivotLow) break;
   }

   if(!isPivotHigh && !isPivotLow) return;

   // Update OB candidate tracking on HTF
   if(g_mtf.trend == TREND_UP || g_mtf.trend == TREND_NEUTRAL)
      if(g_htfRates[i].close < g_htfRates[i].open) g_mtf.obCandidateIdx = i;
   if(g_mtf.trend == TREND_DOWN || g_mtf.trend == TREND_NEUTRAL)
      if(g_htfRates[i].close >= g_htfRates[i].open) g_mtf.obCandidateIdx = i;

   // Seed references if not yet set
   if(g_mtf.lastSwHigh == 0.0 && g_mtf.lastSwLow == DBL_MAX)
   {
      if(isPivotHigh) { g_mtf.lastSwHigh = g_htfRates[i].high; g_mtf.lastSwHighTime = g_htfRates[i].time; }
      if(isPivotLow)  { g_mtf.lastSwLow  = g_htfRates[i].low;  g_mtf.lastSwLowTime  = g_htfRates[i].time; }
      return;
   }

   int breakBar = i + InpMTFSwingLen;
   if(breakBar >= total) return;

   double breakClose = g_htfRates[breakBar].close;

   bool bullBreak = (breakClose > g_mtf.lastSwHigh && g_mtf.lastSwHigh > 0.0);
   bool bearBreak = (breakClose < g_mtf.lastSwLow  && g_mtf.lastSwLow  < DBL_MAX);
   if(!bullBreak && !bearBreak) return;

   bool isBullish = bullBreak;
   bool isChoCh   = false;

   if(g_mtf.trend == TREND_NEUTRAL)
   {
      if(bullBreak) g_mtf.trend = TREND_UP;
      else          g_mtf.trend = TREND_DOWN;
   }
   else if(g_mtf.trend == TREND_UP)
   {
      isChoCh = bearBreak;
      if(bearBreak) g_mtf.trend = TREND_DOWN;
   }
   else
   {
      isChoCh = bullBreak;
      if(bullBreak) g_mtf.trend = TREND_UP;
   }

   // Draw HTF structure line on the current (LTF) chart
   datetime t1 = isBullish ? g_mtf.lastSwHighTime : g_mtf.lastSwLowTime;
   double   p1 = isBullish ? g_mtf.lastSwHigh     : g_mtf.lastSwLow;
   datetime t2 = g_htfRates[breakBar].time;
   double   p2 = p1;

   string htfLabel = isChoCh ? "HTF-ChoCh" : "HTF-BoS";
   color  htfClr   = isChoCh ? InpMTFChoCHColor : InpMTFBoSColor;
   ENUM_LINE_STYLE htfStyle = isChoCh ? STYLE_SOLID : STYLE_DOT;

   string name = OBJ_PFX + "MTF_" + htfLabel + "_" + Key(t2);
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate    (0, name, OBJ_TREND, 0, t1, p1, t2, p2);
      ObjectSetInteger(0, name, OBJPROP_COLOR,      htfClr);
      ObjectSetInteger(0, name, OBJPROP_STYLE,      htfStyle);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,      InpMTFLineWidth);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT,  false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);

      string lname = name + "_L";
      ObjectCreate    (0, lname, OBJ_TEXT, 0, t2, p2);
      ObjectSetString (0, lname, OBJPROP_TEXT,       htfLabel);
      ObjectSetInteger(0, lname, OBJPROP_COLOR,      htfClr);
      ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   9);
      ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lname, OBJPROP_HIDDEN,     true);
   }

   // Update HTF swing references
   if(isBullish) { g_mtf.lastSwHigh = g_htfRates[i].high; g_mtf.lastSwHighTime = g_htfRates[i].time; }
   else          { g_mtf.lastSwLow  = g_htfRates[i].low;  g_mtf.lastSwLowTime  = g_htfRates[i].time; }
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessSwings
//   Confirms pivot highs/lows at bar [i] (look-right already elapsed).
//   Then checks for BoS or ChoCh against the prevailing trend.
//   Also registers the OB candidate = last opposing candle before the break.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessSwings(int i, int total,
                   const datetime &time[], const double &open[],
                   const double &high[],  const double &low[],
                   const double &close[], int prevCalc)
{
   // ── 1. Confirm pivot high at bar [i] ────────────────────────────────────
   bool isPivotHigh = true;
   bool isPivotLow  = true;

   for(int k = 1; k <= InpSwingLen; k++)
   {
      if(high[i - k] >= high[i]) isPivotHigh = false;
      if(low [i - k] <= low [i]) isPivotLow  = false;
      if(high[i + k] >= high[i]) isPivotHigh = false;
      if(low [i + k] <= low [i]) isPivotLow  = false;
      if(!isPivotHigh && !isPivotLow) break;
   }

   if(!isPivotHigh && !isPivotLow) return;

   // ── 2. Store confirmed swing in ring buffer ──────────────────────────────
   if(isPivotHigh)
   {
      SwingPoint sp;
      sp.time      = time[i];
      sp.price     = high[i];
      sp.isHigh    = true;
      sp.confirmed = true;
      g_swings[g_swingHead % SWING_HIST] = sp;
      g_swingHead++;
      if(g_swingCount < SWING_HIST) g_swingCount++;
   }

   if(isPivotLow)
   {
      SwingPoint sp;
      sp.time      = time[i];
      sp.price     = low[i];
      sp.isHigh    = false;
      sp.confirmed = true;
      g_swings[g_swingHead % SWING_HIST] = sp;
      g_swingHead++;
      if(g_swingCount < SWING_HIST) g_swingCount++;
   }

   // ── 3. We check structure breaks at bar [i + InpSwingLen] (the current   ──
   //       "live" bar that sees the close past the pivot).                     ──
   //       This function is called at the pivot bar itself; the actual break   ──
   //       check below uses the most recent close = close[i + InpSwingLen].    ──
   int breakBar = i + InpSwingLen;

   // ── 4. Update pending OB candidate ──────────────────────────────────────
   // The OB is the last candle opposing the expected break direction just
   // before price actually breaks. We track it as we step forward.
   // Here we simply record the most recent opposing candle relative to trend.
   if(g_trend == TREND_UP || g_trend == TREND_NEUTRAL)
   {
      // In uptrend look for last bearish candle as potential OB before bull BoS
      if(close[i] < open[i])
         g_obCandidateBar = i;
   }
   if(g_trend == TREND_DOWN || g_trend == TREND_NEUTRAL)
   {
      if(close[i] >= open[i])
         g_obCandidateBar = i;
   }

   // ── 5. Structure break detection ────────────────────────────────────────
   // We need a valid reference swing to compare against.
   if(g_lastSwHigh == 0.0 && g_lastSwLow == DBL_MAX)
   {
      // Seed the first references from confirmed pivots
      if(isPivotHigh) { g_lastSwHigh = high[i]; g_lastSwHighTime = time[i]; }
      if(isPivotLow)  { g_lastSwLow  = low[i];  g_lastSwLowTime  = time[i]; }
      return;
   }

   double breakClose = close[breakBar];

   bool bullBreak = (breakClose > g_lastSwHigh && g_lastSwHigh > 0.0);
   bool bearBreak = (breakClose < g_lastSwLow  && g_lastSwLow  < DBL_MAX);

   if(!bullBreak && !bearBreak) return;

   bool isChoCh = false;
   bool isBullish = bullBreak;

   // Determine BoS vs ChoCh based on current trend
   if(g_trend == TREND_NEUTRAL)
   {
      isChoCh = false;  // first break just establishes trend
      if(bullBreak) g_trend = TREND_UP;
      else          g_trend = TREND_DOWN;
   }
   else if(g_trend == TREND_UP)
   {
      isChoCh = bearBreak;   // break below low while in uptrend = ChoCh
      if(bearBreak) g_trend = TREND_DOWN;
   }
   else // TREND_DOWN
   {
      isChoCh = bullBreak;   // break above high while in downtrend = ChoCh
      if(bullBreak) g_trend = TREND_UP;
   }

   // ── 6. Draw structure line ───────────────────────────────────────────────
   bool drawObj = (prevCalc <= 0)
                  ? (breakBar >= total - 1 - MAX_OBJ_HIST)
                  : true;

   if(drawObj)
   {
      datetime t1 = isBullish ? g_lastSwHighTime : g_lastSwLowTime;
      double   p1 = isBullish ? g_lastSwHigh     : g_lastSwLow;
      datetime t2 = time[breakBar];
      double   p2 = isBullish ? g_lastSwHigh     : g_lastSwLow;

      if(isChoCh && InpShowChoCh)
         DrawStructureLine("CHOCH", t1, p1, t2, p2, InpChoCHColor, STYLE_SOLID, time[breakBar]);
      else if(!isChoCh && InpShowBoS)
         DrawStructureLine("BOS",   t1, p1, t2, p2, InpBoSColor,   STYLE_DOT,   time[breakBar]);
   }

   // ── 7. Register Order Block linked to this break ─────────────────────────
   if(InpShowOB && g_obCandidateBar >= 0 && drawObj)
   {
      int ob = g_obCandidateBar;
      RegisterOrderBlock(ob, isBullish, time, open, high, low);
      g_obCandidateBar = -1;
   }

   // ── 8. Update OTE after a ChoCh ─────────────────────────────────────────
   if(isChoCh && InpShowOTE)
      UpdateOTEAfterChoCh(isBullish, time[breakBar]);

   // ── 8b. Update Premium/Discount after every structural break ────────────
   if(drawObj)
      UpdatePremiumDiscount(time[breakBar]);

   // ── 9. Update swing reference levels ────────────────────────────────────
   if(isBullish)
   {
      g_lastSwHigh     = high[i];
      g_lastSwHighTime = time[i];
   }
   else
   {
      g_lastSwLow     = low[i];
      g_lastSwLowTime = time[i];
   }

   // ── 10. Alert ────────────────────────────────────────────────────────────
   bool doAlert = isChoCh ? InpAlertChoCh : InpAlertBoS;
   if(doAlert && (!InpAlertBarClose || prevCalc > 0))
   {
      string tag    = isChoCh ? "ChoCh" : "BoS";
      string detail = StringFormat("%s @ %.5f", isBullish ? "Bullish" : "Bearish", breakClose);
      TriggerAlert(tag, detail);
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// DrawStructureLine  –  OBJ_TREND horizontal ray from pivot to break bar
// ─────────────────────────────────────────────────────────────────────────────
void DrawStructureLine(const string tag,
                       datetime t1, double p1,
                       datetime t2, double p2,
                       color    clr,
                       ENUM_LINE_STYLE style,
                       datetime anchor)
{
   string name = OBJ_PFX + tag + "_" + Key(anchor);
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate      (0, name, OBJ_TREND, 0, t1, p1, t2, p2);
   ObjectSetInteger  (0, name, OBJPROP_COLOR,     clr);
   ObjectSetInteger  (0, name, OBJPROP_STYLE,     style);
   ObjectSetInteger  (0, name, OBJPROP_WIDTH,     InpStructLineWidth);
   ObjectSetInteger  (0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger  (0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger  (0, name, OBJPROP_HIDDEN,    true);

   // Text label at the right end
   string lname = name + "_L";
   ObjectCreate    (0, lname, OBJ_TEXT, 0, t2, p2);
   ObjectSetString (0, lname, OBJPROP_TEXT,      tag);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,  8);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,    true);
}

// ─────────────────────────────────────────────────────────────────────────────
// RegisterOrderBlock  –  adds a new OB to the active array
// ─────────────────────────────────────────────────────────────────────────────
void RegisterOrderBlock(int bar, bool bullish,
                        const datetime &time[],
                        const double   &open[],
                        const double   &high[],
                        const double   &low[])
{
   // Evict oldest if at capacity
   if(g_obCount >= InpMaxOBs)
   {
      ObjectDelete(0, g_ob[0].objName);
      ObjectDelete(0, g_ob[0].objName + "_L");
      for(int k = 0; k < g_obCount - 1; k++) g_ob[k] = g_ob[k + 1];
      g_obCount--;
   }

   OrderBlock ob;
   ob.timeStart  = time[bar];
   ob.timeEnd    = time[bar] + (datetime)(PeriodSeconds(_Period) * 20); // initial width
   ob.top        = high[bar];
   ob.bottom     = low[bar];
   ob.bodyTop    = MathMax(open[bar], close_approx(bar));
   ob.bodyBottom = MathMin(open[bar], close_approx(bar));
   ob.bullish    = bullish;
   ob.mitigated  = false;
   ob.objName    = OBJ_PFX + "OB_" + (bullish ? "B" : "R") + "_" + Key(time[bar]);

   color clr = bullish ? InpOBBullColor : InpOBBearColor;
   DrawZoneRect(ob.objName, ob.timeStart, ob.timeEnd, ob.top, ob.bottom, clr, InpOBAlpha);

   string lname = ob.objName + "_L";
   string ltext = bullish ? "OB+" : "OB-";
   ObjectCreate    (0, lname, OBJ_TEXT, 0, ob.timeStart, ob.top);
   ObjectSetString (0, lname, OBJPROP_TEXT,      ltext);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,  8);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,    true);

   g_ob[g_obCount++] = ob;
}

// Helper – returns open[bar] as a stand-in for close when close[] not in scope.
// The real close is passed in via ProcessSwings; here we use the open as a
// conservative body approximation. Full body uses open vs close from arrays.
double close_approx(int bar) { return iClose(_Symbol, _Period, bar); }

// ─────────────────────────────────────────────────────────────────────────────
// ProcessFVG
//   Detects 3-candle imbalances at bar [i] (middle candle of the trio).
//   Trio: [i-1] = left candle, [i] = impulse, [i+1] = right candle.
//   Called at bar [i] where i is the middle (impulse) candle.
//   FVG condition checked at i-1 (left) vs i+1 (right).
//   Actually the classic check: left candle vs right candle gap.
//     Bullish FVG: high[i-1] < low[i+1]  → gap between those two
//     Bearish FVG: low[i-1]  > high[i+1]
//   We call this when bar [i+1] has just been confirmed so trio is complete.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessFVG(int i, const datetime &time[],
                const double &high[], const double &low[])
{
   if(!InpShowFVG) return;
   if(i < 1) return;   // need [i-1], [i], [i+1] — caller already bounds-checked

   // Check bullish FVG: gap between candle[i-2] high and candle[i] low
   if(high[i - 2] < low[i])
   {
      double gapTop    = low[i];
      double gapBottom = high[i - 2];
      if(gapTop > gapBottom)
         AddFVG(time[i - 1], gapTop, gapBottom, true);
   }

   // Check bearish FVG: gap between candle[i-2] low and candle[i] high
   if(low[i - 2] > high[i])
   {
      double gapTop    = low[i - 2];
      double gapBottom = high[i];
      if(gapTop > gapBottom)
         AddFVG(time[i - 1], gapTop, gapBottom, false);
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// AddFVG  –  stores a new FVG and draws its rectangle
// ─────────────────────────────────────────────────────────────────────────────
void AddFVG(datetime t, double top, double bottom, bool bullish)
{
   // Evict oldest if at capacity
   if(g_fvgCount >= InpMaxFVGs)
   {
      ObjectDelete(0, g_fvg[0].objName);
      ObjectDelete(0, g_fvg[0].objName + "_L");
      for(int k = 0; k < g_fvgCount - 1; k++) g_fvg[k] = g_fvg[k + 1];
      g_fvgCount--;
   }

   FVGZone fvg;
   fvg.timeStart = t;
   fvg.timeEnd   = t + (datetime)(PeriodSeconds(_Period) * 50);
   fvg.top       = top;
   fvg.bottom    = bottom;
   fvg.bullish   = bullish;
   fvg.mitigated = false;
   fvg.objName   = OBJ_PFX + "FVG_" + (bullish ? "B" : "R") + "_" + Key(t);

   color clr = bullish ? InpFVGBullColor : InpFVGBearColor;
   DrawZoneRect(fvg.objName, fvg.timeStart, fvg.timeEnd, fvg.top, fvg.bottom, clr, InpFVGAlpha);

   // Label
   string lname = fvg.objName + "_L";
   string ltext = bullish ? "FVG+" : "FVG-";
   ObjectCreate    (0, lname, OBJ_TEXT, 0, fvg.timeStart, fvg.top);
   ObjectSetString (0, lname, OBJPROP_TEXT,      ltext);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,  7);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,    true);

   if(InpAlertFVG)
      TriggerAlert(ltext, StringFormat("Gap: %.5f – %.5f", bottom, top));

   g_fvg[g_fvgCount++] = fvg;
}

// ─────────────────────────────────────────────────────────────────────────────
// UpdateFVGMitigation
//   For each unmitigated FVG, extend its right edge to the current bar.
//   Mark as mitigated when price closes inside the gap.
// ─────────────────────────────────────────────────────────────────────────────
void UpdateFVGMitigation(int i, const datetime &time[],
                         const double &high[], const double &low[],
                         const double &close[])
{
   if(!InpShowFVG) return;

   for(int k = 0; k < g_fvgCount; k++)
   {
      if(g_fvg[k].mitigated) continue;

      // Extend right edge to current bar
      if(InpFVGMitigation)
      {
         g_fvg[k].timeEnd = time[i] + (datetime)PeriodSeconds(_Period);
         ObjectSetInteger(0, g_fvg[k].objName, OBJPROP_TIME,  1, (long)g_fvg[k].timeEnd);
      }

      // Mitigation: close inside the gap
      bool filled = g_fvg[k].bullish
                    ? (close[i] <= g_fvg[k].top && close[i] >= g_fvg[k].bottom)
                    : (close[i] >= g_fvg[k].bottom && close[i] <= g_fvg[k].top);

      // Also mitigated if price crosses fully through the gap
      bool crossedThrough = g_fvg[k].bullish
                            ? (low[i]  <= g_fvg[k].bottom)
                            : (high[i] >= g_fvg[k].top);

      if(filled || crossedThrough)
      {
         g_fvg[k].mitigated = true;
         // Fade the zone by making it semi-transparent grey
         ObjectSetInteger(0, g_fvg[k].objName, OBJPROP_COLOR, clrDarkGray);
         ObjectSetInteger(0, g_fvg[k].objName, OBJPROP_FILL,  false);
         ObjectSetString (0, g_fvg[k].objName + "_L", OBJPROP_TEXT,
                          g_fvg[k].bullish ? "FVG+ ✓" : "FVG- ✓");
      }
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// UpdateOBMitigation
//   Extend each OB's right edge to the current bar.
//   Mark as mitigated when price enters the OB body zone.
// ─────────────────────────────────────────────────────────────────────────────
void UpdateOBMitigation(int i, const datetime &time[],
                        const double &high[], const double &low[])
{
   if(!InpShowOB) return;

   for(int k = 0; k < g_obCount; k++)
   {
      if(g_ob[k].mitigated) continue;

      // Extend right edge
      if(InpOBMitigation)
      {
         g_ob[k].timeEnd = time[i] + (datetime)PeriodSeconds(_Period);
         ObjectSetInteger(0, g_ob[k].objName, OBJPROP_TIME, 1, (long)g_ob[k].timeEnd);
      }

      // Mitigated when price wicks into the OB body
      bool entered = g_ob[k].bullish
                     ? (low[i]  <= g_ob[k].bodyTop)
                     : (high[i] >= g_ob[k].bodyBottom);

      if(entered)
      {
         g_ob[k].mitigated = true;
         ObjectSetInteger(0, g_ob[k].objName, OBJPROP_COLOR, clrDarkGray);
         ObjectSetInteger(0, g_ob[k].objName, OBJPROP_FILL,  false);
         ObjectSetString (0, g_ob[k].objName + "_L", OBJPROP_TEXT,
                          g_ob[k].bullish ? "OB+ ✓" : "OB- ✓");
      }
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// UpdatePremiumDiscount
//   Called whenever g_lastSwHigh or g_lastSwLow updates (i.e. after each BoS).
//   Draws three zones: Premium (above 50%), Equilibrium line, Discount (below 50%).
//   Zones extend rightward until the next BoS overwrites them.
// ─────────────────────────────────────────────────────────────────────────────
void UpdatePremiumDiscount(datetime anchor)
{
   if(!InpShowPD) return;

   double hi = g_lastSwHigh;
   double lo = g_lastSwLow;
   if(hi <= 0.0 || lo >= DBL_MAX || hi <= lo) return;

   // Remove previous P/D objects
   if(g_pd.active)
   {
      string k = Key(g_pd.originTime);
      ObjectDelete(0, OBJ_PFX + "PD_PREM_"  + k);
      ObjectDelete(0, OBJ_PFX + "PD_DISC_"  + k);
      ObjectDelete(0, OBJ_PFX + "PD_EQ_"    + k);
      ObjectDelete(0, OBJ_PFX + "PD_EQ_L_"  + k);
      ObjectDelete(0, OBJ_PFX + "PD_PREM_L_"+ k);
      ObjectDelete(0, OBJ_PFX + "PD_DISC_L_"+ k);
   }

   double eq    = (hi + lo) * 0.5;
   datetime t2  = anchor + (datetime)(PeriodSeconds(_Period) * 200);
   string   k   = Key(anchor);

   // Premium zone (above equilibrium)
   DrawZoneRect(OBJ_PFX + "PD_PREM_" + k, anchor, t2, hi, eq, InpPremiumColor, InpPDAlpha);
   // Discount zone (below equilibrium)
   DrawZoneRect(OBJ_PFX + "PD_DISC_" + k, anchor, t2, eq, lo, InpDiscountColor, InpPDAlpha);

   // Equilibrium dashed line
   string eqLine = OBJ_PFX + "PD_EQ_" + k;
   ObjectCreate    (0, eqLine, OBJ_TREND, 0, anchor, eq, t2, eq);
   ObjectSetInteger(0, eqLine, OBJPROP_COLOR,     InpEqColor);
   ObjectSetInteger(0, eqLine, OBJPROP_STYLE,     STYLE_DASH);
   ObjectSetInteger(0, eqLine, OBJPROP_WIDTH,     1);
   ObjectSetInteger(0, eqLine, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, eqLine, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, eqLine, OBJPROP_HIDDEN,    true);

   // Labels
   string eqLbl = OBJ_PFX + "PD_EQ_L_" + k;
   ObjectCreate    (0, eqLbl, OBJ_TEXT, 0, anchor + (datetime)(PeriodSeconds(_Period) * 3), eq);
   ObjectSetString (0, eqLbl, OBJPROP_TEXT,       "EQ 50%");
   ObjectSetInteger(0, eqLbl, OBJPROP_COLOR,      InpEqColor);
   ObjectSetInteger(0, eqLbl, OBJPROP_FONTSIZE,   7);
   ObjectSetInteger(0, eqLbl, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, eqLbl, OBJPROP_HIDDEN,     true);

   string premLbl = OBJ_PFX + "PD_PREM_L_" + k;
   ObjectCreate    (0, premLbl, OBJ_TEXT, 0, anchor + (datetime)(PeriodSeconds(_Period) * 3), (hi + eq) * 0.5);
   ObjectSetString (0, premLbl, OBJPROP_TEXT,       "PREMIUM");
   ObjectSetInteger(0, premLbl, OBJPROP_COLOR,      InpPremiumColor);
   ObjectSetInteger(0, premLbl, OBJPROP_FONTSIZE,   7);
   ObjectSetInteger(0, premLbl, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, premLbl, OBJPROP_HIDDEN,     true);

   string discLbl = OBJ_PFX + "PD_DISC_L_" + k;
   ObjectCreate    (0, discLbl, OBJ_TEXT, 0, anchor + (datetime)(PeriodSeconds(_Period) * 3), (lo + eq) * 0.5);
   ObjectSetString (0, discLbl, OBJPROP_TEXT,       "DISCOUNT");
   ObjectSetInteger(0, discLbl, OBJPROP_COLOR,      InpDiscountColor);
   ObjectSetInteger(0, discLbl, OBJPROP_FONTSIZE,   7);
   ObjectSetInteger(0, discLbl, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, discLbl, OBJPROP_HIDDEN,     true);

   g_pd.rangeHigh  = hi;
   g_pd.rangeLow   = lo;
   g_pd.eq50       = eq;
   g_pd.active     = true;
   g_pd.originTime = anchor;
}

// ─────────────────────────────────────────────────────────────────────────────
// DrawZoneRect  –  filled rectangle common to FVG and OB drawing
// ─────────────────────────────────────────────────────────────────────────────
void DrawZoneRect(const string name,
                  datetime t1, datetime t2,
                  double top,  double bottom,
                  color clr,   int alpha)
{
   if(ObjectFind(0, name) >= 0) return;

   // MT5 uses ARGB for filled objects; blend the alpha into the colour
   color fillClr = AlphaColor(clr, alpha);

   ObjectCreate    (0, name, OBJ_RECTANGLE, 0, t1, top, t2, bottom);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     fillClr);
   ObjectSetInteger(0, name, OBJPROP_FILL,      true);
   ObjectSetInteger(0, name, OBJPROP_BACK,      true);
   ObjectSetInteger(0, name, OBJPROP_STYLE,     STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,     1);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,    true);
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessIDM  –  Inducement Levels
//   An IDM is the first minor swing that forms in the pullback direction
//   after a confirmed BoS / ChoCh. It marks the liquidity resting just above
//   a bullish OB (or below a bearish OB) that price is likely to sweep before
//   continuing in the impulse direction.
//
//   Detection: a small pivot (InpIDMSwingLen) that forms between the last
//   structural break and the most recent OB zone.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessIDM(int i, const datetime &time[],
                const double &high[], const double &low[])
{
   if(!InpShowIDM) return;
   if(i < InpIDMSwingLen) return;

   // Only look for IDMs when we have an active trend and at least one OB
   if(g_trend == TREND_NEUTRAL || g_obCount == 0) return;

   // In uptrend: IDM is a minor swing HIGH that forms in the retracement,
   //             sitting above the most recent bullish OB top.
   // In downtrend: IDM is a minor swing LOW below the most recent bearish OB bottom.
   bool lookHigh = (g_trend == TREND_DOWN);
   bool lookLow  = (g_trend == TREND_UP);

   bool isPivot = true;
   for(int k = 1; k <= InpIDMSwingLen; k++)
   {
      if(lookHigh)
      {
         if(high[i - k] >= high[i] || high[i + k] >= high[i]) { isPivot = false; break; }
      }
      else
      {
         if(low[i - k] <= low[i] || low[i + k] <= low[i]) { isPivot = false; break; }
      }
   }
   if(!isPivot) return;

   // The IDM must sit between the last BoS/ChoCh time and the last active OB
   OrderBlock lastOB = g_ob[g_obCount - 1];
   if(time[i] <= lastOB.timeStart) return;  // IDM must be newer than the OB

   // Avoid duplicate IDM at the same price
   double idmPrice = lookHigh ? high[i] : low[i];
   for(int k = 0; k < g_idmCount; k++)
      if(MathAbs(g_idm[k].price - idmPrice) < _Point * 2) return;

   // Evict oldest
   if(g_idmCount >= MAX_IDM)
   {
      ObjectDelete(0, g_idm[0].objName);
      ObjectDelete(0, g_idm[0].objName + "_L");
      for(int k = 0; k < g_idmCount - 1; k++) g_idm[k] = g_idm[k + 1];
      g_idmCount--;
   }

   string name = OBJ_PFX + "IDM_" + Key(time[i]);

   // Draw a dashed horizontal line at the IDM level
   datetime t2 = time[i] + (datetime)(PeriodSeconds(_Period) * 60);
   ObjectCreate    (0, name, OBJ_TREND, 0, time[i], idmPrice, t2, idmPrice);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     InpIDMColor);
   ObjectSetInteger(0, name, OBJPROP_STYLE,     STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,     1);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,    true);

   string lname = name + "_L";
   ObjectCreate    (0, lname, OBJ_TEXT, 0, time[i], idmPrice);
   ObjectSetString (0, lname, OBJPROP_TEXT,       "IDM");
   ObjectSetInteger(0, lname, OBJPROP_COLOR,      InpIDMColor);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   7);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,     true);

   IDMLevel idm;
   idm.time    = time[i];
   idm.price   = idmPrice;
   idm.isHigh  = lookHigh;
   idm.hit     = false;
   idm.objName = name;
   g_idm[g_idmCount++] = idm;
}

// ─────────────────────────────────────────────────────────────────────────────
// UpdateIDMMitigation  –  mark IDM as hit when price touches the level
// ─────────────────────────────────────────────────────────────────────────────
void UpdateIDMMitigation(int i, const double &high[], const double &low[])
{
   if(!InpShowIDM) return;
   for(int k = 0; k < g_idmCount; k++)
   {
      if(g_idm[k].hit) continue;
      bool touched = g_idm[k].isHigh ? (high[i] >= g_idm[k].price)
                                      : (low[i]  <= g_idm[k].price);
      if(touched)
      {
         g_idm[k].hit = true;
         ObjectSetInteger(0, g_idm[k].objName, OBJPROP_COLOR, clrDarkGray);
         ObjectSetString (0, g_idm[k].objName + "_L", OBJPROP_TEXT, "IDM ✓");
      }
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessEqualHighsLows
//   Scans the swing ring-buffer for pairs of swing highs (or lows) whose
//   prices are within InpEQTolerance points of each other.
//   Draws a dashed line connecting them and labels "EQH" or "EQL".
//   Only checks the most recent swing against the prior InpEQLookback bars.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessEqualHighsLows(int i, const datetime &time[],
                           const double &high[], const double &low[])
{
   if(!InpShowEQ) return;
   if(g_swingCount < 2) return;

   double tol = InpEQTolerance * _Point;

   // Get the latest confirmed swing from the ring buffer
   int latestIdx = (g_swingHead - 1 + SWING_HIST) % SWING_HIST;
   SwingPoint latest = g_swings[latestIdx];

   // Compare against previous swings of the same type within lookback
   int checked = 0;
   for(int k = 2; k <= g_swingCount && checked < InpEQLookback; k++, checked++)
   {
      int priorIdx = (g_swingHead - k + SWING_HIST) % SWING_HIST;
      SwingPoint prior = g_swings[priorIdx];

      if(prior.isHigh != latest.isHigh) continue;  // must be same type
      if(MathAbs(prior.price - latest.price) > tol) continue;

      // Check we haven't already drawn this pair
      string name = OBJ_PFX + "EQ_" + Key(prior.time) + "_" + Key(latest.time);
      if(ObjectFind(0, name) >= 0) continue;

      // Evict oldest EQ if at capacity
      if(g_eqCount >= MAX_EQ)
      {
         ObjectDelete(0, g_eq[0].objName);
         ObjectDelete(0, g_eq[0].objName + "_L");
         for(int j = 0; j < g_eqCount - 1; j++) g_eq[j] = g_eq[j + 1];
         g_eqCount--;
      }

      color  clr  = latest.isHigh ? InpEQHColor : InpEQLColor;
      string lbl  = latest.isHigh ? "EQH" : "EQL";

      ObjectCreate    (0, name, OBJ_TREND, 0, prior.time, prior.price, latest.time, latest.price);
      ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE,     STYLE_DASH);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,     1);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN,    true);

      string lname = name + "_L";
      ObjectCreate    (0, lname, OBJ_TEXT, 0, latest.time, latest.price);
      ObjectSetString (0, lname, OBJPROP_TEXT,       lbl);
      ObjectSetInteger(0, lname, OBJPROP_COLOR,      clr);
      ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   7);
      ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, lname, OBJPROP_HIDDEN,     true);

      EQLevel eq;
      eq.time1   = prior.time;
      eq.time2   = latest.time;
      eq.price   = (prior.price + latest.price) * 0.5;
      eq.isHigh  = latest.isHigh;
      eq.objName = name;
      g_eq[g_eqCount++] = eq;

      break;   // one match per new swing is enough
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessSweeps
//   A sweep occurs when price wicks beyond the last confirmed swing
//   extreme and the candle CLOSES back on the other side (false breakout).
// ─────────────────────────────────────────────────────────────────────────────
void ProcessSweeps(int i, const datetime &time[],
                   const double &high[], const double &low[],
                   const double &close[])
{
   if(!InpShowSweeps) return;
   if(g_lastSwHigh == 0.0 && g_lastSwLow == DBL_MAX) return;

   // Bearish sweep: wick above last swing high but close back below it
   if(g_lastSwHigh > 0.0)
   {
      if(high[i] > g_lastSwHigh && close[i] < g_lastSwHigh)
      {
         string name = OBJ_PFX + "SWP_R_" + Key(time[i]);
         DrawSweepArrow(name, time[i], high[i], false);

         if(InpAlertSweep)
            TriggerAlert("Sweep-", StringFormat("Swept %.5f | Close %.5f", g_lastSwHigh, close[i]));
      }
   }

   // Bullish sweep: wick below last swing low but close back above it
   if(g_lastSwLow < DBL_MAX)
   {
      if(low[i] < g_lastSwLow && close[i] > g_lastSwLow)
      {
         string name = OBJ_PFX + "SWP_B_" + Key(time[i]);
         DrawSweepArrow(name, time[i], low[i], true);

         if(InpAlertSweep)
            TriggerAlert("Sweep+", StringFormat("Swept %.5f | Close %.5f", g_lastSwLow, close[i]));
      }
   }
}

// ─────────────────────────────────────────────────────────────────────────────
// DrawSweepArrow  –  places an arrow + "Sweep" label on the price chart
// ─────────────────────────────────────────────────────────────────────────────
void DrawSweepArrow(const string name, datetime t, double price, bool bullish)
{
   if(ObjectFind(0, name) >= 0) return;

   double offset = _Point * 20.0 * InpSweepArrowSize;
   double y      = bullish ? price - offset : price + offset;
   int    code   = bullish ? 233 : 234;   // Wingdings up/down arrows
   color  clr    = bullish ? InpSweepBullColor : InpSweepBearColor;

   ObjectCreate      (0, name, OBJ_ARROW, 0, t, y);
   ObjectSetInteger  (0, name, OBJPROP_ARROWCODE,  code);
   ObjectSetInteger  (0, name, OBJPROP_COLOR,      clr);
   ObjectSetInteger  (0, name, OBJPROP_WIDTH,      InpSweepArrowSize);
   ObjectSetInteger  (0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger  (0, name, OBJPROP_HIDDEN,     true);

   // Text label
   string lname = name + "_L";
   ObjectCreate    (0, lname, OBJ_TEXT, 0, t, bullish ? price - offset * 2.5 : price + offset * 2.5);
   ObjectSetString (0, lname, OBJPROP_TEXT,       "Sweep");
   ObjectSetInteger(0, lname, OBJPROP_COLOR,      clr);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   8);
   ObjectSetInteger(0, lname, OBJPROP_ANCHOR,     ANCHOR_CENTER);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,     true);
}

// ─────────────────────────────────────────────────────────────────────────────
// UpdateOTEAfterChoCh
//   Called from ProcessSwings when a ChoCh is confirmed.
//   Builds the OTE zone from the most recent impulse leg.
// ─────────────────────────────────────────────────────────────────────────────
void UpdateOTEAfterChoCh(bool bullish, datetime anchor)
{
   if(!InpShowOTE) return;

   // Remove previous OTE if still active
   if(g_ote.active)
   {
      ObjectDelete(0, OBJ_PFX + "OTE_" + Key(g_ote.originTime));
      ObjectDelete(0, OBJ_PFX + "OTE_50_"  + Key(g_ote.originTime));
      ObjectDelete(0, OBJ_PFX + "OTE_618_" + Key(g_ote.originTime));
      ObjectDelete(0, OBJ_PFX + "OTE_79_"  + Key(g_ote.originTime));
   }

   g_ote.bullish    = bullish;
   g_ote.legHigh    = g_lastSwHigh;
   g_ote.legLow     = g_lastSwLow;
   g_ote.active     = false;
   g_ote.originTime = anchor;

   double range = g_ote.legHigh - g_ote.legLow;
   if(range <= 0) return;

   if(bullish)
   {
      // Bullish impulse: OTE retracement drawn from leg high down
      g_ote.ote61 = g_ote.legHigh - range * 0.618;
      g_ote.ote79 = g_ote.legHigh - range * 0.790;
      g_ote.eq50  = g_ote.legHigh - range * 0.500;
   }
   else
   {
      // Bearish impulse: OTE retracement from leg low up
      g_ote.ote61 = g_ote.legLow + range * 0.618;
      g_ote.ote79 = g_ote.legLow + range * 0.790;
      g_ote.eq50  = g_ote.legLow + range * 0.500;
   }

   g_ote.active = true;

   // Zone top/bottom
   double zoneTop    = MathMax(g_ote.ote61, g_ote.ote79);
   double zoneBottom = MathMin(g_ote.ote61, g_ote.ote79);

   // Draw OTE shaded zone
   datetime t2 = anchor + (datetime)(PeriodSeconds(_Period) * 100);
   string   zoneName = OBJ_PFX + "OTE_" + Key(anchor);
   DrawZoneRect(zoneName, anchor, t2, zoneTop, zoneBottom, InpOTEColor, InpOTEAlpha);

   // 50% equilibrium line
   DrawOTELine(OBJ_PFX + "OTE_50_"  + Key(anchor), anchor, g_ote.eq50,  "50%",   clrSilver);
   // 61.8% golden ratio line
   DrawOTELine(OBJ_PFX + "OTE_618_" + Key(anchor), anchor, g_ote.ote61, "61.8%", InpOTEColor);
   // 79% entry line
   DrawOTELine(OBJ_PFX + "OTE_79_"  + Key(anchor), anchor, g_ote.ote79, "79%",   InpOTEColor);
}

// ─────────────────────────────────────────────────────────────────────────────
// DrawOTELine  –  horizontal ray for OTE Fibonacci levels
// ─────────────────────────────────────────────────────────────────────────────
void DrawOTELine(const string name, datetime t, double price,
                 const string label, color clr)
{
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate      (0, name, OBJ_TREND, 0, t, price,
                      t + (datetime)(PeriodSeconds(_Period) * 100), price);
   ObjectSetInteger  (0, name, OBJPROP_COLOR,     clr);
   ObjectSetInteger  (0, name, OBJPROP_STYLE,     STYLE_DASH);
   ObjectSetInteger  (0, name, OBJPROP_WIDTH,     1);
   ObjectSetInteger  (0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger  (0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger  (0, name, OBJPROP_HIDDEN,    true);

   string lname = name + "_L";
   ObjectCreate    (0, lname, OBJ_TEXT, 0,
                    t + (datetime)(PeriodSeconds(_Period) * 2), price);
   ObjectSetString (0, lname, OBJPROP_TEXT,       label);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,      clr);
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   7);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lname, OBJPROP_HIDDEN,     true);
}

// ─────────────────────────────────────────────────────────────────────────────
// ProcessOTE
//   Each bar, check if price has entered the active OTE zone and fire alert.
// ─────────────────────────────────────────────────────────────────────────────
void ProcessOTE(int i, const datetime &time[],
                const double &high[], const double &low[],
                const double &close[])
{
   if(!InpShowOTE || !g_ote.active) return;

   double zoneTop    = MathMax(g_ote.ote61, g_ote.ote79);
   double zoneBottom = MathMin(g_ote.ote61, g_ote.ote79);

   bool inZone = (low[i] <= zoneTop && high[i] >= zoneBottom);
   if(inZone && InpAlertOTE)
   {
      TriggerAlert("OTE", StringFormat("%s zone %.5f–%.5f | Price %.5f",
         g_ote.bullish ? "Bullish" : "Bearish",
         zoneBottom, zoneTop, close[i]));
      g_ote.active = false;   // fire once per OTE zone
   }
}
//+------------------------------------------------------------------+
