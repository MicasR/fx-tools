"""
symbol_specs.py — print the broker's live volume/margin limits for our symbols.

Checks the user's question: VOL_MAX=200 is the per-ORDER cap; can we exceed it
by splitting across multiple positions?  That is allowed iff SYMBOL_VOLUME_LIMIT
(the max TOTAL volume across all positions+orders in one direction) is 0 or big
enough.  Prints volume_min/max/step/limit + margin/contract so we know for sure.

Run with MetaTrader 5 open and logged in:  python symbol_specs.py
"""
import MetaTrader5 as mt5
from fetch_data import find_symbol

QUERIES = ["XAUUSD", "BTCUSD"]

FILLING = {0: "FOK", 1: "IOC", 2: "RETURN", 3: "BOC"}


def main():
    if not mt5.initialize():
        raise SystemExit(f"mt5.initialize() failed: {mt5.last_error()}\n"
                         "Open MetaTrader 5 and log in, then re-run.")
    try:
        for q in QUERIES:
            try:
                name = find_symbol(q)
            except SystemExit as e:
                print(f"{q}: {e}"); continue
            mt5.symbol_select(name, True)
            s = mt5.symbol_info(name)
            if s is None:
                print(f"{name}: no symbol_info ({mt5.last_error()})"); continue
            print(f"\n=== {name} ===")
            print(f"  volume_min   : {s.volume_min}")
            print(f"  volume_max   : {s.volume_max}     (max per SINGLE order/position)")
            print(f"  volume_step  : {s.volume_step}")
            print(f"  volume_limit : {s.volume_limit}     "
                  f"({'0 = NO total cap -> splitting works' if s.volume_limit == 0 else 'TOTAL cap across all positions/orders one side'})")
            print(f"  contract_size: {s.trade_contract_size}")
            print(f"  margin_initial: {s.margin_initial}  (0 => computed from leverage)")
            print(f"  digits/point : {s.digits} / {s.point}")
            print(f"  filling_mode : {s.filling_mode}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
