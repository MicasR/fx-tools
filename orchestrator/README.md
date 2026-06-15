# CrossKing Orchestrator (deployment Phase C)

Capital/control brain + telemetry ingest + dashboard + Telegram bot for the **KING**
(GROWTH-6 weight-opt). EA-dumb / orchestrator-brain: **trade execution never depends on this
being up** — if it dies, the EAs keep trading; only rebalancing/monitoring pause.

## Components
| file | role | tested |
|---|---|---|
| `config.py` | single source of truth — KING PD3 weights, `F_total` budget, breaker, account map | — |
| `capital.py` | targets = W·F_total·T, event-driven rebalance (open-op lock, sweep/topup), breaker | `test_capital.py` 10/10 |
| `db.py` | SQLite: account state + immutable telemetry/ops/transfers/events audit | — |
| `app.py` | FastAPI: `/telemetry` `/op_close` `/control/{acct}` `/halt` `/resume` `/status` `/` (dashboard) | `test_app.py` 12/12 e2e |
| `static/dashboard.html` | web control center (polls `/status`) | — |
| `bot.py` | Telegram alerts + `/status /halt /resume /kill` (HTTP client of the orchestrator) | needs token |

## Run (local / VPS)
```
pip install -r orchestrator/requirements.txt
uvicorn orchestrator.app:app --host 0.0.0.0 --port 8800     # API + dashboard at http://VPS:8800/
# optional bot (set env first):  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
python -m orchestrator.bot
```
Tests (offline, no MT5): `python -m orchestrator.test_capital` && `python -m orchestrator.test_app`.

## Wire the EAs
- Each leg terminal: attach `CrossKing_EA` + its `PD3_*.set` (gold → XAUUSDc H1 chart / mgmt M15;
  BTC → BTCUSDc H1). Set **`InpTelemetryURL` = the orchestrator base** (e.g. `http://127.0.0.1:8800`).
- **Whitelist that URL**: Tools ▸ Options ▸ Expert Advisors ▸ Allow WebRequest.
- `account` = `InpLegName` (the PD3 name) and **must equal** the orchestrator account id in `config.py`.
- Main reporter terminal: an EA reporting `account="Main"` balance (or reuse the EA with telemetry only).

## Deploy on the HONEST numbers (SYSTEM_PLAN.md §12 falsifiability contract)
Expectation = **bootstrap median ≈ 12×**, NOT the $41k headline. Kill-triggers (de-risk, don't
rationalize): realized DD > ~30%; monster freq < ~1/qtr; any 3-mo live segment < ~−5R; aggressive-leg
live-vs-tester divergence > ~15%. Rollout: demo → $100 shakedown (mechanics) → $1000 @ f≈1%.

## Still needed for go-live (not code)
- Telegram bot token + chat id (env).
- Windows VPS + 7 portable MT5 terminals (6 ops + Main), auto-login, WebRequest whitelist, auto-start
  services + watchdog (§7).
- A live EA→orchestrator round-trip smoke (tester has WebRequest OFF, so this needs a live/demo chart).
