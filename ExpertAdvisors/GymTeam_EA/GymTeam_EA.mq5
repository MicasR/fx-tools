//+------------------------------------------------------------------+
//|                                               GymTeam_EA.mq5       |
//|                                          Dercio Micas - 2026       |
//|                                                                    |
//|  THE fx_gym PROM-3 team binary (docs/PROM3_TEAM_SPEC.md): one      |
//|  binary, SIGNAL MODULES (InpSignal), per-leg .set presets.         |
//|  Derived from CrossKing_EA (all mechanics identical & validated:   |
//|  OCO breakout entry, whole-account sizing, margin-line, stacking,  |
//|  OnTester NBP scoring + weekly prom-date vectors, telemetry).      |
//|  NEW vs CrossKing:                                                 |
//|   * InpSignal module switch: V-pattern (legacy), NR7, inside bar,  |
//|     NR7-or-inside (comp), warm+hours. Crown presets: JPY_H4_nr7    |
//|     and XAU_H4_comp are the NR7 module on H4 charts (comp = nr7    |
//|     UNION nr7&inside = nr7); BTC_wh_shield = warm+hours on H1.     |
//|   * InpMaxHoldBars: close the op at market after N entry-TF bars   |
//|     (fxgym simulate_ops max_hold=240; exit reason "END").          |
//|   * Tester op log: single-pass tester runs append every closed op  |
//|     to MQL5/Files/gt_ops_<leg>.csv (open/close time, dir, R) for   |
//|     the shadow-stream gate (fxgym is the oracle, <15% divergence). |
//|                                                                    |
//|  CrossKing heritage (unchanged mechanics):                         |
//|  port of  backtest/conc_engine.run_tf_conc (max_conc = 1)  +       |
//|  pyramid_engine primitives (margin_line / lot_to_pin / proggeo /   |
//|  geofloor sizing).                                                 |
//|                                                                    |
//|  Model ("EA-dumb / orchestrator-brain"): the EA risks its WHOLE    |
//|  account balance per operation. E0 = balance at op-open; the base  |
//|  lot pins the broker equity-0 line onto the structural SL, so a    |
//|  full stop = -E0 = -1R = the whole account. All portfolio          |
//|  weighting/pooling lives in how much cash the orchestrator funds    |
//|  each account with -- NOT in this EA.                              |
//|                                                                    |
//|  Mechanics (one operation at a time, max_conc = 1):                |
//|   CHART ON H1 ALWAYS (entry native to the chart); InpEntryTF=H1,    |
//|   InpMgmtTF = the add/bounce/trail TF (gold M15, BTC H1). Decoupling |
//|   chart from mgmt kills the tester's cross-TF H1-volume reconstruct  |
//|   (FIDELITY_PLAN §3.2): live `CopyTickVolume(H1)` reads real H1 bars.|
//|   1. ENTRY (InpEntryTF=H1, native to the H1 chart): V-pattern volume |
//|      trigger on a closed H1 bar -> arm an OCO breakout pair (Buy    |
//|      Stop @ trigger high, Sell Stop @ trigger low); first fill      |
//|      starts the op, sibling cancelled; stale-cancel after 4 H1      |
//|      bars. R = trigger H1 bar range; SL = opposite extreme.         |
//|   2. BASE SIZE: lot0 = E0/(TR*R) (pins equity-0 to the structural   |
//|      SL), capped by free margin and broker max.                     |
//|   3. STACK (stack presets): on a fast-SMA(InpMgmtTF) close bounce    |
//|      (wrong side then back), GATED (close beyond the last add AND op |
//|      >= 0.5R favourable), add one position. proggeo: base*mult*step^k|
//|      geofloor: max(that, lot pinning equity-0 to the slow SMA).     |
//|      Each add capped by free margin (eq/MPL - openLots).            |
//|   4. FLOOR / EXIT: the synthetic SL = margin_line(book) (equity-0)  |
//|      is written to EVERY position each InpMgmtTF bar -> the whole    |
//|      book exits together at -1R. Plus, per preset, a fixed TP =     |
//|      e0 + tp_R*R, OR a chandelier trail = max(margin_line,          |
//|      extreme - trail_R*R) for the BTC gf leg (tp_R = 0).            |
//|                                                                    |
//|  Entry detection block (V-pattern threshold) is reused from        |
//|  VolumeSpikeBreakOut_Book_EA; the management core is a NEW port of  |
//|  conc_engine, NOT the Book EA's confBtrail model.                  |
//|                                                                    |
//|  Scope: gold (XAU, mgmt M15) & BTC (BTC, mgmt H1); CHART BOTH ON H1.|
//|  Leverage 1:2000.                                                   |
//|  ** Validate every preset in the Strategy Tester against           |
//|     backtest/out/shadow/<leg>.csv BEFORE any live use. **          |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.00"
#property description "fx_gym PROM-3 team binary: one EA, signal modules, per-leg presets (CrossKing core)."

#include <Trade\Trade.mqh>

enum ENUM_CK_SIZING  { CK_PROGGEO = 0, CK_GEOFLOOR = 1 };          // stack add-sizing rule
enum ENUM_CK_ADDTRIG { ADD_SMA_BOUNCE = 0, ADD_POSCANDLE = 1 };    // when an add arms (RSI_RECOVERY reserved)
enum ENUM_CK_LINE    { LINE_MARGIN = 0, LINE_NBACK = 1, LINE_PINPREV = 2 }; // add liquidation anchor
enum ENUM_GT_SIGNAL  { SIG_VPATTERN = 0, SIG_NR7 = 1, SIG_INSIDE = 2,      // the signal modules
                       SIG_NR7_OR_INSIDE = 3, SIG_WARMHOURS = 4,
                       SIG_KELTNER = 5, SIG_ENGULF = 6,                    // thread-36 live-mechanics
                       SIG_DONCHIAN = 7, SIG_MA_ALIGN = 8 };               // survivors (fat-bar family)

input group              "== Leg identity / preset =="
input string             InpLegName       = "JPY_H4_nr7";   // Leg name (telemetry)
input long               InpMagicNumber   = 20260705;       // Magic number (unique per account)

