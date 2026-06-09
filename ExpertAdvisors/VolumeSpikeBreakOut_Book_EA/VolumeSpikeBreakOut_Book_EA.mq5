//+------------------------------------------------------------------+
//|                               VolumeSpikeBreakOut_Book_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  The "confB+trail" book strategy (best in backtest, gold & BTC). |
//|  Pyramids into a trend and trails the whole book out as one.     |
//|  Self-contained (embedded detection mirrors the indicator).      |
//|                                                                   |
//|   1. V-pattern (default) / Spike trigger on a closed bar.         |
//|   2. FLAT  -> arm an OCO break-out pair (Buy Stop @ high,          |
//|      Sell Stop @ low); first fill starts the book, sibling killed.|
//|   3. IN A BOOK -> a CONFLUENT (same-side) trigger arms a single   |
//|      add Stop, but only if its structural SL locks every open     |
//|      position to break-even+ (the BE gate). Contrary signals are  |
//|      ignored. No reversals.                                       |
//|   4. EXIT: one shared chandelier stop = max(latest structure SL,  |
//|      running_extreme - TrailMult*latest_range), ratcheting up,    |
//|      written to ALL positions' broker SL each bar -> the whole    |
//|      book exits together.                                         |
//|   5. SIZE: each entry risks InpRiskPct% of equity over its        |
//|      structural range. The BE gate keeps total open book risk at  |
//|      ~1 unit no matter how many are stacked (backtest-verified).  |
//|                                                                   |
//|  Scope: gold & BTC. Do NOT run on mean-reverting FX.              |
//|  ** Validate in the Strategy Tester (visual) before any use. **   |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.02"

#include <Trade\Trade.mqh>

enum ENUM_BO_TRIGGER { BO_TRIGGER_SPIKE = 0, BO_TRIGGER_VPATTERN = 1 };
enum ENUM_BO_METHOD  { BO_METHOD_STDDEV = 0, BO_METHOD_ZSCORE = 1, BO_METHOD_PERCENTILE = 2,
                       BO_METHOD_RVOL = 3, BO_METHOD_THRESHOLD = 4 };

input group              "── Detection ──────────────────────────────";
input ENUM_BO_TRIGGER    InpTrigger       = BO_TRIGGER_VPATTERN; // Setup trigger
input int                InpBreakBars     = 4;                   // Breakout window (bars)
input ENUM_BO_METHOD     InpMethod        = BO_METHOD_THRESHOLD; // Detection method
input int                InpMAPeriod      = 20;                  // MA period
input ENUM_MA_METHOD     InpMAType        = MODE_SMA;            // MA type
input double             InpMultiplier    = 2.0;                 // Std Dev multiplier
input double             InpZThreshold    = 2.5;                 // Z-score threshold
input int                InpPctPeriod     = 100;                 // Percentile lookback
input double             InpPctCutoff     = 95.0;                // Percentile cutoff (%)
input int                InpRvolDays      = 10;                  // RVOL history (days)
input double             InpRvolThreshold = 2.0;                 // RVOL multiplier
input double             InpRisePct       = 0.02;                // V rise leg (V-pattern only)

input group              "── Risk / Book ─────────────────────────────";
input double             InpRiskPct       = 0.5;                 // Risk % of equity per entry
input double             InpTrailMult     = 2.5;                 // Shared trail = mult x latest range
input int                InpMinRangePts   = 100;                 // Skip trigger if range < this (points)
input int                InpMaxPositions  = 0;                   // Max stacked positions (0 = unlimited)

input group              "── Trade ───────────────────────────────────";
input int                InpMaxSpread     = -1;                  // Max spread in points (-1 = off)
input long               InpMagicNumber   = 20260609;            // Magic number
input int                InpDeviation     = 30;                  // Max slippage (points)

input group              "── Time Filter ─────────────────────────────";
input bool               InpTimeFilter    = false;
input int                InpTimeFromHour  = 9;
input int                InpTimeFromMin   = 0;
input int                InpTimeToHour    = 23;
input int                InpTimeToMin     = 59;

