//+------------------------------------------------------------------+
//|                                           VolumeSpike_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Expert Advisor that trades VolumeSpike indicator signals.       |
//|  Detection logic is embedded (mirrors VolumeSpike.mq5) so the   |
//|  EA is fully self-contained for the Strategy Tester.            |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.01"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enumerations (mirrors VolumeSpike.mq5)                          |
//+------------------------------------------------------------------+
enum ENUM_VS_DETECT_METHOD
{
   VS_METHOD_STDDEV     = 0,   // MA + Standard Deviation (recommended)
   VS_METHOD_ZSCORE     = 1,   // Z-Score Normalisation
   VS_METHOD_PERCENTILE = 2,   // Percentile Rank
   VS_METHOD_RVOL       = 3    // Relative Volume – session-aware
};

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group                 "── Detection ──────────────────────────────";
input ENUM_VS_DETECT_METHOD InpMethod        = VS_METHOD_STDDEV; // Detection method
input int                   InpMAPeriod      = 20;               // MA period (bars)
input ENUM_MA_METHOD        InpMAType        = MODE_SMA;         // MA type
input double                InpMultiplier    = 2.0;              // Std Dev multiplier
input double                InpZThreshold    = 2.5;              // Z-score threshold
input int                   InpPctPeriod     = 100;              // Percentile lookback (bars)
input double                InpPctCutoff     = 95.0;             // Percentile cutoff (%)
input int                   InpRvolDays      = 10;               // RVOL history (days)
input double                InpRvolThreshold = 2.0;              // RVOL multiplier

input group                 "── Time Filter ─────────────────────────────";
input bool                  InpTimeFilter    = false;            // Enable time-of-day filter
input int                   InpTimeFromHour  = 9;                // From – hour   (0-23)
input int                   InpTimeFromMin   = 0;                // From – minute (0-59)
input int                   InpTimeToHour    = 23;               // To   – hour   (0-23)
input int                   InpTimeToMin     = 59;               // To   – minute (0-59)

input group                 "── Trade ───────────────────────────────────";
input double                InpLotSize       = 0.01;             // Lot size
input int                   InpSL            = 1000;             // Stop loss (points)
input int                   InpTP            = 3000;             // Take profit (points)
input int                   InpMaxTrades     = 3;                // Max open trades (-1 = unlimited)
input int                   InpMaxSpread     = 50;               // Max spread in points (-1 = disabled)
input long                  InpMagicNumber   = 20260521;         // Magic number
input int                   InpDeviation     = 10;               // Max slippage (points)
input bool                  InpUseBarClose   = true;             // true = wait for bar close, false = act on tick

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
datetime g_last_bar      = 0;
datetime g_last_buy_bar  = 0;
datetime g_last_sell_bar = 0;
CTrade   g_trade;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   if(InpUseBarClose)
   {
      datetime current_bar = iTime(_Symbol, _Period, 0);
      if(current_bar == g_last_bar) return;
      g_last_bar = current_bar;
   }

   if(!IsInTimeWindow(TimeCurrent())) return;
   if(InpMaxSpread != -1 && (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) return;

   int  idx = InpUseBarClose ? 1 : 0;
   bool is_spike, bullish;
   if(!DetectSpike(idx, is_spike, bullish)) return;
   if(!is_spike) return;

   datetime signal_bar = iTime(_Symbol, _Period, idx);
   bool buy_signal  = bullish;
   bool sell_signal = !bullish;

   if(buy_signal  && signal_bar == g_last_buy_bar)  return;
   if(sell_signal && signal_bar == g_last_sell_bar) return;

   if(buy_signal)  CloseAllByType(POSITION_TYPE_SELL);
   if(sell_signal) CloseAllByType(POSITION_TYPE_BUY);
   if(InpMaxTrades != -1 && CountOpenTrades() >= InpMaxTrades) return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(buy_signal)
   {
      g_last_buy_bar   = signal_bar;
      double price     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_trade.Buy(InpLotSize, _Symbol, price,
                  price - InpSL * point, price + InpTP * point);
   }
   else
   {
      g_last_sell_bar  = signal_bar;
      double price     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      g_trade.Sell(InpLotSize, _Symbol, price,
                   price + InpSL * point, price - InpTP * point);
   }
}

