"""Live MT5 validation against the real broker (min lot, cent account).

Read-only by default. With --trade it opens ONE min-lot market order and closes it BY TICKET, so it
NEVER flattens the EA's own live positions. Proves the collector read path + the flatten/close-order
mechanics work against Exness before we wire them into the orchestrator.

Usage:  .venv/Scripts/python.exe ops/validate_mt5.py <login> [--trade]
"""
import sys
import os
import json
import time

import MetaTrader5 as mt5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)                       # so `orchestrator` imports when run from ops/
from orchestrator.config import SEED_LEGS

DONE = mt5.TRADE_RETCODE_DONE


def _send(req):
    """order_send with an IOC->FOK filling-mode fallback (Exness rejects the wrong mode)."""
    r = mt5.order_send({**req, "type_filling": mt5.ORDER_FILLING_IOC})
    if r is None or r.retcode != DONE:
        r = mt5.order_send({**req, "type_filling": mt5.ORDER_FILLING_FOK})
    return r


def main():
    if len(sys.argv) < 2:
        print("usage: validate_mt5.py <login> [--trade]"); return 2
    login = sys.argv[1]
    do_trade = "--trade" in sys.argv
    leg = next(l for l in SEED_LEGS if l["login"] == login)
    server, term, symbol = leg["server"], leg["terminal_path"], leg["symbol"]
    pw = json.load(open(os.path.join(ROOT, "orchestrator", "secrets.json")))[login]

    if not mt5.initialize(path=term):
        print("FAIL initialize:", mt5.last_error()); return 1
    print(f"[1] initialize OK  ({term})")
    if not mt5.login(int(login), password=pw, server=server):
        print("FAIL login:", mt5.last_error()); mt5.shutdown(); return 1
    ai = mt5.account_info()
    print(f"[2] login OK  #{login}  server={ai.server}  balance={ai.balance} {ai.currency}  equity={ai.equity}")

    before = mt5.positions_get() or []
    print(f"[3] positions before: {len(before)}  tickets={[p.ticket for p in before]}")

    if not do_trade:
        print("READ-ONLY validation OK  (pass --trade to test open/close).")
        mt5.shutdown(); return 0

    si = mt5.symbol_info(symbol)
    if si is None:
        print("FAIL symbol not found:", symbol); mt5.shutdown(); return 1
    if not si.visible:
        mt5.symbol_select(symbol, True); si = mt5.symbol_info(symbol)
    vol, tick = si.volume_min, mt5.symbol_info_tick(symbol)
    base = dict(action=mt5.TRADE_ACTION_DEAL, symbol=symbol, volume=vol, type=mt5.ORDER_TYPE_BUY,
                price=tick.ask, deviation=50, magic=999999, comment="validate-open",
                type_time=mt5.ORDER_TIME_GTC)
    r = _send(base)
    print(f"[4] OPEN {vol} {symbol} BUY -> retcode={getattr(r,'retcode',None)} '{getattr(r,'comment','')}'")
    if r is None or r.retcode != DONE:
        print("FAIL open"); mt5.shutdown(); return 1
    time.sleep(1.0)

    after = mt5.positions_get() or []
    new = [p for p in after if p.ticket not in {q.ticket for q in before}]
    print(f"[5] new position(s): {[p.ticket for p in new]}")
    closed = 0
    for p in new:
        t2 = mt5.symbol_info_tick(p.symbol)
        is_buy = (p.type == mt5.POSITION_TYPE_BUY)
        cr = _send(dict(action=mt5.TRADE_ACTION_DEAL, position=p.ticket, symbol=p.symbol,
                        volume=p.volume, type=(mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY),
                        price=(t2.bid if is_buy else t2.ask), deviation=50, magic=p.magic,
                        comment="validate-close", type_time=mt5.ORDER_TIME_GTC))
        ok = cr is not None and cr.retcode == DONE
        print(f"[6] CLOSE ticket {p.ticket} -> retcode={getattr(cr,'retcode',None)} '{getattr(cr,'comment','')}'")
        closed += 1 if ok else 0
    time.sleep(1.0)
    final = mt5.positions_get() or []
    leftover = [p for p in final if p.ticket not in {q.ticket for q in before}]
    ok = (closed == len(new) and not leftover)
    print(f"[7] positions after: {len(final)}  my-leftover={len(leftover)}")
    print("RESULT:", "PASS — opened + closed a min-lot trade cleanly" if ok else "FAIL — leftovers, inspect")
    mt5.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