//--- book state (persisted across bars; reset when flat)
datetime g_last_bar = 0;
datetime g_arm_bar  = 0;     // trigger bar time of the live pending setup
int      g_count    = 0;     // last known open-position count
int      g_dir      = 0;     // book direction (+1/-1, 0 = flat)
double   g_bsl = 0, g_bext = 0, g_brng = 0, g_bstop = 0;   // shared-stop state
double   g_pH = 0, g_pL = 0, g_pR = 0;   // last-armed trigger high/low/range
CTrade   g_trade;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnTick()
{
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    count, dir;
   double max_long, min_short, anchor;
   ScanBook(count, dir, max_long, min_short, anchor);

   // ===================== EVERY TICK: book management =====================
   // (fill/close detection, sibling cancel, SL sync — must be prompt, not per-bar)
   if(count > g_count)                          // an order filled
   {
      if(g_count == 0)                           // new book opened
      {
         g_dir  = dir;
         g_bsl  = (dir == 1) ? g_pL : g_pH;
         g_brng = g_pR;
         g_bext = anchor;                         // single entry = book extreme seed
         g_bstop = g_bsl;
      }
      else                                        // add filled
      {
         g_bsl  = (g_dir == 1) ? g_pL : g_pH;
         g_brng = g_pR;
         g_bstop = (g_dir == 1) ? MathMax(g_bstop, g_bsl) : MathMin(g_bstop, g_bsl);
      }
   }
   else if(count < g_count && count == 0)        // whole book closed out
   {
      g_dir = 0; g_bstop = g_bext = g_bsl = g_brng = 0;
      DeletePendings(0);
   }
   g_count = count;

   if(count > 0)
   {
      ApplyStopAll(NormalizeDouble(g_bstop, _Digits));  // sync ALL SLs (incl. just-added) every tick
      DeletePendings(g_dir == 1 ? 2 : 1);               // kill contrary/sibling leg at once
   }

   // ===================== NEW BAR ONLY: trail ratchet + signals =====================
   datetime cb = iTime(_Symbol, _Period, 0);
   if(cb == g_last_bar) return;
   g_last_bar = cb;

   bool time_ok = IsInTimeWindow(TimeCurrent());
   bool spread_ok = (InpMaxSpread == -1 ||
                     (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpread);
   // bars-since-arm via iBarShift (gap-immune; wall-clock/PeriodSeconds over-counts on gaps)
   bool stale = (CountPendings() > 0 &&
                 iBarShift(_Symbol, _Period, g_arm_bar, false) >= InpBreakBars);

   if(count > 0)
   {
      if(g_dir == 1)
      {
         g_bext  = MathMax(g_bext, iHigh(_Symbol, _Period, 1));
         g_bstop = MathMax(g_bstop, MathMax(g_bsl, g_bext - InpTrailMult * g_brng));
      }
      else
      {
         g_bext  = MathMin(g_bext, iLow(_Symbol, _Period, 1));
         g_bstop = MathMin(g_bstop, MathMin(g_bsl, g_bext + InpTrailMult * g_brng));
      }
      ApplyStopAll(NormalizeDouble(g_bstop, _Digits));
      if(stale) DeletePendings(0);

      bool cap_ok = (InpMaxPositions <= 0 || count < InpMaxPositions);
      if(CountPendings() == 0 && time_ok && spread_ok && cap_ok && IsTriggerBar())
      {
         double th = iHigh(_Symbol, _Period, 1), tl = iLow(_Symbol, _Period, 1);
         double rng = th - tl;
         bool gate = (g_dir == 1) ? (tl >= max_long) : (th <= min_short);
         if(rng >= InpMinRangePts * point && gate)
         {
            if(g_dir == 1) ArmStop(true, th, tl); else ArmStop(false, tl, th);
            g_pH = th; g_pL = tl; g_pR = rng; g_arm_bar = cb;
         }
      }
   }
   else   // flat
   {
      if(stale) DeletePendings(0);
      if(CountPendings() == 0 && time_ok && spread_ok && IsTriggerBar())
      {
         double th = iHigh(_Symbol, _Period, 1), tl = iLow(_Symbol, _Period, 1);
         double rng = th - tl;
         if(rng >= InpMinRangePts * point)
         {
            ArmStop(true,  th, tl);            // Buy Stop @ high, SL = low
            ArmStop(false, tl, th);            // Sell Stop @ low, SL = high
            g_pH = th; g_pL = tl; g_pR = rng; g_arm_bar = cb;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Scan this EA's open positions on the symbol.                     |
//+------------------------------------------------------------------+
void ScanBook(int &count, int &dir, double &max_long, double &min_short, double &anchor)
{
   count = 0; dir = 0; max_long = -DBL_MAX; min_short = DBL_MAX; anchor = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      count++;
      double e = PositionGetDouble(POSITION_PRICE_OPEN);
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
      { dir = 1; max_long = MathMax(max_long, e); anchor = e; }
      else
      { dir = -1; min_short = MathMin(min_short, e); anchor = e; }
   }
   if(dir == 1)  anchor = max_long;
   if(dir == -1) anchor = min_short;
}

//+------------------------------------------------------------------+
//| Write a shared stop to every open position (skip if unchanged).  |
//+------------------------------------------------------------------+
void ApplyStopAll(double stop)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      if(MathAbs(PositionGetDouble(POSITION_SL) - stop) < _Point * 0.5) continue;
      g_trade.PositionModify(tk, stop, 0.0);
   }
}

//+------------------------------------------------------------------+
//| Total open lots for this EA on the symbol (for the margin cap).  |
//+------------------------------------------------------------------+
double OpenBookLots()
{
   double v = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      v += PositionGetDouble(POSITION_VOLUME);
   }
   return v;
}

//+------------------------------------------------------------------+
//| Embedded from Dercio Micas' SameRiskLotSizing::CalculateSafeLotSize|
//| Risk-% lot, but capped by a margin-call-safe lot (so a losing    |
//| book can't be margin-called before its stops hit). totalLots =   |
//| the symbol's already-open lots; stopLossPoints in TICK_SIZE units.|
//+------------------------------------------------------------------+
double CalculateSafeLotSize(double riskPercent, string symbol, int stopLossPoints,
                            ENUM_ORDER_TYPE orderType, double marginCallLevelPercent,
                            double totalLots, double riskAmount)
{
   double bid       = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask       = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double price     = (orderType == ORDER_TYPE_SELL) ? bid : ask;
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   if(riskPercent <= 0 || stopLossPoints <= 0 || tickValue <= 0 || tickSize <= 0 || price <= 0)
      return 0.0;

   double tickRatio  = tickValue / tickSize;
   double stopLoss   = stopLossPoints * SymbolInfoDouble(symbol, SYMBOL_POINT);
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   if(riskAmount == 0) riskAmount = equity * (riskPercent / 100.0);
   double lossPerLot = stopLoss * tickRatio;
   if(lossPerLot <= 0) return 0.0;

   double mrgCall    = marginCallLevelPercent / 100.0;
   double marg       = AccountInfoDouble(ACCOUNT_MARGIN);
   double margPerLot = 0.0;
   if(!OrderCalcMargin(orderType, symbol, 1, price, margPerLot))
      margPerLot = 0.0;               // margin term drops out; risk-lot still capped by equity

   double riskLot     = riskAmount / lossPerLot;
   double denom       = mrgCall * margPerLot + lossPerLot;
   double margCallLot = (denom > 0)
                        ? ((equity - lossPerLot * totalLots) - mrgCall * marg) / denom
                        : riskLot;

   double lot = (margCallLot < riskLot) ? margCallLot : riskLot;   // safer of the two
   return (lot > 0) ? lot : 0.0;
}

//+------------------------------------------------------------------+
//| Risk-% lot for a |price-sl| stop. Skips if margin-unsafe (<=0);  |
//| floors a sub-min risk-lot to the broker minimum (allowed).       |
//+------------------------------------------------------------------+
double LotForRisk(double risk_dist, ENUM_ORDER_TYPE ot)
{
   double ticksz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(risk_dist <= 0 || ticksz <= 0) return 0.0;
   int    slpts   = (int)MathRound(risk_dist / ticksz);
   double stopOut = AccountInfoDouble(ACCOUNT_MARGIN_SO_SO) + 5.0;
   double lot = CalculateSafeLotSize(InpRiskPct, _Symbol, slpts, ot, stopOut, OpenBookLots(), 0);
   if(lot <= 0) return 0.0;             // margin-unsafe / invalid → skip
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   lot = MathFloor(lot / step) * step;
   if(lot < minl) lot = minl;           // min lot allowed (per user)
   if(lot > maxl) lot = maxl;
   return lot;
}

//+------------------------------------------------------------------+
//| Place a sized break-out stop order (returns false if invalid).   |
//+------------------------------------------------------------------+
void ArmStop(bool is_buy, double price, double sl)
{
   double lot = LotForRisk(MathAbs(price - sl), is_buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(lot <= 0) return;
   price = NormalizeDouble(price, _Digits);
   sl    = NormalizeDouble(sl, _Digits);
   double point   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minstop = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   if(is_buy)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(price - ask < minstop) return;
      g_trade.BuyStop(lot, price, _Symbol, sl, 0.0, ORDER_TIME_GTC, 0, "VSBO_BK");
   }
   else
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(bid - price < minstop) return;
      g_trade.SellStop(lot, price, _Symbol, sl, 0.0, ORDER_TIME_GTC, 0, "VSBO_BK");
   }
}

