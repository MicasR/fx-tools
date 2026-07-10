"""Unit tests for the pull collector: op-R reconstruction (pure) + one poll cycle (mocked MT5).
The collector must reproduce the EA's whole-account R (1R = balance at op-open) with NO EA telemetry.
Run: python -m orchestrator.test_collector  (from repo root)."""
import os
DBP = "orchestrator/test_collector.db"
for p in (DBP, DBP + "-wal", DBP + "-shm"):
    if os.path.exists(p):
        os.remove(p)

from orchestrator import collector as C
from orchestrator.db import DB as Database

P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


def pos(n, typ=0, sym="XAUUSDc"):
    return [dict(type=typ, volume=0.01, symbol=sym) for _ in range(n)]


print("== R reconstruction (1R = balance at op-open) ==")
st = C.LegState()
t, oc = C.snapshot_to_events(st, 100.0, 100.0, pos(2))          # 0 -> 2 : open
chk("open latches E0 + is_open", st.e0 == 100.0 and t["is_open"] and oc is None and t["stack"] == 2)
t, oc = C.snapshot_to_events(st, 100.0, 130.0, pos(2))          # still open, +30 floating
chk("open_r = floating/E0 = 0.30", abs(t["open_r"] - 0.30) < 1e-9 and oc is None)
t, oc = C.snapshot_to_events(st, 125.0, 125.0, pos(0))          # 2 -> 0 : closed at +25
chk("close realizes R = 0.25", oc and abs(oc["realized_r"] - 0.25) < 1e-9 and oc["positions"] == 2)
chk("flat after close", not t["is_open"] and st.e0 == 0.0)

print("== loss + scratch ==")
st = C.LegState()
C.snapshot_to_events(st, 100.0, 100.0, pos(1))
_, oc = C.snapshot_to_events(st, 90.0, 90.0, pos(0))
chk("loss realizes R = -0.10", oc and abs(oc["realized_r"] + 0.10) < 1e-9)
st = C.LegState()
_, oc = C.snapshot_to_events(st, 50.0, 50.0, pos(0))            # flat -> flat
chk("flat->flat -> no op_close", oc is None)

print("== cent-account invariance (R is unitless) ==")
st = C.LegState()
C.snapshot_to_events(st, 3300.0, 3300.0, pos(1))               # cent acct: $33 -> 3300 USc
_, oc = C.snapshot_to_events(st, 4125.0, 4125.0, pos(0))       # +25% expressed in cents
chk("R identical in cents vs USD (0.25)", oc and abs(oc["realized_r"] - 0.25) < 1e-9)

print("== one poll cycle (mocked MT5) ==")
db = Database(DBP)
db.leg_upsert("161611609", tn="T1", server="Exness-MT5Real21", role="ops", weight=1.0,
              strategy="XAU_H4_align", symbol="XAUUSDc", cents=True, enabled=True)
sent = []
C._post = lambda path, payload: (sent.append((path, payload)), True)[1]   # capture feeds


class FakePos:
    def __init__(s, typ, sym): s.type = typ; s.volume = 0.01; s.symbol = sym


class FakeInfo:
    def __init__(s, b, e): s.balance = b; s.equity = e


class FakeMT5:
    def __init__(s): s.bal = 3300.0; s.eq = 3300.0; s.pos = []
    def login(s, *a, **k): return True
    def account_info(s): return FakeInfo(s.bal, s.eq)
    def positions_get(s): return s.pos
    def last_error(s): return (0, "ok")


m = FakeMT5(); states = {}
m.pos = [FakePos(0, "XAUUSDc")]                                 # open
C.poll_once(m, db, {"161611609": "inv-pw"}, states)
chk("poll pushes /telemetry for the login",
    any(p == "/telemetry" and pl["account"] == "161611609" and pl["is_open"] for p, pl in sent))
sent.clear(); m.pos = []; m.bal = 3400.0; m.eq = 3400.0        # closed at profit
C.poll_once(m, db, {"161611609": "inv-pw"}, states)
chk("poll emits /op_close on close", any(p == "/op_close" and pl["account"] == "161611609" for p, pl in sent))
chk("skips accounts without secrets", C.poll_once(m, db, {}, {}) == 0)

print(f"\n{sum(P)}/{len(P)} passed")
for p in (DBP, DBP + "-wal", DBP + "-shm"):
    try:
        os.remove(p)
    except OSError:
        pass
raise SystemExit(0 if all(P) else 1)
