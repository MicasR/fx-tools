//+------------------------------------------------------------------+
//| GT_Signals_Core.mqh — shared engine for the per-leg GymTeam       |
//| signal indicators (GT_<leg>_Signals.mq5 declares the inputs with  |
//| that leg's preset defaults, then #includes this file).            |
//|                                                                    |
//| WHAT IT SHOWS — "where would the king trade":                      |
//|   ◇  trigger bar        the signal module fired on this closed bar |
//|   ⋯  armed OCO levels   Buy Stop @ trigger high / Sell Stop @ low, |
//|                         alive for InpBreakBars bars (stale-cancel) |
//|   ▲▼ entry              where the breakout stop would fill         |
//|   ─  SL / TP lines      the op's -1R structural stop (opposite     |
//|                         trigger extreme; = margin-line by design,  |
//|                         the base lot pins equity-0 there) and the  |
//|                         +InpTpR*R fixed target, while the op runs  |
//|   ×  exit               TP / SL / END(max-hold) close              |
//|                                                                    |
//| FIDELITY: mirrors GymTeam_EA's EntryCadence state machine at BAR   |
//| resolution — one op at a time (triggers suppressed while armed or  |
//| in-op, exactly like the EA), 4-bar OCO window with the EA's        |
//| skip-one-eval stale-cancel, max-hold END exit at bar open.         |
//| Bar-level approximations (documented in the leg .md):              |
//|   * fills/exits use bar extremes (no intrabar tick sequence);      |
//|     if a bar touches both armed levels, the side nearer the open   |
//|     fills; if a bar touches both SL and TP, SL wins (conservative) |
//|   * spread, slippage, margin caps and the live stops-level skip    |
//|     are not modeled                                                |
//| Stats overlay: Comment() panel — triggers/fills/exit mix/sum R     |
//| over the loaded chart history (R: TP=+TpR, SL=-1, END=mark2mkt).   |
//+------------------------------------------------------------------+

//--- plot buffers (properties + input declarations live in the leg .mq5)
double TrigBuf[], ArmHBuf[], ArmLBuf[], EntryUpBuf[], EntryDnBuf[],
       SlBuf[], TpBuf[], ExitBuf[];

//--- state machine (persists between OnCalculate calls; reset on full recalc)
int      g_done   = 0;      // closed bars already processed
bool     g_armed  = false;  // OCO pair pending
int      g_trigbar = 0;     // bar index of the trigger bar
double   g_aH = 0, g_aL = 0, g_aR = 0;   // armed high/low/range
bool     g_inop   = false;  // op open
int      g_dir    = 0, g_fillbar = 0;
double   g_e0 = 0, g_r0 = 0, g_sl = 0, g_tp = 0;
//--- incremental EMA state (pandas ewm adjust=False over the full history)
double   g_ema = 0, g_ema_prev = 0;
int      g_ema_bar = -1;
//--- previous-bar signal conditions (edge detection)
bool     g_kup_prev = false, g_kdn_prev = false;   // keltner
bool     g_dup_prev = false, g_ddn_prev = false;   // donchian
int      g_align_prev = 0;                          // ma_align
//--- warm+hours allowed-hour lookup
bool     g_wh_hours[24];
//--- stats
int      g_ntrig = 0, g_nl = 0, g_ns = 0, g_ntp = 0, g_nsl = 0, g_nend = 0;
double   g_sumR = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, TrigBuf,    INDICATOR_DATA);
   SetIndexBuffer(1, ArmHBuf,    INDICATOR_DATA);
   SetIndexBuffer(2, ArmLBuf,    INDICATOR_DATA);
   SetIndexBuffer(3, EntryUpBuf, INDICATOR_DATA);
   SetIndexBuffer(4, EntryDnBuf, INDICATOR_DATA);
   SetIndexBuffer(5, SlBuf,      INDICATOR_DATA);
   SetIndexBuffer(6, TpBuf,      INDICATOR_DATA);
   SetIndexBuffer(7, ExitBuf,    INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_ARROW, 119);          // ◆ trigger
   PlotIndexSetInteger(0, PLOT_ARROW_SHIFT, -12);
   PlotIndexSetInteger(3, PLOT_ARROW, 233);          // ▲ long fill
   PlotIndexSetInteger(4, PLOT_ARROW, 234);          // ▼ short fill
   PlotIndexSetInteger(7, PLOT_ARROW, 251);          // × exit
   for(int p = 0; p < 8; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, EMPTY_VALUE);
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
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) { Comment(""); }

