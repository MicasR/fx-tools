//+------------------------------------------------------------------+
//|                                    VolumeSpikeBreakOut_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Expert Advisor that trades the VolumeSpikeBreakOut indicator.   |
//|  Detection + breakout logic are embedded (mirror the indicator)  |
//|  so the EA is fully self-contained for the Strategy Tester.      |
//|                                                                   |
//|  Logic (validated on XAUUSD H1, see indicator spec §11):         |
//|   1. A TRIGGER fires on a closed bar T — V-pattern (default) or   |
//|      Spike — using the selected method's line.                    |
//|   2. The first of the next InpBreakBars closed bars to break T's  |
//|      range gives the trade: break the high → BUY, the low → SELL  |
//|      (direction confirmed by price, not candle colour).           |
//|   3. Structural stop at T's opposite extreme; take-profit at      |
//|      1:InpRR. Entry at the breakout bar's close (bar-close tool). |
//|                                                                   |
//|  Default trigger = V-pattern; on H4 the Spike trigger is better.  |
//|  Edge is demonstrated on gold & BTC only — do NOT run on          |
//|  mean-reverting FX (it is a net loser there).                     |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.00"

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
input int                InpBreakBars     = 4;                   // Breakout window (bars to confirm)
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
input int                InpMaxTrades     = 1;                  // Max open trades (-1 = unlimited)
input int                InpMaxSpread     = -1;                 // Max spread in points (-1 = disabled)
input long               InpMagicNumber   = 20260608;           // Magic number
input int                InpDeviation     = 30;                 // Max slippage (points)

input group              "── Risk ────────────────────────────────────";
input double             InpRR            = 3.0;                // Take-profit risk:reward (1:RR)
input int                InpSLMinPoints   = 100;                // Minimum stop distance floor (points)

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
datetime g_last_bar    = 0;
datetime g_last_entry  = 0;   // open-time of the breakout bar we last traded
int      g_min_bars;
CTrade   g_trade;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_min_bars   = MathMax(InpMAPeriod, InpPctPeriod) + 1;
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnTick – act once per newly closed bar                           |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime current_bar = iTime(_Symbol, _Period, 0);
   if(current_bar == g_last_bar) return;     // only on a new bar
   g_last_bar = current_bar;

   if(!IsInTimeWindow(TimeCurrent())) return;
   if(InpMaxSpread != -1 && (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread) return;
   if(InpMaxTrades != -1 && CountOpenTrades() >= InpMaxTrades) return;

   // ---- evaluate the just-closed bar (series index 1) as a breakout entry ----
   bool buy; int trig_idx;
   if(!DetectBreakout(buy, trig_idx)) return;

   datetime entry_bar = iTime(_Symbol, _Period, 1);
   if(entry_bar == g_last_entry) return;     // already traded this bar

   // structural stop = trigger bar's opposite extreme
   double sl = buy ? iLow(_Symbol, _Period, trig_idx) : iHigh(_Symbol, _Period, trig_idx);
   double entry = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                      : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   sl = ApplyStopFloor(buy, entry, sl);
   if((buy && sl >= entry) || (!buy && sl <= entry)) return;   // invalid geometry

   double risk = MathAbs(entry - sl);
   double tp   = buy ? entry + InpRR * risk : entry - InpRR * risk;
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);

   g_last_entry = entry_bar;
   if(buy) g_trade.Buy (InpLotSize, _Symbol, entry, sl, tp);
   else    g_trade.Sell(InpLotSize, _Symbol, entry, sl, tp);
}

//+------------------------------------------------------------------+
//| Detect whether the just-closed bar (index 1) is a breakout entry.|
//| Mirrors the indicator's backward scan: find the most recent      |
//| un-broken trigger within InpBreakBars whose range bar[1] breaks. |
//| Returns true and sets `buy` + `trig_idx` (series index of T).    |
//+------------------------------------------------------------------+
bool DetectBreakout(bool &buy, int &trig_idx)
{
   int need_back = InpBreakBars + 3;               // deepest trigger bar (T+2 for the V)
   int win       = MathMax(3 * InpMAPeriod, InpPctPeriod + 1);
   int total     = need_back + win + 2;

   long     vol[];
   double   high[], low[];
   datetime time[];
   ArraySetAsSeries(vol,  true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low,  true);
   ArraySetAsSeries(time, true);

   if(CopyTickVolume(_Symbol, _Period, 0, total, vol)  < total)        return false;
   if(CopyHigh(_Symbol, _Period, 0, need_back + 2, high) < need_back+2) return false;
   if(CopyLow (_Symbol, _Period, 0, need_back + 2, low)  < need_back+2) return false;
   if(CopyTime(_Symbol, _Period, 0, total, time)        < total)        return false;

   int maxlook = MathMin(InpBreakBars, total - g_min_bars - 3);
   for(int back = 1; back <= maxlook; back++)
   {
      int T = 1 + back;                            // candidate trigger bar (older)
      if(!TriggerFired(vol, time, T))              continue;

      double hiT = high[T];
      double loT = low[T];

      // skip if any bar strictly between T and 1 already broke the range
      bool resolved = false;
      for(int j = 2; j < T; j++)
         if(high[j] >= hiT || low[j] <= loT) { resolved = true; break; }
      if(resolved)                                 continue;

      bool up = (high[1] >= hiT);
      bool dn = (low[1]  <= loT);
      if(up && dn)                                 continue;   // straddle → ambiguous
      if(!up && !dn)                               continue;   // bar 1 didn't break it

      buy      = up;
      trig_idx = T;
      return true;
   }
   return false;
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
//| Widen the stop to the broker / user minimum distance if needed.  |
//+------------------------------------------------------------------+
double ApplyStopFloor(bool buy, double entry, double sl)
{
   double point      = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double broker_min = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double min_dist   = MathMax(InpSLMinPoints * point, broker_min);
   if(buy  && entry - sl < min_dist) sl = entry - min_dist;
   if(!buy && sl - entry < min_dist) sl = entry + min_dist;
   return sl;
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
