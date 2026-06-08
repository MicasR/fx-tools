"""
Pull XAU/USD history from the local MetaTrader 5 terminal and cache it to CSV.

Both indicators key off tick_volume, which MT5 provides directly, so we pull
straight from the terminal rather than a third-party feed.

Usage:
    python fetch_data.py --tf M15 --from 2026-01-01
"""
import argparse
import sys
from datetime import datetime, timedelta

import pandas as pd
import MetaTrader5 as mt5

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def find_gold_symbol(preferred: str | None) -> str:
    """Resolve the broker's gold symbol (XAUUSD / GOLD / XAUUSD.r ...)."""
    syms = mt5.symbols_get()
    names = [s.name for s in syms]
    if preferred and preferred in names:
        return preferred
    # exact-ish first, then any containing XAU+USD, then any with GOLD
    cands = [n for n in names if n.upper().replace(".", "").replace("_", "") == "XAUUSD"]
    if not cands:
        cands = [n for n in names if "XAU" in n.upper() and "USD" in n.upper()]
    if not cands:
        cands = [n for n in names if "GOLD" in n.upper()]
    if not cands:
        raise SystemExit("Could not find a gold symbol. Available sample: "
                         + ", ".join(names[:30]))
    cands.sort(key=len)  # prefer the cleanest name
    return cands[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M15", choices=list(TIMEFRAMES))
    ap.add_argument("--symbol", default=None, help="override gold symbol name")
    ap.add_argument("--from", dest="date_from", default="2026-01-01")
    args = ap.parse_args()

    if not mt5.initialize():
        raise SystemExit(f"mt5.initialize() failed: {mt5.last_error()}\n"
                         "Open MetaTrader 5 and log in, then re-run.")

    try:
        symbol = find_gold_symbol(args.symbol)
        mt5.symbol_select(symbol, True)
        tf = TIMEFRAMES[args.tf]
        date_from = datetime.fromisoformat(args.date_from)

        # copy_rates_range is flaky on this terminal ("Invalid params"); pull by
        # position instead, grabbing the largest block the terminal will return,
        # then trim to the requested start date.
        rates = None
        for cnt in (80000, 60000, 40000, 20000, 10000, 5000, 2000):
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, cnt)
            if rates is not None and len(rates) > 0:
                break
        if rates is None or len(rates) == 0:
            raise SystemExit(f"No data for {symbol} {args.tf}: {mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df[df["time"] >= date_from].reset_index(drop=True)
        out = f"data/{symbol}_{args.tf}.csv"
        df.to_csv(out, index=False)
        print(f"Saved {len(df):,} bars  {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
        print(f"Symbol: {symbol}   ->  {out}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
