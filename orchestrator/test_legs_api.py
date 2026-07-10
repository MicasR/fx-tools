"""Integration test for the roster-registry CRUD API — register / update / disable / remove an
account LIVE with no restart, and telemetry for a just-registered login is accepted immediately.
Run: python -m orchestrator.test_legs_api  (from repo root)."""
import os
os.environ["CK_TEST"] = "1"
DBP = os.environ.setdefault("CK_DB", "orchestrator/test_legs.db")
SECP = os.environ["CK_SECRETS"] = "orchestrator/test_legs_secrets.json"   # never touch the real secrets.json
for p in (DBP, DBP + "-wal", DBP + "-shm", SECP):
    if os.path.exists(p):
        os.remove(p)

from fastapi.testclient import TestClient
from orchestrator import app as A

client = TestClient(A.app)
P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


NEW = "555000111"

# an unknown account is rejected before it is registered
r = client.post("/telemetry", json=dict(account=NEW, balance=100, equity=100)).json()
chk("unknown account rejected pre-register", r.get("ok") is False)

# register it LIVE (no restart), with an account password
res = client.post("/legs", json=dict(login=NEW, tn="T9", server="Exness-MT5Real21", role="ops",
                  weight=0.2, strategy="TEST_strat", symbol="XAUUSDc", cents=True,
                  password="s3cr3t-pw")).json()
chk("register ok + in accounts", res["ok"] and NEW in res["accounts"])
chk("new leg live in cfg.legs", NEW in {l.account for l in A.cfg.legs})

# password stored in secrets.json (gitignored) + exposed only as has_password, never the value
legrow = {x["login"]: x for x in client.get("/legs").json()["legs"]}[NEW]
chk("has_password = True after supplying one", legrow.get("has_password") is True)
chk("password never returned by the API", "password" not in legrow)
import json as _json
chk("password actually written to the secret store", _json.load(open(SECP)).get(NEW) == "s3cr3t-pw")

# telemetry for it is now accepted (the roster knew nothing about it a moment ago)
r = client.post("/telemetry", json=dict(account=NEW, balance=200, equity=200)).json()
chk("telemetry accepted post-register", r.get("ok") is True)
st = client.get("/status").json()
chk("appears on the dashboard", any(a["name"] == NEW for a in st["accounts"]))

# swap the strategy on the account — login identity + presence unchanged
client.post("/legs", json=dict(login=NEW, tn="T9", server="Exness-MT5Real21", role="ops",
            weight=0.2, strategy="DIFFERENT", symbol="BTCUSDc", cents=True))
legs = {x["login"]: x for x in client.get("/legs").json()["legs"]}
chk("strategy swapped, login kept", legs[NEW]["strategy"] == "DIFFERENT")

# disable -> drops out of the ops roster (soft)
client.post(f"/legs/{NEW}/enabled?on=0")
chk("disabled leaves the ops roster", NEW not in {l.account for l in A.cfg.legs})

# remove -> gone from registry + in-memory state
client.delete(f"/legs/{NEW}")
chk("removed from registry", NEW not in {x["login"] for x in client.get("/legs").json()["legs"]})
chk("removed from ACCT", NEW not in A.ACCT)

print(f"\n{sum(P)}/{len(P)} passed")
for p in (DBP, DBP + "-wal", DBP + "-shm", SECP):
    try:
        os.remove(p)
    except OSError:
        pass
raise SystemExit(0 if all(P) else 1)
