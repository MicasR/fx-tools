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


def tlabel(name, term):
    """`T1 PD3_BtcTrail_1 #12345` when the terminal map is present, else just the leg name."""
    if not term:
        return name
    tn = term.get("tn")
    login = term.get("login")
    return (f"{tn} " if tn else "") + name + (f" #{login}" if login else "")


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


ORCH_FAIL_ALERT = 24        # consecutive failed /status polls (~2 min at 5s) before alerting


class AlertState:
    """Edge-detection memory between poll cycles — every alert fires once per transition."""
    def __init__(self):
        self.seen_xfer = set()
        self.was_halted = False
        self.stale = set()          # leg names stale last cycle
        self.all_stale = False      # full-outage latch (collector/terminals down)
        self.orch_fails = 0         # consecutive /status failures
        self.orch_down = False      # unreachable alert already sent


def status_alerts(st, s):
    """PURE (no I/O): fold one /status snapshot into `st` and return this cycle's alert messages.
    `s` is the /status dict, or None when the orchestrator was unreachable. The 2026-07-07..10
    incident (collector dead 3 days, dashboard blind, nobody paged) is what the all-stale
    escalation + recovery messages exist for."""
    msgs = []
    if s is None:
        st.orch_fails += 1
        if st.orch_fails >= ORCH_FAIL_ALERT and not st.orch_down:
            st.orch_down = True
            msgs.append("🚨 ORCHESTRATOR UNREACHABLE — /status failing. Dashboard + alerts blind. "
                        "Check CrossKing-Orchestrator task.")
        return msgs
    if st.orch_down:
        msgs.append("✅ orchestrator reachable again.")
    st.orch_fails, st.orch_down = 0, False

    term = {a["name"]: a.get("terminal") for a in s["accounts"]}
    for t in s.get("pending_transfers", []):
        if t["id"] not in st.seen_xfer:
            st.seen_xfer.add(t["id"])
            src = tlabel(t["src"], t.get("src_terminal"))
            dst = tlabel(t["dst"], t.get("dst_terminal"))
            msgs.append(f"💸 TRANSFER: move ${t['amount']:,.2f}  {src} → {dst}  ({t['reason']})")
    if s["halted"] and not st.was_halted:
        msgs.append(f"🛑 CIRCUIT BREAKER — DD {s['drawdown']*100:.1f}%. New ops halted. /resume to clear.")
    elif st.was_halted and not s["halted"]:
        msgs.append("✅ breaker cleared — running.")
    st.was_halted = s["halted"]

    names = {a["name"] for a in s["accounts"]}
    now_stale = {a["name"] for a in s["accounts"] if a["stale"]}
    all_stale = bool(names) and now_stale == names
    if all_stale and not st.all_stale:
        msgs.append(f"🚨 ALL {len(names)} LEGS STALE — collector or terminals down; the dashboard "
                    "is blind (trading unaffected). Fix per ops/RUNBOOK.md 'Collector'.")
    elif st.all_stale and not all_stale:
        msgs.append(f"✅ telemetry restored — {len(names - now_stale)}/{len(names)} legs alive.")
    elif not all_stale:                       # per-leg edges (a full outage is one alert, not 7)
        for n in sorted(now_stale - st.stale):
            msgs.append(f"⚠️ {tlabel(n, term.get(n))} heartbeat STALE (terminal/EA down?).")
        for n in sorted(st.stale - now_stale):
            msgs.append(f"✅ {tlabel(n, term.get(n))} heartbeat back.")
    st.stale, st.all_stale = now_stale, all_stale
    return msgs


def run():
    send("CrossKing bot online.")
    offset = 0
    st = AlertState()
    while True:
        try:                                            # commands
            r = httpx.get(f"{TG}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = (u.get("message") or {}).get("text", "")
                if msg.startswith("/"):
                    send(handle(msg))
        except Exception as e:
            print(f"[bot] getUpdates failed: {e}")
        s = None
        try:                                            # alerts off /status
            s = httpx.get(f"{ORCH}/status", timeout=10).json()
        except Exception as e:
            print(f"[bot] /status failed: {e}")
        for m in status_alerts(st, s):
            send(m)
        time.sleep(5)


if __name__ == "__main__":
    run()
