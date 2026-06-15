"""Telegram bot — alerts + control, a decoupled CLIENT of the orchestrator HTTP API.
Polls /status to detect events (new pending transfers, breaker trips, stale EAs) and
sends alerts; handles commands (/status /halt /resume /kill). Import-safe (loop only under
__main__). Env: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ORCH_URL (default http://127.0.0.1:8800).
Run: python -m orchestrator.bot
"""
import os
import time
import httpx

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
ORCH = os.environ.get("ORCH_URL", "http://127.0.0.1:8800")
TG = f"https://api.telegram.org/bot{TOKEN}"


def send(text):
    if not (TOKEN and CHAT):
        print("[bot] (no token/chat) " + text); return
    try:
        httpx.post(f"{TG}/sendMessage", json={"chat_id": CHAT, "text": text}, timeout=10)
    except Exception as e:
        print(f"[bot] send failed: {e}")


def fmt_status(s):
    lines = [f"T=${s['T']:,.0f}  DD={s['drawdown']*100:.1f}% / {s['breaker_dd']*100:.0f}%"
             f"  {'HALTED' if s['halted'] else 'running'}"]
    for a in s["accounts"]:
        flag = "OPEN" if a["is_open"] else "flat"
        dead = " STALE" if a["stale"] else ""
        lines.append(f"  {a['name']}: ${a['balance']:,.0f}/{a['target']:,.0f} {flag}{dead}")
    for t in s.get("pending_transfers", []):
        lines.append(f"  → move ${t['amount']:,.2f}  {t['src']}→{t['dst']} ({t['reason']})")
    return "\n".join(lines)


def handle(cmd):
    cmd = cmd.split("@")[0].strip().lower()
    try:
        if cmd == "/status":
            return fmt_status(httpx.get(f"{ORCH}/status", timeout=10).json())
        if cmd in ("/halt", "/kill"):
            httpx.post(f"{ORCH}/halt", timeout=10); return "HALTED — no new ops (open ops manage out)."
        if cmd == "/resume":
            httpx.post(f"{ORCH}/resume", timeout=10); return "RESUMED."
    except Exception as e:
        return f"orchestrator unreachable: {e}"
    return "commands: /status /halt /resume /kill"


def run():
    send("CrossKing bot online.")
    offset = 0
    seen_xfer, was_halted, stale = set(), False, set()
    while True:
        try:                                            # commands
            r = httpx.get(f"{TG}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = (u.get("message") or {}).get("text", "")
                if msg.startswith("/"):
                    send(handle(msg))
        except Exception:
            pass
        try:                                            # alerts off /status
            s = httpx.get(f"{ORCH}/status", timeout=10).json()
            for t in s.get("pending_transfers", []):
                if t["id"] not in seen_xfer:
                    seen_xfer.add(t["id"])
                    send(f"💸 TRANSFER: move ${t['amount']:,.2f} {t['src']}→{t['dst']} ({t['reason']})")
            if s["halted"] and not was_halted:
                send(f"🛑 CIRCUIT BREAKER — DD {s['drawdown']*100:.1f}%. New ops halted. /resume to clear.")
            was_halted = s["halted"]
            now_stale = {a["name"] for a in s["accounts"] if a["stale"]}
            for n in now_stale - stale:
                send(f"⚠️ {n} heartbeat STALE (terminal/EA down?).")
            stale = now_stale
        except Exception:
            pass
        time.sleep(5)


if __name__ == "__main__":
    run()
