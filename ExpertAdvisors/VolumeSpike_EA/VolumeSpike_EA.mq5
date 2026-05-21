//+------------------------------------------------------------------+
//|                                           VolumeSpike_EA.mq5     |
//|                                          Dercio Micas – 2026     |
//|                                                                   |
//|  Expert Advisor that trades VolumeSpike indicator signals.       |
//|  One trade per spike bar per direction; contrary signals close   |
//|  opposite positions before opening a new one.                   |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.00"

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
//| Constants                                                        |
//+------------------------------------------------------------------+
#define VS_SPIKE_BULL  2    // color index value for bullish spike
#define VS_SPIKE_BEAR  3    // color index value for bearish spike

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
int      g_handle        = INVALID_HANDLE;
datetime g_last_bar      = 0;   // bar-close mode: last processed bar open time
datetime g_last_buy_bar  = 0;   // open time of bar that last triggered a buy
datetime g_last_sell_bar = 0;   // open time of bar that last triggered a sell
CTrade   g_trade;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);

   g_handle = iCustom(_Symbol, _Period,
      "VolumeSpike\\VolumeSpike",
      // Detection
      (int)InpMethod, InpMAPeriod, (int)InpMAType,
      InpMultiplier, InpZThreshold,
      InpPctPeriod, InpPctCutoff,
      InpRvolDays, InpRvolThreshold,
      // Price Chart (visuals disabled)
      false, false, clrDodgerBlue, clrOrangeRed, clrGold, 1,
      // Sub-Window
      clrSteelBlue, clrDimGray, clrDodgerBlue, clrOrangeRed, false,
      // Alerts (all disabled)
      false, false, false, false, "", "", "", "",
      // Time Filter
      InpTimeFilter, InpTimeFromHour, InpTimeFromMin,
      InpTimeToHour, InpTimeToMin
   );

   if(g_handle == INVALID_HANDLE)
   {
      Print("VolumeSpike_EA: failed to load indicator – error ", GetLastError());
      return INIT_FAILED;
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_handle != INVALID_HANDLE)
      IndicatorRelease(g_handle);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   // Bar-close mode: only run once when a new bar opens
   if(InpUseBarClose)
   {
      datetime current_bar = iTime(_Symbol, _Period, 0);
      if(current_bar == g_last_bar)
         return;
      g_last_bar = current_bar;
   }

   // Time filter
   if(!IsInTimeWindow(TimeCurrent()))
      return;

   // Spread filter
   if(InpMaxSpread != -1 && (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread)
      return;

   // Bar-close mode reads the just-closed bar (index 1).
   // Tick mode reads the forming bar (index 0).
   int idx = InpUseBarClose ? 1 : 0;

   double buf[1];
   if(CopyBuffer(g_handle, 1, idx, 1, buf) <= 0)
      return;

   int      signal     = (int)MathRound(buf[0]);
   datetime signal_bar = iTime(_Symbol, _Period, idx);

   bool buy_signal  = (signal == VS_SPIKE_BULL);
   bool sell_signal = (signal == VS_SPIKE_BEAR);

   if(!buy_signal && !sell_signal)
      return;

   // Act at most once per spike bar per direction
   if(buy_signal  && signal_bar == g_last_buy_bar)  return;
   if(sell_signal && signal_bar == g_last_sell_bar) return;

   // Close contrary positions first, then recount
   if(buy_signal)  CloseAllByType(POSITION_TYPE_SELL);
   if(sell_signal) CloseAllByType(POSITION_TYPE_BUY);

   if(InpMaxTrades != -1 && CountOpenTrades() >= InpMaxTrades)
      return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(buy_signal)
   {
      g_last_buy_bar   = signal_bar;
      double price     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      g_trade.Buy(InpLotSize, _Symbol, price,
                  price - InpSL * point,
                  price + InpTP * point);
   }
   else
   {
      g_last_sell_bar  = signal_bar;
      double price     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      g_trade.Sell(InpLotSize, _Symbol, price,
                   price + InpSL * point,
                   price - InpTP * point);
   }
}

//+------------------------------------------------------------------+
//| Count open positions belonging to this EA on the current symbol  |
//+------------------------------------------------------------------+
int CountOpenTrades()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetTicket(i) == 0)                                    continue;
      if(PositionGetString(POSITION_SYMBOL)  != _Symbol)               continue;
      if(PositionGetInteger(POSITION_MAGIC)  != (long)InpMagicNumber)  continue;
      count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| Close all positions of a given type for this EA / symbol         |
//+------------------------------------------------------------------+
void CloseAllByType(POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)                                                   continue;
      if(PositionGetString(POSITION_SYMBOL)  != _Symbol)               continue;
      if(PositionGetInteger(POSITION_MAGIC)  != (long)InpMagicNumber)  continue;
      if((POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)     continue;
      g_trade.PositionClose(ticket);
   }
}

//+------------------------------------------------------------------+
//| Mirrors the time window logic from VolumeSpike.mq5              |
//| Handles overnight ranges (e.g. 22:00 – 06:00).                 |
//+------------------------------------------------------------------+
bool IsInTimeWindow(datetime t)
{
   if(!InpTimeFilter) return true;

   MqlDateTime dt;
   TimeToStruct(t, dt);
   int cur  = dt.hour * 60 + dt.min;
   int from = InpTimeFromHour * 60 + InpTimeFromMin;
   int to   = InpTimeToHour   * 60 + InpTimeToMin;

   if(from <= to)
      return (cur >= from && cur <= to);
   else
      return (cur >= from || cur <= to);   // overnight wrap
}
//+------------------------------------------------------------------+