//+------------------------------------------------------------------+
//| Count / delete this EA's pending orders.  which: 0=all,1=buy,2=sell|
//+------------------------------------------------------------------+
int CountPendings()
{
   int c = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber) continue;
      c++;
   }
   return c;
}

void DeletePendings(int which)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber) continue;
      ENUM_ORDER_TYPE ot = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if(which == 1 && ot != ORDER_TYPE_BUY_STOP)  continue;
      if(which == 2 && ot != ORDER_TYPE_SELL_STOP) continue;
      g_trade.OrderDelete(tk);
   }
}

//+------------------------------------------------------------------+
//| Detection (mirrors VolumeSpikeBreakOut.mq5).                     |
//+------------------------------------------------------------------+
bool IsTriggerBar()
{
   int win = MathMax(3 * InpMAPeriod, InpPctPeriod + 1), total = win + 6;
   long vol[]; datetime time[];
   ArraySetAsSeries(vol, true); ArraySetAsSeries(time, true);
   if(CopyTickVolume(_Symbol, _Period, 0, total, vol) < total) return false;
   if(CopyTime(_Symbol, _Period, 0, total, time) < total) return false;
   return TriggerFired(vol, time, 1);
}

bool TriggerFired(const long &vol[], const datetime &time[], int idx)
{
   if(InpTrigger == BO_TRIGGER_SPIKE) return SpikeAt(vol, time, idx);
   double s1 = SourceLineAt(vol, time, idx), s2 = SourceLineAt(vol, time, idx + 1),
          s3 = SourceLineAt(vol, time, idx + 2);
   if(!(s3 > s2 && s1 > s2)) return false;
   return ((s1 - s2) / MathMax(MathAbs(s2), 1e-10) >= InpRisePct);
}

