# CrossKing KING — Deployment Runbook

End-to-end setup to take the crowned **KING** (GROWTH-6 weight-opt) from repo → live, per
`SYSTEM_PLAN.md`. Model: **EA-dumb / orchestrator-brain**, 7 accounts (6 ops + 1 Main),
semi-manual cash sweeps. Work top-to-bottom; each section states its **Objective** and the
**Deliverables** you should have before moving on.

> **Golden rules**
> - Trading never depends on the orchestrator (control poll is fail-open). It's safe to start EAs before the brain.
> - **Deploy on the honest number: bootstrap-median ≈ 12×, NOT the $41k headline** (`SYSTEM_PLAN.md §12`).
> - Demo first, then $100 (mechanics), then $1000. Kill-triggers armed throughout.
> - Secrets (account passwords, Telegram token) live in a `.env` on the VPS — **never commit them.**

---

## 0. Prerequisites & cost reality

**Objective:** know what you're buying and why before spending.

**Deliverables:** a shortlist of provider + plan, and the 7 Exness accounts planned.

- The strategy is **H1 / M15 closed-bar** — *not* latency-sensitive. **Do NOT pay for a premium
  "Forex VPS" / low-latency colocation.** A cheap general-purpose VPS near the broker region is fine.
- You need **Windows** (7 MT5 terminals) **or** Linux + Wine (cheaper, fiddlier — see §2 option B).
- Sizing: 7 MT5 terminals (~300–500 MB each) + Python ⇒ **8 GB RAM minimum**, 4 vCPU, ~80 GB disk.
- All-in cost target: **~$15–40/mo** (VPS) + $0 software. Nothing is spent in research; cost starts here.

---

## 1. Broker accounts (Exness)

**Objective:** seven real MT5 accounts under one Exness profile, correctly typed and leveraged.

**Deliverables:** a table of 7 logins (number / password / server) saved to your password manager
(and later the VPS `.env`), each set to **leverage 1:2000**, account currency **USD**.

1. In your Exness Personal Area, create **7 MT5 accounts** (Standard or the c-symbol type you
   backtested — symbols must be `XAUUSDc` / `BTCUSDc`, matching the research):
   | terminal | account role | preset | symbol/chart |
   |---|---|---|---|
   | T1 | ops `PD3_BtcTrail_1` | PD3_BtcTrail_1.set | BTCUSDc H1 |
   | T2 | ops `PD3_GoldGeo_0` | PD3_GoldGeo_0.set | XAUUSDc H1 (mgmt M15) |
   | T3 | ops `PD3_BtcTrail_4` | PD3_BtcTrail_4.set | BTCUSDc H1 |
   | T4 | ops `PD3_BtcNb_2` | PD3_BtcNb_2.set | BTCUSDc H1 |
   | T5 | ops `PD3_BtcPin_5` | PD3_BtcPin_5.set | BTCUSDc H1 |
   | T6 | ops `PD3_GoldGeo_3` | PD3_GoldGeo_3.set | XAUUSDc H1 (mgmt M15) |
   | T7 | **Main** reporter | (telemetry only) | any (no trading) |
2. Set every account to **1:2000 leverage** (the add-cap math assumes it) and **USD**.
3. Record login / investor-password-NO-use-master / server name for each. Confirm `XAUUSDc` and
   `BTCUSDc` exist in Market Watch on these accounts.

> NB: do not fund yet — funding is §9, after the system is verified on demo.

---

## 2. VPS provisioning

**Objective:** one always-on Windows host sized for 7 terminals + the orchestrator.

**Deliverables:** a running Windows VPS you can RDP into, with admin login saved.

### Option A — Windows VPS (recommended; simplest for 7 MT5 terminals)
Pick the cheapest that gives **≥8 GB RAM / 4 vCPU / ~80 GB**:

| provider | ~price/mo (8GB Win) | notes |
|---|---|---|
| **Contabo** "Cloud VPS" + Windows license | ~$15–25 | cheapest reliable; pick a region near the Exness server |
| **Hostinger** KVM 4/8 (you have an account) | ~$10–18 | **KVM plans run Windows via custom OS install** — see below |
| Vultr / Kamatera | ~$25–40 | hourly billing, easy Windows images, many regions |
| ForexVPS.net / Cheap-Windows-VPS | ~$30–60 | turnkey MT5, but you're overpaying for latency you don't need |

**Hostinger specifics (since you have an account):** Hostinger's **KVM VPS** plans support a
**custom OS / template**; choose a Windows Server template if offered on your plan, or install
Windows Server via custom ISO. If your Hostinger plan is Linux-only with no Windows option, either
(a) upgrade to a KVM plan that allows custom OS, or (b) use Option B (Wine), or (c) use Contabo for
the Windows box. Aim for the **KVM 4** tier (≈4 vCPU / 16 GB) for comfortable headroom.

