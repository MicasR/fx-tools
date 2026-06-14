//+------------------------------------------------------------------+
//|                                              CrossKing_EA.mq5      |
//|                                          Dercio Micas - 2026       |
//|                                                                    |
//|  ONE leg of the cross-instrument king portfolio. A faithful MQL5   |
//|  port of  backtest/conc_engine.run_tf_conc (max_conc = 1)  +       |
//|  pyramid_engine primitives (margin_line / lot_to_pin / proggeo /   |
//|  geofloor sizing). ONE binary, SIX .set presets (3 gold + 3 BTC).  |
//|                                                                    |
//|  Model ("EA-dumb / orchestrator-brain"): the EA risks its WHOLE    |
//|  account balance per operation. E0 = balance at op-open; the base  |
//|  lot pins the broker equity-0 line onto the structural SL, so a    |
//|  full stop = -E0 = -1R = the whole account. All portfolio          |
//|  weighting/pooling lives in how much cash the orchestrator funds    |
//|  each account with -- NOT in this EA.                              |
//|                                                                    |
//|  Mechanics (one operation at a time, max_conc = 1):                |
//|   1. ENTRY (always H1, regardless of chart TF): V-pattern volume    |
//|      trigger on a closed H1 bar -> arm an OCO breakout pair (Buy    |
//|      Stop @ trigger high, Sell Stop @ trigger low); first fill      |
//|      starts the op, sibling cancelled; stale-cancel after 4 H1      |
//|      bars. R = trigger H1 bar range; SL = opposite extreme.         |
//|   2. BASE SIZE: lot0 = E0/(TR*R) (pins equity-0 to the structural   |
//|      SL), capped by free margin and broker max.                     |
//|   3. STACK (stack presets): on a fast-SMA close bounce (wrong side  |
//|      then back), GATED (close beyond the last add AND op >= 0.5R    |
//|      favourable), add one position. proggeo: base*mult*step^k;      |
//|      geofloor: max(that, lot pinning equity-0 to the slow SMA).     |
//|      Each add capped by free margin (eq/MPL - openLots).            |
//|   4. FLOOR / EXIT: the synthetic SL = margin_line(book) (equity-0)  |
//|      is written to EVERY position each management bar -> the whole   |
//|      book exits together at -1R. Plus, per preset, a fixed TP =     |
//|      e0 + tp_R*R, OR a chandelier trail = max(margin_line,          |
//|      extreme - trail_R*R) for the BTC gf leg (tp_R = 0).            |
//|                                                                    |
//|  Entry detection block (V-pattern threshold) is reused from        |
//|  VolumeSpikeBreakOut_Book_EA; the management core is a NEW port of  |
//|  conc_engine, NOT the Book EA's confBtrail model.                  |
//|                                                                    |
//|  Scope: gold (XAU M15) & BTC (BTC H1) only. Leverage 1:2000.       |
//|  ** Validate every preset in the Strategy Tester against           |
//|     backtest/out/shadow/<leg>.csv BEFORE any live use. **          |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.00"
#property description "One leg of the cross-instrument king portfolio (conc_engine port)."

#include <Trade\Trade.mqh>

enum ENUM_CK_SIZING { CK_PROGGEO = 0, CK_GEOFLOOR = 1 };   // stack add-sizing rule

input group              "== Leg identity / preset =="
input string             InpLegName       = "GoldGeo17";   // Leg name (telemetry)
input long               InpMagicNumber   = 20260614;       // Magic number (unique per account)

input group              "== Entry detection (H1 V-pattern, fixed across presets) =="
input ENUM_TIMEFRAMES    InpEntryTF       = PERIOD_H1;       // Entry timeframe (always H1)
input int                InpMAPeriod      = 20;              // Volume MA period
input double             InpMultiplier    = 2.0;             // Threshold = MA + mult*popStdDev
input double             InpRisePct       = 0.02;            // V rise leg (>= 2%)
input int                InpBreakBars     = 4;               // Breakout window (H1 bars)