//+------------------------------------------------------------------+
//| Detect whether bar[idx] is a volume spike.                      |
//| Returns false when there is not enough history to compute.      |
//+------------------------------------------------------------------+
bool DetectSpike(int idx, bool &is_spike, bool &bullish)
{
   // Buffer size: 3× MA period for EMA warmup + percentile window
   int win   = MathMax(3 * InpMAPeriod, InpPctPeriod + 1);
   int total = idx + win + 1;

   long   vol_raw[];
   double open1[], close1[];
   ArraySetAsSeries(vol_raw, true);

   if(CopyTickVolume(_Symbol, _Period, 0, total, vol_raw) < total) return false;
   if(CopyOpen (_Symbol, _Period, idx, 1, open1)  <= 0) return false;
   if(CopyClose(_Symbol, _Period, idx, 1, close1) <= 0) return false;

   double vol  = (double)vol_raw[idx];
   bullish     = (close1[0] >= open1[0]);

   double ma_vol  = CalcVolMA(vol_raw, idx);
   double std_vol = CalcVolStdDev(vol_raw, idx, ma_vol);
   double z_score = (std_vol > 1e-10) ? (vol - ma_vol) / std_vol : 0.0;

   switch(InpMethod)
   {
      case VS_METHOD_STDDEV:
         is_spike = (vol > ma_vol + InpMultiplier * std_vol);
         break;

      case VS_METHOD_ZSCORE:
         is_spike = (z_score > InpZThreshold);
         break;

      case VS_METHOD_PERCENTILE:
      {
         int below = 0;
         for(int k = 1; k <= InpPctPeriod; k++)
            if((double)vol_raw[idx + k] < vol) below++;
         is_spike = (100.0 * below / InpPctPeriod > InpPctCutoff);
         break;
      }

      case VS_METHOD_RVOL:
      {
         int bars_per_day = (int)MathMax(1.0, MathCeil(86400.0 / PeriodSeconds(_Period)));
         int rvol_total   = idx + InpRvolDays * bars_per_day * 2 + 100;
         long     rvol_vol[];
         datetime rvol_time[];
         ArraySetAsSeries(rvol_vol,  true);
         ArraySetAsSeries(rvol_time, true);
         if(CopyTickVolume(_Symbol, _Period, 0, rvol_total, rvol_vol) <= idx)
            { is_spike = false; break; }
         if(CopyTime(_Symbol, _Period, 0, ArraySize(rvol_vol), rvol_time) <= 0)
            { is_spike = false; break; }
         double avg_sess = CalcRvolAvg(rvol_vol, rvol_time, idx);
         is_spike = (avg_sess > 0.0 && vol / avg_sess > InpRvolThreshold);
         break;
      }

      default: is_spike = false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Volume MA for bar[idx]. EMA/SMMA use warmup from oldest bars.   |
//+------------------------------------------------------------------+
double CalcVolMA(const long &vol_raw[], int idx)
{
   int total = ArraySize(vol_raw);

   switch(InpMAType)
   {
      case MODE_EMA:
      {
         int    seed_start = total - 1;
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++) seed += (double)vol_raw[seed_start - k];
         double ema = seed / InpMAPeriod;
         double k_f = 2.0 / (InpMAPeriod + 1.0);
         for(int i = seed_start - InpMAPeriod; i >= idx; i--)
            ema = (double)vol_raw[i] * k_f + ema * (1.0 - k_f);
         return ema;
      }

      case MODE_SMMA:
      {
         int    seed_start = total - 1;
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++) seed += (double)vol_raw[seed_start - k];
         double smma = seed / InpMAPeriod;
         double k_f  = 1.0 / InpMAPeriod;
         for(int i = seed_start - InpMAPeriod; i >= idx; i--)
            smma = (double)vol_raw[i] * k_f + smma * (1.0 - k_f);
         return smma;
      }

      default: // MODE_SMA and MODE_WMA both use SMA (mirrors indicator)
      {
         double sum = 0;
         for(int k = 0; k < InpMAPeriod; k++) sum += (double)vol_raw[idx + k];
         return sum / InpMAPeriod;
      }
   }
}

//+------------------------------------------------------------------+
//| Population standard deviation of volume over InpMAPeriod bars.  |
//+------------------------------------------------------------------+
double CalcVolStdDev(const long &vol_raw[], int idx, double ma)
{
   double sq = 0;
   for(int k = 0; k < InpMAPeriod; k++)
   {
      double d = (double)vol_raw[idx + k] - ma;
      sq += d * d;
   }
   return (InpMAPeriod > 1) ? MathSqrt(sq / InpMAPeriod) : 0.0;
}

//+------------------------------------------------------------------+
//| Average volume for the same session time-slot over InpRvolDays. |
//| Mirrors SessionAvgVol() from VolumeSpike.mq5.                   |
//+------------------------------------------------------------------+
double CalcRvolAvg(const long &vol[], const datetime &t[], int idx)
{
   MqlDateTime cur;
   TimeToStruct(t[idx], cur);
   double sum = 0;
   int    cnt = 0;
   int    sz  = ArraySize(vol);
   for(int j = idx + 1; j < sz && cnt < InpRvolDays; j++)
   {
      MqlDateTime bar;
      TimeToStruct(t[j], bar);
      if(bar.hour == cur.hour && bar.min == cur.min)
      {
         sum += (double)vol[j];
         cnt++;
      }
   }
   return (cnt > 0) ? sum / cnt : 0.0;
}

//+------------------------------------------------------------------+
//| Count open positions for this EA on the current symbol.         |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0)                                   continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)               continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)  continue;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Close all positions of a given type for this EA / symbol.       |
//+------------------------------------------------------------------+
void CloseAllByType(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)                                                  continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)               continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)  continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type) continue;
      g_trade.PositionClose(ticket);
   }
}

//+------------------------------------------------------------------+
//| Mirrors IsInTimeWindow() from VolumeSpike.mq5.                  |
//+------------------------------------------------------------------+
bool IsInTimeWindow(datetime t)
{
   if(!InpTimeFilter) return true;
   MqlDateTime dt;
   TimeToStruct(t, dt);
   int cur  = dt.hour * 60 + dt.min;
   int from = InpTimeFromHour * 60 + InpTimeFromMin;
   int to   = InpTimeToHour   * 60 + InpTimeToMin;
   if(from <= to) return (cur >= from && cur <= to);
   else           return (cur >= from || cur <= to);
}
//+------------------------------------------------------------------+
