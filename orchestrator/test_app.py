"""End-to-end integration test: synthetic telemetry through the REAL FastAPI app + SQLite.
Verifies SYSTEM_PLAN Phase C exit ('end-to-end on synthetic telemetry: targets, transfers,
alerts, dashboard correct'). Run: python -m orchestrator.test_app  (from repo root)."""
import os
os.environ["CK_TEST"] = "1"
# Use a throwaway DB (never the live state.db) — app.py honors CK_DB. Safe to run on the live box.
DBP = os.environ.setdefault("CK_DB", "orchestrator/test_state.db")
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
    # the real EA reports each account's NATIVE units; cent (USC) legs send x100, which the
    # orchestrator normalizes back to USD. Send native here so USD assertions below hold.
    sc = 100 if acct in A.cfg.cent_accounts else 1
    eqv = bal if eq is None else eq
    return client.post("/telemetry", json=dict(account=acct, balance=bal * sc,
                       equity=eqv * sc, is_open=is_open)).json()

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
chk("biggest target = btc-trail-1 ~33.8", any(abs(a["target"] - 33.8) < 0.6
    and a["name"] == "PD3_BtcTrail_1" for a in st["accounts"]))

# a leg wins (flat, balance above target) -> orchestrator should emit a sweep to Main
r = tele("PD3_GoldGeo_0", round(tg["PD3_GoldGeo_0"] + 25, 2))
chk("telemetry returns halt flag + T", "halt" in r and "T" in r)
st = client.get("/status").json()
sweep = [t for t in st["pending_transfers"] if t["src"] == "PD3_GoldGeo_0" and t["reason"] == "sweep"]
chk("win -> pending sweep gold-geo-0 -> main", len(sweep) == 1)

# simulate executing that sweep in Exness: gold-geo-0 back to target, Main now holds the +25.
# next telemetry must reconcile the pending instruction out (it is no longer needed).
tele("PD3_GoldGeo_0", round(tg["PD3_GoldGeo_0"], 2))
tele("Main", round(T0 - sum(tg.values()) + 25, 2))
st = client.get("/status").json()
chk("executed transfer -> reconciled out of pending",
    not any(t["src"] == "PD3_GoldGeo_0" and t["reason"] == "sweep" for t in st["pending_transfers"]))

# op close records an immutable R-stream row
client.post("/op_close", json=dict(account="PD3_GoldGeo_0", realized_r=2.5, positions=4,
            reason="TP", close_time=1.0))
st = client.get("/status").json()
chk("op_close -> rstream has the row", any(o["account"] == "PD3_GoldGeo_0" and
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

# performance metrics report (one op_close happened above: PD3_GoldGeo_0 R=2.5)
m = client.get("/metrics").json()
chk("/metrics has combined + per_leg", "combined" in m and "per_leg" in m)
chk("/metrics counts the closed op", m["combined"]["trades"] == 1 and abs(m["combined"]["net_r"] - 2.5) < 1e-6)

# live settings: dry_run must NOT mutate; apply must shift weights + persist
g = client.get("/settings").json()
chk("/settings exposes weights + dials", "weights" in g and "f_total" in g)
w0 = g["weights"]["PD3_BtcTrail_1"]
body = dict(f_total=g["f_total"], breaker_dd=g["breaker_dd"], min_transfer=g["min_transfer"],
            heartbeat_timeout_s=g["heartbeat_timeout_s"],
            weights={k: (0.5 if k == "PD3_BtcTrail_1" else 0.1) for k in g["weights"]})
dry = client.post("/settings?dry_run=1", json=body).json()
chk("dry_run returns preview + leaves live config unchanged",
    "preview" in dry and abs(client.get("/settings").json()["weights"]["PD3_BtcTrail_1"] - w0) < 1e-9)
client.post("/settings", json=body)
chk("apply raises BtcTrail_1 weight", client.get("/settings").json()["weights"]["PD3_BtcTrail_1"] > w0)
bad = dict(body); bad["f_total"] = 1.5
chk("invalid f_total -> 400", client.post("/settings", json=bad).status_code == 400)

print("== dashboard ==")
d = client.get("/")
chk("GET / serves the control-center HTML", d.status_code == 200 and "crossking" in d.text.lower())

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