input group              "== Management core (the preset knobs) =="
input bool               InpStack         = true;            // Stack adds (false = shield: single pos)
input ENUM_CK_SIZING     InpSizing        = CK_PROGGEO;      // Add sizing (stack only)
input int                InpSmaP          = 7;               // Fast SMA period (bounce trigger)
input int                InpSlowP         = 0;               // Slow SMA period (geofloor anchor; 0 = off)
input double             InpMult          = 0.01;            // Geometric base multiplier
input double             InpProgStep      = 1.7;             // Geometric step
input double             InpHalf          = 0.5;             // Favourable gate (R) before adds arm
input double             InpTpR           = 3.0;             // Fixed TP in R (0 = none)
input double             InpTrailR        = 0.0;             // Chandelier trail in R (0 = none)

input group              "== Specs / risk (1:2000 assumed) =="
input double             InpTROverride    = 0.0;             // TR $/1.0px/lot override (0 = read live)
input double             InpMPLOverride   = 0.0;             // Margin/lot override (0 = read live)
input int                InpDeviation     = 50;              // Max slippage (points)

input group              "== Telemetry (orchestrator) =="
input string             InpTelemetryURL  = "";              // POST endpoint ("" = off; off in tester)
input int                InpHeartbeatSec  = 30;              // Heartbeat throttle (seconds)

//--- detection constants (V-pattern threshold method, matching signals.py)
#define VOL_MIN  0.01
#define VOL_STEP 0.01
#define VOL_MAX  200.0

//--- operation state (max_conc = 1 -> at most one op) -------------------------
bool     g_inop   = false;     // is an operation open
int      g_dir    = 0;         // +1 long / -1 short
double   g_e0     = 0.0;       // base entry price
double   g_r0     = 0.0;       // R in price units (H1 trigger range)
double   g_E0     = 0.0;       // 1R in $ = account balance at op-open
bool     g_ok     = false;     // favourable gate reached (>= InpHalf*R)
double   g_ext    = 0.0;       // running extreme since entry (for the trail)
bool     g_arm_b  = false;     // bounce armed (price went wrong side of SMA)
datetime g_op_open_time = 0;   // op open timestamp (telemetry)

//--- entry-arming state (pending breakout pair) ------------------------------
datetime g_arm_bar = 0;        // H1 trigger-bar time of the live pending pair
double   g_pH = 0, g_pL = 0, g_pR = 0;   // armed trigger high/low/range

//--- bar-cadence trackers
datetime g_last_h1   = 0;      // last processed entry-TF (H1) bar
datetime g_last_mgmt = 0;      // last processed chart-TF management bar
datetime g_last_hb   = 0;      // last heartbeat send

//--- cached specs
double   g_TR  = 0.0;          // $ P&L per 1.0 price move per 1.0 lot
double   g_MPL = 0.0;          // margin per 1.0 lot ($)
double   g_point = 0.0;

CTrade   g_trade;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(InpDeviation);
   g_point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   RefreshSpecs();
   PrintFormat("[CrossKing:%s] init  sym=%s chartTF=%s entryTF=%s  stack=%d sizing=%d "
               "smaP=%d slowP=%d mult=%.4f step=%.2f tpR=%.2f trailR=%.2f  TR=%.5f MPL=%.5f",
               InpLegName, _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
               EnumToString(InpEntryTF), InpStack, InpSizing, InpSmaP, InpSlowP,
               InpMult, InpProgStep, InpTpR, InpTrailR, g_TR, g_MPL);
   // adopt an already-open op (restart safety): if positions exist, resume managing.
   AdoptExistingOp();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {}

