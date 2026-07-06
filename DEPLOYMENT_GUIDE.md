# TESTER-TRUE BOOK — Deployment Runbook (v2, 2026-07-06)

End-to-end setup to take the **tester-true 6-leg book** (fx_gym
`docs/TESTERTRUE_TEAM_SPEC.md` — supersedes the PD3 KING; never quote king/PROM3 numbers)
from repo → live. Model unchanged: **EA-dumb / orchestrator-brain**, 7 accounts
(6 ops + 1 Main), semi-manual cash sweeps. Work top-to-bottom; each section states its
**Objective** and the **Deliverables** you should have before moving on.

> **Golden rules**
> - Trading never depends on the orchestrator (control poll is fail-open). It's safe to start EAs before the brain.
> - **Deploy on the honest numbers: holdout 3.26×/5.6mo at full f is the OPTIMISTIC ceiling
>   (window read ~3×); the live shakedown is the real test. P&L is not the shakedown criterion.**
> - Demo smoke first, then the $100 cent shakedown (mechanics), then the $10k standard migration.
>   The falsifiability contract (spec §contract, 6 triggers) is armed from the first fill.
> - EA binary: the 2026-07-06 base-TOP-UP build — **cent-validation gate PASSED 6/6**
>   (e100 runs reproduce archives exactly; see `run_topup_validation.ps1`).
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

1. In your Exness Personal Area, create **7 MT5 CENT accounts** (the c-suffix symbol type the
   entire research stack runs on — `XAUUSDc`/`BTCUSDc`; 1 USD = 100 USc, cent lot = 0.01 std;
   spec §topology, cent-validation gate PASSED at these fundings):
   | terminal | account role | preset (GymTeam_EA) | magic | chart | funding |
   |---|---|---|---|---|---|
   | T1 | ops `XAU_H4_align` | XAU_H4_align.set | 20260713 | XAUUSDc **H4** | $33 = 3,300 USc |
   | T2 | ops `XAU_H4_engulf` | XAU_H4_engulf.set | 20260712 | XAUUSDc **H4** | $31 |
   | T3 | ops `BTC_wh_shield` | BTC_wh_shield.set | 20260707 | BTCUSDc **H1** | $16 |
   | T4 | ops `XAU_H4_keltner` | XAU_H4_keltner.set | 20260710 | XAUUSDc **H4** | $10 |
   | T5 | ops `XAU_H1_don55` | XAU_H1_don55.set | 20260714 | XAUUSDc **H1** | $6 |
   | T6 | ops `XAU_H1_keltner` | XAU_H1_keltner.set | 20260711 | XAUUSDc **H1** | $4 |
   | T7 | **Main** reporter | (telemetry only) | — | any (no trading) | rebalance hub |
2. Set every account to **1:2000 leverage** (MarginCap math assumes it) and account currency
   **USc (cent)**.
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

**Deliverables:** 7 terminals open, each logged into its account, the correct chart up, `GymTeam_EA`
attached with its leg `.set`, and a smiley (EA enabled). Main runs telemetry only.

1. Install MT5 **7 times as portable** (separate folders `C:\ck\mt5\T1 … T7`, each launched with
   the `/portable` flag so each keeps its own data dir + login).
2. In each terminal: **File ▸ Login to Trade Account** → that account's login/password/server.
   Enable **Tools ▸ Options ▸ auto-login** so it reconnects on reboot.
3. Deploy the EA: copy `ExpertAdvisors/GymTeam_EA/GymTeam_EA.ex5` (the top-up build, cent-gate
   PASSED) to each terminal's `MQL5\Experts\`, and the matching set file from
   `ExpertAdvisors/GymTeam_EA/presets/` to `MQL5\Presets\` (or load it from the chart's Inputs
   tab). *Or* junction the project folder (the research terminal uses exactly this pattern:
   `MQL5\Experts\GymTeam_EA -> <repo>\ExpertAdvisors\GymTeam_EA`).
4. **WebRequest whitelist** (each terminal): Tools ▸ Options ▸ Expert Advisors ▸ *Allow WebRequest
   for listed URL* → add the orchestrator base, e.g. `http://127.0.0.1:8800` (same box) or
   `http://<VPS-LAN-IP>:8800`.