input group              "== Signal module (fx_gym generator; closed entry-TF bars) =="
input ENUM_GT_SIGNAL     InpSignal        = SIG_NR7;        // Signal module (the fire generator)
input ENUM_TIMEFRAMES    InpEntryTF       = PERIOD_H4;      // Entry/signal TF (= chart TF for price signals)
input int                InpBreakBars     = 4;              // Breakout OCO window (entry-TF bars)
input int                InpMaxHoldBars   = 240;            // Max op hold in entry-TF bars (fxgym max_hold; 0=off)
input int                InpNRWindow      = 7;              // NR window: bar range == N-bar min (SIG_NR7*)
input int                InpMAPeriod      = 20;             // V-pattern: volume MA period
input double             InpMultiplier    = 2.0;            // V-pattern: threshold = MA + mult*popStdDev
input double             InpRisePct       = 0.02;           // V-pattern: V rise leg (>= 2%)
input string             InpWHHours       = "12,13,14,15,16"; // warm+hours: allowed bar hours (server time)
input double             InpWHLo          = 80.0;           // warm+hours: vol_pct > this
input double             InpWHHi          = 98.0;           // warm+hours: vol_pct <= this
input int                InpWHPctWin      = 100;            // warm+hours: percentile window (incl current bar)
input int                InpKelP          = 20;             // Keltner: EMA period
input double             InpKelMult       = 2.0;            // Keltner: ATR multiple
input int                InpATRP          = 14;             // ATR period (SMA of TR; Keltner/ma_align)
input int                InpDonP          = 55;             // Donchian lookback
input int                InpAlignFast     = 10;             // ma_align: fast SMA
input int                InpAlignSlow     = 50;             // ma_align: slow SMA
input double             InpAlignImp      = 1.2;            // ma_align: impulse rng > x*ATR

input group              "== Management core (the preset knobs) =="
input ENUM_TIMEFRAMES    InpMgmtTF        = PERIOD_M15;       // Management TF: bounce/add/trail cadence (gold M15, BTC H1)
input bool               InpStack         = true;            // Stack adds (false = shield: single pos)
input ENUM_CK_SIZING     InpSizing        = CK_PROGGEO;      // Add sizing (stack only)
input int                InpSmaP          = 7;               // Fast SMA period (bounce trigger)
input int                InpSlowP         = 0;               // Slow SMA period (geofloor anchor; 0 = off)
input double             InpMult          = 0.01;            // Geometric base multiplier
input double             InpProgStep      = 1.7;             // Geometric step
input double             InpHalf          = 0.5;             // Favourable gate (R) before adds arm
input double             InpTpR           = 3.0;             // Fixed TP in R (0 = none)
input double             InpTrailR        = 0.0;             // Chandelier trail in R (0 = none)
input ENUM_CK_ADDTRIG    InpAddTrigger    = ADD_SMA_BOUNCE;  // Add trigger: SMA-bounce vs poscandle
input ENUM_CK_LINE       InpLinePlace     = LINE_MARGIN;     // Add anchor: margin / N-back struct / pinprev
input int                InpNBack         = 0;               // N candles back for structural anchor (LINE_NBACK)
input double             InpLineBuffer    = 0.0;             // Margin-line buffer in R (0=aggressive; >0=keep line >= buf*R from price)

input group              "== Specs / risk (1:2000 assumed) =="
input double             InpFixedE0       = 0.0;             // Fixed 1R in $ (0 = whole balance/LIVE; >0 = tester validation)
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
double   g_E0     = 0.0;       // 1R in $ (whole balance at op-open, or InpFixedE0)
double   g_bal_open = 0.0;     // account balance at op-open (for realized-R = PnL/E0)
bool     g_ok     = false;     // favourable gate reached (>= InpHalf*R)
double   g_ext    = 0.0;       // running extreme since entry (for the trail)
bool     g_arm_b  = false;     // bounce armed (price went wrong side of SMA)
double   g_anc_b  = 0.0;       // current bounce extreme accumulator (0 = none)
double   g_prev_anc = 0.0;     // previous bounce extreme (LINE_PINPREV reference)
datetime g_op_open_time = 0;   // op open timestamp (telemetry)
//--- geometric add-sizing state (latched at op-open; do NOT derive from the live
//--- book -- MT5's PositionsTotal() order is newest-first, so ScanBook()[0] is the
//--- most-recent add, NOT the base.  Reading the base/k off the book collapsed the
//--- proggeo/geofloor ramp to 0.01 on every gold stack (the dominant fidelity gap;
//--- see backtest/FIDELITY_FINDINGS.md).  Mirrors Python: base = pos[0] lot, the
//--- geometric add index k = number of adds already placed (= len(pos)-1).
double   g_base_lot = 0.0;     // base-position volume = geometric unit lot
int      g_add_count = 0;      // adds placed so far = geometric index k for the next add

//--- OnTester scoring: chronological per-op realized-R stream (FIDELITY §3.6 search).
//--- OnTester NBP-clamps it (loss capped at -1R, the live accounting) and returns a
//--- robustness-weighted score so the MT5 optimizer surfaces robust kings, not 1-op
//--- jackpots.  Mirrors backtest/tester_truth.py.
double   g_opR[];              // realized R per closed op, in order
//--- "PROM DATE" (FIDELITY §3.6): each pass also ships its performance-IN-TIME, so the
//--- Python selector can pick a TEAM whose members lift each other on bad weeks
//--- (empirical time-decorrelation), not by pre-assigned shield/sword roles. Calendar
//--- WEEKLY buckets of NBP-clamped R from a fixed epoch = the common clock to align
//--- different EAs (op index can't align across EAs; calendar time can).
#define  CK_EPOCH   D'2024.02.26 00:00'
#define  CK_WEEKSEC 604800
#define  CK_NWEEK   130            // weeks 2024-02-26 .. ~2026-08 (covers the test window)
#define  CK_NMETA   26             // leading metadata columns shipped before the weekly vector
#define  CK_MONSTER_R 5.0          // op R >= this counts as a "monster" (aggressive-gate diagnostic)
double   g_week[CK_NWEEK];      // NBP-clamped R summed per calendar week

//--- entry-arming state (pending breakout pair) ------------------------------
datetime g_arm_bar = 0;        // H1 trigger-bar time of the live pending pair
double   g_pH = 0, g_pL = 0, g_pR = 0;   // armed trigger high/low/range

//--- bar-cadence trackers
datetime g_last_h1   = 0;      // last processed entry-TF (H1) bar
datetime g_last_mgmt = 0;      // last processed chart-TF management bar
datetime g_last_hb   = 0;      // last heartbeat send
bool     g_halt      = false;  // orchestrator "no new ops" flag (polled; fail-open)

