"""FastAPI orchestrator: ingest EA telemetry, run the capital/breaker brain, expose the
EA control-flag + dashboard JSON. Trade execution NEVER depends on this being up.
Run: uvicorn orchestrator.app:app --host 0.0.0.0 --port 8800
"""
import os
import copy
import time
import hmac
import hashlib
import secrets
from fastapi import FastAPI, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from .config import DEFAULT
from .capital import Account, targets, plan_transfers, total_equity, Breaker
from .db import DB
from .metrics import compute as compute_metrics
from . import terminalctl
from . import secretstore

cfg = DEFAULT
db = DB(os.environ.get("CK_DB", "orchestrator/state.db"))   # CK_DB lets tests use a throwaway DB
cfg.load_registry(db)                                 # authoritative roster from the registry (seeds first run)
cfg.apply_overrides(db.get_settings())                # restore owner's persisted live settings
breaker = Breaker()
_was_halted = False           # tracks the breaker's halt edge (fire auto-close once per trip)
_START = time.time()
CLOSE_CMD = {}                # in-memory per-account one-shot "flatten now" command (war room)
CLOSE_TTL_S = 90             # auto-expire an unacked close so it can't fire on a later EA restart
ACCT = {a: Account(a) for a in cfg.accounts}          # in-memory live state
for name, r in db.accounts().items():                 # warm-start from DB
    if name in ACCT:
        ACCT[name] = Account(name, r["balance"], r["equity"], bool(r["is_open"]), r["last_hb"])

app = FastAPI(title="CrossKing Orchestrator")
_STATIC = os.path.join(os.path.dirname(__file__), "static")

# --- access control -------------------------------------------------------------------------
# Two zones, so the dashboard can be exposed to the internet (phone) without exposing the brain:
#   * machine-to-machine (EA telemetry/op_close/control-poll + watchdog /health): VPS-local ONLY,
#     no password. The MT5 EAs hit 127.0.0.1:8800 and can't carry an Authorization header; a
#     remote caller could otherwise poison the brain's state, so these are hidden (404) off-box.
#   * everything else (dashboard /, /status, /halt, /resume): HTTP Basic auth from DASH_USER/PASS.
#     If no creds are configured we fail CLOSED -- allow only from localhost -- so opening the
#     firewall can never accidentally publish an unprotected control panel.
_TEST = bool(os.environ.get("CK_TEST"))                  # test client connects as a non-local host
DASH_USER = os.environ.get("DASH_USER", "")
DASH_PASS = os.environ.get("DASH_PASS", "")
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _client_is_local(request) -> bool:
    return bool(request.client) and request.client.host in _LOCAL_HOSTS


def _is_m2m(path: str) -> bool:
    return (path in ("/telemetry", "/op_close", "/health")
            or path == "/control" or path.startswith("/control/"))


# Stateless signed session cookie set by the /login form. The signing secret is derived from the
# creds, so cookies survive a uvicorn restart (no server-side store) yet rotate automatically if
# the password changes -- invalidating every old session.
def _session_secret():
    return hashlib.sha256(f"ck-session::{DASH_USER}:{DASH_PASS}".encode()).digest()