5. Attach EA to the right chart per the §1 table — **chart TF must match the preset's
   `InpEntryTF`** (H4 for align/engulf/keltner-H4; H1 for shield/don55/keltner-H1). In the
   EA Inputs set **`InpTelemetryURL` = the orchestrator base url**. Leave `InpFixedE0=0` (live = whole
   account balance), `InpTROverride=0`, `InpMPLOverride=0` (read live). Enable **Algo Trading**.
   Do NOT copy anything from tester inis (their fixed E0 is validation-only).
6. Main (T7): attach the EA (or a reporter) with `InpLegName=Main` and `InpTelemetryURL` set; it
   reports balance only (it won't trade if you give it no trading preset / disable its entries).

> Verify each shows a 🙂 and prints the `[GymTeam:<leg>] init` line in the Experts log.

---

## 6. Orchestrator service

**Objective:** the brain + dashboard running 24/7 and auto-restarting.

**Deliverables:** `http://<VPS>:8800/` shows the control center; all 7 accounts appear (green dots)
within a heartbeat; it survives a reboot.

1. `orchestrator/config.py` already carries the tester-true roster (22/22 tests green,
   2026-07-06): weights 33/31/16/10/6/4, **`f_total=1.0`** (the spec's cent topology funds the
   whole $100 into ops; de-risk trigger #3 = drop f_total to 0.5, parking half in Main),
   **`breaker_dd=0.30`** (contract trigger #2), `min_transfer` $0.50 for the shakedown.
   Confirm the 6 leg account ids equal your `InpLegName`s (they are the spec leg names).
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

- **Phase D — $100 cent shakedown:** deposit $100 to Main, then move to ops per the §1 table
  ($33/$31/$16/$10/$6/$4 — the dashboard targets equal these at `f_total=1.0`, T=$100). Every
  leg sizes cleanly at cent granularity (validated: `tools/centval_compare.py` 6/6 PASS). The
  point is **mechanics**, not P&L.
- The orchestrator never moves money — it *instructs*; you execute the internal transfer in the
  Exness Personal Area and the next balance heartbeat confirms it (logged to the transfers audit).
- Transfer lag is safe: an un-topped account just opens a smaller op.

---

## 10. Go-live phases (with kill-criteria armed)

**Objective:** scale only as mechanics prove out; never on P&L.

**Deliverables:** a clean Phase-D shakedown log, then a funded $1000 run.

- **Phase D — $100 cent shakedown, breaker 30%.** Exit = mechanics correct over the run (fills,
  base top-up firing where pin > cap, open-op lock holds, transfers fire & confirm,
  dashboard/alerts track, live-vs-shadow < 15% per leg via `fx_gym tools/compare_shadow.py`).
  **P&L is not the criterion.**
- **Phase E — $10k standard-account migration** (same weights: $3.3k/$3.1k/$1.6k/$1k/$600/$400;
  per-order cap is 200 STD lots there — never binds). Same presets, same magics.
- **Kill-triggers (pre-committed, any → act, don't rationalize — spec §FALSIFIABILITY):**
  (1) leg rolling-quarter < −12R → bench it; (2) book DD > 30% → halt new ops; (3) positive-week
  rate < 40% over 13wk → de-risk 50%; (4) live-vs-shadow > 15% on a leg → halt, investigate;
  (5) realized cost/op > 2× tester → de-risk that leg; (6) 4 XAU legs negative in the same
  quarter → halt gold book, shield continues. **Quote holdout 3.26×/5.6mo as the optimistic
  ceiling, nothing higher.**

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