//--- signal-module state / shadow-gate op log
bool     g_wh_hours[24];       // warm+hours allowed-hour lookup (parsed from InpWHHours)
int      g_ops_fh = INVALID_HANDLE;   // tester op-log CSV (single pass only; the shadow gate)

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
   ArrayResize(g_opR, 0);                       // fresh R-stream per (optimization) pass
   ArrayInitialize(g_week, 0.0);                // fresh weekly performance vector (prom date)
   ParseWHHours();
   // shadow-gate op log: single-pass tester runs only (fxgym oracle comparison)
   if((bool)MQLInfoInteger(MQL_TESTER) && !(bool)MQLInfoInteger(MQL_OPTIMIZATION))
   {
      g_ops_fh = FileOpen("gt_ops_" + InpLegName + ".csv", FILE_WRITE | FILE_TXT | FILE_ANSI);
      if(g_ops_fh != INVALID_HANDLE)
         FileWrite(g_ops_fh, "open_time,close_time,dir,positions,realizedR,"
                             "entry_px,exit_px,lots,profit,swap,commission,E0,r0");
   }
   RefreshSpecs();
   PrintFormat("[GymTeam:%s] init  sym=%s chartTF=%s signal=%s entryTF=%s mgmtTF=%s  stack=%d sizing=%d "
               "smaP=%d slowP=%d mult=%.4f step=%.2f tpR=%.2f trailR=%.2f maxHold=%d  TR=%.5f MPL=%.5f",
               InpLegName, _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period), EnumToString(InpSignal),
               EnumToString(InpEntryTF), EnumToString(InpMgmtTF), InpStack, InpSizing, InpSmaP, InpSlowP,
               InpMult, InpProgStep, InpTpR, InpTrailR, InpMaxHoldBars, g_TR, g_MPL);
   // adopt an already-open op (restart safety): if positions exist, resume managing.
   AdoptExistingOp();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_ops_fh != INVALID_HANDLE) { FileClose(g_ops_fh); g_ops_fh = INVALID_HANDLE; }
}

//+------------------------------------------------------------------+
//| Parse InpWHHours ("12,13,14,15,16") -> g_wh_hours[24] lookup.     |
//+------------------------------------------------------------------+
void ParseWHHours()
{
   for(int i = 0; i < 24; i++) g_wh_hours[i] = false;
   string parts[];
   int n = StringSplit(InpWHHours, ',', parts);
   for(int i = 0; i < n; i++)
   {
      string s = parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      int h = (int)StringToInteger(s);
      if(h >= 0 && h < 24) g_wh_hours[h] = true;
   }
}

//+==================================================================+
//|  OnTester — the FIDELITY §3.6 search criterion.                  |
//|  NBP-clamp the op R-stream (loss capped at -1R = live accounting),|
//|  then return a robustness-weighted score: nbpR * (positive 6-seg  |
//|  count / 6).  This rewards BOTH magnitude and 6-segment robustness|
//|  so the optimizer surfaces durable kings, not single-op jackpots. |
//|  Finalists are re-run single-pass for the full fingerprint + the   |
//|  portfolio blend (Python).  Mirrors backtest/tester_truth.py.     |
//+==================================================================+
double OnTester()
{
   int n = ArraySize(g_opR);
   if(n <= 0) return 0.0;
   double nbpR = 0.0, cum = 0.0, peak = 0.0, dd = 0.0, mx = -1e18;
   int nmonster = 0;                               // ops >= CK_MONSTER_R (aggressive recurrence)
   for(int i = 0; i < n; i++)
   {
      double r = MathMax(g_opR[i], -1.0);          // negative-balance protection
      nbpR += r;
      cum += r; if(cum > peak) peak = cum; if(peak - cum > dd) dd = peak - cum;
      if(r > mx) mx = r;
      if(r >= CK_MONSTER_R) nmonster++;
   }
   double extop1R = nbpR - mx;                      // totR ex the single best op (repeatability)
   // positive 6-segment count (equal-count chunks, chronological)
   int q = n / 6, segpos = 0;
   for(int k = 0; k < 6; k++)
   {
      int a = k * q, b = (k == 5) ? n : (k + 1) * q;
      double s = 0.0; for(int i = a; i < b; i++) s += MathMax(g_opR[i], -1.0);
      if(s > 0) segpos++;
   }
   // R2 (championship): segment-positive count after removing the 3 biggest WINNING ops.
   // Admits aggressive legs (high oneop OK) but proves the edge isn't carried by <=3 trades.
   int top3[3]; top3[0] = top3[1] = top3[2] = -1;
   for(int t = 0; t < 3; t++)
   {
      double bv = -1e18; int bi = -1;
      for(int i = 0; i < n; i++)
      {
         if(i == top3[0] || i == top3[1] || i == top3[2]) continue;
         if(g_opR[i] > bv) { bv = g_opR[i]; bi = i; }
      }
      top3[t] = bi;
   }
   int segpos_ex3 = 0;
   for(int k = 0; k < 6; k++)
   {
      int a = k * q, b = (k == 5) ? n : (k + 1) * q;
      double s = 0.0;
      for(int i = a; i < b; i++)
      {
         if(i == top3[0] || i == top3[1] || i == top3[2]) continue;   // drop the 3 biggest winners
         s += MathMax(g_opR[i], -1.0);
      }
      if(s > 0) segpos_ex3++;
   }
   // R3 (championship): anti-recency -- totR in the first vs second half of the window.
   int hmid = n / 2; double h1R = 0.0, h2R = 0.0;
   for(int i = 0; i < n; i++)
   { double r = MathMax(g_opR[i], -1.0); if(i < hmid) h1R += r; else h2R += r; }
   int wins = 0; for(int i = 0; i < n; i++) if(g_opR[i] > 0) wins++;
   double win   = 100.0 * wins / n;
   double rf    = (dd > 0) ? nbpR / dd : 0.0;
   double oneop = (nbpR > 0) ? mx / nbpR : 0.0;
   double score = nbpR * (segpos / 6.0);            // robustness-weighted (the criterion)
   PrintFormat("[GymTeam:%s] OnTester  ops=%d nbpR=%.1f segpos=%d/6 RF=%.1f 1op=%.0f%% score=%.1f",
               InpLegName, n, nbpR, segpos, rf, 100.0 * oneop, score);
   // ship metrics, this pass's params, AND its weekly performance vector (prom date)
   // back to the terminal (the agent holds the correct Inp*/g_week for the pass) -> OnTesterPass
   double data[CK_NMETA + CK_NWEEK];
   data[0] = score; data[1] = nbpR; data[2] = (double)segpos; data[3] = rf;
   data[4] = 100.0 * oneop; data[5] = (double)n; data[6] = win;
   data[7] = (double)InpSizing; data[8] = (double)InpSmaP; data[9] = (double)InpSlowP;
   data[10] = InpMult; data[11] = InpProgStep; data[12] = InpTpR; data[13] = InpTrailR;
   data[14] = InpHalf; data[15] = (double)InpMgmtTF; data[16] = InpStack ? 1.0 : 0.0;
   data[17] = extop1R; data[18] = (double)nmonster; data[19] = (double)InpAddTrigger;
   data[20] = (double)InpLinePlace; data[21] = (double)InpNBack; data[22] = InpLineBuffer;
   data[23] = (double)segpos_ex3; data[24] = h1R; data[25] = h2R;
   for(int w = 0; w < CK_NWEEK; w++) data[CK_NMETA + w] = g_week[w];
   FrameAdd("ck", 0, score, data);
   return score;
}

