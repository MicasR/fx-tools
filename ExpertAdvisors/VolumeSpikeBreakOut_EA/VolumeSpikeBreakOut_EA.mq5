//+------------------------------------------------------------------+
//|                                    VolumeSpikeBreakOut_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Expert Advisor that trades the VolumeSpikeBreakOut indicator.   |
//|  Detection logic is embedded (mirrors the indicator) so the EA   |
//|  is fully self-contained for the Strategy Tester.               |
//|                                                                   |
//|  Logic (validated on XAUUSD H1, see indicator spec §11):         |
//|   1. A TRIGGER fires on a closed bar T — V-pattern (default) or   |
//|      Spike — using the selected method's line.                    |
//|   2. An OCO pending pair is armed at T's range: a Buy Stop at T's |
//|      HIGH and a Sell Stop at T's LOW, each with a structural stop |
//|      at the opposite extreme and a 1:InpRR target. The FIRST to   |
//|      fill cancels the other (OCO). If neither fills within         |
//|      InpBreakBars bars, the pair is deleted (expires).            |
//|                                                                   |
//|  This gives the IDEALIZED break-level fill the backtest measured  |
//|  (gold/BTC H1 ~0.21 avg R, net of cost). One setup at a time.     |
//|                                                                   |
//|  Default trigger = V-pattern; on H4 the Spike trigger is better.  |
//|  Edge is demonstrated on gold & BTC only — do NOT run on          |
//|  mean-reverting FX (it is a net loser there).                     |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.01"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enumerations (mirror VolumeSpikeBreakOut.mq5)                    |
//+------------------------------------------------------------------+
enum ENUM_BO_TRIGGER
{
   BO_TRIGGER_SPIKE    = 0,   // Spike      (volume crosses the level)
   BO_TRIGGER_VPATTERN = 1    // V-pattern  (selected line traces a V)
};

enum ENUM_BO_METHOD
{
   BO_METHOD_STDDEV     = 0,   // MA + Standard Deviation
   BO_METHOD_ZSCORE     = 1,   // Z-Score Normalisation
   BO_METHOD_PERCENTILE = 2,   // Percentile Rank
   BO_METHOD_RVOL       = 3,   // Relative Volume – session-aware
   BO_METHOD_THRESHOLD  = 4    // Threshold line (MA + Multiplier*StdDev)
};

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group              "── Detection ──────────────────────────────";
input ENUM_BO_TRIGGER    InpTrigger       = BO_TRIGGER_VPATTERN; // Setup trigger (V-pattern: H1; Spike: H4)
input int                InpBreakBars     = 4;                   // Breakout window (bars before the pair expires)
input ENUM_BO_METHOD     InpMethod        = BO_METHOD_THRESHOLD; // Detection method
input int                InpMAPeriod      = 20;                  // MA period (bars)
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;            // MA type
input double             InpMultiplier    = 2.0;                 // Std Dev multiplier
input double             InpZThreshold    = 2.5;                 // Z-score threshold
input int                InpPctPeriod     = 100;                 // Percentile lookback (bars)
input double             InpPctCutoff     = 95.0;                // Percentile cutoff (%)
input int                InpRvolDays      = 10;                  // RVOL history (days)
input double             InpRvolThreshold = 2.0;                 // RVOL multiplier
input double             InpRisePct       = 0.02;                // V rise leg (only if trigger = V-pattern)

input group              "── Time Filter ─────────────────────────────";
input bool               InpTimeFilter    = false;              // Enable time-of-day filter
input int                InpTimeFromHour  = 9;                  // From – hour   (0-23)
input int                InpTimeFromMin   = 0;                  // From – minute (0-59)
input int                InpTimeToHour    = 23;                 // To   – hour   (0-23)
input int                InpTimeToMin     = 59;                 // To   – minute (0-59)

input group              "── Trade ───────────────────────────────────";
input double             InpLotSize       = 0.01;               // Lot size (fixed)
input int                InpMaxTrades     = 1;                  // Max open trades (one setup at a time)
input int                InpMaxSpread     = -1;                 // Max spread in points (-1 = disabled)
input long               InpMagicNumber   = 20260608;           // Magic number
input int                InpDeviation     = 30;                 // Max slippage (points)

