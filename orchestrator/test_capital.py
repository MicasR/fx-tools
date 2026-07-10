"""Offline unit tests for the capital/rebalance/breaker brain (no I/O, no MT5).
Run: python -m orchestrator.test_capital   (from repo root)
Covers SYSTEM_PLAN.md Phase B/C exit: targets, sweeps, top-ups, open-op lock, breaker.
Accounts are keyed by MT5 login now; legs are picked from the seed roster by rank, not by name."""
from orchestrator.config import Config
from orchestrator.capital import Account, targets, plan_transfers, total_equity, Breaker

cfg = Config(f_total=0.10, breaker_dd=0.35, min_transfer=0.50)   # f_total=10% for clear numbers
MAIN = cfg.main                                   # reserve account login (was the "Main" sentinel)
big = cfg.legs[0]                                  # biggest ops leg (align, w=0.33)
sweeper = cfg.legs[1]                              # second leg (engulf, w=0.31) — used for the win
loser = cfg.legs[3]                               # a mid leg (keltner-H4, w=0.10, target 10) — the loss
P = []


def chk(name, cond):
    P.append(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")


def at_target(T):
    """All accounts flat and exactly at target for total equity T."""
    accts = {a: Account(a) for a in cfg.accounts}
    tg = targets(accts, cfg, T)               # targets need account dict; T explicit
    for a in cfg.accounts:
        accts[a].balance = accts[a].equity = round(tg[a], 2)
    return accts


print("== targets ==")
a = at_target(1000.0)
ops_sum = sum(a[l.account].balance for l in cfg.legs)
chk("ops targets sum = F_total*T (0.10*1000=100)", abs(ops_sum - 100.0) < 0.5)
chk("Main reserve = T*(1-F_total) (~900)", abs(a[MAIN].balance - 900.0) < 0.5)
chk(f"biggest leg {big.strategy} = 33%*100 = 33.0", abs(a[big.account].balance - 33.0) < 0.5)
chk("at target -> no transfers", len(plan_transfers(a, cfg)) == 0)

print("== win -> sweep to Main ==")
a = at_target(1000.0)
a[sweeper.account].balance += 20.0; a[sweeper.account].equity += 20.0   # won, flat
tr = plan_transfers(a, cfg)
sweep = [t for t in tr if t.src == sweeper.account and t.dst == MAIN and t.reason == "sweep"]
chk("won flat leg -> a sweep to Main", len(sweep) == 1 and sweep[0].amount > 0)

print("== loss -> Main tops up ==")
a = at_target(1000.0)
a[loser.account].balance -= 5.0; a[loser.account].equity -= 5.0          # lost, flat
tr = plan_transfers(a, cfg)
topup = [t for t in tr if t.dst == loser.account and t.src == MAIN and t.reason == "topup"]
chk("lost flat leg -> a top-up from Main", len(topup) == 1 and topup[0].amount > 0)

print("== open-op LOCK ==")
a = at_target(1000.0)
a[loser.account].balance -= 5.0; a[loser.account].equity -= 5.0
a[loser.account].is_open = True                                      # locked
tr = plan_transfers(a, cfg)
chk("open leg is never touched", all(t.src != loser.account and t.dst != loser.account for t in tr))

print("== transfer lag safety (Main can't overdraw) ==")
a = at_target(1000.0)
a[MAIN].balance = 1.0; a[MAIN].equity = 1.0                       # Main nearly empty
for l in cfg.legs:
    a[l.account].balance -= 3.0; a[l.account].equity -= 3.0       # all short
tr = plan_transfers(a, cfg)
moved = sum(t.amount for t in tr if t.src == MAIN)
chk("top-ups never exceed Main balance", moved <= 1.0 + 1e-6)

print("== circuit breaker ==")
b = Breaker()
b.update(1000.0, cfg)
halted, dd = b.update(640.0, cfg)                                 # 36% DD > 35%
chk("breaker trips past 35% DD", halted and abs(dd - 0.36) < 0.01)
b.clear()
chk("breaker resets on clear()", not b.halted)

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