def _make_token(ttl=30 * 86400):
    exp = str(int(time.time()) + ttl)
    sig = hmac.new(_session_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _valid_session(request) -> bool:
    exp, _, sig = request.cookies.get("ck_session", "").partition(".")
    if not sig or not exp.isdigit() or int(exp) < time.time():
        return False
    good = hmac.new(_session_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, good)


def _gate(request):
    """Return a denial Response, or None to allow."""
    if _TEST:
        return None
    path = request.url.path
    local = _client_is_local(request)
    if _is_m2m(path):
        return None if local else Response(status_code=404)
    if path in ("/login", "/logout"):
        return None                                  # public; POST /login validates creds itself
    # The VPS itself (EAs, the Telegram bot, ops scripts on 127.0.0.1) is trusted. Remote callers
    # MUST have a valid login session cookie. Basic auth is intentionally NOT accepted: browsers
    # cache Basic creds and resend them silently, which would bypass the /login page.
    if local or _valid_session(request):
        return None
    if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/login", status_code=302)   # send browsers to the login page
    return Response(status_code=401)                          # APIs/XHR get a plain 401


@app.middleware("http")
async def _gateway(request, call_next):
    """Access gate, then force Connection: close. MT5 WebRequest (WinINet) mishandles HTTP
    keep-alive: it reuses an idle-closed pooled connection and (for POST) fails with err=5203
    instead of retrying, so every EA request must use a fresh connection."""
    denied = _gate(request)
    resp = denied if denied is not None else await call_next(request)
    resp.headers["Connection"] = "close"
    return resp


@app.get("/")
def dashboard():
    # no-cache so a redeployed dashboard always reaches the phone (the page is tiny; the only
    # heavy asset is the Chart.js CDN, which the browser caches independently).
    return FileResponse(os.path.join(_STATIC, "dashboard.html"),
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


class Login(BaseModel):
    username: str
    password: str


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(_STATIC, "login.html"),
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.post("/login")
def login(c: Login):
    if (DASH_USER and DASH_PASS
            and secrets.compare_digest(c.username, DASH_USER)
            and secrets.compare_digest(c.password, DASH_PASS)):
        r = JSONResponse({"ok": True})
        r.set_cookie("ck_session", _make_token(), max_age=30 * 86400,
                     httponly=True, samesite="lax", path="/")
        return r
    return JSONResponse({"ok": False, "error": "invalid credentials"}, status_code=401)


@app.post("/logout")
def logout():
    r = JSONResponse({"ok": True})
    r.delete_cookie("ck_session", path="/")
    return r


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


def _breaker_close_all():
    """Best-effort decoupled halt: close every registered leg's terminal on a breaker trip. Opt-in
    (CK_BREAKER_CLOSE=1) so it can't surprise-kill terminals before it's validated on demo."""
    for l in cfg.legs:
        if not l.terminal_path:
            continue
        try:
            terminalctl.close_terminal(l.terminal_path)
            db.log("terminal", f"breaker CLOSE #{l.account} ({l.tn})")
        except Exception as e:
            db.log("terminal", f"breaker close #{l.account} failed: {e}")


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
    global _was_halted
    if halted and not _was_halted:                       # fire once on the False->True transition
        db.log("breaker", f"HALT: dd={dd:.1%} peakT={breaker.peak_T:.2f}")
        if os.environ.get("CK_BREAKER_CLOSE") == "1":    # opt-in: halt == close every terminal
            _breaker_close_all()
    _was_halted = halted
    # RECONCILE first: a pending transfer is fulfilled once its leg is back within min_transfer
    # of target (you executed it in Exness, or it's no longer needed). Confirm it so it clears
    # the dashboard and unblocks the dedup. Without this, instructions stay 'pending' forever.
    tg = targets(ACCT, cfg, T)
    for t in db.pending_transfers():
        leg = t["dst"] if t["src"] == cfg.main else t["src"]
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


def _maybe_clear_close(account, now):
    """Clear a pending manual-close command once the leg confirms FLAT (it closed), or after
    CLOSE_TTL_S (so an unacknowledged command can't linger and re-fire on a later EA restart).
    Called on each telemetry ingest, where ACCT[account].is_open is freshly set."""
    cmd = CLOSE_CMD.get(account)
    if cmd and (not ACCT[account].is_open or now - cmd["ts"] > CLOSE_TTL_S):
        CLOSE_CMD.pop(account, None)


def _ingest_telemetry(t: Telemetry):
    if t.account not in ACCT:
        return {"ok": False, "error": "unknown account"}
    now = time.time()
    a = ACCT[t.account]
    bal, eq = cfg.to_usd(t.account, t.balance), cfg.to_usd(t.account, t.equity)  # USC -> USD
    a.balance, a.equity, a.is_open, a.last_hb = bal, eq, t.is_open, now
    a.dir, a.stack, a.open_r = t.dir, t.stack, t.open_r
    db.upsert_account(t.account, bal, eq, t.is_open, now)
    db.add_telemetry(ts=now, account=t.account, symbol=t.symbol, balance=bal,
                     equity=eq, is_open=int(t.is_open), dir=t.dir, stack=t.stack,
                     open_r=t.open_r, ml_sl=t.ml_sl, ver=t.ver)
    _maybe_clear_close(t.account, now)
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
    talking (even before its first telemetry lands) shows live on the dashboard.
    `close_id` is a one-shot manual 'flatten now' command (0 = none); the EA acts once per
    NEW id it sees, then ignores it -- a lingering id never re-fires."""
    if account in ACCT:
        ACCT[account].last_ctrl = time.time()      # proof-of-life only (NOT balance freshness)
    cmd = CLOSE_CMD.get(account)
    return {"halt": breaker.halted, "close_id": cmd["id"] if cmd else 0}


@app.post("/halt")
def halt():
    breaker.halted = True; db.log("control", "manual HALT"); return {"halted": True}


@app.post("/resume")
def resume():
    breaker.clear(); db.log("control", "manual RESUME"); return {"halted": False}


@app.post("/close/{account}")
def close_account(account: str):
    """Manual one-shot 'flatten this leg NOW' (war room). Sets a close command the EA reads on
    its next /control poll and acts on once; the EA's normal book-empty -> OnOpClosed() path
    then realizes R and resets. Cleared when the leg reports flat (or after CLOSE_TTL_S).
    This is the ONLY orchestrator->execution command path -- manual + optional: if the
    orchestrator is down you simply close in MT5 directly, so execution autonomy is preserved.
    NOTE: 'close' flattens current positions only; it does NOT stop re-entry -- use /halt for
    that. Auth: not an m2m path, so the gate requires a valid dashboard session (like /halt)."""
    if account not in ACCT:
        raise HTTPException(status_code=404, detail="unknown account")
    cid = int(time.time() * 1000)
    CLOSE_CMD[account] = {"id": cid, "ts": time.time()}
    db.log("control", f"manual CLOSE-ALL {account} (cmd {cid})")
    return {"ok": True, "account": account, "close_id": cid}


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
                          dir=a.dir, stack=a.stack, open_r=round(a.open_r, 3),
                          stale=(now - seen > cfg.heartbeat_timeout_s) if seen else True,
                          age_s=round(now - seen, 1) if seen else None,   # since last contact
                          no_data=(a.last_hb == 0),     # alive but never sent balance yet
                          terminal=cfg.terminal(name)))
    pending = db.pending_transfers()
    for t in pending:                                   # name the real terminal/account on each move
        t["src_terminal"] = cfg.terminal(t["src"])
        t["dst_terminal"] = cfg.terminal(t["dst"])
    sc = cfg.start_capital
    return dict(T=round(T, 2), peak_T=round(breaker.peak_T, 2),
                drawdown=round(0 if breaker.peak_T <= 0 else (breaker.peak_T - T) / breaker.peak_T, 4),
                breaker_dd=cfg.breaker_dd, halted=breaker.halted, f_total=cfg.f_total,
                start_capital=round(sc, 2), profit=round(T - sc, 2),
                profit_pct=(round((T - sc) / sc, 4) if sc > 0 else None),
                accounts=accts, pending_transfers=pending,
                rstream=db.op_rstream())


@app.get("/health")
def health():
    """Lightweight liveness/health for the watchdog + ops checks. Reports uptime and, per leg,
    telemetry age (seconds since last balance push) and whether it's currently alive."""
    now = time.time()
    legs = []
    for name in cfg.accounts:
        a = ACCT[name]
        seen = a.last_seen()
        legs.append(dict(name=name,
                         telemetry_age_s=round(now - a.last_hb, 1) if a.last_hb else None,
                         alive=bool(seen and (now - seen) <= cfg.heartbeat_timeout_s)))
    return dict(ok=True, uptime_s=round(now - _START, 1), T=round(total_equity(ACCT), 2),
                halted=breaker.halted, legs_alive=sum(1 for l in legs if l["alive"]),
                legs_total=len(legs), legs=legs)


@app.get("/metrics")
def metrics_report():
    """Backtest-grade performance report (R units) over the full closed-op stream — combined
    + per leg. See metrics.py for the metric set (profit factor, expectancy, recovery, ...)."""
    return compute_metrics(db.ops_all())


@app.get("/events")
def events(since: float = 0.0):
    """Recent event-log rows (newest first) after `since` epoch-s — drives the in-page alert feed."""
    return {"events": db.events_since(since)}


# ---- live settings (war room): full control, confirm-to-apply, persisted -------------------
class Settings(BaseModel):
    f_total: float
    breaker_dd: float
    min_transfer: float
    heartbeat_timeout_s: float
    start_capital: float | None = None                 # None = leave unchanged (partial update safe)
    weights: dict = {}                                  # {leg account: weight} (renormalized on apply)


def _settings_payload():
    return dict(f_total=cfg.f_total, breaker_dd=cfg.breaker_dd, min_transfer=cfg.min_transfer,
                heartbeat_timeout_s=cfg.heartbeat_timeout_s, start_capital=cfg.start_capital,
                weights={l.account: round(l.weight, 4) for l in cfg.legs},
                legmeta={l.account: dict(tn=l.tn, strategy=l.strategy) for l in cfg.legs},
                bounds=dict(f_total=[0.0, 1.0], breaker_dd=[0.0, 1.0],
                            min_transfer=[0.0, None], heartbeat_timeout_s=[30, None],
                            start_capital=[0.0, None]))


def _validate(s: Settings):
    """Validate + flatten to an overrides dict (weight_<account> keys). Raises 400 on bad input."""
    errs = []
    if not (0 < s.f_total <= 1):        errs.append("f_total must be in (0, 1]")
    if not (0 < s.breaker_dd <= 1):     errs.append("breaker_dd must be in (0, 1]")
    if s.min_transfer < 0:              errs.append("min_transfer must be >= 0")
    if s.heartbeat_timeout_s < 30:      errs.append("heartbeat_timeout_s must be >= 30")
    if s.start_capital is not None and s.start_capital < 0:
        errs.append("start_capital must be >= 0")
    valid = {l.account for l in cfg.legs}
    w = {k: float(v) for k, v in s.weights.items() if k in valid}
    if w:
        if any(v < 0 for v in w.values()):  errs.append("weights must be >= 0")
        if sum(w.values()) <= 0:            errs.append("weights must sum to > 0")
    if errs:
        raise HTTPException(status_code=400, detail="; ".join(errs))
    ov = dict(f_total=s.f_total, breaker_dd=s.breaker_dd, min_transfer=s.min_transfer,
              heartbeat_timeout_s=s.heartbeat_timeout_s)
    if s.start_capital is not None:
        ov["start_capital"] = s.start_capital
    ov.update({f"weight_{k}": v for k, v in w.items()})
    return ov


def _preview(overrides):
    """What applying `overrides` would do RIGHT NOW: target deltas + transfers it would fire.
    Computed on a deep copy so the live config is untouched (used by dry_run)."""
    trial = copy.deepcopy(cfg)
    trial.apply_overrides(overrides)
    T = total_equity(ACCT)
    cur, new = targets(ACCT, cfg, T), targets(ACCT, trial, T)
    plan = plan_transfers(ACCT, trial, T)
    return dict(T=round(T, 2),
                targets={k: dict(old=round(cur[k], 2), new=round(new[k], 2)) for k in new},
                transfers=[dict(src=t.src, dst=t.dst, amount=t.amount, reason=t.reason)
                           for t in plan])


@app.get("/settings")
def get_settings():
    return _settings_payload()


@app.post("/settings")
def post_settings(s: Settings, dry_run: int = 0):
    overrides = _validate(s)
    if dry_run:
        return dict(ok=True, preview=_preview(overrides))
    for k, v in overrides.items():
        if k.startswith("weight_"):
            db.leg_set_weight(k[len("weight_"):], v)    # weights are the registry's (single source of truth)
        else:
            db.set_setting(k, v)                         # scalar dials persist in settings
    _reload_roster()                                    # rebuild legs from the registry (new weights) + dials
    db.log("settings", "f_total={f_total} breaker_dd={breaker_dd} min_transfer={min_transfer} "
           "heartbeat={heartbeat_timeout_s}".format(**overrides)
           + " weights=" + ",".join(f"{k[7:]}:{v:.3f}" for k, v in overrides.items()
                                     if k.startswith("weight_")))
    return dict(ok=True, applied=_settings_payload())


# ---- roster registry (war room): register / remove / enable accounts LIVE, no restart ----------
def _reload_roster():
    """Rebuild the live roster from the DB registry (+ persisted scalar dials) and re-sync ACCT so
    a just-registered account gets an in-memory slot (warm-started from the DB if seen before) and a
    removed one is dropped. The capital brain reads cfg.legs/ACCT next tick — no restart."""
    cfg.load_registry(db)
    cfg.apply_overrides(db.get_settings())
    seen = db.accounts()
    for a in cfg.accounts:
        if a not in ACCT:
            r = seen.get(a)
            ACCT[a] = (Account(a, r["balance"], r["equity"], bool(r["is_open"]), r["last_hb"])
                       if r else Account(a))
    for a in [a for a in ACCT if a not in cfg.accounts]:
        del ACCT[a]


class LegReg(BaseModel):
    login: str
    tn: str = ""
    server: str = ""
    role: str = "ops"                 # "ops" | "main" (the reserve hub)
    weight: float = 0.0
    strategy: str = ""                # swappable label (current preset/EA); not an identity
    symbol: str = ""
    cents: bool = True
    terminal_path: str = ""
    enabled: bool = True
    password: str = ""                # the account's MT5 password for the collector; -> secrets.json
                                      # (gitignored, never stored in the DB or returned by any API)


@app.get("/legs")
def list_legs():
    """Full registry (incl. disabled) for the roster-management UI. Adds `has_password` (whether the
    collector has creds to poll it) — the password itself is NEVER returned."""
    legs = db.legs_all()
    for l in legs:
        l["has_password"] = secretstore.has_password(l["login"])
    return {"legs": legs}


@app.post("/legs")
def register_leg(r: LegReg):
    """Register a new account or update an existing one (upsert by login). Swapping the strategy on
    an account is just an update here — the login identity and weight are untouched."""
    login = r.login.strip()
    if not login:
        raise HTTPException(status_code=400, detail="login required")
    if r.weight < 0:
        raise HTTPException(status_code=400, detail="weight must be >= 0")
    db.leg_upsert(login, tn=r.tn.strip(), server=r.server.strip(), role=r.role, weight=r.weight,
                  strategy=r.strategy.strip(), symbol=r.symbol.strip(), cents=r.cents,
                  enabled=r.enabled, terminal_path=r.terminal_path.strip())
    if r.password:
        secretstore.set_password(login, r.password)     # -> gitignored secrets.json (collector creds)
    _reload_roster()
    db.log("registry", f"register {r.tn or '-'} #{login} ({r.strategy or r.role})")
    return list_legs() | dict(ok=True, accounts=cfg.accounts)


@app.delete("/legs/{login}")
def remove_leg(login: str):
    db.leg_remove(login)
    _reload_roster()
    db.log("registry", f"remove #{login}")
    return dict(ok=True, accounts=cfg.accounts, legs=db.legs_all())


@app.post("/legs/{login}/enabled")
def enable_leg(login: str, on: int = 1):
    db.leg_set_enabled(login, bool(on))
    _reload_roster()
    db.log("registry", f"{'enable' if on else 'disable'} #{login}")
    return dict(ok=True, enabled=bool(on), accounts=cfg.accounts, legs=db.legs_all())


# ---- terminal control (war room): halt = close the terminal; open re-launches; flatten closes trades
def _leg_path(login: str):
    t = cfg.terminal(login)
    path = t.get("terminal_path") if t else None
    if not path:
        raise HTTPException(status_code=404, detail=f"no terminal_path registered for #{login}")
    return path


@app.post("/terminal/{login}/open")
def terminal_open(login: str):
    """Launch the leg's terminal (auto-login + auto-attach EA). Un-halts a closed leg."""
    db.log("terminal", f"OPEN #{login}")
    return terminalctl.open_terminal(_leg_path(login))


@app.post("/terminal/{login}/close")
def terminal_close(login: str):
    """Kill the leg's terminal process — the decoupled HALT: no more new trades on this leg."""
    db.log("terminal", f"CLOSE #{login} (halt)")
    return terminalctl.close_terminal(_leg_path(login))


@app.post("/flatten/{login}")
def flatten(login: str):
    """Close all open trades on the leg, via the terminal's own authorized session (no trade creds)."""
    import MetaTrader5 as mt5
    db.log("terminal", f"FLATTEN #{login}")
    return terminalctl.flatten_positions(mt5, _leg_path(login))