bool SpikeAt(const long &vol[], const datetime &time[], int idx)
{
   double v = (double)vol[idx], ma = VolMA(vol, idx), std = VolStd(vol, idx, ma);
   switch(InpMethod)
   {
      case BO_METHOD_ZSCORE:     return ((std > 1e-10 ? (v - ma) / std : 0.0) > InpZThreshold);
      case BO_METHOD_PERCENTILE: return (RankAt(vol, idx) > InpPctCutoff);
      case BO_METHOD_RVOL:     { double a = RvolAvg(vol, time, idx); return (a > 0 && v / a > InpRvolThreshold); }
      default:                   return (v > ma + InpMultiplier * std);
   }
}

double SourceLineAt(const long &vol[], const datetime &time[], int idx)
{
   double v = (double)vol[idx], ma = VolMA(vol, idx), std = VolStd(vol, idx, ma);
   switch(InpMethod)
   {
      case BO_METHOD_PERCENTILE: return RankAt(vol, idx);
      case BO_METHOD_RVOL:     { double a = RvolAvg(vol, time, idx); return (a > 0 ? v / a : 0.0); }
      case BO_METHOD_THRESHOLD:  return ma + InpMultiplier * std;
      default:                   return (std > 1e-10 ? (v - ma) / std : 0.0);
   }
}

double VolMA(const long &vol[], int idx)
{
   int total = ArraySize(vol);
   if(InpMAType == MODE_EMA || InpMAType == MODE_SMMA)
   {
      int ss = total - 1; double seed = 0;
      for(int k = 0; k < InpMAPeriod; k++) seed += (double)vol[ss - k];
      double m = seed / InpMAPeriod;
      double kf = (InpMAType == MODE_EMA) ? 2.0 / (InpMAPeriod + 1.0) : 1.0 / InpMAPeriod;
      for(int i = ss - InpMAPeriod; i >= idx; i--) m = (double)vol[i] * kf + m * (1.0 - kf);
      return m;
   }
   double sum = 0;
   for(int k = 0; k < InpMAPeriod; k++) sum += (double)vol[idx + k];
   return sum / InpMAPeriod;
}

double VolStd(const long &vol[], int idx, double ma)
{
   double sq = 0;
   for(int k = 0; k < InpMAPeriod; k++) { double d = (double)vol[idx + k] - ma; sq += d * d; }
   return (InpMAPeriod > 1) ? MathSqrt(sq / InpMAPeriod) : 0.0;
}

double RankAt(const long &vol[], int idx)
{
   double v = (double)vol[idx]; int below = 0;
   for(int k = 1; k <= InpPctPeriod; k++) if((double)vol[idx + k] < v) below++;
   return 100.0 * below / InpPctPeriod;
}

double RvolAvg(const long &vol[], const datetime &time[], int idx)
{
   MqlDateTime cur; TimeToStruct(time[idx], cur);
   double sum = 0; int cnt = 0, sz = ArraySize(time);
   for(int j = idx + 1; j < sz && cnt < InpRvolDays; j++)
   {
      MqlDateTime b; TimeToStruct(time[j], b);
      if(b.hour == cur.hour && b.min == cur.min) { sum += (double)vol[j]; cnt++; }
   }
   return (cnt > 0) ? sum / cnt : 0.0;
}

bool IsInTimeWindow(datetime t)
{
   if(!InpTimeFilter) return true;
   MqlDateTime dt; TimeToStruct(t, dt);
   int cur = dt.hour * 60 + dt.min, from = InpTimeFromHour * 60 + InpTimeFromMin,
       to = InpTimeToHour * 60 + InpTimeToMin;
   return (from <= to) ? (cur >= from && cur <= to) : (cur >= from || cur <= to);
}
//+------------------------------------------------------------------+
