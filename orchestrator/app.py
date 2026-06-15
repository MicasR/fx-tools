"""FastAPI orchestrator: ingest EA telemetry, run the capital/breaker brain, expose the
EA control-flag + dashboard JSON. Trade execution NEVER depends on this being up.
Run: uvicorn orchestrator.app:app --host 0.0.0.0 --port 8800
"""
import os
import time
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import DEFAULT, MAIN
from .capital import Account, targets, plan_transfers, total_equity, Breaker
from .db import DB

cfg = DEFAULT
db = DB()
breaker = Breaker()
ACCT = {a: Account(a) for a in cfg.accounts}          # in-memory live state
for name, r in db.accounts().items():                 # warm-start from DB
    if name in ACCT:
        ACCT[name] = Account(name, r["balance"], r["equity"], bool(r["is_open"]), r["last_hb"])

app = FastAPI(title="CrossKing Orchestrator")
_STATIC = os.path.join(os.path.dirname(__file__), "static")


@app.get("/")
def dashboard():
    return FileResponse(os.path.join(_STATIC, "dashboard.html"))


class Telemetry(BaseModel):
    account: str
    symbol: str = ""
    balance: float
    equity: float
    is_open: bool = False
    dir: int = 0
    stack: int = 0
    open_r: float = 0.0
    ml_sl: float = 0.0
    ver: str = ""


class OpClose(BaseModel):
    account: str
    symbol: str = ""
    realized_r: float
    positions: int = 1
    reason: str = ""
    open_time: float = 0.0
    close_time: float = 0.0


def _rebalance():
    """Recompute T + breaker, emit any new (deduped) pending transfers. Returns the plan.
    GUARD: act only on a COMPLETE picture -- if any account has never reported (warm-up) or
    its heartbeat is stale, T is incomplete, so skip breaker+transfers (don't act on partial
    state). Aligns with the §5 health/watchdog principle."""
    T = total_equity(ACCT)
    now = time.time()
    warm = all(a.last_hb > 0 and (now - a.last_hb) <= cfg.heartbeat_timeout_s
               for a in ACCT.values())
    if not warm:
        return T, 0.0, []
    halted, dd = breaker.update(T, cfg)
    if halted:
        db.log("breaker", f"HALT new ops: dd={dd:.1%} peakT={breaker.peak_T:.2f}")
    plan = plan_transfers(ACCT, cfg, T)
    pending = {(t["src"], t["dst"]) for t in db.pending_transfers()}
    for t in plan:
        if (t.src, t.dst) not in pending:             # don't re-emit an outstanding instruction
            db.add_transfer(t.src, t.dst, t.amount, t.reason)
            db.log("transfer", f"{t.reason} {t.src}->{t.dst} ${t.amount:.2f}")
    return T, dd, plan


@app.post("/telemetry")
def telemetry(t: Telemetry):
    if t.account not in ACCT:
        return {"ok": False, "error": "unknown account"}
    now = time.time()
    a = ACCT[t.account]
    a.balance, a.equity, a.is_open, a.last_hb = t.balance, t.equity, t.is_open, now
    db.upsert_account(t.account, t.balance, t.equity, t.is_open, now)
    db.add_telemetry(ts=now, account=t.account, symbol=t.symbol, balance=t.balance,
                     equity=t.equity, is_open=int(t.is_open), dir=t.dir, stack=t.stack,
                     open_r=t.open_r, ml_sl=t.ml_sl, ver=t.ver)
    T, dd, _ = _rebalance()
    return {"ok": True, "halt": breaker.halted, "T": round(T, 2), "dd": round(dd, 4)}


@app.post("/op_close")
def op_close(o: OpClose):
    db.add_op(ts=time.time(), account=o.account, symbol=o.symbol, realized_r=o.realized_r,
              positions=o.positions, reason=o.reason, open_time=o.open_time, close_time=o.close_time)
    db.log("op", f"{o.account} R={o.realized_r:+.3f} x{o.positions} {o.reason}")
    return {"ok": True}


@app.get("/control/{account}")
def control(account: str):
    """EA polls this; trade execution continues if the orchestrator is down (fail-open)."""
    return {"halt": breaker.halted}


@app.post("/halt")
def halt():
    breaker.halted = True; db.log("control", "manual HALT"); return {"halted": True}


@app.post("/resume")
def resume():
    breaker.clear(); db.log("control", "manual RESUME"); return {"halted": False}


@app.get("/status")
def status():
    now = time.time()
    T = total_equity(ACCT)
    tg = targets(ACCT, cfg, T)
    accts = []
    for name in cfg.accounts:
        a = ACCT[name]
        accts.append(dict(name=name, weight=cfg.weight(name), balance=round(a.balance, 2),
                          equity=round(a.equity, 2), target=round(tg[name], 2), is_open=a.is_open,
                          stale=(now - a.last_hb > cfg.heartbeat_timeout_s) if a.last_hb else True))
    return dict(T=round(T, 2), peak_T=round(breaker.peak_T, 2),
                drawdown=round(0 if breaker.peak_T <= 0 else (breaker.peak_T - T) / breaker.peak_T, 4),
                breaker_dd=cfg.breaker_dd, halted=breaker.halted, f_total=cfg.f_total,
                accounts=accts, pending_transfers=db.pending_transfers(),
                rstream=db.op_rstream())
