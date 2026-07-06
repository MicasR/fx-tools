"""End-to-end integration test: synthetic telemetry through the REAL FastAPI app + SQLite.
Verifies SYSTEM_PLAN Phase C exit ('end-to-end on synthetic telemetry: targets, transfers,
alerts, dashboard correct'). Run: python -m orchestrator.test_app  (from repo root)."""
import os
os.environ["CK_TEST"] = "1"
DBP = "orchestrator/state.db"
for p in (DBP, DBP + "-wal", DBP + "-shm"):
    if os.path.exists(p):
        os.remove(p)                               # fresh db

from fastapi.testclient import TestClient
from orchestrator import app as A

A.cfg.f_total = 0.10                               # clear numbers
client = TestClient(A.app)
P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


def tele(acct, bal, eq=None, is_open=False):
    return client.post("/telemetry", json=dict(account=acct, balance=bal,
                       equity=bal if eq is None else eq, is_open=is_open)).json()

# seed all accounts at $1000 total, on-target (Main holds reserve)
T0 = 1000.0
tg = {l.account: l.weight * 0.10 * T0 for l in A.cfg.legs}
for l in A.cfg.legs:
    tele(l.account, round(tg[l.account], 2))
tele("Main", round(T0 - sum(tg.values()), 2))

st = client.get("/status").json()
chk("status T ~= 1000", abs(st["T"] - 1000) < 1.0)
chk("not halted at start", st["halted"] is False)
chk("no pending transfers on-target", len(st["pending_transfers"]) == 0)
chk("biggest target = XAU_H4_align ~33.0", any(abs(a["target"] - 33.0) < 0.6
    and a["name"] == "XAU_H4_align" for a in st["accounts"]))

# a leg wins (flat, balance above target) -> orchestrator should emit a sweep to Main
r = tele("XAU_H4_engulf", round(tg["XAU_H4_engulf"] + 25, 2))
chk("telemetry returns halt flag + T", "halt" in r and "T" in r)
st = client.get("/status").json()
sweep = [t for t in st["pending_transfers"] if t["src"] == "XAU_H4_engulf" and t["reason"] == "sweep"]
chk("win -> pending sweep engulf -> main", len(sweep) == 1)

# op close records an immutable R-stream row
client.post("/op_close", json=dict(account="XAU_H4_engulf", realized_r=2.5, positions=4,
            reason="TP", close_time=1.0))
st = client.get("/status").json()
chk("op_close -> rstream has the row", any(o["account"] == "XAU_H4_engulf" and
    abs(o["realized_r"] - 2.5) < 1e-6 for o in st["rstream"]))

# control flag fail-open; manual halt/resume
chk("control flag halt=False initially", client.get("/control/btc-nb-2").json()["halt"] is False)
client.post("/halt")
chk("manual /halt -> control halt=True", client.get("/control/btc-nb-2").json()["halt"] is True)
client.post("/resume")
chk("manual /resume -> halt=False", client.get("/control/btc-nb-2").json()["halt"] is False)

# circuit breaker via telemetry: crater equity > 35% from peak
for l in A.cfg.legs:
    tele(l.account, 1.0, eq=1.0)
tele("Main", 1.0, eq=1.0)
chk("breaker trips on >35% equity crater", client.get("/status").json()["halted"] is True)

print("== dashboard ==")
d = client.get("/")
chk("GET / serves the control-center HTML", d.status_code == 200 and "CROSSKING" in d.text)

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
