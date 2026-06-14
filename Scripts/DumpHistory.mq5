//+------------------------------------------------------------------+
//|                                              DumpHistory.mq5       |
//|                                          Dercio Micas - 2026       |
//|                                                                    |
//|  FIDELITY §3.3 enabler: dump FULL-WINDOW history (esp. M1) to CSV  |
//|  from inside the terminal, bypassing the Python                    |
//|  copy_rates_from_pos ~90000-bar cap (which only gave ~2-3 months   |
//|  of M1).  The broker HAS full M1 (the Model-1 tester uses it); an  |
//|  in-terminal CopyRates by DATE RANGE forces the download of any    |
//|  missing bars, so we can export the whole 2.2yr.                   |
//|                                                                    |
//|  WHY: we proved (decomposition, 2026-06-14) that Python's per-op   |
//|  physics already MATCH the MQL5 tester on matched ops; the only    |
//|  residual is the intrabar entry/exit timing that decides which     |
//|  breakouts the max_conc=1 slot catches. An M1-intrabar Python      |
//|  engine fed with full-window M1 should reproduce the tester ->     |
//|  restoring the FAST research engine. This script gets that M1.     |
//|                                                                    |
//|  Output: MQL5/Files/<SYMBOL>_<TF>_dump.csv  (same columns as the  |
//|  existing data CSVs: time,open,high,low,close,tick_volume,spread,  |
//|  real_volume).  Copy it into backtest/data/ (rename to match the   |
//|  <SYM>USDc_<TF>.csv convention) for the Python engine.            |
//|                                                                    |
//|  USAGE: drag onto any chart (the symbol/TF below are explicit      |
//|  inputs, not the chart's). Run once per (symbol,TF) you need:      |
//|  XAUUSDc M1, BTCUSDc M1 (and re-pull M15/H1 to extend if wanted).  |
//|  Raise Tools>Options>Charts>"Max bars in chart" to Unlimited first |
//|  if the range comes back short.                                    |
//+------------------------------------------------------------------+
#property copyright "Dercio Micas"
#property version   "1.00"
#property script_show_inputs

input string            InpSymbol  = "XAUUSDc";          // Symbol to dump
input ENUM_TIMEFRAMES   InpTF      = PERIOD_M1;          // Timeframe
input datetime          InpFrom    = D'2024.02.01 00:00';// Start date (>= broker history)
input datetime          InpTo      = D'2026.06.13 00:00';// End date
input int               InpMaxWaitSec = 120;             // Max seconds to wait for async download

//+------------------------------------------------------------------+
void OnStart()
{
   string sym = InpSymbol;
   if(!SymbolSelect(sym, true)) { PrintFormat("DumpHistory: cannot select %s", sym); return; }

   // Request the range repeatedly: the first calls trigger an async history
   // download and may return partial; loop until the count stops growing or
   // the timeout elapses.
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int got = 0, stable = 0;
   datetime deadline = TimeCurrent() + InpMaxWaitSec;
   while(TimeCurrent() < deadline)
   {
      int n = CopyRates(sym, InpTF, InpFrom, InpTo, rates);
      if(n > 0 && n == got) { if(++stable >= 3) break; }   // count steady across 3 polls -> done
      else                  { stable = 0; }
      if(n > got) got = n;
      Sleep(1000);
   }

   int n = CopyRates(sym, InpTF, InpFrom, InpTo, rates);
   if(n <= 0) { PrintFormat("DumpHistory: CopyRates(%s,%s) returned %d, err=%d  (raise 'Max bars in chart' / let history download)",
                            sym, EnumToString(InpTF), n, GetLastError()); return; }

   string tf = EnumToString(InpTF); StringReplace(tf, "PERIOD_", "");
   string fname = sym + "_" + tf + "_dump.csv";
   int fh = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ",");
   if(fh == INVALID_HANDLE) { PrintFormat("DumpHistory: FileOpen %s failed err=%d", fname, GetLastError()); return; }

   FileWrite(fh, "time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");
   for(int i = 0; i < n; i++)
   {
      // match the existing CSVs: "YYYY-MM-DD HH:MM:SS" and full price precision
      string t = TimeToString(rates[i].time, TIME_DATE | TIME_SECONDS);
      StringReplace(t, ".", "-");                          // 2024.04.01 -> 2024-04-01
      FileWrite(fh,
                t,
                DoubleToString(rates[i].open,  _Digits),
                DoubleToString(rates[i].high,  _Digits),
                DoubleToString(rates[i].low,   _Digits),
                DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume,
                (int)rates[i].spread,
                (long)rates[i].real_volume);
   }
   FileClose(fh);
   PrintFormat("DumpHistory: wrote %d bars of %s %s  %s -> %s  to MQL5/Files/%s",
               n, sym, EnumToString(InpTF),
               TimeToString(rates[0].time), TimeToString(rates[n-1].time), fname);
}
//+------------------------------------------------------------------+
