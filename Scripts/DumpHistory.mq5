//+------------------------------------------------------------------+
//|                                              DumpHistory.mq5       |
//|                                          Dercio Micas - 2026       |
//|                                                                    |
//|  FIDELITY §3.3 enabler: dump FULL-WINDOW history to CSV from       |
//|  inside the terminal, bypassing the Python copy_rates_from_pos     |
//|  ~90000-bar cap (which only gave ~2-3 months of M1). The broker    |
//|  HAS full history (the Model-1 tester uses it); an in-terminal     |
//|  CopyRates/CopyTicksRange by DATE RANGE forces the download.       |
//|                                                                    |
//|  ==== DATA PARITY (the point) ====                                 |
//|  When we compare the M1-intrabar PYTHON engine to the MQL5 tester  |
//|  (EA on an H1 chart), both must consume the SAME input series. In  |
//|  the tester's **Model 1** EVERYTHING is built from M1: the H1 bars |
//|  (and their tick_volume, which drives the V-pattern ENTRY), the    |
//|  M15 management bars, and the simulated intrabar path. So:         |
//|   - DUMP M1 (mode=BARS, TF=M1). In Python DERIVE H1 & M15 from     |
//|     this M1 by aggregation (H1 tick_volume = SUM of M1 tick_vols)  |
//|     -- do NOT read a separately-pulled H1 CSV (its tick_volume can |
//|     differ from the M1-sum the tester uses -> different entries).  |
//|   - FALLBACK: mode=TICKS dumps real ticks (CopyTicksRange, day-    |
//|     chunked) for exact **Model 4** parity (bigger/slower).         |
//|                                                                    |
//|  Output -> MQL5/Files/<SYMBOL>_<TF>_dump.csv (bars) or             |
//|            <SYMBOL>_ticks_dump.csv (ticks). Copy into              |
//|            backtest/data/ for the Python engine.                   |
//|                                                                    |
//|  USAGE: drag onto any chart (symbol/TF are explicit inputs). Raise |
//|  Tools>Options>Charts>"Max bars in chart" to Unlimited first if a  |
//|  bar range comes back short. Run once per (symbol, mode) needed.   |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.10"
#property script_show_inputs

enum ENUM_DUMP_MODE { DUMP_BARS = 0, DUMP_TICKS = 1 };

input ENUM_DUMP_MODE    InpMode    = DUMP_BARS;            // BARS (M1 OHLC) or TICKS (real ticks)
input string            InpSymbol  = "XAUUSDc";            // Symbol to dump
input ENUM_TIMEFRAMES   InpTF      = PERIOD_M1;            // Timeframe (BARS mode) -- use M1 for parity
input datetime          InpFrom    = D'2024.02.01 00:00';  // Start date (>= broker history)
input datetime          InpTo      = D'2026.06.13 00:00';  // End date
input int               InpMaxWaitSec = 120;               // Max seconds to wait for async bar download

//+------------------------------------------------------------------+
void OnStart()
{
   string sym = InpSymbol;
   if(!SymbolSelect(sym, true)) { PrintFormat("DumpHistory: cannot select %s", sym); return; }
   if(InpMode == DUMP_BARS) DumpBars(sym);
   else                     DumpTicks(sym);
}

//+------------------------------------------------------------------+
//| BARS: CopyRates by date range (retry until the async download    |
//| settles), write OHLC + tick_volume + spread + real_volume.       |
//+------------------------------------------------------------------+
void DumpBars(string sym)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int got = 0, stable = 0;
   datetime deadline = TimeCurrent() + InpMaxWaitSec;
   while(TimeCurrent() < deadline)
   {
      int n = CopyRates(sym, InpTF, InpFrom, InpTo, rates);
      if(n > 0 && n == got) { if(++stable >= 3) break; } else stable = 0;
      if(n > got) got = n;
      Sleep(1000);
   }
   int n = CopyRates(sym, InpTF, InpFrom, InpTo, rates);
   if(n <= 0) { PrintFormat("DumpHistory[BARS]: CopyRates(%s,%s) -> %d err=%d (raise 'Max bars in chart' / let history download)",
                            sym, EnumToString(InpTF), n, GetLastError()); return; }

   string tf = EnumToString(InpTF); StringReplace(tf, "PERIOD_", "");
   string fname = sym + "_" + tf + "_dump.csv";
   int fh = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ",");
   if(fh == INVALID_HANDLE) { PrintFormat("DumpHistory: FileOpen %s err=%d", fname, GetLastError()); return; }
   FileWrite(fh, "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");
   for(int i = 0; i < n; i++)
   {
      string t = TimeToString(rates[i].time, TIME_DATE | TIME_SECONDS); StringReplace(t, ".", "-");
      FileWrite(fh, t,
                DoubleToString(rates[i].open,  _Digits), DoubleToString(rates[i].high, _Digits),
                DoubleToString(rates[i].low,   _Digits), DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume, (int)rates[i].spread, (long)rates[i].real_volume);
   }
   FileClose(fh);
   PrintFormat("DumpHistory[BARS]: wrote %d %s %s bars  %s -> %s  to MQL5/Files/%s",
               n, sym, EnumToString(InpTF), TimeToString(rates[0].time), TimeToString(rates[n-1].time), fname);
}

//+------------------------------------------------------------------+
//| TICKS: CopyTicksRange day-by-day (bounds memory + forces the      |
//| per-day download), append bid/ask/last/volume keyed by time_msc. |
//| Python: pd.to_datetime(time_msc, unit='ms').                     |
//+------------------------------------------------------------------+
void DumpTicks(string sym)
{
   string fname = sym + "_ticks_dump.csv";
   int fh = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ",");
   if(fh == INVALID_HANDLE) { PrintFormat("DumpHistory: FileOpen %s err=%d", fname, GetLastError()); return; }
   FileWrite(fh, "time_msc", "time", "bid", "ask", "last", "volume", "flags");

   long total = 0;
   const long DAY = 86400; // seconds
   for(datetime day = InpFrom; day < InpTo; day = (datetime)(day + DAY))
   {
      ulong from_msc = (ulong)day * 1000UL;
      ulong to_msc   = (ulong)(day + DAY) * 1000UL;
      MqlTick ticks[];
      int n = -1, tries = 0;
      // retry a few times: the first call for a day may kick off the download
      while(tries++ < InpMaxWaitSec)
      {
         n = CopyTicksRange(sym, ticks, COPY_TICKS_ALL, from_msc, to_msc);
         if(n >= 0) break;
         Sleep(500);
      }
      if(n <= 0) continue;
      for(int i = 0; i < n; i++)
      {
         string t = TimeToString(ticks[i].time, TIME_DATE | TIME_SECONDS); StringReplace(t, ".", "-");
         FileWrite(fh, (long)ticks[i].time_msc, t,
                   DoubleToString(ticks[i].bid, _Digits), DoubleToString(ticks[i].ask, _Digits),
                   DoubleToString(ticks[i].last, _Digits), (long)ticks[i].volume, (int)ticks[i].flags);
      }
      total += n;
      if(((day - InpFrom) / DAY) % 30 == 0)
         PrintFormat("DumpHistory[TICKS]: %s ... %s  (%I64d ticks so far)", sym, TimeToString(day), total);
   }
   FileClose(fh);
   PrintFormat("DumpHistory[TICKS]: wrote %I64d ticks for %s  %s -> %s  to MQL5/Files/%s",
               total, sym, TimeToString(InpFrom), TimeToString(InpTo), fname);
}
//+------------------------------------------------------------------+
