"""Terminal process control + flatten for the war room.

The decoupled halt model: **halt = close the terminal**. Killing terminal64.exe stops the EA from
opening anything new — no EA cooperation, no control-poll needed. Re-open relaunches it (MT5
auto-logs-in from saved creds and re-attaches the EA per its chart profile).

`flatten` closes open positions on the account the terminal is logged into, using the terminal's
OWN already-authorized session (mt5 attach by install path) — so NO trade password is ever stored;
the read-only collector creds stay the only secrets. `flatten_positions` is pure w.r.t. the injected
`mt5` module, so its close-order construction is unit-tested with a fake mt5.

All process control is Windows/VPS-local (the orchestrator runs on the terminal host).
"""
import os
import subprocess

# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — the launched terminal outlives the orchestrator.
_DETACHED = 0x00000008 | 0x00000200


def open_terminal(path):
    """Launch a terminal (auto-login + auto-attach EA). Detached so it survives an orchestrator restart."""
    if not path or not os.path.exists(path):
        return {"ok": False, "error": f"terminal not found: {path}"}
    subprocess.Popen([path], creationflags=_DETACHED, close_fds=True)
    return {"ok": True, "action": "open", "path": path}


def close_terminal(path):
    """Kill ONLY the terminal64.exe whose ExecutablePath == path (not every MT5 instance on the box).
    The path is passed via env (not string-interpolated) so it can't break the PowerShell command."""
    if not path:
        return {"ok": False, "error": "no terminal_path"}
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
          "Where-Object { $_.ExecutablePath -eq $env:CKPATH } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       env={**os.environ, "CKPATH": path}, capture_output=True, text=True, timeout=25)
    return {"ok": r.returncode == 0, "action": "close", "path": path,
            "error": (r.stderr.strip() or None) if r.returncode else None}


def _close_request(mt5, p):
    """Build a market close order for open position `p` (opposite side, full volume)."""
    is_buy = (p.type == mt5.POSITION_TYPE_BUY)
    tick = mt5.symbol_info_tick(p.symbol)
    price = tick.bid if is_buy else tick.ask
    return dict(action=mt5.TRADE_ACTION_DEAL, position=p.ticket, symbol=p.symbol, volume=p.volume,
                type=(mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY), price=price,
                deviation=50, magic=getattr(p, "magic", 0), comment="war-room flatten",
                type_time=mt5.ORDER_TIME_GTC, type_filling=mt5.ORDER_FILLING_IOC)


def flatten_positions(mt5, path):
    """Close every open position on the account the terminal at `path` is logged into, via that
    terminal's live (trade-authorized) session. Returns {ok, closed, failed}."""
    if not mt5.initialize(path=path):
        return {"ok": False, "error": str(mt5.last_error())}
    try:
        closed = failed = 0
        for p in (mt5.positions_get() or []):
            res = mt5.order_send(_close_request(mt5, p))
            if res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
                closed += 1
            else:
                failed += 1
        return {"ok": failed == 0, "closed": closed, "failed": failed}
    finally:
        mt5.shutdown()