//+------------------------------------------------------------------+
//| forward-indexed helpers (index 0 = oldest; bar i uses data <= i)  |
//+------------------------------------------------------------------+
double Sma(const double &close[], int period, int i)
{
   if(period <= 0 || i - period + 1 < 0) return 0.0;
   double s = 0; for(int k = i - period + 1; k <= i; k++) s += close[k];
   return s / period;
}

// ATR = SMA of true range over `period`, ending at bar i (pandas tr.rolling(p).mean())
double AtrSma(const double &high[], const double &low[], const double &close[], int period, int i)
{
   if(i - period < 0) return 0.0;
   double s = 0;
   for(int k = i - period + 1; k <= i; k++)
   {
      double tr = MathMax(high[k] - low[k],
                  MathMax(MathAbs(high[k] - close[k - 1]), MathAbs(low[k] - close[k - 1])));
      s += tr;
   }
   return s / period;
}

//--- signal modules (each evaluates CLOSED bar i; ports of the EA detectors) -----------------
bool IsNR(const double &high[], const double &low[], int i)
{
   double rng1 = high[i] - low[i];
   if(rng1 <= 0 || i - InpNRWindow + 1 < 0) return false;
   for(int k = 1; k < InpNRWindow; k++)
      if(high[i - k] - low[i - k] < rng1) return false;
   return true;
}

bool IsInside(const double &high[], const double &low[], int i)
{
   return i > 0 && high[i] < high[i - 1] && low[i] > low[i - 1];
}

bool IsWarmHours(const long &tick_volume[], const datetime &time[], int i)
{
   if(i - InpWHPctWin - 1 < 0) return false;
   if(!((double)tick_volume[i] > (double)tick_volume[i - 1] &&
        (double)tick_volume[i - 1] > (double)tick_volume[i - 2])) return false;
   double cur = (double)tick_volume[i];
   int prevn = InpWHPctWin - 1, cnt = 0;
   for(int k = 1; k <= prevn; k++) if((double)tick_volume[i - k] < cur) cnt++;
   double pct = 100.0 * cnt / prevn;
   if(!(pct > InpWHLo && pct <= InpWHHi)) return false;
   MqlDateTime dt;
   TimeToStruct(time[i], dt);
   return g_wh_hours[dt.hour];
}

bool KelUp(const double &close[], double ema, double atr, int i) { return atr > 0 && ema > 0 && close[i] > ema + InpKelMult * atr; }
bool KelDn(const double &close[], double ema, double atr, int i) { return atr > 0 && ema > 0 && close[i] < ema - InpKelMult * atr; }

bool IsEngulf(const double &open[], const double &close[], int i)
{
   if(i < 1) return false;
   double c1 = close[i], o1 = open[i], c2 = close[i - 1], o2 = open[i - 1];
   bool b = (c1 > o1) && (c2 < o2) && (c1 > o2) && (o1 < c2);
   bool s = (c1 < o1) && (c2 > o2) && (c1 < o2) && (o1 > c2);
   return b || s;
}

// Donchian: close[i] crosses the extreme of the PRIOR InpDonP bars (excl. bar i)
void DonCond(const double &high[], const double &low[], const double &close[], int i,
             bool &up, bool &dn)
{
   up = dn = false;
   if(i - InpDonP < 0) return;
   double hh = high[i - 1], ll = low[i - 1];
   for(int k = 2; k <= InpDonP; k++) { hh = MathMax(hh, high[i - k]); ll = MathMin(ll, low[i - k]); }
   up = close[i] > hh;
   dn = close[i] < ll;
}