//+------------------------------------------------------------------+
//| Read TR ($/1.0px/lot) and MPL (margin/lot) from the symbol, or   |
//| use the override inputs (for Strategy-Tester calibration).       |
//+------------------------------------------------------------------+
void RefreshSpecs()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   g_TR = (InpTROverride > 0) ? InpTROverride : ((ts > 0) ? tv / ts : 0.0);

   double mpl = 0.0;
   double px  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, 1.0, px, mpl)) mpl = 0.0;
   g_MPL = (InpMPLOverride > 0) ? InpMPLOverride : mpl;
}

//+------------------------------------------------------------------+
//| Quantize down to the lot step (qfloor in pyramid_engine).        |
//+------------------------------------------------------------------+
double QFloor(double x)
{
   return MathFloor(x / VOL_STEP + 1e-9) * VOL_STEP;
}

//+------------------------------------------------------------------+
//| Scan this EA's open positions -> the book (entries[]+lots[]).    |
//| Returns count; sets dir, total lots, weighted entry sums.        |
//+------------------------------------------------------------------+
int ScanBook(double &entries[], double &lots[])
{
   ArrayResize(entries, 0); ArrayResize(lots, 0);
   int cnt = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      double e = PositionGetDouble(POSITION_PRICE_OPEN);
      double v = PositionGetDouble(POSITION_VOLUME);
      int sz = ArraySize(entries);
      ArrayResize(entries, sz + 1); ArrayResize(lots, sz + 1);
      entries[sz] = e; lots[sz] = v;
      cnt++;
   }
   return cnt;
}

double SumLots(const double &lots[])
{
   double s = 0; for(int i = 0; i < ArraySize(lots); i++) s += lots[i]; return s;
}

//+------------------------------------------------------------------+
//| margin_line(book): price where book equity hits 0 (liquidation). |
//| we = sum(e*l)/L ;  return we - dd*E0/(TR*L).                     |
//+------------------------------------------------------------------+
double MarginLine(const double &entries[], const double &lots[], int dd, double E0)
{
   double L = SumLots(lots);
   if(L <= 0 || g_TR <= 0) return 0.0;
   double we = 0; for(int i = 0; i < ArraySize(lots); i++) we += entries[i] * lots[i];
   we /= L;
   return we - dd * E0 / (g_TR * L);
}

//+------------------------------------------------------------------+
//| lot_to_pin: lot to add at P so book liquidation becomes S.       |
//+------------------------------------------------------------------+
double LotToPin(const double &entries[], const double &lots[], double P, double S,
                int dd, double E0)
{
   double A = 0; for(int i = 0; i < ArraySize(lots); i++) A += dd * (S - entries[i]) * lots[i];
   double denom = g_TR * dd * (S - P);
   if(denom >= 0) return 0.0;
   double x = (-E0 - g_TR * A) / denom;
   return MathMax(0.0, QFloor(MathMin(x, VOL_MAX)));
}

//+------------------------------------------------------------------+
//| flr(x): cap, then below-min positive -> use VOL_MIN (pyramid).   |
//+------------------------------------------------------------------+
double Flr(double x)
{
   if(x <= 0) return 0.0;
   double q = QFloor(x);
   return MathMax(VOL_MIN, q);
}

//+------------------------------------------------------------------+
//| Add-lot under the leg's sizing rule (proggeo / geofloor).        |
//| base = book[0] lot ; k = current book size - 1 ; anchor = slow   |
//| SMA (geofloor) ; free-margin cap applied by caller.              |
//+------------------------------------------------------------------+
double SizeAdd(const double &entries[], const double &lots[], double P, double slow,
               int dd, double E0, double ml)
{
   double base = lots[0];
   int    k    = ArraySize(lots) - 1;          // add index (0 for first add)
   double g    = Flr(base * InpMult * MathPow(InpProgStep, k));
   if(InpSizing == CK_PROGGEO)
      return g;
   // geofloor: max(geometric ramp, lot pinning equity-0 to the slow-SMA anchor)
   double S = (dd == 1) ? MathMax(ml, slow) : MathMin(ml, slow);
   double pin = LotToPin(entries, lots, P, S, dd, E0);
   return MathMax(g, pin);
}