//+------------------------------------------------------------------+
//| Optimization result collection (terminal side). Frames from every|
//| pass (local + MQL5 Cloud) -> one CSV row per pass with its inputs.|
//| -> MQL5/Files/ck_opt.csv ; the harness copies it out per sweep.  |
//+------------------------------------------------------------------+
int g_opt_fh = INVALID_HANDLE;

int OnTesterInit()
{
   g_opt_fh = FileOpen("gt_opt.csv", FILE_WRITE | FILE_TXT | FILE_ANSI);   // TXT: variable cols
   if(g_opt_fh != INVALID_HANDLE)
   {
      string hdr = "pass,score,nbpR,segpos,rf,oneop,ops,win,"
                   "sizing,smaP,slowP,mult,step,tpR,trailR,half,mgmtTF,stack,"
                   "extop1R,nmonster,addtrig,lineplace,nback,buffer,"
                   "segpos_ex3,h1R,h2R";
      for(int w = 0; w < CK_NWEEK; w++) hdr += ",w" + IntegerToString(w);
      FileWrite(g_opt_fh, hdr);
   }
   return INIT_SUCCEEDED;
}

void OnTesterPass()
{
   ulong pass; string fname; long fid; double fval; double data[];
   while(FrameNext(pass, fname, fid, fval, data))
   {
      if(g_opt_fh == INVALID_HANDLE || ArraySize(data) < CK_NMETA + CK_NWEEK) continue;
      string row = StringFormat("%d,%.4f,%.4f,%d,%.4f,%.2f,%d,%.4f,%d,%d,%d,%.5f,%.3f,%.3f,%.3f,%.3f,%d,%d,"
                   "%.4f,%d,%d,%d,%d,%.3f,%d,%.4f,%.4f",
                   (long)pass, data[0], data[1], (int)data[2], data[3], data[4], (int)data[5], data[6],
                   (int)data[7], (int)data[8], (int)data[9], data[10], data[11], data[12], data[13],
                   data[14], (int)data[15], (int)data[16],
                   data[17], (int)data[18], (int)data[19], (int)data[20], (int)data[21], data[22],
                   (int)data[23], data[24], data[25]);
      for(int w = 0; w < CK_NWEEK; w++) row += "," + DoubleToString(data[CK_NMETA + w], 3);
      FileWrite(g_opt_fh, row);
   }
}

void OnTesterDeinit()
{
   if(g_opt_fh != INVALID_HANDLE) { FileClose(g_opt_fh); g_opt_fh = INVALID_HANDLE; }
}

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
//| 1R in $ for a new op. LIVE: whole account balance (the orchestrator|
//| keeps the account ~1R). TESTER: InpFixedE0 > 0 pins E0 constant so |
//| the lone account does not self-compound (no orchestrator sweep) -- |
//| matches the backtest's fixed E0 = risk_frac*cap0.                  |
//+------------------------------------------------------------------+
double OpE0()
{
   return (InpFixedE0 > 0) ? InpFixedE0 : AccountInfoDouble(ACCOUNT_BALANCE);
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
   return MathMax(0.0, QFloor(x));    // per-order VOL_MAX now applied at placement (PlaceSplit)
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
//| base = g_base_lot (latched at open) ; k = g_add_count (adds so   |
//| far) ; anchor = slow SMA (geofloor) ; free-margin cap by caller. |
//| NB: base/k come from latched op-state, NOT lots[0]/ArraySize --   |
//| the live book is newest-first and (with order splits) longer than |
//| the add count, both of which break the geometric ramp.           |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Buffer floor: keep the pin target >= InpLineBuffer*R from price P |
//| (mirrors conc_engine floored_anchor). 0 buffer = aggressive: the  |
//| line may hug price -> margin-maxed lot. >0 caps the pin family.   |
//+------------------------------------------------------------------+
double FloorAnchor(double S, double P, int dd)
{
   if(InpLineBuffer <= 0.0) return S;
   double buf = InpLineBuffer * g_r0;
   return (dd == 1) ? MathMin(S, P - buf) : MathMax(S, P + buf);
}

double SizeAdd(const double &entries[], const double &lots[], double P, double anchor,
               int dd, double E0, double ml)
{
   double base = g_base_lot;
   int    k    = g_add_count;                  // add index (0 for first add)
   double g    = Flr(base * InpMult * MathPow(InpProgStep, k));
   if(InpSizing == CK_PROGGEO)
      return g;
   // geofloor: max(geometric ramp, lot pinning equity-0 to the anchor); anchor 0 -> ml
   double S = (anchor != 0.0) ? ((dd == 1) ? MathMax(ml, anchor) : MathMin(ml, anchor)) : ml;
   S = FloorAnchor(S, P, dd);                  // buffer: line can't hug price
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
   if(g_MPL <= 0) return x;                         // no margin model -> only the split caps per order
   double Lb = SumLots(lots);
   double eq = E0;
   for(int i = 0; i < ArraySize(lots); i++) eq += dd * (P - entries[i]) * lots[i] * g_TR;
   double cap = QFloor(MathMax(0.0, eq / g_MPL - Lb));
   return MathMin(x, cap);                          // free-margin cap only; per-order VOL_MAX -> PlaceSplit
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
      // max-hold: close the book at market after InpMaxHoldBars entry-TF bars
      // (fxgym simulate_ops END exit: mark-to-market at bar j+max_hold's close)
      if(g_inop && InpMaxHoldBars > 0 && g_op_open_time > 0 &&
         iBarShift(_Symbol, InpEntryTF, g_op_open_time, false) > InpMaxHoldBars)
         CloseBook();
      EntryCadence();
   }

   // ----- management cadence: new InpMgmtTF bar -> adds + stop ratchet -----
   datetime cb = iTime(_Symbol, InpMgmtTF, 0);
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
   g_E0   = OpE0();                          // 1R = whole balance (live) or InpFixedE0
   g_bal_open = AccountInfoDouble(ACCOUNT_BALANCE);
   g_ok   = (InpHalf <= 0);
   g_ext  = g_e0;
   g_arm_b = false;
   g_anc_b = 0.0; g_prev_anc = 0.0;
   g_base_lot = SumLots(lots);   // book = just the base at op-open -> geometric unit lot
   g_add_count = 0;              // no adds yet -> next add is k = 0
   g_op_open_time = TimeCurrent();
   RefreshSpecs();
   DeletePendings(g_dir == 1 ? 2 : 1);      // cancel the sibling
   double stop, tp; ComputeStops(entries, lots, stop, tp);
   ApplyStopAll(stop, tp);
   PrintFormat("[GymTeam:%s] OP OPEN dir=%d e0=%.5f R=%.5f E0=%.2f", InpLegName, g_dir, g_e0, g_r0, g_E0);
   TelemetryOp("open");
}

