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


@app.middleware("http")
async def _force_close(request, call_next):
    """MT5 WebRequest (WinHTTP) mishandles HTTP keep-alive: the first POST on a fresh socket
    succeeds, then reuse of the idle-closed keep-alive connection fails with err=5203 (the POST
    never reaches us). Return Connection: close so every EA request uses a fresh connection."""
    resp = await call_next(request)
    resp.headers["Connection"] = "close"
    return resp


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
    # RECONCILE first: a pending transfer is fulfilled once its leg is back within min_transfer
    # of target (you executed it in Exness, or it's no longer needed). Confirm it so it clears
    # the dashboard and unblocks the dedup. Without this, instructions stay 'pending' forever.
    tg = targets(ACCT, cfg, T)
    for t in db.pending_transfers():
        leg = t["dst"] if t["src"] == MAIN else t["src"]
        acc = ACCT.get(leg)
        if acc and not acc.is_open and abs(acc.balance - tg[leg]) <= cfg.min_transfer:
            db.confirm_transfer(t["id"])
            db.log("transfer", f"confirm {t['reason']} {t['src']}->{t['dst']} ${t['amount']:.2f}")
    plan = plan_transfers(ACCT, cfg, T)
    pending = {(t["src"], t["dst"]) for t in db.pending_transfers()}   # re-read after confirms
    for t in plan:
        if (t.src, t.dst) not in pending:             # don't re-emit an outstanding instruction
            db.add_transfer(t.src, t.dst, t.amount, t.reason)
            db.log("transfer", f"{t.reason} {t.src}->{t.dst} ${t.amount:.2f}")
    return T, dd, plan


def _ingest_telemetry(t: Telemetry):
    if t.account not in ACCT:
        return {"ok": False, "error": "unknown account"}
    now = time.time()
    a = ACCT[t.account]
    bal, eq = cfg.to_usd(t.account, t.balance), cfg.to_usd(t.account, t.equity)  # USC -> USD
    a.balance, a.equity, a.is_open, a.last_hb = bal, eq, t.is_open, now
    db.upsert_account(t.account, bal, eq, t.is_open, now)
    db.add_telemetry(ts=now, account=t.account, symbol=t.symbol, balance=bal,
                     equity=eq, is_open=int(t.is_open), dir=t.dir, stack=t.stack,
                     open_r=t.open_r, ml_sl=t.ml_sl, ver=t.ver)
    T, dd, _ = _rebalance()
    return {"ok": True, "halt": breaker.halted, "T": round(T, 2), "dd": round(dd, 4)}


# The EA sends telemetry over GET (query params), not POST: MT5's WebRequest runs on WinINet,
# which mishandles reused keep-alive connections for POST (non-idempotent -> not auto-retried,
# fails err=5203), while GET self-heals. POST is kept for tests/other clients.
@app.post("/telemetry")
def telemetry_post(t: Telemetry):
    return _ingest_telemetry(t)


@app.get("/telemetry")
def telemetry_get(account: str, symbol: str = "", balance: float = 0.0, equity: float = 0.0,
                  is_open: bool = False, dir: int = 0, stack: int = 0, open_r: float = 0.0,
                  ml_sl: float = 0.0, ver: str = ""):
    return _ingest_telemetry(Telemetry(account=account, symbol=symbol, balance=balance,
                             equity=equity, is_open=is_open, dir=dir, stack=stack,
                             open_r=open_r, ml_sl=ml_sl, ver=ver))


def _ingest_op_close(o: OpClose):
    db.add_op(ts=time.time(), account=o.account, symbol=o.symbol, realized_r=o.realized_r,
              positions=o.positions, reason=o.reason, open_time=o.open_time, close_time=o.close_time)
    db.log("op", f"{o.account} R={o.realized_r:+.3f} x{o.positions} {o.reason}")
    return {"ok": True}


@app.post("/op_close")
def op_close_post(o: OpClose):
    return _ingest_op_close(o)


@app.get("/op_close")
def op_close_get(account: str, symbol: str = "", realized_r: float = 0.0, positions: int = 1,
                 reason: str = "", open_time: float = 0.0, close_time: float = 0.0):
    return _ingest_op_close(OpClose(account=account, symbol=symbol, realized_r=realized_r,
                            positions=positions, reason=reason, open_time=open_time,
                            close_time=close_time))


@app.get("/control/{account}")
def control(account: str):
    """EA polls this every heartbeat; trade execution continues if the orchestrator is down
    (fail-open). The poll is also proof-of-life: refresh last_hb so a leg that is alive and
    talking (even before its first telemetry lands) shows live on the dashboard."""
    if account in ACCT:
        ACCT[account].last_ctrl = time.time()      # proof-of-life only (NOT balance freshness)
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
        seen = a.last_seen()
        accts.append(dict(name=name, weight=cfg.weight(name), balance=round(a.balance, 2),
                          equity=round(a.equity, 2), target=round(tg[name], 2), is_open=a.is_open,
                          stale=(now - seen > cfg.heartbeat_timeout_s) if seen else True,
                          no_data=(a.last_hb == 0)))    # alive but never sent balance yet
    return dict(T=round(T, 2), peak_T=round(breaker.peak_T, 2),
                drawdown=round(0 if breaker.peak_T <= 0 else (breaker.peak_T - T) / breaker.peak_T, 4),
                breaker_dd=cfg.breaker_dd, halted=breaker.halted, f_total=cfg.f_total,
                accounts=accts, pending_transfers=db.pending_transfers(),
                rstream=db.op_rstream())