int AlignCond(const double &high[], const double &low[], const double &close[], int i)
{
   if(i - InpAlignSlow - 1 < 0 || i - InpATRP < 0) return 0;
   double sl1 = Sma(close, InpAlignSlow, i), sl2 = Sma(close, InpAlignSlow, i - 1);
   double f1  = Sma(close, InpAlignFast, i), f2  = Sma(close, InpAlignFast, i - 1);
   if(sl1 <= 0 || sl2 <= 0 || f1 <= 0 || f2 <= 0) return 0;
   double atr = AtrSma(high, low, close, InpATRP, i);
   if(atr <= 0) return 0;
   double rng = high[i] - low[i];
   if(rng <= InpAlignImp * atr) return 0;
   if(close[i] > sl1 && sl1 > sl2 && f1 > f2) return 1;
   if(close[i] < sl1 && sl1 < sl2 && f1 < f2) return -1;
   return 0;
}

// V-pattern volume threshold (legacy module; kept so the switch is complete)
double VThreshold(const long &tick_volume[], int i)
{
   if(i - InpMAPeriod + 1 < 0) return 0.0;
   double ma = 0;
   for(int k = 0; k < InpMAPeriod; k++) ma += (double)tick_volume[i - k];
   ma /= InpMAPeriod;
   double sq = 0;
   for(int k = 0; k < InpMAPeriod; k++) { double d = (double)tick_volume[i - k] - ma; sq += d * d; }
   double sd = (InpMAPeriod > 1) ? MathSqrt(sq / InpMAPeriod) : 0.0;   // population std
   return ma + InpMultiplier * sd;
}

bool IsVPattern(const long &tick_volume[], int i)
{
   if(i - InpMAPeriod - 2 < 0) return false;
   double s1 = VThreshold(tick_volume, i), s2 = VThreshold(tick_volume, i - 1),
          s3 = VThreshold(tick_volume, i - 2);
   if(!(s3 > s2 && s1 > s2)) return false;
   return (s1 - s2) / MathMax(MathAbs(s2), 1e-10) >= InpRisePct;
}

//+------------------------------------------------------------------+
//| trigger dispatch for closed bar i (keltner/donchian/align keep    |
//| their own previous-bar condition for the rising-edge test)        |
//+------------------------------------------------------------------+
bool IsTriggerBar(const double &open[], const double &high[], const double &low[],
                  const double &close[], const long &tick_volume[], const datetime &time[], int i)
{
   switch(InpSignal)
   {
      case SIG_NR7:           return IsNR(high, low, i);
      case SIG_INSIDE:        return IsInside(high, low, i);
      case SIG_NR7_OR_INSIDE: return IsNR(high, low, i) || IsInside(high, low, i);
      case SIG_WARMHOURS:     return IsWarmHours(tick_volume, time, i);
      case SIG_KELTNER:
      {
         double atr = AtrSma(high, low, close, InpATRP, i);
         bool up = KelUp(close, g_ema, atr, i), dn = KelDn(close, g_ema, atr, i);
         bool fire = (up && !g_kup_prev) || (dn && !g_kdn_prev);
         g_kup_prev = up; g_kdn_prev = dn;
         return fire;
      }
      case SIG_ENGULF:        return IsEngulf(open, close, i);
      case SIG_DONCHIAN:
      {
         bool up, dn; DonCond(high, low, close, i, up, dn);
         bool fire = (up && !g_dup_prev) || (dn && !g_ddn_prev);
         g_dup_prev = up; g_ddn_prev = dn;
         return fire;
      }
      case SIG_MA_ALIGN:
      {
         int a = AlignCond(high, low, close, i);
         bool fire = (a == 1 && g_align_prev != 1) || (a == -1 && g_align_prev != -1);
         g_align_prev = a;
         return fire;
      }
      default:                return IsVPattern(tick_volume, i);
   }
}

void ResetState()
{
   g_done = 0; g_armed = false; g_inop = false; g_dir = 0;
   g_aH = g_aL = g_aR = g_e0 = g_r0 = g_sl = g_tp = 0;
   g_ema = g_ema_prev = 0; g_ema_bar = -1;
   g_kup_prev = g_kdn_prev = g_dup_prev = g_ddn_prev = false; g_align_prev = 0;
   g_ntrig = g_nl = g_ns = g_ntp = g_nsl = g_nend = 0; g_sumR = 0;
}