//+------------------------------------------------------------------+
//| Op closed: realize R from balance delta, reset, go flat.         |
//+------------------------------------------------------------------+
void OnOpClosed()
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double realizedR = (g_E0 > 0) ? (bal - g_bal_open) / g_E0 : 0.0;   // op PnL / 1R
   int _sz = ArraySize(g_opR); ArrayResize(g_opR, _sz + 1); g_opR[_sz] = realizedR;  // for OnTester
   int _wk = (int)((TimeCurrent() - CK_EPOCH) / CK_WEEKSEC);                          // prom-date bucket
   if(_wk >= 0 && _wk < CK_NWEEK) g_week[_wk] += MathMax(realizedR, -1.0);            // NBP-clamped
   if(g_ops_fh != INVALID_HANDLE)                                                     // shadow-gate op log
   {
      // deal-accurate op record for the cent-level oracle reconciliation:
      // sum this op's deals (by magic, since op open) -> profit/swap/commission,
      // entry price (first IN deal), exit price (last OUT deal), total IN lots.
      double d_profit = 0, d_swap = 0, d_comm = 0, d_lots = 0, d_in = 0, d_out = 0;
      if(HistorySelect(g_op_open_time - 120, TimeCurrent() + 120))
      {
         for(int i = 0; i < HistoryDealsTotal(); i++)
         {
            ulong tk = HistoryDealGetTicket(i);
            if(tk == 0) continue;
            if(HistoryDealGetInteger(tk, DEAL_MAGIC) != (long)InpMagicNumber) continue;
            if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
            d_profit += HistoryDealGetDouble(tk, DEAL_PROFIT);
            d_swap   += HistoryDealGetDouble(tk, DEAL_SWAP);
            d_comm   += HistoryDealGetDouble(tk, DEAL_COMMISSION);
            long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
            if(entry == DEAL_ENTRY_IN)
            {
               if(d_in == 0) d_in = HistoryDealGetDouble(tk, DEAL_PRICE);
               d_lots += HistoryDealGetDouble(tk, DEAL_VOLUME);
            }
            else if(entry == DEAL_ENTRY_OUT)
               d_out = HistoryDealGetDouble(tk, DEAL_PRICE);
         }
      }
      FileWrite(g_ops_fh, StringFormat("%s,%s,%d,%d,%.4f,%.5f,%.5f,%.2f,%.2f,%.2f,%.2f,%.2f,%.5f",
                TimeToString(g_op_open_time, TIME_DATE | TIME_SECONDS),
                TimeToString(TimeCurrent(),  TIME_DATE | TIME_SECONDS),
                g_dir, g_add_count + 1, realizedR,
                d_in, d_out, d_lots, d_profit, d_swap, d_comm, g_E0, g_r0));
   }
   PrintFormat("[GymTeam:%s] OP CLOSE  R=%.3f  bal=%.2f", InpLegName, realizedR, bal);
   TelemetryOpClose(realizedR);
   g_inop = false; g_dir = 0; g_e0 = g_r0 = g_E0 = g_ext = 0; g_ok = false; g_arm_b = false;
   g_anc_b = 0.0; g_prev_anc = 0.0;
   g_base_lot = 0.0; g_add_count = 0;
   DeletePendings(0);
}

//+------------------------------------------------------------------+
//| Close every position of this EA at market (max-hold END exit).   |
//| Op-close accounting flows through OnTick's cnt==0 transition.    |
//+------------------------------------------------------------------+
void CloseBook()
{
   PrintFormat("[GymTeam:%s] MAX-HOLD close after %d %s bars", InpLegName,
               InpMaxHoldBars, EnumToString(InpEntryTF));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      g_trade.PositionClose(tk);
   }
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
   if(g_halt)                                  // orchestrator "no new ops" (breaker/kill): never flatten, just don't arm
   {
      if(CountPendings() > 0) DeletePendings(0);
      return;
   }
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
   double E0 = OpE0();
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

//+------------------------------------------------------------------+
//| Structural anchor: low/high InpNBack candles back (LINE_NBACK).   |
//| 0 unless LINE_NBACK is selected with InpNBack > 0.                |
//+------------------------------------------------------------------+
double StructAnchor()
{
   if(InpLinePlace != LINE_NBACK || InpNBack <= 0) return 0.0;
   return (g_dir == 1) ? iLow(_Symbol, InpMgmtTF, 1 + InpNBack)
                       : iHigh(_Symbol, InpMgmtTF, 1 + InpNBack);
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

   double bh = iHigh(_Symbol, InpMgmtTF, 1), bl = iLow(_Symbol, InpMgmtTF, 1),
          bc = iClose(_Symbol, InpMgmtTF, 1);

   // 1) running extreme (for the chandelier trail) -- updated AFTER the bar's exit
   if(g_dir == 1) g_ext = MathMax(g_ext, bh);
   else           g_ext = MathMin(g_ext, bl);

   // 2) favourable gate: fav = dd*((H or L) - e0)/R  >= half  -> latch ok
   double adv = (g_dir == 1) ? bh : bl;
   double fav = g_dir * (adv - g_e0) / g_r0;
   if(fav >= InpHalf) g_ok = true;

   // 3) ADD trigger (stack presets only): SMA-bounce or poscandle; anchor per InpLinePlace
   if(InpStack && g_ok)
   {
      double last  = LadderExtreme(e_arr);                   // most-recent add entry
      bool   gated = (g_dir == 1) ? (bc > last) : (bc < last);
      double nb    = StructAnchor();                         // 0 unless LINE_NBACK & InpNBack>0
      double slowA = (InpSlowP > 0) ? SmaClose(InpSlowP, 1) : 0.0;

      if(InpAddTrigger == ADD_POSCANDLE)
      {
         double bo = iOpen(_Symbol, InpMgmtTF, 1);           // add on every confluent in-trend candle
         bool   confluent = (g_dir == 1) ? (bc > bo) : (bc < bo);
         if(confluent && gated)
            DoAdd(e_arr, l_arr, bc, (nb != 0.0) ? nb : slowA, false);
      }
      else  // ADD_SMA_BOUNCE: wrong-side-of-SMA, then back
      {
         double sma   = SmaClose(InpSmaP, 1);
         bool   wrong = (g_dir == 1) ? (bc < sma) : (bc > sma);
         bool   back  = (g_dir == 1) ? (bc >= sma) : (bc <= sma);
         if(wrong)
         {
            g_arm_b = true;
            double ext = (g_dir == 1) ? bl : bh;             // accumulate the bounce extreme
            g_anc_b = (g_anc_b == 0.0) ? ext
                      : ((g_dir == 1) ? MathMin(g_anc_b, ext) : MathMax(g_anc_b, ext));
         }
         else if(back && g_arm_b)
         {
            g_arm_b = false;
            double cur_anc = g_anc_b;
            if(gated && InpLinePlace == LINE_PINPREV)
            {
               bool beyond = (g_prev_anc != 0.0) &&
                             ((g_dir == 1) ? (g_prev_anc < cur_anc) : (g_prev_anc > cur_anc));
               double S = beyond ? g_prev_anc : cur_anc;     // prev_fb = "current"
               if(S != 0.0) DoAdd(e_arr, l_arr, bc, S, true);
            }
            else if(gated)
            {
               double anc = (nb != 0.0) ? nb : (slowA != 0.0 ? slowA : cur_anc);
               DoAdd(e_arr, l_arr, bc, anc, false);
            }
            if(cur_anc != 0.0) g_prev_anc = cur_anc;
            g_anc_b = 0.0;
         }
      }
   }

   // 4) re-sync the shared stop/TP to the (possibly enlarged) book
   double e2[], l2[]; ScanBook(e2, l2);
   double stop, tp; ComputeStops(e2, l2, stop, tp);
   ApplyStopAll(stop, tp);
}

