# VPS Claude-Code task brief

For the Claude Code instance **running on the Windows VPS**. Point it here. It complements
`DEPLOYMENT_GUIDE.md` (the human runbook) — this lists what the *agent* can do vs what needs a
human (GUI / broker / secrets). Secret inputs live in `terminals.xlsx` + `vps.txt` (root,
gitignored) — **read them locally, never commit, never paste secrets into chat or git.**

## Legend
✅ Claude Code can do it fully · 🟡 partial (some GUI step remains) · 👤 human-only (GUI/broker)

---

## §4 Repo + brain health — ✅ FULLY
**Objective:** brain verified on the VPS. **Deliverable:** 10/10 + 12/12 green here.
```
cd C:\ck\fx_tools && git pull
python -m venv .venv && .venv\Scripts\activate
pip install -r orchestrator\requirements.txt
python -m orchestrator.test_capital   # 10/10
python -m orchestrator.test_app        # 12/12
```

## §5 MT5 terminals — 🟡 PARTIAL
**Objective:** 7 portable terminals, EA+preset attached, telemetry on. **Deliverable:** 7 terminals
trading-ready, each printing `[CrossKing:<leg>] init`.
- ✅ Agent: create `C:\ck\mt5\T1..T7\` portable dirs; deploy `CrossKing_EA.ex5` + the matching
  `PD3_*.set` into each `MQL5\Experts\` and `MQL5\Presets\`; generate a per-terminal **startup
  config ini** with a `[StartUp]` section (`Expert=CrossKing_EA`, `Symbol=`, `Period=H1`,
  `ExpertParameters=PD3_X.set`) and launch each with `terminal64.exe /portable /config:startup.ini`;
  generate the launch + auto-start scripts. Read the leg→account map from `terminals.xlsx`.
- 🟡 Agent should TRY to template the **WebRequest URL whitelist** (stored in the terminal's
  `config\*.ini` / common config) and **auto-login** (if the terminal config format on this build
  supports stored creds) — inspect a terminal that's been logged-in-once to learn the format.
- 👤 If the build won't accept scripted login: the human does the **one-time GUI login** per
  terminal (Exness creds from `terminals.xlsx`) + ticks **Allow WebRequest** for the orchestrator
  URL + enables Algo Trading. After that, auto-login persists across reboots.

## §6 Orchestrator service — ✅ FULLY
**Objective:** brain+dashboard 24/7, auto-restart. **Deliverable:** `http://localhost:8800/` live;
survives reboot.
- ✅ Set `f_total` (shakedown hot e.g. 0.25 / live ~0.054), `breaker_dd` (0.35 / 0.80), `min_transfer`
  in `config.py`; confirm leg ids == `InpLegName`s and weights == `PD3_KING_manifest.md`.
- ✅ Run `uvicorn orchestrator.app:app --host 0.0.0.0 --port 8800`; wrap as a **Scheduled Task**
  (run at boot, restart on failure) or NSSM service. Verify `/status` returns and dots go green.
- **CENT ACCOUNT:** numbers are in cents (×100 USD). Either leave native or add a display ÷100 toggle.

## §7 Telegram bot — ✅ (token is 👤)
**Objective:** alerts + control. **Deliverable:** `/status` replies in the chat.
- 👤 Human pastes `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` (from BotFather) into `.env` (gitignored).
- ✅ Agent loads `.env`, runs `python -m orchestrator.bot`, wraps as a second auto-start service,
  and tests `/status //halt //resume`.

## §8 Live round-trip smoke (DEMO first) — ✅ great fit for the agent
**Objective:** prove EA→orchestrator→dashboard→Telegram end-to-end. **Deliverable:** an op shows
OPEN on the dashboard, an R-stream point on close, a transfer alert on a win.
- ✅ Agent: tail each terminal's `MQL5\Logs\` + `Experts` log, parse for `WebRequest ... failed`
  (→ usually a missing whitelist entry, fix §5), poll `/status`, confirm heartbeats/op/close/alert.
  This debug loop is exactly what the agent is good at.
- 👤 Human: point terminals at **demo** accounts first; fund the demo to the shakedown shape.

## §11 Ops — ✅ FULLY
**Objective:** keep it alive + auditable. **Deliverables:** watchdog, daily DB backup, reconcile script.
- ✅ Write a watchdog (restart crashed terminals/uvicorn/bot), a daily `state.db` backup task, and a
  reconciliation script (live R-stream vs backtest; verify every transfer instruction executed).

---

## Human-only (the agent cannot do these)
- 👤 §1 create the 7 Exness accounts (broker GUI), set 1:2000 / USD-cent, record creds → `terminals.xlsx`.
- 👤 MT5 GUI **install**, one-time **login**, **Allow WebRequest** checkbox, **Algo Trading** toggle.
- 👤 §9 execute the **internal cash transfers** in the Exness Personal Area (the orchestrator only
  instructs via Telegram; you move the money). Confirm via the next balance heartbeat.

## Suggested order for the VPS agent
§4 (verify) → §6 (orchestrator + dashboard up) → §7 (bot, once token in `.env`) → §5 (deploy EA +
startup inis; human does GUI login/whitelist) → §8 (demo smoke + debug) → §11 (watchdog/backup).
Get the orchestrator+dashboard live FIRST so the EA work is observable as you go.