### Option B — Linux VPS + Wine (cheapest, more setup)
A Hostinger KVM Linux VPS (~$8–10/mo) running MT5 under Wine. Works but: 7 Wine prefixes is
fiddly, updates can break, and you'll manage it via headless X. **Only choose this if you're
comfortable with Wine.** (Everything else in this guide is identical; the orchestrator is pure
Python and runs natively on Linux.)

**Steps:** create the VPS → choose region near the broker → set a strong admin password → note the
public IP → enable RDP (Windows) / SSH (Linux).

---

## 3. VPS base setup

**Objective:** a clean host with the toolchain and correct clock.

**Deliverables:** Python 3.11+, Git installed; firewall allowing your dashboard port; server clock
matching broker time.

1. RDP in (Windows) or SSH (Linux). Apply OS updates.
2. Install **Python 3.11+** (tick "Add to PATH") and **Git**.
3. Set the **time zone to the broker's server time** (detection is closed-bar / server-time based).
4. Firewall: allow inbound **TCP 8800** only from **your IP** (the dashboard). Keep RDP/SSH locked
   to your IP too. Everything else closed.
5. Create a working folder, e.g. `C:\ck\`.

---

## 4. Get the code on the VPS

**Objective:** the repo present and the orchestrator deps installed.

**Deliverables:** `git pull` works; `python -m orchestrator.test_capital` and `test_app` pass on the VPS.

```
cd C:\ck
git clone <your repo url> fx_tools
cd fx_tools
python -m venv .venv && .venv\Scripts\activate
pip install -r orchestrator\requirements.txt
python -m orchestrator.test_capital     # expect 10/10
python -m orchestrator.test_app          # expect 12/12
```
If both test suites pass on the VPS, the brain is healthy on this box.

---

## 5. MT5 terminals (7 portable installs)

**Objective:** one terminal per account, each auto-logging in and running the right EA+preset, with
WebRequest allowed to the orchestrator.

**Deliverables:** 7 terminals open, each logged into its account, the correct chart up, `CrossKing_EA`
attached with its `PD3_*.set`, and a smiley (EA enabled). Main runs telemetry only.

1. Install MT5 **7 times as portable** (separate folders `C:\ck\mt5\T1 … T7`, each launched with
   the `/portable` flag so each keeps its own data dir + login).
2. In each terminal: **File ▸ Login to Trade Account** → that account's login/password/server.
   Enable **Tools ▸ Options ▸ auto-login** so it reconnects on reboot.
3. Deploy the EA: copy `ExpertAdvisors/CrossKing_EA/CrossKing_EA.ex5` to each terminal's
   `MQL5\Experts\`, and the matching `PD3_*.set` to `MQL5\Presets\` (or load it from the chart's
   Inputs tab). *Or* junction the project folder (see `reference_mt5_junction_setup` pattern).
4. **WebRequest whitelist** (each terminal): Tools ▸ Options ▸ Expert Advisors ▸ *Allow WebRequest
   for listed URL* → add the orchestrator base, e.g. `http://127.0.0.1:8800` (same box) or
   `http://<VPS-LAN-IP>:8800`.
5. Attach EA to the right chart per the §1 table (gold → XAUUSDc H1 chart; BTC → BTCUSDc H1). In the
   EA Inputs set **`InpTelemetryURL` = the orchestrator base url**. Leave `InpFixedE0=0` (live = whole
   account balance), `InpTROverride=0`, `InpMPLOverride=0` (read live). Enable **Algo Trading**.