//+------------------------------------------------------------------+
//| Apply the free-margin cap: x <= qfloor(eq/MPL - openLots).       |
//| eq = E0 + floating(book @ P).                                    |
//+------------------------------------------------------------------+
double MarginCap(double x, const double &entries[], const double &lots[], double P,
                 int dd, double E0)
{
   if(g_MPL <= 0) return MathMin(x, VOL_MAX);
   double Lb = SumLots(lots);
   double eq = E0;
   for(int i = 0; i < ArraySize(lots); i++) eq += dd * (P - entries[i]) * lots[i] * g_TR;
   double cap = QFloor(MathMax(0.0, eq / g_MPL - Lb));
   return MathMin(MathMin(x, VOL_MAX), cap);
}

//+------------------------------------------------------------------+
//| Normalize a lot to the symbol's step/min/max.                    |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0) step = VOL_STEP;
   lot = MathFloor(lot / step + 1e-9) * step;
   if(lot < minl) lot = minl;
   if(lot > maxl) lot = maxl;
   return lot;
}

//+------------------------------------------------------------------+
//| Write a shared stop (and optional TP) to every open position.    |
//+------------------------------------------------------------------+
void ApplyStopAll(double stop, double tp)
{
   double s  = (stop > 0) ? NormalizeDouble(stop, _Digits) : 0.0;
   double tpn = (tp  > 0) ? NormalizeDouble(tp,  _Digits) : 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      double cur_sl = PositionGetDouble(POSITION_SL);
      double cur_tp = PositionGetDouble(POSITION_TP);
      if(MathAbs(cur_sl - s) < g_point * 0.5 && MathAbs(cur_tp - tpn) < g_point * 0.5) continue;
      g_trade.PositionModify(tk, s, tpn);
   }
}

//+------------------------------------------------------------------+
//| Count / delete this EA's pending orders. which: 0=all,1=buy,2=sell|
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

//+==================================================================+
//|                         MAIN  TICK                                |
//+==================================================================+
void OnTick()
{
   double e_arr[], l_arr[];
   int cnt = ScanBook(e_arr, l_arr);

   // ----- fill / close transitions -----
   if(!g_inop && cnt > 0)              // a breakout stop just filled -> op opens
      OnOpOpened(e_arr, l_arr);
   else if(g_inop && cnt == 0)         // book fully closed -> op done
      OnOpClosed();

   // ----- per-tick safety: keep the sibling pending dead, SL synced -----
   if(g_inop && cnt > 0)
   {
      DeletePendings(g_dir == 1 ? 2 : 1);                 // kill contrary leg promptly
      double stop, tp; ComputeStops(e_arr, l_arr, stop, tp);
      ApplyStopAll(stop, tp);
   }

   Heartbeat(cnt);

   // ----- entry cadence: new H1 bar -> detect + arm (only when flat) -----
   datetime h1b = iTime(_Symbol, InpEntryTF, 0);
   if(h1b != g_last_h1)
   {
      g_last_h1 = h1b;
      EntryCadence();
   }

   // ----- management cadence: new chart bar -> adds + stop ratchet -----
   datetime cb = iTime(_Symbol, _Period, 0);
   if(cb != g_last_mgmt)
   {
      g_last_mgmt = cb;
      if(g_inop) ManagementCadence();
   }
}

