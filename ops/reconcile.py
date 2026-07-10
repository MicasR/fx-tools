"""Reconciliation report (DEPLOYMENT_GUIDE §11): live R-stream vs backtest expectation, plus a
transfer audit (any pending/unconfirmed instruction). Read-only — pulls /status and reads the
audit DB directly. Run:  .venv\\Scripts\\python ops\\reconcile.py
"""
import os
import sqlite3
import statistics
import urllib.request
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "orchestrator", "state.db")
ORCH = os.environ.get("ORCH_URL", "http://127.0.0.1:8800")


def status():
    try:
        return json.load(urllib.request.urlopen(f"{ORCH}/status", timeout=5))
    except Exception as e:
        return {"error": str(e)}


def main():
    s = status()
    print("== ORCHESTRATOR ==")
    if "error" in s:
        print(f"  unreachable: {s['error']}")
    else:
        print(f"  T={s['T']}  peak={s['peak_T']}  DD={s['drawdown']*100:.1f}%/{s['breaker_dd']*100:.0f}%"
              f"  {'HALTED' if s['halted'] else 'running'}  f_total={s['f_total']}")
        for a in s["accounts"]:
            flag = "OPEN" if a["is_open"] else "flat"
            dead = " STALE!" if a["stale"] else ""
            print(f"    {a['name']:<16} bal={a['balance']:>10.2f} target={a['target']:>10.2f} {flag}{dead}")

    cx = sqlite3.connect(DB)
    cx.row_factory = sqlite3.Row

    print("\n== LIVE R-STREAM (closed ops) ==")
    rows = cx.execute("SELECT account, realized_r FROM ops ORDER BY close_time").fetchall()
    if not rows:
        print("  (no closed ops yet)")
    else:
        by = {}
        for r in rows:
            by.setdefault(r["account"], []).append(r["realized_r"])
        for acct, rs in by.items():
            tot = sum(rs)
            mean = statistics.mean(rs)
            print(f"    {acct:<16} n={len(rs):<4} sumR={tot:+.2f}  meanR={mean:+.3f}  min={min(rs):+.3f}")
        allr = [r["realized_r"] for r in rows]
        print(f"    {'ALL':<16} n={len(allr):<4} sumR={sum(allr):+.2f}  meanR={statistics.mean(allr):+.3f}")
        print("  NOTE: compare sumR/meanR to backtest/out/shadow/<leg>.csv expectation (§11 weekly reconcile).")

    print("\n== TRANSFER AUDIT ==")
    trs = cx.execute("SELECT src,dst,amount,reason,status,ts,confirmed_ts FROM transfers ORDER BY ts").fetchall()
    if not trs:
        print("  (no transfers instructed yet)")
    else:
        pend = 0
        for t in trs:
            mark = "" if t["status"] == "confirmed" else "  <-- UNCONFIRMED"
            if t["status"] != "confirmed":
                pend += 1
            print(f"    {t['status']:<9} ${t['amount']:>8.2f} {t['src']}->{t['dst']} ({t['reason']}){mark}")
        if pend:
            print(f"  ACTION: {pend} transfer(s) not yet confirmed — verify you executed them in Exness PA.")
    cx.close()


if __name__ == "__main__":
    main()
