"""Unit tests for flatten order construction (mock mt5). Process control (open/close terminal) is a
Windows side effect validated live. Run: python -m orchestrator.test_terminalctl  (from repo root)."""
from orchestrator import terminalctl as T

P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


class Pos:
    def __init__(s, ticket, typ, vol, sym, magic=7):
        s.ticket = ticket; s.type = typ; s.volume = vol; s.symbol = sym; s.magic = magic


class Tick:
    def __init__(s, bid, ask): s.bid = bid; s.ask = ask


class Res:
    def __init__(s, rc): s.retcode = rc


class FakeMT5:
    POSITION_TYPE_BUY = 0; POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 0; ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1; ORDER_TIME_GTC = 0; ORDER_FILLING_IOC = 2
    TRADE_RETCODE_DONE = 10009

    def __init__(s, positions, fail=False):
        s._pos = positions; s._fail = fail; s.sent = []; s.shutdown_called = False
    def initialize(s, path=None): return True
    def positions_get(s): return s._pos
    def symbol_info_tick(s, sym): return Tick(100.0, 100.5)
    def order_send(s, req): s.sent.append(req); return Res(10 if s._fail else s.TRADE_RETCODE_DONE)
    def last_error(s): return (0, "ok")
    def shutdown(s): s.shutdown_called = True


print("== close request builds the opposite side ==")
m = FakeMT5([])
req = T._close_request(m, Pos(1, m.POSITION_TYPE_BUY, 0.05, "XAUUSDc"))
chk("BUY position -> SELL order at bid", req["type"] == m.ORDER_TYPE_SELL and req["price"] == 100.0
    and req["position"] == 1 and req["volume"] == 0.05)
req2 = T._close_request(m, Pos(2, m.POSITION_TYPE_SELL, 0.02, "BTCUSDc"))
chk("SELL position -> BUY order at ask", req2["type"] == m.ORDER_TYPE_BUY and req2["price"] == 100.5)

print("== flatten closes every position ==")
m = FakeMT5([Pos(1, 0, 0.01, "XAUUSDc"), Pos(2, 1, 0.02, "XAUUSDc")])
r = T.flatten_positions(m, "x")
chk("flatten closes both", r["ok"] and r["closed"] == 2 and r["failed"] == 0)
chk("sent one order per position", len(m.sent) == 2)
chk("session shut down after", m.shutdown_called)

print("== flatten reports order failures ==")
m = FakeMT5([Pos(1, 0, 0.01, "XAUUSDc")], fail=True)
r = T.flatten_positions(m, "x")
chk("order failure -> not ok", (not r["ok"]) and r["failed"] == 1 and r["closed"] == 0)

print("== flatten with no positions is a clean no-op ==")
r = T.flatten_positions(FakeMT5([]), "x")
chk("no positions -> ok, closed 0", r["ok"] and r["closed"] == 0)

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