//+------------------------------------------------------------------+
//| Op opened: latch e0/r0/E0 from the armed pair + fresh balance.   |
//+------------------------------------------------------------------+
void OnOpOpened(const double &entries[], const double &lots[])
{
   g_inop = true;
   g_dir  = (PositionFirstType() == POSITION_TYPE_BUY) ? 1 : -1;
   g_e0   = (g_dir == 1) ? g_pH : g_pL;     // breakout level = trigger extreme
   g_r0   = g_pR;                            // H1 trigger range
   g_E0   = AccountInfoDouble(ACCOUNT_BALANCE);   // 1R = whole account
   g_ok   = (InpHalf <= 0);
   g_ext  = g_e0;
   g_arm_b = false;
   g_op_open_time = TimeCurrent();
   RefreshSpecs();
   DeletePendings(g_dir == 1 ? 2 : 1);      // cancel the sibling
   double stop, tp; ComputeStops(entries, lots, stop, tp);
   ApplyStopAll(stop, tp);
   PrintFormat("[CrossKing:%s] OP OPEN dir=%d e0=%.5f R=%.5f E0=%.2f", InpLegName, g_dir, g_e0, g_r0, g_E0);
   TelemetryOp("open");
}

//+------------------------------------------------------------------+
//| Op closed: realize R from balance delta, reset, go flat.         |
//+------------------------------------------------------------------+
void OnOpClosed()
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double realizedR = (g_E0 > 0) ? (bal - g_E0) / g_E0 : 0.0;
   PrintFormat("[CrossKing:%s] OP CLOSE  R=%.3f  bal=%.2f", InpLegName, realizedR, bal);
   TelemetryOpClose(realizedR);
   g_inop = false; g_dir = 0; g_e0 = g_r0 = g_E0 = g_ext = 0; g_ok = false; g_arm_b = false;
   DeletePendings(0);
}

ENUM_POSITION_TYPE PositionFirstType()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      return (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   }
   return POSITION_TYPE_BUY;
}

//+------------------------------------------------------------------+
//| Compute the shared stop (and TP) for the open op given the book. |
//|   stop = margin_line ; trail leg -> max(margin_line, ext-trailR) |
//|   tp   = e0 + dd*tp_R*R  (0 if tp_R == 0)                        |
//+------------------------------------------------------------------+
void ComputeStops(const double &entries[], const double &lots[], double &stop, double &tp)
{
   double ml = MarginLine(entries, lots, g_dir, g_E0);
   if(InpTrailR > 0)
   {
      double trail = g_ext - g_dir * InpTrailR * g_r0;
      stop = (g_dir == 1) ? MathMax(ml, trail) : MathMin(ml, trail);
   }
   else
      stop = ml;
   tp = (InpTpR > 0) ? (g_e0 + g_dir * InpTpR * g_r0) : 0.0;
}

//+==================================================================+
//|   ENTRY CADENCE  (closed H1 bar; arm only when flat, no pendings) |
//+==================================================================+
void EntryCadence()
{
   if(g_inop) return;                          // max_conc = 1: no new op while open
   // stale-cancel a pending pair older than InpBreakBars H1 bars (gap-immune)
   if(CountPendings() > 0)
   {
      if(iBarShift(_Symbol, InpEntryTF, g_arm_bar, false) >= InpBreakBars)
         DeletePendings(0);
      return;                                  // keep waiting for a fill
   }
   if(!IsTriggerBar()) return;
   double th = iHigh(_Symbol, InpEntryTF, 1), tl = iLow(_Symbol, InpEntryTF, 1);
   double rng = th - tl;
   if(rng <= 0) return;
   ArmStop(true,  th, tl);                      // Buy Stop @ high, SL = low
   ArmStop(false, tl, th);                      // Sell Stop @ low, SL = high
   g_pH = th; g_pL = tl; g_pR = rng; g_arm_bar = iTime(_Symbol, InpEntryTF, 0);
}

