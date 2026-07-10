"""Unit tests for the login-keyed roster registry (db.legs + Config.load_registry).
The roster is DATA now (dashboard-managed), not code: register / remove / reweight / disable a
leg and reload with NO restart. Run: python -m orchestrator.test_registry  (from repo root)."""
import os
DBP = "orchestrator/test_registry.db"
for p in (DBP, DBP + "-wal", DBP + "-shm"):
    if os.path.exists(p):
        os.remove(p)

from orchestrator.db import DB as Database
from orchestrator.config import Config, SEED_LEGS

P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


db = Database(DBP)

print("== seed ==")
db.seed_legs(SEED_LEGS)
n1 = len(db.legs_all())
db.seed_legs(SEED_LEGS)                                  # second call must be a no-op
chk("seed populates the registry", n1 == len(SEED_LEGS))
chk("seed is idempotent (no dupes)", len(db.legs_all()) == n1)

print("== load: login-keyed roster ==")
cfg = Config(); cfg.load_registry(db)
chk("legs are login-keyed", all(l.account.isdigit() for l in cfg.legs))
chk("cfg.main is the reserve login", cfg.main == "408962391")
chk("reserve is not an ops leg", cfg.main not in {l.account for l in cfg.legs})
chk("ops weights renormalize to 1", abs(sum(l.weight for l in cfg.legs) - 1.0) < 1e-9)
chk("terminal() metadata by login", cfg.terminal("161611609")["tn"] == "T1")
chk("strategy is a label on the account", cfg.terminal("161611609")["strategy"] == "XAU_H4_align")

print("== register a new account live (no restart) ==")
db.leg_upsert("999999999", tn="T8", server="Exness-MT5Real21", role="ops", weight=0.5,
              strategy="NEW_strat", symbol="XAUUSDc", cents=True, terminal_path="x")
cfg.load_registry(db)
chk("register -> new leg appears", "999999999" in {l.account for l in cfg.legs})
chk("register renormalizes weights", abs(sum(l.weight for l in cfg.legs) - 1.0) < 1e-9)

print("== reweight by number ==")
db.leg_set_weight("999999999", 0.9)
cfg.load_registry(db)
chk("reweight makes it the heaviest leg", cfg.weight("999999999") == max(l.weight for l in cfg.legs))

print("== swap strategy, identity unchanged ==")
db.leg_upsert("999999999", tn="T8", server="Exness-MT5Real21", role="ops", weight=0.9,
              strategy="DIFFERENT", symbol="BTCUSDc", cents=True, terminal_path="x")
cfg.load_registry(db)
chk("strategy swaps but login stays the leg identity",
    cfg.terminal("999999999")["strategy"] == "DIFFERENT" and "999999999" in {l.account for l in cfg.legs})

print("== disable / remove ==")
db.leg_set_enabled("999999999", False)
cfg.load_registry(db)
chk("disabled leg excluded from the roster", "999999999" not in {l.account for l in cfg.legs})
db.leg_remove("999999999")
cfg.load_registry(db)
chk("remove -> gone from the registry", "999999999" not in {r["login"] for r in db.legs_all()})

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