void CloseOp(int i, double px, string how)
{
   ExitBuf[i] = px;
   double R = (g_r0 > 0) ? g_dir * (px - g_e0) / g_r0 : 0.0;
   if(how == "TP") { g_ntp++; R = InpTpR; }
   else if(how == "SL") { g_nsl++; R = -1.0; }
   else g_nend++;
   g_sumR += MathMax(R, -1.0);                     // NBP clamp, like OnTester
   g_inop = false; g_dir = 0;
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated,
                const datetime &time[], const double &open[], const double &high[],
                const double &low[], const double &close[], const long &tick_volume[],
                const long &volume[], const int &spread[])
{
   // pin every array to forward indexing (0 = oldest) — the series flag of the
   // OnCalculate inputs is not guaranteed, and the whole engine assumes forward.
   ArraySetAsSeries(time, false);   ArraySetAsSeries(open, false);
   ArraySetAsSeries(high, false);   ArraySetAsSeries(low, false);
   ArraySetAsSeries(close, false);  ArraySetAsSeries(tick_volume, false);
   ArraySetAsSeries(TrigBuf, false);   ArraySetAsSeries(ArmHBuf, false);
   ArraySetAsSeries(ArmLBuf, false);   ArraySetAsSeries(EntryUpBuf, false);
   ArraySetAsSeries(EntryDnBuf, false); ArraySetAsSeries(SlBuf, false);
   ArraySetAsSeries(TpBuf, false);     ArraySetAsSeries(ExitBuf, false);
   if(prev_calculated == 0)
   {
      ResetState();
      ArrayInitialize(TrigBuf, EMPTY_VALUE);  ArrayInitialize(ArmHBuf, EMPTY_VALUE);
      ArrayInitialize(ArmLBuf, EMPTY_VALUE);  ArrayInitialize(EntryUpBuf, EMPTY_VALUE);
      ArrayInitialize(EntryDnBuf, EMPTY_VALUE); ArrayInitialize(SlBuf, EMPTY_VALUE);
      ArrayInitialize(TpBuf, EMPTY_VALUE);    ArrayInitialize(ExitBuf, EMPTY_VALUE);
   }
   // warmup: enough history for the deepest lookback of the active module
   int warm = MathMax(MathMax(InpWHPctWin + 2, InpDonP + 2),
              MathMax(InpAlignSlow + 2, MathMax(InpATRP + 2, 3 * InpMAPeriod + 6))) + 2;

   for(int i = (g_done > warm ? g_done : warm); i <= rates_total - 2; i++, g_done = i)
   {
      // new-bar buffers default empty (full recalcs pre-initialized; incremental bars not)
      TrigBuf[i] = ArmHBuf[i] = ArmLBuf[i] = EntryUpBuf[i] = EntryDnBuf[i] = EMPTY_VALUE;
      SlBuf[i] = TpBuf[i] = ExitBuf[i] = EMPTY_VALUE;

      // incremental EMA over the full history (pandas ewm adjust=False)
      if(g_ema_bar < 0) { g_ema = close[i]; g_ema_prev = close[i]; g_ema_bar = i; }
      while(g_ema_bar < i)
      {
         g_ema_bar++;
         g_ema_prev = g_ema;
         g_ema = (2.0 / (InpKelP + 1)) * close[g_ema_bar] + (1.0 - 2.0 / (InpKelP + 1)) * g_ema;
      }

      // 1) max-hold END exit — the EA closes at market on the new-bar open
      if(g_inop && InpMaxHoldBars > 0 && i - g_fillbar > InpMaxHoldBars)
         CloseOp(i, open[i], "END");

      // 2) armed OCO: fill during bar i? (window = trigbar+1 .. trigbar+InpBreakBars)
      if(g_armed && i > g_trigbar)
      {
         bool hitH = high[i] >= g_aH, hitL = low[i] <= g_aL;
         int fill = 0;
         if(hitH && hitL)                          // both touched: side nearer the open fills
            fill = (open[i] >= g_aH) ? 1 : (open[i] <= g_aL) ? -1
                 : ((g_aH - open[i] <= open[i] - g_aL) ? 1 : -1);
         else if(hitH) fill = 1;
         else if(hitL) fill = -1;
         if(fill != 0)
         {
            g_armed = false; g_inop = true; g_dir = fill; g_fillbar = i;
            g_e0 = (fill == 1) ? g_aH : g_aL;
            g_r0 = g_aR;
            g_sl = (fill == 1) ? g_aL : g_aH;      // -1R structural stop = margin line (pinned)
            g_tp = (InpTpR > 0) ? g_e0 + fill * InpTpR * g_r0 : 0.0;
            if(fill == 1) { EntryUpBuf[i] = g_e0; g_nl++; } else { EntryDnBuf[i] = g_e0; g_ns++; }
         }
         else
         {
            ArmHBuf[i] = g_aH; ArmLBuf[i] = g_aL;  // still waiting: draw the armed levels
            if(i - g_trigbar >= InpBreakBars) g_armed = false;   // stale-cancel (skips this bar's eval, like the EA)
         }
      }

      // 3) open op: SL / TP inside bar i (SL first on ambiguous bars — conservative)
      if(g_inop)
      {
         bool slHit = (g_dir == 1) ? low[i] <= g_sl : high[i] >= g_sl;
         bool tpHit = (g_tp > 0) && ((g_dir == 1) ? high[i] >= g_tp : low[i] <= g_tp);
         if(slHit)      CloseOp(i, g_sl, "SL");
         else if(tpHit) CloseOp(i, g_tp, "TP");
         else { SlBuf[i] = g_sl; if(g_tp > 0) TpBuf[i] = g_tp; }
      }

      // 4) entry cadence at this bar's close: flat + not armed -> evaluate the trigger.
      // NB: keltner/donchian/align keep per-bar edge state, so their detector must run
      // EVERY bar; suppression applies to acting on it, matching the EA's EntryCadence.
      bool fired = IsTriggerBar(open, high, low, close, tick_volume, time, i);
      if(fired && !g_inop && !g_armed)
      {
         double rng = high[i] - low[i];
         if(rng > 0)
         {
            g_armed = true; g_trigbar = i;
            g_aH = high[i]; g_aL = low[i]; g_aR = rng;
            TrigBuf[i] = high[i];
            g_ntrig++;
         }
      }
   }

   // project live state onto the forming bar so open levels extend to "now"
   int f = rates_total - 1;
   if(f >= 0 && g_done >= warm)
   {
      TrigBuf[f] = EntryUpBuf[f] = EntryDnBuf[f] = ExitBuf[f] = EMPTY_VALUE;
      ArmHBuf[f] = g_armed ? g_aH : EMPTY_VALUE;
      ArmLBuf[f] = g_armed ? g_aL : EMPTY_VALUE;
      SlBuf[f]   = g_inop ? g_sl : EMPTY_VALUE;
      TpBuf[f]   = (g_inop && g_tp > 0) ? g_tp : EMPTY_VALUE;
   }

   if(InpShowStats)
   {
      int nfill = g_nl + g_ns, nexit = g_ntp + g_nsl + g_nend;
      string warnTF = (Period() != InpEntryTF)
         ? "\n!! chart TF != preset entry TF (" + EnumToString(InpEntryTF) + ") — signals differ from live !!" : "";
      Comment(StringFormat(
         "GT %s — signal sim (preset defaults)%s\n"
         "triggers: %d   fills: %d (L %d / S %d)\n"
         "exits: TP %d · SL %d · END %d%s\n"
         "sum R (NBP): %+.1f   avg R/op: %+.2f\n"
         "bar-level sim: SL-first on ambiguous bars; no spread/margin/stops-level",
         InpLegName, warnTF, g_ntrig, nfill, g_nl, g_ns, g_ntp, g_nsl, g_nend,
         g_inop ? " · 1 open" : "", g_sumR, nexit > 0 ? g_sumR / nexit : 0.0));
   }
   return rates_total;
}
//+------------------------------------------------------------------+