//+------------------------------------------------------------------+
//| Place one sized breakout stop. Lot pins equity-0 onto the        |
//| structural SL: lot0 = E0/(TR*R), free-margin & broker capped.    |
//+------------------------------------------------------------------+
void ArmStop(bool is_buy, double price, double sl)
{
   double E0 = AccountInfoDouble(ACCOUNT_BALANCE);
   double rng = MathAbs(price - sl);
   if(rng <= 0 || g_TR <= 0) return;
   double lot = E0 / (g_TR * rng);              // lot_to_pin([], entry, SL) = E0/(TR*R)
   lot = MathMax(QFloor(lot), VOL_MIN);
   if(g_MPL > 0) lot = MathMin(lot, QFloor(E0 / g_MPL));   // base must fit the deposit
   lot = MathMin(lot, VOL_MAX);
   lot = NormalizeLot(lot);
   if(lot <= 0) return;
   price = NormalizeDouble(price, _Digits);
   sl    = NormalizeDouble(sl, _Digits);
   double minstop = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * g_point;
   if(is_buy)
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(price - ask < minstop) return;
      g_trade.BuyStop(lot, price, _Symbol, 0.0, 0.0, ORDER_TIME_GTC, 0, "CK_" + InpLegName);
   }
   else
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(bid - price < minstop) return;
      g_trade.SellStop(lot, price, _Symbol, 0.0, 0.0, ORDER_TIME_GTC, 0, "CK_" + InpLegName);
   }
}

//+==================================================================+
//|   MANAGEMENT CADENCE  (closed chart bar; the just-closed bar = 1) |
//|   Order mirrors conc_engine: update ext (trail) -> update ok ->   |
//|   evaluate the SMA-bounce add -> re-sync the shared stop.         |
//+==================================================================+
void ManagementCadence()
{
   double e_arr[], l_arr[];
   int cnt = ScanBook(e_arr, l_arr);
   if(cnt == 0) return;

   double bh = iHigh(_Symbol, _Period, 1), bl = iLow(_Symbol, _Period, 1),
          bc = iClose(_Symbol, _Period, 1);

   // 1) running extreme (for the chandelier trail) -- updated AFTER the bar's exit
   if(g_dir == 1) g_ext = MathMax(g_ext, bh);
   else           g_ext = MathMin(g_ext, bl);

   // 2) favourable gate: fav = dd*((H or L) - e0)/R  >= half  -> latch ok
   double adv = (g_dir == 1) ? bh : bl;
   double fav = g_dir * (adv - g_e0) / g_r0;
   if(fav >= InpHalf) g_ok = true;

   // 3) SMA-bounce add (stack presets only)
   if(InpStack && g_ok)
   {
      double sma = SmaClose(InpSmaP, 1);
      bool wrong = (g_dir == 1) ? (bc < sma) : (bc > sma);
      bool back  = (g_dir == 1) ? (bc >= sma) : (bc <= sma);
      if(wrong)
         g_arm_b = true;
      else if(back && g_arm_b)
      {
         g_arm_b = false;
         double last = LadderExtreme(e_arr);                 // most-recent add entry
         bool gated = (g_dir == 1) ? (bc > last) : (bc < last);
         if(gated)
            DoAdd(e_arr, l_arr, bc);
      }
   }

   // 4) re-sync the shared stop/TP to the (possibly enlarged) book
   double e2[], l2[]; ScanBook(e2, l2);
   double stop, tp; ComputeStops(e2, l2, stop, tp);
   ApplyStopAll(stop, tp);
}

//+------------------------------------------------------------------+
//| Place one stacking add (market order at ~close).                 |
//+------------------------------------------------------------------+
void DoAdd(const double &entries[], const double &lots[], double P)
{
   double slow = (InpSlowP > 0) ? SmaClose(InpSlowP, 1) : 0.0;
   double ml   = MarginLine(entries, lots, g_dir, g_E0);
   double x    = SizeAdd(entries, lots, P, slow, g_dir, g_E0, ml);
   x = MarginCap(x, entries, lots, P, g_dir, g_E0);
   if(x < VOL_STEP) return;
   x = NormalizeLot(x);
   if(x <= 0) return;
   bool ok = (g_dir == 1) ? g_trade.Buy(x, _Symbol, 0.0, 0.0, 0.0, "CK_" + InpLegName + "_add")
                          : g_trade.Sell(x, _Symbol, 0.0, 0.0, 0.0, "CK_" + InpLegName + "_add");
   if(ok)
   {
      PrintFormat("[CrossKing:%s] ADD lot=%.2f @~%.5f  depth->%d", InpLegName, x, P, ArraySize(lots) + 1);
      TelemetryOp("add");
   }
}