//+------------------------------------------------------------------+
//| Place `total` lots as market order(s), each <= VOL_MAX (and the   |
//| broker's SYMBOL_VOLUME_MAX): an add wanting more than the per-     |
//| order cap is split across positions, e.g. 250 -> 200 + 50. The    |
//| broker rejects any single order above its max, so the full desired |
//| volume is placed in <= VOL_MAX chunks (each its own position, all  |
//| <= the per-position cap). Returns the number of orders placed.    |
//+------------------------------------------------------------------+
int PlaceSplit(bool is_buy, double total, string comment)
{
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP); if(step <= 0) step = VOL_STEP;
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double bmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double cap  = (bmax > 0) ? MathMin(VOL_MAX, bmax) : VOL_MAX;     // per-order ceiling
   int placed = 0, guard = 0;
   while(total >= minl && guard++ < 1000)
   {
      double chunk = MathFloor(MathMin(total, cap) / step + 1e-9) * step;   // floor; never force min up
      if(chunk < minl) break;
      bool ok = is_buy ? g_trade.Buy(chunk, _Symbol, 0.0, 0.0, 0.0, comment)
                       : g_trade.Sell(chunk, _Symbol, 0.0, 0.0, 0.0, comment);
      if(!ok) break;                                                // stop on a broker rejection
      placed++; total -= chunk;
   }
   return placed;
}