input group              "── Risk ────────────────────────────────────";
input double             InpRR            = 3.0;                // Take-profit risk:reward (1:RR)
input int                InpMinRangePts   = 100;                // Skip if trigger-bar range < this (points)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
datetime g_last_bar = 0;
datetime g_arm_time = 0;   // open-time of the trigger bar whose OCO pair is live
int      g_min_bars;
CTrade   g_trade;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_min_bars = MathMax(InpMAPeriod, InpPctPeriod) + 1;
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   // ---- OCO: a fill on one side cancels the still-pending other side ----
   if(CountOpenTrades() > 0 && CountPendings() > 0)
      DeleteAllPendings();

   // ---- the rest runs once per newly closed bar ----
   datetime current_bar = iTime(_Symbol, _Period, 0);
   if(current_bar == g_last_bar) return;
   g_last_bar = current_bar;

   // ---- expire an un-filled pair after the breakout window ----
   if(CountPendings() > 0 && g_arm_time > 0 &&
      (current_bar - g_arm_time) / PeriodSeconds(_Period) > InpBreakBars)
      DeleteAllPendings();

   // ---- gating: one setup at a time ----
   if(!IsInTimeWindow(TimeCurrent())) return;
   if(InpMaxSpread != -1 && (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) return;
   if(CountOpenTrades() > 0 || CountPendings() > 0) return;
   if(InpMaxTrades != -1 && CountOpenTrades() >= InpMaxTrades) return;

   // ---- arm the OCO pair if the just-closed bar is a trigger ----
   if(IsTriggerBar())
      ArmBreakoutPair();
}

//+------------------------------------------------------------------+
//| Arm a Buy Stop @ trigger high and Sell Stop @ trigger low, each   |
//| with a structural stop (opposite extreme) and a 1:InpRR target.   |
//+------------------------------------------------------------------+
void ArmBreakoutPair()
{
   double hi = iHigh(_Symbol, _Period, 1);
   double lo = iLow (_Symbol, _Period, 1);
   double range = hi - lo;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(range <= 0.0 || range < InpMinRangePts * point) return;   // range too tight

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double min_stop = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

   // both break levels must be a valid stop-order distance from the market
   if(hi - ask < min_stop || bid - lo < min_stop) return;

   double buy_price  = NormalizeDouble(hi, _Digits);
   double buy_sl     = NormalizeDouble(lo, _Digits);
   double buy_tp     = NormalizeDouble(hi + InpRR * range, _Digits);

   double sell_price = NormalizeDouble(lo, _Digits);
   double sell_sl    = NormalizeDouble(hi, _Digits);
   double sell_tp    = NormalizeDouble(lo - InpRR * range, _Digits);

   // GTC orders; expiry is managed manually per-bar (broker-independent)
   bool ok1 = g_trade.BuyStop (InpLotSize, buy_price,  _Symbol, buy_sl,  buy_tp,
                               ORDER_TIME_GTC, 0, "VSBO");
   bool ok2 = g_trade.SellStop(InpLotSize, sell_price, _Symbol, sell_sl, sell_tp,
                               ORDER_TIME_GTC, 0, "VSBO");

   if(ok1 || ok2)
      g_arm_time = iTime(_Symbol, _Period, 1);
   // if only one leg placed, clean up so we never hold a one-sided setup
   if(ok1 != ok2)
      DeleteAllPendings();
}

//+------------------------------------------------------------------+
//| Is the just-closed bar (series index 1) a trigger?               |
//+------------------------------------------------------------------+
bool IsTriggerBar()
{
   int win   = MathMax(3 * InpMAPeriod, InpPctPeriod + 1);
   int total = win + 6;
   long     vol[];
   datetime time[];
   ArraySetAsSeries(vol,  true);
   ArraySetAsSeries(time, true);
   if(CopyTickVolume(_Symbol, _Period, 0, total, vol)  < total) return false;
   if(CopyTime      (_Symbol, _Period, 0, total, time) < total) return false;
   return TriggerFired(vol, time, 1);
}

//+------------------------------------------------------------------+
//| Did the trigger fire on series-index `idx`?                      |
//+------------------------------------------------------------------+
bool TriggerFired(const long &vol[], const datetime &time[], int idx)
{
   if(InpTrigger == BO_TRIGGER_SPIKE)
      return SpikeAt(vol, time, idx);

   // V-pattern: idx = C1 (rise), idx+1 = C2 (trough), idx+2 = C3 (pre-drop)
   double s1 = SourceLineAt(vol, time, idx);
   double s2 = SourceLineAt(vol, time, idx + 1);
   double s3 = SourceLineAt(vol, time, idx + 2);
   if(!(s3 > s2 && s1 > s2)) return false;
   double denom = MathMax(MathAbs(s2), 1e-10);
   return ((s1 - s2) / denom >= InpRisePct);
}

//+------------------------------------------------------------------+
//| is_spike at series-index idx (mirrors the indicator)             |
//+------------------------------------------------------------------+
bool SpikeAt(const long &vol[], const datetime &time[], int idx)
{
   double v   = (double)vol[idx];
   double ma  = VolMA(vol, idx);
   double std = VolStd(vol, idx, ma);
   switch(InpMethod)
   {
      case BO_METHOD_ZSCORE:     return ((std > 1e-10 ? (v - ma) / std : 0.0) > InpZThreshold);
      case BO_METHOD_PERCENTILE: return (RankAt(vol, idx) > InpPctCutoff);
      case BO_METHOD_RVOL:     { double a = RvolAvg(vol, time, idx); return (a > 0 && v / a > InpRvolThreshold); }
      default:                   return (v > ma + InpMultiplier * std);   // STDDEV & THRESHOLD
   }
}