//+------------------------------------------------------------------+
//| Most-recent add entry (gate reference): the rising/falling       |
//| ladder's extreme = max entry (long) / min entry (short).         |
//+------------------------------------------------------------------+
double LadderExtreme(const double &entries[])
{
   double v = entries[0];
   for(int i = 1; i < ArraySize(entries); i++)
      v = (g_dir == 1) ? MathMax(v, entries[i]) : MathMin(v, entries[i]);
   return v;
}

//+------------------------------------------------------------------+
//| SMA of CLOSE over `period` on the chart TF, ending at shift.     |
//+------------------------------------------------------------------+
double SmaClose(int period, int shift)
{
   if(period <= 0) return 0.0;
   double c[];
   if(CopyClose(_Symbol, _Period, shift, period, c) < period) return 0.0;
   double s = 0; for(int i = 0; i < period; i++) s += c[i];
   return s / period;
}

//+------------------------------------------------------------------+
//| Adopt an already-open op after a restart (best-effort).          |
//+------------------------------------------------------------------+
void AdoptExistingOp()
{
   double e_arr[], l_arr[];
   int cnt = ScanBook(e_arr, l_arr);
   if(cnt == 0) return;
   g_inop = true;
   g_dir  = (PositionFirstType() == POSITION_TYPE_BUY) ? 1 : -1;
   // r0/e0 unknown across restart -> reconstruct conservatively from the book:
   // e0 = the worst (first) leg entry; ext = current extreme; R from the SL distance.
   double worst = e_arr[0];
   for(int i = 1; i < cnt; i++) worst = (g_dir == 1) ? MathMin(worst, e_arr[i]) : MathMax(worst, e_arr[i]);
   g_e0  = worst;
   double sl0 = PositionAnySL();
   g_r0  = (sl0 > 0) ? MathAbs(g_e0 - sl0) : MathAbs(g_e0 - MarginLine(e_arr, l_arr, g_dir, AccountInfoDouble(ACCOUNT_BALANCE)));
   g_E0  = AccountInfoDouble(ACCOUNT_BALANCE);   // approximation post-restart
   g_ok  = true;                                  // assume gate already passed
   g_ext = (g_dir == 1) ? iHigh(_Symbol, _Period, 0) : iLow(_Symbol, _Period, 0);
   PrintFormat("[CrossKing:%s] ADOPTED open op dir=%d e0=%.5f R=%.5f (post-restart)", InpLegName, g_dir, g_e0, g_r0);
}

double PositionAnySL()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(sl > 0) return sl;
   }
   return 0.0;
}

//+==================================================================+
//|   DETECTION  (V-pattern threshold; reused from the Book EA)       |
//+==================================================================+
bool IsTriggerBar()
{
   int win = 3 * InpMAPeriod, total = win + 6;
   long vol[]; datetime time[];
   ArraySetAsSeries(vol, true); ArraySetAsSeries(time, true);
   if(CopyTickVolume(_Symbol, InpEntryTF, 0, total, vol) < total) return false;
   if(CopyTime(_Symbol, InpEntryTF, 0, total, time) < total) return false;
   return TriggerFired(vol, 1);
}

bool TriggerFired(const long &vol[], int idx)
{
   double s1 = ThresholdAt(vol, idx), s2 = ThresholdAt(vol, idx + 1), s3 = ThresholdAt(vol, idx + 2);
   if(!(s3 > s2 && s1 > s2)) return false;          // V shape on the threshold line
   return ((s1 - s2) / MathMax(MathAbs(s2), 1e-10) >= InpRisePct);
}