//+------------------------------------------------------------------+
//| Place one stacking add (market at ~close), splitting over VOL_MAX.|
//+------------------------------------------------------------------+
void DoAdd(const double &entries[], const double &lots[], double P, double anchor, bool pinExact)
{
   double ml = MarginLine(entries, lots, g_dir, g_E0);
   // pinExact (LINE_PINPREV): size the add so book liquidation lands exactly on `anchor`
   // (the structural level), buffer-floored away from price; else proggeo/geofloor via SizeAdd.
   double x = pinExact ? LotToPin(entries, lots, P, FloorAnchor(anchor, P, g_dir), g_dir, g_E0)
                       : SizeAdd(entries, lots, P, anchor, g_dir, g_E0, ml);
   x = MarginCap(x, entries, lots, P, g_dir, g_E0);     // free-margin cap (no per-order clamp)
   if(x < VOL_STEP) return;
   // split a >VOL_MAX add into multiple positions (250 -> 200 + 50)
   int n = PlaceSplit(g_dir == 1, x, "CK_" + InpLegName + "_add");
   if(n > 0)
   {
      g_add_count++;        // one logical add placed -> advance the geometric index k
      PrintFormat("[GymTeam:%s] ADD #%d lot=%.2f in %d order(s) @~%.5f  depth->%d",
                  InpLegName, g_add_count, x, n, P, ArraySize(lots) + n);
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
//| SMA of CLOSE over `period` on the management TF, ending at shift.|
//+------------------------------------------------------------------+
double SmaClose(int period, int shift)
{
   if(period <= 0) return 0.0;
   double c[];
   if(CopyClose(_Symbol, InpMgmtTF, shift, period, c) < period) return 0.0;
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
   g_E0  = OpE0();                                 // approximation post-restart
   g_bal_open = AccountInfoDouble(ACCOUNT_BALANCE);
   g_r0  = (sl0 > 0) ? MathAbs(g_e0 - sl0) : MathAbs(g_e0 - MarginLine(e_arr, l_arr, g_dir, g_E0));
   g_ok  = true;                                  // assume gate already passed
   g_arm_b = false; g_anc_b = 0.0; g_prev_anc = 0.0;
   g_ext = (g_dir == 1) ? iHigh(_Symbol, InpMgmtTF, 0) : iLow(_Symbol, InpMgmtTF, 0);
   // best-effort sizing state: base = the oldest (first-opened) position's volume;
   // k = number of adds already on the book (= positions - 1).
   g_base_lot = OldestPositionLot();
   if(g_base_lot <= 0) g_base_lot = l_arr[0];
   g_add_count = MathMax(0, cnt - 1);
   PrintFormat("[GymTeam:%s] ADOPTED open op dir=%d e0=%.5f R=%.5f base=%.2f k=%d (post-restart)",
               InpLegName, g_dir, g_e0, g_r0, g_base_lot, g_add_count);
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

//+------------------------------------------------------------------+
//| Volume of this EA's oldest (first-opened) position = the base    |
//| lot. Used only by AdoptExistingOp (post-restart reconstruction). |
//+------------------------------------------------------------------+
double OldestPositionLot()
{
   double lot = 0.0; datetime best = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber) continue;
      datetime t = (datetime)PositionGetInteger(POSITION_TIME);
      if(best == 0 || t < best) { best = t; lot = PositionGetDouble(POSITION_VOLUME); }
   }
   return lot;
}

//+==================================================================+
//|   DETECTION — the signal modules. All evaluate the just-CLOSED    |
//|   entry-TF bar (shift 1), matching fxgym generator conventions.   |
//+==================================================================+
bool IsTriggerBar()
{
   switch(InpSignal)
   {
      case SIG_NR7:           return IsNR(1);
      case SIG_INSIDE:        return IsInside(1);
      case SIG_NR7_OR_INSIDE: return IsNR(1) || IsInside(1);   // "comp" (union of fires)
      case SIG_WARMHOURS:     return IsWarmHours(1);
      case SIG_KELTNER:       return IsKeltner();
      case SIG_ENGULF:        return IsEngulf();
      case SIG_DONCHIAN:      return IsDonchian();
      case SIG_MA_ALIGN:      return IsMaAlign();
      default:                return IsVPattern();
   }
}

//+------------------------------------------------------------------+
//| NR7: bar range == min of the last InpNRWindow ranges (incl self). |
//| Python: rng == rng.rolling(7).min() -> range <= all 6 priors.    |
//+------------------------------------------------------------------+
bool IsNR(int sh)
{
   double rng1 = iHigh(_Symbol, InpEntryTF, sh) - iLow(_Symbol, InpEntryTF, sh);
   if(rng1 <= 0) return false;
   for(int k = 1; k < InpNRWindow; k++)
   {
      double r = iHigh(_Symbol, InpEntryTF, sh + k) - iLow(_Symbol, InpEntryTF, sh + k);
      if(r < rng1) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Inside bar: high < prior high AND low > prior low (strict).       |
//+------------------------------------------------------------------+
bool IsInside(int sh)
{
   return iHigh(_Symbol, InpEntryTF, sh) < iHigh(_Symbol, InpEntryTF, sh + 1)
       && iLow(_Symbol, InpEntryTF, sh)  > iLow(_Symbol, InpEntryTF, sh + 1);
}

//+------------------------------------------------------------------+
//| warm+hours (fxgym run_revalidate.warm_fires, FROZEN):             |
//|   vol_pct in (InpWHLo, InpWHHi]  -- percentile of the closed bar's|
//|   tick volume vs the prior (win-1) bars (window incl current,     |
//|   rank vs the win-1 predecessors; matches signals.add_features)   |
//|   AND volume rose vs prior bar AND prior rose vs the one before   |
//|   AND bar hour in the frozen allowed set (server time).           |
//+------------------------------------------------------------------+
bool IsWarmHours(int sh)
{
   int need = sh + InpWHPctWin + 2;                 // window + the 2 rising-vol lookbacks
   long vol[];
   ArraySetAsSeries(vol, true);
   if(CopyTickVolume(_Symbol, InpEntryTF, 0, need, vol) < need) return false;
   if(!((double)vol[sh] > (double)vol[sh + 1] && (double)vol[sh + 1] > (double)vol[sh + 2]))
      return false;                                 // two rising volume bars
   double cur = (double)vol[sh];
   int prevn = InpWHPctWin - 1, cnt = 0;            // rank vs the 99 predecessors
   for(int k = 1; k <= prevn; k++) if((double)vol[sh + k] < cur) cnt++;
   double pct = 100.0 * cnt / prevn;
   if(!(pct > InpWHLo && pct <= InpWHHi)) return false;
   MqlDateTime dt;
   TimeToStruct(iTime(_Symbol, InpEntryTF, sh), dt);
   return g_wh_hours[dt.hour];
}

//+------------------------------------------------------------------+
//| Entry-TF price helpers (manual, CrossKing style; pandas-matched). |
//+------------------------------------------------------------------+
double SmaCloseEntry(int period, int shift)
{
   double c[];
   if(CopyClose(_Symbol, InpEntryTF, shift, period, c) < period) return 0.0;
   double s = 0; for(int i = 0; i < period; i++) s += c[i];
   return s / period;
}

// EMA(close) as pandas ewm(span, adjust=False): recursive from a long warmup
double EmaCloseEntry(int period, int shift, int warm = 300)
{
   int need = shift + warm;
   double c[]; ArraySetAsSeries(c, true);
   if(CopyClose(_Symbol, InpEntryTF, 0, need, c) < need) return 0.0;
   double k = 2.0 / (period + 1);
   double e = c[need - 1];
   for(int i = need - 2; i >= shift; i--) e = k * c[i] + (1.0 - k) * e;
   return e;
}

// ATR = SMA of true range over `period`, ending at `shift` (pandas tr.rolling(p).mean())
double AtrSmaEntry(int period, int shift)
{
   int need = shift + period + 1;
   double h[], l[], c[];
   ArraySetAsSeries(h, true); ArraySetAsSeries(l, true); ArraySetAsSeries(c, true);
   if(CopyHigh(_Symbol, InpEntryTF, 0, need, h) < need) return 0.0;
   if(CopyLow(_Symbol, InpEntryTF, 0, need, l) < need) return 0.0;
   if(CopyClose(_Symbol, InpEntryTF, 0, need, c) < need) return 0.0;
   double s = 0;
   for(int i = shift; i < shift + period; i++)
   {
      double tr = MathMax(h[i] - l[i], MathMax(MathAbs(h[i] - c[i + 1]), MathAbs(l[i] - c[i + 1])));
      s += tr;
   }
   return s / period;
}

//+------------------------------------------------------------------+
//| Keltner break: close crosses out of EMA(P) +/- mult*ATR (edge:    |
//| outside now, not outside on the previous bar). Either side fires. |
//+------------------------------------------------------------------+
bool IsKeltner()
{
   double atr1 = AtrSmaEntry(InpATRP, 1), atr2 = AtrSmaEntry(InpATRP, 2);
   if(atr1 <= 0 || atr2 <= 0) return false;
   double e1 = EmaCloseEntry(InpKelP, 1), e2 = EmaCloseEntry(InpKelP, 2);
   if(e1 <= 0 || e2 <= 0) return false;
   double c1 = iClose(_Symbol, InpEntryTF, 1), c2 = iClose(_Symbol, InpEntryTF, 2);
   bool up1 = c1 > e1 + InpKelMult * atr1, up2 = c2 > e2 + InpKelMult * atr2;
   bool dn1 = c1 < e1 - InpKelMult * atr1, dn2 = c2 < e2 - InpKelMult * atr2;
   return (up1 && !up2) || (dn1 && !dn2);
}

//+------------------------------------------------------------------+
//| Engulfing (both directions; matches signals2 formula exactly).    |
//+------------------------------------------------------------------+
bool IsEngulf()
{
   double c1 = iClose(_Symbol, InpEntryTF, 1), o1 = iOpen(_Symbol, InpEntryTF, 1);
   double c2 = iClose(_Symbol, InpEntryTF, 2), o2 = iOpen(_Symbol, InpEntryTF, 2);
   bool b = (c1 > o1) && (c2 < o2) && (c1 > o2) && (o1 < c2);
   bool s = (c1 < o1) && (c2 > o2) && (c1 < o2) && (o1 > c2);
   return b || s;
}

//+------------------------------------------------------------------+
//| Donchian break: close crosses the prior InpDonP-bar extreme (edge |
//| vs the previous bar's same condition). Either side fires.         |
//+------------------------------------------------------------------+
bool IsDonchian()
{
   int need = InpDonP + 3;
   double h[], l[], c[];
   ArraySetAsSeries(h, true); ArraySetAsSeries(l, true); ArraySetAsSeries(c, true);
   if(CopyHigh(_Symbol, InpEntryTF, 0, need, h) < need) return false;
   if(CopyLow(_Symbol, InpEntryTF, 0, need, l) < need) return false;
   if(CopyClose(_Symbol, InpEntryTF, 0, need, c) < need) return false;
   double hh1 = h[2], ll1 = l[2], hh2 = h[3], ll2 = l[3];
   for(int i = 2; i < 2 + InpDonP; i++)      { hh1 = MathMax(hh1, h[i]); ll1 = MathMin(ll1, l[i]); }
   for(int i = 3; i < 3 + InpDonP && i < need; i++) { hh2 = MathMax(hh2, h[i]); ll2 = MathMin(ll2, l[i]); }
   bool up1 = c[1] > hh1, up2 = c[2] > hh2;
   bool dn1 = c[1] < ll1, dn2 = c[2] < ll2;
   return (up1 && !up2) || (dn1 && !dn2);
}

//+------------------------------------------------------------------+
//| MA-alignment impulse: close vs slow SMA, both SMAs rising/falling,|
//| bar range > imp*ATR (edge vs previous bar's condition).           |
//+------------------------------------------------------------------+
int AlignCond(int sh)   // +1 up-aligned impulse, -1 down, 0 neither
{
   double sl1 = SmaCloseEntry(InpAlignSlow, sh), sl2 = SmaCloseEntry(InpAlignSlow, sh + 1);
   double f1 = SmaCloseEntry(InpAlignFast, sh), f2 = SmaCloseEntry(InpAlignFast, sh + 1);
   if(sl1 <= 0 || sl2 <= 0 || f1 <= 0 || f2 <= 0) return 0;
   double atr = AtrSmaEntry(InpATRP, sh);
   if(atr <= 0) return 0;
   double c = iClose(_Symbol, InpEntryTF, sh);
   double rng = iHigh(_Symbol, InpEntryTF, sh) - iLow(_Symbol, InpEntryTF, sh);
   if(rng <= InpAlignImp * atr) return 0;
   if((c > sl1) && (sl1 > sl2) && (f1 > f2)) return 1;
   if((c < sl1) && (sl1 < sl2) && (f1 < f2)) return -1;
   return 0;
}

bool IsMaAlign()   // per-side rising edge (matches signals2._dir_sig)
{
   int a1 = AlignCond(1), a2 = AlignCond(2);
   return (a1 == 1 && a2 != 1) || (a1 == -1 && a2 != -1);
}

//+------------------------------------------------------------------+
//| V-pattern threshold (legacy CrossKing/Book detection).            |
//+------------------------------------------------------------------+
bool IsVPattern()
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

// POST `body` to InpTelemetryURL + path (base URL = the orchestrator, no trailing slash).
void PushJson(string path, string body)
{
   if(!TelemetryEnabled()) return;
   char post[], result[]; string headers = "Content-Type: application/json\r\n", rhdr;
   StringToCharArray(body, post, 0, StringLen(body), CP_UTF8);
   int sz = ArraySize(post); if(sz > 0) ArrayResize(post, sz - 1);   // drop trailing NUL
   int code = WebRequest("POST", InpTelemetryURL + path, headers, 5000, post, result, rhdr);
   if(code == -1) PrintFormat("[GymTeam:%s] WebRequest %s failed err=%d (whitelist the URL)",
                              InpLegName, path, GetLastError());
}

// Current account + op state -> POST /telemetry (matches orchestrator Telemetry contract).
void SendState()
{
   if(!TelemetryEnabled()) return;
   double e_arr[], l_arr[]; int n = ScanBook(e_arr, l_arr);
   double ml = (n > 0) ? MarginLine(e_arr, l_arr, g_dir, g_E0) : 0.0;
   double openR = 0.0;
   if(g_inop && g_r0 > 0)
   {
      double px = (g_dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      openR = g_dir * (px - g_e0) / g_r0;
   }
   string body = StringFormat("{\"account\":\"%s\",\"symbol\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,"
                 "\"is_open\":%s,\"dir\":%d,\"stack\":%d,\"open_r\":%.3f,\"ml_sl\":%.5f,\"ver\":\"%s\"}",
                 InpLegName, _Symbol, AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
                 (g_inop ? "true" : "false"), g_dir, n, openR, ml, "1.0");
   PushJson("/telemetry", body);
}

// Poll the orchestrator "no new ops" flag. FAIL-OPEN: on any error g_halt is left unchanged
// (trade execution never depends on the orchestrator being reachable).
void PollControl()
{
   if(!TelemetryEnabled()) return;
   char data[], result[]; string rhdr;
   int code = WebRequest("GET", InpTelemetryURL + "/control/" + InpLegName, "", 5000, data, result, rhdr);
   if(code == 200)
      g_halt = (StringFind(CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8), "\"halt\":true") >= 0);
}

void Heartbeat(int cnt)
{
   if(!TelemetryEnabled()) return;
   datetime now = TimeCurrent();
   if(now - g_last_hb < InpHeartbeatSec) return;
   g_last_hb = now;
   SendState();
   PollControl();
}

void TelemetryOp(string ev)            // op open / add -> immediate state refresh
{
   SendState();
}

void TelemetryOpClose(double realizedR)   // closed op -> POST /op_close (the live R-stream)
{
   if(!TelemetryEnabled()) return;
   string body = StringFormat("{\"account\":\"%s\",\"symbol\":\"%s\",\"realized_r\":%.4f,"
                 "\"positions\":%d,\"reason\":\"%s\",\"open_time\":%d,\"close_time\":%d}",
                 InpLegName, _Symbol, realizedR, g_add_count + 1, "close",
                 (long)g_op_open_time, (long)TimeCurrent());
   PushJson("/op_close", body);
   SendState();                         // refresh balance / flat state post-close
}
//+------------------------------------------------------------------+
