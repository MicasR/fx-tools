"""Unit tests for the bot's alert brain: status_alerts() (pure, edge-triggered).
Born from the 2026-07-07..10 incident (collector dead 3 days, no page): all-stale must escalate
once, recover once, and never spam per-leg warnings during a full outage.
Run: python -m orchestrator.test_bot  (from repo root)."""
from orchestrator.bot import AlertState, status_alerts, ORCH_FAIL_ALERT

P = []


def chk(n, c):
    P.append(c); print(f"  [{'PASS' if c else 'FAIL'}] {n}")


def snap(stale=(), names=("A", "B", "C"), halted=False, transfers=()):
    return dict(halted=halted, drawdown=0.05,
                accounts=[dict(name=n, stale=(n in stale),
                               terminal=dict(tn=f"T{i+1}", login=n)) for i, n in enumerate(names)],
                pending_transfers=list(transfers))


print("== quiet steady state ==")
st = AlertState()
chk("all-healthy -> no alerts", status_alerts(st, snap()) == [])
chk("still healthy -> still quiet", status_alerts(st, snap()) == [])

print("== per-leg stale edge + recovery ==")
st = AlertState()
status_alerts(st, snap())
m = status_alerts(st, snap(stale=("B",)))
chk("one leg stale -> one warning", len(m) == 1 and "STALE" in m[0] and "B" in m[0])
chk("stays stale -> no repeat", status_alerts(st, snap(stale=("B",))) == [])
m = status_alerts(st, snap())
chk("leg recovers -> one back message", len(m) == 1 and "back" in m[0] and "B" in m[0])

print("== full outage escalates once (the 07-07 incident) ==")
st = AlertState()
status_alerts(st, snap())
m = status_alerts(st, snap(stale=("A", "B", "C")))
chk("all stale -> single escalation, no per-leg spam", len(m) == 1 and "ALL 3 LEGS STALE" in m[0])
chk("outage continues -> quiet", status_alerts(st, snap(stale=("A", "B", "C"))) == [])
m = status_alerts(st, snap(stale=("C",)))
chk("partial recovery -> single restored message", len(m) == 1 and "restored" in m[0] and "2/3" in m[0])
st2 = AlertState()                                     # bot restarted mid-outage
m = status_alerts(st2, snap(stale=("A", "B", "C")))
chk("restart mid-outage re-alerts", len(m) == 1 and "ALL 3 LEGS STALE" in m[0])

print("== breaker edges ==")
st = AlertState()
status_alerts(st, snap())
m = status_alerts(st, snap(halted=True))
chk("halt trips -> breaker alert", len(m) == 1 and "BREAKER" in m[0])
chk("halted stays -> quiet", status_alerts(st, snap(halted=True)) == [])
m = status_alerts(st, snap(halted=False))
chk("halt clears -> cleared message", len(m) == 1 and "cleared" in m[0])

print("== transfers dedup ==")
st = AlertState()
xfer = dict(id=7, src="A", dst="B", amount=1.25, reason="feed")
m = status_alerts(st, snap(transfers=(xfer,)))
chk("new transfer -> one alert", len(m) == 1 and "TRANSFER" in m[0])
chk("same transfer -> deduped", status_alerts(st, snap(transfers=(xfer,))) == [])

print("== orchestrator unreachable ==")
st = AlertState()
status_alerts(st, snap())
quiet = all(status_alerts(st, None) == [] for _ in range(ORCH_FAIL_ALERT - 1))
chk(f"quiet for first {ORCH_FAIL_ALERT - 1} failures", quiet)
m = status_alerts(st, None)
chk("threshold -> unreachable alert", len(m) == 1 and "UNREACHABLE" in m[0])
chk("keeps failing -> no repeat", status_alerts(st, None) == [])
m = status_alerts(st, snap())
chk("back -> reachable message", len(m) == 1 and "reachable" in m[0])

print(f"\n{sum(P)}/{len(P)} passed")
raise SystemExit(0 if all(P) else 1)