double ThresholdAt(const long &vol[], int idx)      // ma + mult*popStdDev
{
   double ma = VolMA(vol, idx), std = VolStd(vol, idx, ma);
   return ma + InpMultiplier * std;
}

double VolMA(const long &vol[], int idx)
{
   double sum = 0;
   for(int k = 0; k < InpMAPeriod; k++) sum += (double)vol[idx + k];
   return sum / InpMAPeriod;
}

double VolStd(const long &vol[], int idx, double ma)
{
   double sq = 0;
   for(int k = 0; k < InpMAPeriod; k++) { double d = (double)vol[idx + k] - ma; sq += d * d; }
   return (InpMAPeriod > 1) ? MathSqrt(sq / InpMAPeriod) : 0.0;   // population std (ddof=0)
}

//+==================================================================+
//|   TELEMETRY  (orchestrator; no-op in tester / when URL empty)     |
//+==================================================================+
bool TelemetryEnabled()
{
   return (InpTelemetryURL != "" && !(bool)MQLInfoInteger(MQL_TESTER));
}

void PushJson(string body)
{
   if(!TelemetryEnabled()) return;
   char post[], result[]; string headers = "Content-Type: application/json\r\n", rhdr;
   StringToCharArray(body, post, 0, StringLen(body), CP_UTF8);
   int sz = ArraySize(post); if(sz > 0) ArrayResize(post, sz - 1);   // drop trailing NUL
   int code = WebRequest("POST", InpTelemetryURL, headers, 5000, post, result, rhdr);
   if(code == -1) PrintFormat("[CrossKing:%s] WebRequest failed err=%d (whitelist the URL)", InpLegName, GetLastError());
}

void Heartbeat(int cnt)
{
   if(!TelemetryEnabled()) return;
   datetime now = TimeCurrent();
   if(now - g_last_hb < InpHeartbeatSec) return;
   g_last_hb = now;
   string body = StringFormat("{\"type\":\"heartbeat\",\"leg\":\"%s\",\"symbol\":\"%s\",\"ver\":\"%s\","
                              "\"ts\":%d,\"balance\":%.2f,\"equity\":%.2f,\"open\":%s,\"depth\":%d}",
                              InpLegName, _Symbol, "1.00", (long)now,
                              AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
                              (g_inop ? "true" : "false"), cnt);
   PushJson(body);
}

void TelemetryOp(string ev)
{
   if(!TelemetryEnabled()) return;
   double e_arr[], l_arr[]; ScanBook(e_arr, l_arr);
   double ml = MarginLine(e_arr, l_arr, g_dir, g_E0);
   string body = StringFormat("{\"type\":\"op\",\"event\":\"%s\",\"leg\":\"%s\",\"symbol\":\"%s\","
                              "\"dir\":%d,\"e0\":%.5f,\"R\":%.5f,\"E0\":%.2f,\"depth\":%d,"
                              "\"lots\":%.2f,\"ml\":%.5f,\"equity\":%.2f}",
                              ev, InpLegName, _Symbol, g_dir, g_e0, g_r0, g_E0,
                              ArraySize(l_arr), SumLots(l_arr), ml, AccountInfoDouble(ACCOUNT_EQUITY));
   PushJson(body);
}

void TelemetryOpClose(double realizedR)
{
   if(!TelemetryEnabled()) return;
   string body = StringFormat("{\"type\":\"op\",\"event\":\"close\",\"leg\":\"%s\",\"symbol\":\"%s\","
                              "\"dir\":%d,\"R\":%.4f,\"E0\":%.2f,\"open_ts\":%d,\"close_ts\":%d,"
                              "\"balance\":%.2f}",
                              InpLegName, _Symbol, g_dir, realizedR, g_E0,
                              (long)g_op_open_time, (long)TimeCurrent(),
                              AccountInfoDouble(ACCOUNT_BALANCE));
   PushJson(body);
}
//+------------------------------------------------------------------+