6. Main (T7): attach the EA (or a reporter) with `InpLegName=Main` and `InpTelemetryURL` set; it
   reports balance only (it won't trade if you give it no trading preset / disable its entries).

> Verify each shows a 🙂 and prints the `[CrossKing:<leg>] init` line in the Experts log.

---

## 6. Orchestrator service

**Objective:** the brain + dashboard running 24/7 and auto-restarting.

**Deliverables:** `http://<VPS>:8800/` shows the control center; all 7 accounts appear (green dots)
within a heartbeat; it survives a reboot.

1. Configure `orchestrator/config.py` (or env): set **`f_total`** = the deployment risk budget
   (shakedown: hot, e.g. 0.20–0.30; $1000 live: ~0.054 for the 24%-DD design point), **`breaker_dd`**
   (0.35 shakedown / 0.80 live), `min_transfer` (e.g. $0.50 shakedown / scale up later). Confirm the
   6 leg account ids equal your `InpLegName`s and weights match `PD3_KING_manifest.md`.
2. Run it: `uvicorn orchestrator.app:app --host 0.0.0.0 --port 8800`.
3. **Auto-start + watchdog:** wrap it as a Windows *Scheduled Task* (or NSSM service) set to run at
   boot and restart on failure. (Linux: a `systemd` unit with `Restart=always`.)
4. Open the dashboard from your machine; confirm T, per-account cards, and health dots populate.

---

## 7. Telegram bot

**Objective:** push alerts (transfers, breaker, dead EA) and accept control commands.

**Deliverables:** `/status` in your Telegram chat returns the live system state; you receive a
"transfer" alert when a leg wins/loses.

1. In Telegram, talk to **@BotFather** → `/newbot` → save the **token**.
2. Get your **chat id**: message the bot once, then open
   `https://api.telegram.org/bot<token>/getUpdates` and read `chat.id`.
3. On the VPS create `C:\ck\fx_tools\.env` (NOT committed):
   ```
   TELEGRAM_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ORCH_URL=http://127.0.0.1:8800
   ```
4. Run `python -m orchestrator.bot` (load the env first), and make it a second auto-start service.
5. Test: send `/status`, `/halt`, `/resume` from your phone; confirm responses + that `/halt` flips
   the dashboard banner to HALTED.

---

## 8. Live round-trip smoke (DEMO accounts first)

**Objective:** prove EA → orchestrator → dashboard → Telegram works end-to-end **before real money**.
This is the one validation impossible offline (the Strategy Tester disables WebRequest).

**Deliverables:** on demo, a leg opens an op → dashboard shows it OPEN with stack/open-R; on close,
the R-stream chart gets a point and `/op_close` is logged; a win produces a pending-transfer alert.

1. Point all 7 terminals at **demo** accounts first (same leverage/symbols). Fund the demo to the
   shakedown shape.
2. Let it run through at least one full op on a couple of legs (BTC trades often; gold less so).
3. Verify: heartbeats (green dots), an OPEN badge during an op, a new R-stream point on close, the
   pending-transfer panel + Telegram alert on a win, and that `/halt` actually stops new ops.
4. Fix any WebRequest errors (the Experts log prints them — usually a missing whitelist entry).

---

## 9. Funding & the capital model

**Objective:** fund the accounts to the King's target shape.

**Deliverables:** Main holds the reserve; each ops-account holds `W_i · F_total · T` (the dashboard
"target" matches the actual balance, bars full).

- **Phase D — $100 shakedown (hot, mechanics test):** deposit ~$100 to Main. With a hot `f_total`
  (e.g. 0.25), targets are tiny (cents–dollars); the point is to watch **mechanics**, not P&L. Move
  cash Main→ops per the dashboard targets / Telegram instructions.
- The orchestrator never moves money — it *instructs*; you execute the internal transfer in the
  Exness Personal Area and the next balance heartbeat confirms it (logged to the transfers audit).
- Transfer lag is safe: an un-topped account just opens a smaller op.

---

## 10. Go-live phases (with kill-criteria armed)

**Objective:** scale only as mechanics prove out; never on P&L.

**Deliverables:** a clean Phase-D shakedown log, then a funded $1000 run.

- **Phase D — $100 @ hot f, breaker 35%.** Exit = mechanics correct over the run (EAs size/floor
  right, open-op lock holds, transfers fire & confirm, dashboard/alerts track, no unexplained
  behaviour). **P&L is not the criterion.**
- **Phase E — $1000 @ f≈1% (f_total≈0.054), breaker 80%, add a BTC weekend-gap cash buffer.**
- **Kill-triggers (any → de-risk/halt, don't rationalize — `SYSTEM_PLAN.md §12`):** realized DD
  > ~30%; monster frequency < ~1/quarter; any rolling 3-month live segment < ~−5R; aggressive-leg
  live-vs-tester divergence > ~15%. **Expectation = ~12× over ~2.4yr, not the headline.**

---

## 11. Operations

**Objective:** keep it alive and auditable.

**Deliverables:** watchdog restarts, daily DB backup, a reconciliation habit.

- **Watchdog** restarts crashed terminals/services (Scheduled Task / systemd / a small checker).
- **Backup** `orchestrator/state.db` daily (it holds the immutable op + transfer audit).
- **Weekly reconcile:** live R-stream vs the backtest expectation on the dashboard; check the
  kill-triggers; confirm every Telegram transfer instruction was executed + confirmed.
- **Reboots:** auto-login terminals + auto-start services mean a reboot self-heals; verify dots go
  green afterward.

---

## 12. Cost summary

| item | ~cost/mo |
|---|---|
| Windows VPS (8GB, Contabo/Hostinger KVM) | $15–25 |
| Software (orchestrator, bot, MT5) | $0 |
| Telegram | $0 |
| **Total** | **~$15–25/mo** |

Capital (your money at risk) is separate: $100 (Phase D) → $1000 (Phase E). Frictions
(spread/swap/commission) come out of P&L, already modeled in the tester-true research.
