"""Pull-based telemetry collector — the decoupled replacement for EA push.

Reads each registered account via MT5 (read-only INVESTOR login), reconstructs op state and
realized-R from balance deltas (1R = account balance at op-open, exactly like the EA's OpE0), and
feeds the orchestrator's localhost ingest (`/telemetry`, `/op_close`). The EA no longer reports;
this owns telemetry. Run: python -m orchestrator.collector  (from repo root).

Design split for testability: `snapshot_to_events()` is a PURE function (no MT5, no I/O) — the
op-R reconstruction lives there and is unit-tested. The MT5 login loop + HTTP feed are the only
side-effecting parts. MetaTrader5 is imported lazily inside run() so this module imports without it.

Secrets: investor passwords live in gitignored orchestrator/secrets.json ({ "<login>": "<pw>" }),
never in the DB or git. Read-only investor creds mean the collector physically cannot trade.
"""
import json
import os
import time
import urllib.request

from .secretstore import load as load_secrets

ORCH = os.environ.get("ORCH_URL", "http://127.0.0.1:8800")
POLL_S = int(os.environ.get("COLLECTOR_POLL_S", "30"))


class LegState:
    """Per-account op tracker: latches 1R = balance at op-open, realizes R on the book going flat."""
    __slots__ = ("was_open", "e0", "stack")

    def __init__(self):
        self.was_open = False
        self.e0 = 0.0        # account balance at op-open (== 1R in native units)
        self.stack = 0       # peak concurrent positions seen this op


def snapshot_to_events(state, balance, equity, positions):
    """PURE. Given prior `state` and a fresh account snapshot, mutate `state` and return
    (telemetry_dict, op_close_or_None). `positions` is a list of dicts [{type, volume, symbol}]
    (type 0=BUY, 1=SELL). 1R = balance at op-open, so realized_r = (balance_close - E0) / E0 and
    open_r = floating / E0 — unit-independent (works for cent or USD accounts)."""
    n = len(positions)
    is_open = n > 0
    op_close = None
    if is_open and not state.was_open:           # 0 -> N : op just opened, latch E0
        state.e0 = balance
        state.stack = n
    elif is_open:                                 # still open, track peak add count
        state.stack = max(state.stack, n)
    elif state.was_open and not is_open:          # N -> 0 : op closed, realize R
        e0 = state.e0 or balance
        realized_r = (balance - e0) / e0 if e0 else 0.0
        op_close = dict(realized_r=round(realized_r, 4), positions=state.stack or 1, reason="close")
        state.e0 = 0.0
        state.stack = 0
    state.was_open = is_open

    e0 = state.e0 or balance
    direction = 0
    if positions:
        direction = 1 if positions[0].get("type", 0) == 0 else -1     # 0=BUY -> long, 1=SELL -> short
    open_r = ((equity - balance) / e0) if (is_open and e0) else 0.0    # floating / 1R
    telemetry = dict(balance=balance, equity=equity, is_open=is_open, dir=direction, stack=n,
                     open_r=round(open_r, 3), ml_sl=0.0, ver="collector-1.0")
    return telemetry, op_close


# ---- I/O glue (side-effecting) -----------------------------------------------------------------
def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(ORCH + path, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5).read()
        return True
    except Exception as e:
        print(f"[collector] ingest {path} failed: {e}")
        return False


def push_telemetry(login, symbol, telemetry):
    _post("/telemetry", dict(account=login, symbol=symbol, **telemetry))


def push_op_close(login, symbol, opclose):
    _post("/op_close", dict(account=login, symbol=symbol, close_time=time.time(), **opclose))


def poll_once(mt5, db, secrets, states):
    """One pull cycle over every enabled registered account. Returns count polled."""
    polled = 0
    for r in db.legs_all():
        if not int(r.get("enabled", 1)):
            continue
        login, server = str(r["login"]), r.get("server") or ""
        pw = secrets.get(login)
        if not pw:
            continue                                           # no investor creds -> skip
        if not mt5.login(int(login), password=pw, server=server):
            print(f"[collector] login {login} failed: {mt5.last_error()}")
            continue
        info = mt5.account_info()
        if info is None:
            continue
        raw = mt5.positions_get() or []
        positions = [dict(type=p.type, volume=p.volume, symbol=p.symbol) for p in raw]
        st = states.setdefault(login, LegState())
        tele, opclose = snapshot_to_events(st, info.balance, info.equity, positions)
        symbol = positions[0]["symbol"] if positions else (r.get("symbol") or "")
        push_telemetry(login, symbol, tele)
        if opclose:
            push_op_close(login, symbol, opclose)
        polled += 1
    return polled


def run():
    import MetaTrader5 as mt5
    from .db import DB
    db = DB(os.environ.get("CK_DB", "orchestrator/state.db"))
    secrets = load_secrets()
    reader = os.environ.get("MT5_READER_PATH")

    def _connect():
        mt5.shutdown()                                    # drop any stale IPC link first
        return mt5.initialize(path=reader) if reader else mt5.initialize()

    if not _connect():
        print(f"[collector] mt5.initialize failed: {mt5.last_error()}"); return
    print(f"[collector] up -> {ORCH}  poll={POLL_S}s  accounts_with_creds={len(secrets)}")
    states = {}
    try:
        while True:
            try:
                n = poll_once(mt5, db, secrets, states)
                if n == 0 and secrets:
                    # every login failed -> the MT5 IPC/terminal link is dead (e.g. reader restarted).
                    # Re-establish it so the collector self-heals instead of failing forever.
                    print(f"[collector] 0 polled ({mt5.last_error()}); re-initializing MT5")
                    _connect()
            except Exception as e:
                print(f"[collector] cycle error: {e}; re-initializing")
                _connect()
            time.sleep(POLL_S)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    run()