//+------------------------------------------------------------------+
//| The selected method's line value at series-index idx (V source)  |
//+------------------------------------------------------------------+
double SourceLineAt(const long &vol[], const datetime &time[], int idx)
{
   double v   = (double)vol[idx];
   double ma  = VolMA(vol, idx);
   double std = VolStd(vol, idx, ma);
   switch(InpMethod)
   {
      case BO_METHOD_PERCENTILE: return RankAt(vol, idx);
      case BO_METHOD_RVOL:     { double a = RvolAvg(vol, time, idx); return (a > 0 ? v / a : 0.0); }
      case BO_METHOD_THRESHOLD:  return ma + InpMultiplier * std;
      default:                   return (std > 1e-10 ? (v - ma) / std : 0.0);  // STDDEV & ZSCORE → z
   }
}

//+------------------------------------------------------------------+
//| Volume MA ending at series-index idx (EMA/SMMA warm up from old).|
//+------------------------------------------------------------------+
double VolMA(const long &vol[], int idx)
{
   int total = ArraySize(vol);
   switch(InpMAType)
   {
      case MODE_EMA:
      {
         int seed_start = total - 1;
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++) seed += (double)vol[seed_start - k];
         double ema = seed / InpMAPeriod;
         double kf  = 2.0 / (InpMAPeriod + 1.0);
         for(int i = seed_start - InpMAPeriod; i >= idx; i--)
            ema = (double)vol[i] * kf + ema * (1.0 - kf);
         return ema;
      }
      case MODE_SMMA:
      {
         int seed_start = total - 1;
         double seed = 0;
         for(int k = 0; k < InpMAPeriod; k++) seed += (double)vol[seed_start - k];
         double smma = seed / InpMAPeriod;
         double kf   = 1.0 / InpMAPeriod;
         for(int i = seed_start - InpMAPeriod; i >= idx; i--)
            smma = (double)vol[i] * kf + smma * (1.0 - kf);
         return smma;
      }
      default: // SMA (WMA falls back to SMA, mirrors indicator)
      {
         double sum = 0;
         for(int k = 0; k < InpMAPeriod; k++) sum += (double)vol[idx + k];
         return sum / InpMAPeriod;
      }
   }
}

//+------------------------------------------------------------------+
//| Population standard deviation of volume over InpMAPeriod bars.   |
//+------------------------------------------------------------------+
double VolStd(const long &vol[], int idx, double ma)
{
   double sq = 0;
   for(int k = 0; k < InpMAPeriod; k++)
   {
      double d = (double)vol[idx + k] - ma;
      sq += d * d;
   }
   return (InpMAPeriod > 1) ? MathSqrt(sq / InpMAPeriod) : 0.0;
}

//+------------------------------------------------------------------+
//| Percentile rank of vol[idx] within the trailing InpPctPeriod.    |
//+------------------------------------------------------------------+
double RankAt(const long &vol[], int idx)
{
   double v = (double)vol[idx];
   int below = 0;
   for(int k = 1; k <= InpPctPeriod; k++)
      if((double)vol[idx + k] < v) below++;
   return 100.0 * below / InpPctPeriod;
}

//+------------------------------------------------------------------+
//| Average volume for the same session time-slot over InpRvolDays.  |
//+------------------------------------------------------------------+
double RvolAvg(const long &vol[], const datetime &time[], int idx)
{
   MqlDateTime cur;
   TimeToStruct(time[idx], cur);
   double sum = 0; int cnt = 0;
   int sz = ArraySize(time);
   for(int j = idx + 1; j < sz && cnt < InpRvolDays; j++)
   {
      MqlDateTime bar;
      TimeToStruct(time[j], bar);
      if(bar.hour == cur.hour && bar.min == cur.min) { sum += (double)vol[j]; cnt++; }
   }
   return (cnt > 0) ? sum / cnt : 0.0;
}

//+------------------------------------------------------------------+
//| Count open positions for this EA on the current symbol.          |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0)                                  continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)              continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Count this EA's pending orders on the current symbol.            |
//+------------------------------------------------------------------+
int CountPendings()
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)                                             continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)                continue;
      if(OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber)   continue;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Delete all of this EA's pending orders on the current symbol.    |
//+------------------------------------------------------------------+
void DeleteAllPendings()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0)                                             continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol)                continue;
      if(OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber)   continue;
      g_trade.OrderDelete(ticket);
   }
   g_arm_time = 0;
}

//+------------------------------------------------------------------+
//| Time-of-day window (mirrors the indicator).                      |
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
