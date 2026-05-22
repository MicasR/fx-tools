//+------------------------------------------------------------------+
//|                                           VolumeSpike_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Expert Advisor that trades VolumeSpike indicator signals.       |
//|  Detection logic is embedded (mirrors VolumeSpike.mq5) so the   |
//|  EA is fully self-contained for the Strategy Tester.            |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.04"

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

enum ENUM_VS_SL_METHOD
{
   VS_SL_STRUCTURE = 0,   // Structure – candle high/low before spike
   VS_SL_ATR       = 1,   // ATR × multiplier
   VS_SL_FIXED     = 2    // Fixed points
};

enum ENUM_VS_TP_METHOD
{
   VS_TP_RR    = 0,   // Risk:Reward ratio
   VS_TP_ATR   = 1,   // ATR × multiplier
   VS_TP_FIXED = 2    // Fixed points
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
input int                   InpMaxTrades     = 3;                // Max open trades (-1 = unlimited)
input int                   InpMaxSpread     = 50;               // Max spread in points (-1 = disabled)
input long                  InpMagicNumber   = 20260521;         // Magic number
input int                   InpDeviation     = 10;               // Max slippage (points)
input bool                  InpUseBarClose   = true;             // true = wait for bar close, false = act on tick

input group                 "── Stop Loss ────────────────────────────────";
input ENUM_VS_SL_METHOD     InpSLMethod      = VS_SL_STRUCTURE;  // Stop loss method
input int                   InpSLLookback    = 3;                // Structure: bars to scan
input bool                  InpSLIncludeSpike = false;           // Structure: include spike candle in scan
input int                   InpATRPeriod     = 14;               // ATR period (shared by SL and TP)
input double                InpSLATRMult     = 1.5;              // ATR multiplier for SL
input int                   InpSLFixed       = 1000;             // Fixed SL (points)
input int                   InpSLMinPoints   = 200;              // Minimum SL floor (points)

input group                 "── Take Profit ──────────────────────────────";
input ENUM_VS_TP_METHOD     InpTPMethod      = VS_TP_RR;         // Take profit method
input double                InpTPRR          = 2.0;              // R:R ratio
input double                InpTPATRMult     = 3.0;              // ATR multiplier for TP
input int                   InpTPFixed       = 3000;             // Fixed TP (points)

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

   if(InpMaxTrades != -1 && CountOpenTrades() >= InpMaxTrades) return;

   if(buy_signal)
   {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl    = CalcSL(true, idx, price);
      if(sl <= 0.0) return;
      double tp    = CalcTP(true, price, sl, idx);
      if(tp <= 0.0) return;
      g_last_buy_bar = signal_bar;
      g_trade.Buy(InpLotSize, _Symbol, price, sl, tp);
   }
   else
   {
      double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl    = CalcSL(false, idx, price);
      if(sl <= 0.0) return;
      double tp    = CalcTP(false, price, sl, idx);
      if(tp <= 0.0) return;
      g_last_sell_bar = signal_bar;
      g_trade.Sell(InpLotSize, _Symbol, price, sl, tp);
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
//| Simple ATR (SMA of TR) over InpATRPeriod bars ending at idx.   |
//+------------------------------------------------------------------+
double CalcATR(int idx)
{
   int needed = idx + InpATRPeriod + 1;
   double high[], low[], close[];
   ArraySetAsSeries(high,  true);
   ArraySetAsSeries(low,   true);
   ArraySetAsSeries(close, true);
   if(CopyHigh (_Symbol, _Period, 0, needed, high)  < needed) return 0.0;
   if(CopyLow  (_Symbol, _Period, 0, needed, low)   < needed) return 0.0;
   if(CopyClose(_Symbol, _Period, 0, needed, close) < needed) return 0.0;

   double sum = 0.0;
   for(int i = 0; i < InpATRPeriod; i++)
   {
      int j  = idx + i;
      double tr = high[j] - low[j];
      tr = MathMax(tr, MathAbs(high[j]  - close[j + 1]));
      tr = MathMax(tr, MathAbs(low[j]   - close[j + 1]));
      sum += tr;
   }
   return sum / InpATRPeriod;
}

//+------------------------------------------------------------------+
//| Compute stop loss price. Returns 0.0 on insufficient history.   |
//+------------------------------------------------------------------+
double CalcSL(bool buy, int idx, double entry)
{
   double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl      = 0.0;

   if(InpSLMethod == VS_SL_STRUCTURE)
   {
      double buf[];
      ArraySetAsSeries(buf, true);
      int from = InpSLIncludeSpike ? idx : idx + 1;
      if(buy)
      {
         if(CopyLow(_Symbol, _Period, from, InpSLLookback, buf) < InpSLLookback) return 0.0;
         sl = buf[0];
         for(int i = 1; i < InpSLLookback; i++) sl = MathMin(sl, buf[i]);
      }
      else
      {
         if(CopyHigh(_Symbol, _Period, from, InpSLLookback, buf) < InpSLLookback) return 0.0;
         sl = buf[0];
         for(int i = 1; i < InpSLLookback; i++) sl = MathMax(sl, buf[i]);
      }
   }
   else if(InpSLMethod == VS_SL_ATR)
   {
      double atr = CalcATR(idx);
      if(atr <= 0.0) return 0.0;
      sl = buy ? entry - InpSLATRMult * atr : entry + InpSLATRMult * atr;
   }
   else // VS_SL_FIXED
   {
      sl = buy ? entry - InpSLFixed * point : entry + InpSLFixed * point;
   }

   // Apply minimum SL floor (user setting and broker stop level)
   double broker_min = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double min_dist   = MathMax(InpSLMinPoints * point, broker_min);
   if(buy  && entry - sl < min_dist) sl = entry - min_dist;
   if(!buy && sl - entry < min_dist) sl = entry + min_dist;

   return NormalizeDouble(sl, _Digits);
}

//+------------------------------------------------------------------+
//| Compute take profit price. Returns 0.0 on insufficient history. |
//+------------------------------------------------------------------+
double CalcTP(bool buy, double entry, double sl, int idx)
{
   double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sl_dist = MathAbs(entry - sl);
   double tp      = 0.0;

   if(InpTPMethod == VS_TP_RR)
   {
      tp = buy ? entry + sl_dist * InpTPRR : entry - sl_dist * InpTPRR;
   }
   else if(InpTPMethod == VS_TP_ATR)
   {
      double atr = CalcATR(idx);
      if(atr <= 0.0) return 0.0;
      tp = buy ? entry + InpTPATRMult * atr : entry - InpTPATRMult * atr;
   }
   else // VS_TP_FIXED
   {
      tp = buy ? entry + InpTPFixed * point : entry - InpTPFixed * point;
   }

   return NormalizeDouble(tp, _Digits);
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
