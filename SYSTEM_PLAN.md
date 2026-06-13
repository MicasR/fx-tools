# Cross-Instrument King Portfolio — Live Trading **System** Plan

**Project:** FX Tools — live deployment of the validated cross-instrument king portfolio
**Status:** Planning (the demo-testing / deployment arc)
**Author:** Dercio Micas
**Created:** 2026-06-13

> This is **not a strategy, it is a system.** The strategy research is finished and validated
> in-sample (`cross_kings.py`: GOLD king + BTC king, 1R each, 128.8× @24%DD). This document
> plans everything required to *run it for real money*: the execution EAs, the capital/sizing
> engine, the orchestrator, the control center, the infrastructure, and the risk/ops layer —
> from building & validating the EAs all the way to the live $100 shakedown and scaling to $1000+.

---

## 0. Decisions locked (this session, 2026-06-13)

| # | Decision |
|---|----------|
| Broker | **Exness** (c-suffix symbols; many sub-accounts under one profile, **instant free internal transfers**, free VPS). |
| Topology | **7 real accounts**: 1 **Main** (capital hub, no trading) + **6 ops-accounts** (3 gold + 3 BTC), one leg-EA each. |
| Capital model | **Pooled-geometric via cash sweeps.** Each ops-account funded to its **1R target = weight × f × T**; rebalanced **only while flat**. |
| Sizing engine | **EA-dumb / orchestrator-brain.** Each EA risks its **whole account balance** per op (synthetic SL at the margin-line). All weighting/pooling lives in the cash the orchestrator places. |
| Transfers | **Semi-manual via Telegram.** Orchestrator computes → Telegram "move $X from Y to Z" → user executes (instant) → orchestrator confirms via balance delta. No portal scraping (yet). |
| First live | **No demo. Real $100 first** ($10 gold + $10 BTC ⇒ **f = 10%**, a deliberately hot *shakedown*). Judge on **mechanics, not P&L.** When the rules check out, deploy the remaining $900 at **f ≈ 1%**. |
| Leverage | **1:2000** on every ops-account (the backtest's add-cap math assumes it). |
| Circuit breaker | Halt new ops if **T draws down > threshold** from peak: **35%** for the $100 run, **80%** at $1000+. |
| BTC gaps | Accepted for the shakedown (the −1R floor is *soft* on crypto gaps; NBP caps the account at 0). Add a cash buffer above 1R at $1000+. |
| Stack | **One EA binary + 6 `.set` presets**; Python (FastAPI + SQLite) orchestrator + dashboard + `python-telegram-bot`, all on **one Windows VPS** with the 7 terminals. |
| Kill switch | **"Stop opening new ops"** (never flatten mid-op — flattening breaks the −1R model). Triggerable via Telegram. |

---

## 1. Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │                ONE WINDOWS VPS                │
                          │                                              │
  ┌─────────┐  WebRequest │  ┌────────────┐   ┌────────────┐            │
  │ MT5 #1  │────telemetry┼─▶│            │   │            │            │
  │ gold-1  │ GoldGeo17   │  │ ORCHESTR.  │──▶│  SQLite DB │            │
  ├─────────┤             │  │ (FastAPI)  │   └────────────┘            │
  │ MT5 #2  │────────────▶│  │            │         │                   │
  │ gold-2  │ GoldS210    │  │ • aggregate│         ▼                   │
  ├─────────┤             │  │   T, targets  ┌────────────┐             │
  │ MT5 #3  │────────────▶│  │ • rebalance│  │ WEB CONTROL│◀── browser  │
  │ gold-3  │ GoldShield  │  │   engine   │  │  CENTER    │             │
  ├─────────┤             │  │ • breaker  │  └────────────┘             │
  │ MT5 #4  │────────────▶│  │ • health   │         │                   │
  │ btc-1   │ BtcGF       │  └─────┬──────┘         │                   │
  ├─────────┤             │        │ Telegram Bot API                   │
  │ MT5 #5  │────────────▶│        ▼                                    │
  │ btc-2   │ BtcPG       │   ┌──────────┐  "move $X from Y→Z" ┌──────┐ │
  ├─────────┤             │   │ TELEGRAM │────────────────────▶│ USER │ │
  │ MT5 #6  │────────────▶│   │   BOT    │  alerts / commands  └──────┘ │
  │ btc-3   │ BtcShield   │   └──────────┘                       │      │
  ├─────────┤             │                                user executes │
  │ MT5 #7  │────────────▶│   (Main = reporter EA, balance only)  in Exness PA
  │ Main    │ Reporter    │                                              │
  └─────────┘             └──────────────────────────────────────────────┘
```

**Key property — graceful degradation:** the EAs are autonomous. They size off their own
balance and exit on their own synthetic SL/TP. If the orchestrator (or the whole control
plane) dies, **trading continues safely** — only rebalancing and monitoring pause. The
orchestrator is never in the trade-execution path.

---

## 2. Capital model (the math, formalized)

Let `T` = total equity across all 7 accounts. `f` = risk fraction per king. Per-king 1R = `f·T`.

Target balance for each ops-account = its **king-weight × f × T**:

| Account | Weight | Target balance |
|---|---|---|
| gold-1 GoldGeo17 | 0.500 | 0.500·f·T |
| gold-2 GoldS210 | 0.375 | 0.375·f·T |
| gold-3 GoldShield | 0.125 | 0.125·f·T |
| btc-1 BtcGF | 0.552 | 0.552·f·T |
| btc-2 BtcPG | 0.248 | 0.248·f·T |
| btc-3 BtcShield | 0.200 | 0.200·f·T |
| Main | — | reserve = `T − Σ targets` |

Worked example, **$100 @ f=10%**: gold 1R = $10 → gold-1 $5.00 / gold-2 $3.75 / gold-3 $1.25;
BTC 1R = $10 → btc-1 $5.52 / btc-2 $2.48 / btc-3 $2.00; Main reserve ≈ $80.

**Why funding an account with exactly its 1R is faithful:** the backtest's broker free-margin
check caps each add at `equity/margin` using **E0 (the op's 1R) as the account capital**
(`pyramid_engine._size_add` / the `eq/MPL − Lb` cap). So an ops-account holding exactly 1R,
with the EA risking its whole balance, reproduces the backtest's margin/add behaviour to the
decimal. The −1R floor = equity-0 = the synthetic margin-line SL.

**Rebalance rule (event-driven, lock-respecting):** *whenever an account is **flat**, true it
up to its current target.*
- Lost (balance < target) → Main → account (top-up).
- Won (balance > target) → account → Main (sweep); Main then redistributes by topping up other
  flat accounts to their (now larger, since T grew) targets.
- **Never touch an account with an open op.** A win's profit parks in Main until the target
  accounts close their ops and become flat. Targets are recomputed off live T continuously, so
  growth compounds across legs (the decorrelation lift) without ever moving cash mid-op.
- Transfer lag is safe: an EA always sizes off its **actual** current balance, so an
  un-topped-up account simply opens a smaller-than-target op (never an oversized one). The
  orchestrator flags the pending transfer until confirmed.

---

## 3. Execution layer — the leg EA

**One EA binary, six `.set` presets** (see the table in the conversation / §1). Built as a
**faithful MQL5 port of `conc_engine.run_tf_conc` (max_conc=1) + `pyramid_engine` primitives**
— NOT a reuse of `VolumeSpikeBreakOut_Book_EA` (that's the older `confBtrail` model: broker-SL
pyramiding, risk-% per add, shared chandelier — a different management core).

Reusable from the existing Book EA: the **detection block** (V-pattern volume-threshold,
`TriggerFired`/`SourceLineAt`/`VolMA`/`VolStd`), `CTrade` patterns, and the lot/margin helpers.

### Faithful port checklist (each item must match the Python engine)
1. **Entry** — H1 V-pattern volume-threshold breakout: threshold = MA(20)+2.0·popStdDev(20) of
   tick volume; V = `s[i-2]>s[i-1] && s[i]>s[i-1] && (s[i]-s[i-1])/|s[i-1]| ≥ 0.02`; then a
   break of the trigger bar's high/low within 4 bars, entry at the break level, structural SL =
   opposite extreme, R = bar range. **Read H1 bars regardless of the chart timeframe.**
2. **Base sizing** — `lot0 = lot_to_pin(entry, SL)` so equity-0 (liquidation) sits at the
   structural SL ⇒ a full-stop loss = −1R = the whole account. Cap by free margin (`E0/MPL`).
3. **Stacking** (stack=true legs) — on a `SMA(smaP)` close-bounce (wrong-side then back),
   **gated** (close beyond last add AND op favorable ≥ `half`=0.5·R), add a lot per sizing:
   - **ProgGeo**: `base · mult · step^k`.
   - **GeoFloor**: `max(geometric ramp, lot_to_pin to the SLOW SMA(slowP=210) anchor)`.
   - Cap each add by free margin (`eq/MPL − Lb`).
4. **Margin-line synthetic SL** — recompute `margin_line(book)` after every add; write it to all
   positions' broker SL each bar (the equity-0 / −1R floor, made real).
5. **Exit** — `TP = entry + d·tp_R·R` (gold legs, BTC pg), OR a `trail_R`=2.5 chandelier
   `stop = max(margin_line, ext − d·2.5·R)` (BTC gf, tp_R=0). Shields: single position,
   structural SL, fixed TP, no adds.
6. **One op at a time** — a new breakout while in an op is **dropped** (max_conc=1).
7. **Leverage 1:2000** assumed by the add-cap; set the account accordingly.

### Telemetry the EA pushes (WebRequest → orchestrator)
- Heartbeat (timestamp, symbol, EA version) — for health/liveness.
- Account balance + equity; flat-or-open state.
- Open op: direction, base entry, R, stack depth, total lots, current margin-line SL, floating R.
- **On op close**: realized R, #positions, exit reason (SL/TP/TR), entry/exit time — this is the
  **live R-stream** the dashboard compares to the backtest.

---

## 4. Validation gate — Strategy-Tester port fidelity (offline, not "demo")

Before any live order: each preset run in the **MT5 Strategy Tester** over the same window as
the Python backtest must reproduce that leg's Python R-stream.

- Produce the **expected per-leg R-stream** from the engine (a small `shadow_streams.py` that
  dumps each leg's ops: entry/exit time, R, #pos, reason).
- Compare leg totR / win% / maxDD / 6-segment fingerprint, and ideally op-by-op R within a
  tolerance (broker spread/fill differences will cause small drift; large divergence = port bug).
- **Go/no-go:** all 6 presets reproduce their leg within tolerance ⇒ the port is trustworthy
  for real money. This is unit-testing the port against known-good output — it needs no account
  and is independent of the "no demo" decision.

Also unit/integration-test the **orchestrator rebalance math offline**: feed it synthetic EA
telemetry (sequences of wins/losses across legs) and assert the transfer instructions and
target balances are correct, the open-op lock holds, and the circuit breaker fires at threshold.

---

## 5. Orchestrator — capital + control brain (Python / FastAPI)

- **Ingest**: receive EA telemetry; keep latest per-account state in SQLite + in-memory.
- **Aggregate**: `T = Σ equities`; recompute targets = weight·f·T continuously.
- **Rebalance engine**: on each account-flat event, compute the delta vs target; if |delta| >
  min-transfer, emit a transfer instruction. Respect the open-op lock. Hold swept profit in Main
  until target accounts are flat.
- **Transfer workflow**: instruction → Telegram → user executes → orchestrator confirms via the
  next balance delta → logs to an audit table (every transfer, with before/after balances).
- **Circuit breaker**: track peak T; if drawdown > threshold (35% / 80%), command all EAs
  "no new ops" + Telegram alert. Resume via Telegram command.
- **Config (single source of truth)**: `f`, weights, breaker threshold, account map,
  min-transfer size. Versioned; not in git if it holds credentials.
- **Health/watchdog**: missing heartbeat (N minutes) ⇒ alert (terminal/VPS down).

EA ← orchestrator control: a lightweight "no new ops" flag the EA polls (file the EA reads, or a
WebRequest response). Trade execution never depends on the orchestrator being up.

---

## 6. Observability — the web control center

- **Backend**: FastAPI ingest + query; SQLite for state, telemetry history, transfer/op audit.
- **Dashboard** (web): 
  - System: T, equity curve, **drawdown vs peak** (with the breaker line), reserve in Main.
  - Per-account cards: balance vs target, flat/open, stack depth, open R, last op R, health dot.
  - **Pending transfers** panel (what Telegram has asked for, confirmed/unconfirmed).
  - **Live R-stream vs backtest**: the forward-test chart — cumulative live R per leg and
    combined, overlaid on the backtest expectation. This is how we detect the out-of-sample
    decorrelation holding (or not).
  - Event log: ops opened/closed, transfers, alerts, breaker trips.
- **Telegram bot**: alerts (transfer needed, EA down, DD breach, breaker trip) + commands
  (`/status`, `/halt`, `/resume`, `/kill`).

---

## 7. Infrastructure

- **One Windows VPS** (~4 vCPU / 8 GB). 7 portable MT5 terminals, each own data dir, auto-login,
  the right EA+preset on the right chart (XAU M15 ×3, BTC H1 ×3, Main reporter ×1).
- WebRequest URL whitelist (the local orchestrator endpoint) in each terminal.
- Orchestrator + dashboard + bot run as auto-start services. **Watchdog** restarts crashed
  terminals/services on a schedule.
- Time zone aligned to broker server time (detection is closed-bar / server-time based).
- **Secrets** (account logins, Telegram token) outside git (env / encrypted config).
- **Cost**: see §11 (≈ $20–50/mo all-in; nothing is spent until go-live, Phase D).

---

## 8. Risk & ops

- **−1R soft floor on gaps** (esp. BTC weekends): a gap *through* the synthetic SL loses >1R;
  NBP caps the account at 0. Accepted for the $100 shakedown; add a BTC cash buffer at $1000+.
- **10% is hot by design** on the shakedown — large drawdown or blow-up ≠ rules failed.
- **Circuit breaker + kill switch** as above; kill = stop-new-ops, never flatten.
- **Audit everything**: every op (with R) and every transfer logged immutably for reconciliation
  and live-vs-backtest analysis.
- **Single-regime / in-sample reality**: the live $100 run **is** the first true out-of-sample
  forward test. The thing to watch is whether the gold/BTC opposite-half decorrelation (the
  source of the +231%) persists forward.

---

## 9. Phased rollout

| Phase | Goal | Exit criteria (go/no-go) |
|---|---|---|
| **A. Build EA** | One EA binary + 6 `.set` presets; faithful port; telemetry. | Compiles; manual smoke test in tester runs ops. |
| **B. Port validation** | Strategy-Tester each preset vs Python R-stream; orchestrator math unit-tested offline. | All 6 legs reproduce within tolerance; rebalance/breaker tests pass. |
| **C. System build** | Orchestrator + dashboard + Telegram + VPS + 7 terminals provisioned. | End-to-end on synthetic telemetry: targets, transfers, alerts, dashboard all correct. |
| **D. Live $100 shakedown** | Full system, real $100 (f=10%, breaker 35%). The dress rehearsal, with real (tiny) money. | **Mechanics correct** over the run: EAs size/floor right, open-op lock holds, transfers fire & confirm, dashboard tracks, no unexplained behaviour. (P&L is not the criterion.) |
| **E. Scale to $1000** | f→~1%, fund to $1000, breaker→80%, add BTC gap buffer; optionally automate transfers (portal). | Shakedown mechanics clean; live-vs-backtest not pathologically diverged. |

---

## 10. First concrete steps (next work)

1. **Build the leg EA** (`ExpertAdvisors/CrossKing_EA/`): port the engine, expose the preset
   inputs, wire telemetry. Reuse the Book EA's detection + helpers.
2. **`backtest/shadow_streams.py`**: dump each leg's expected op R-stream for the validation gate.
3. Author the 6 `.set` presets.
4. Then Phase B validation, then the system build.

---

## 11. Cost estimate

Cheap to run — the system is essentially **one VPS**; the whole software stack is free.
Separate *cost* (cash consumed) from *capital* (your money, at risk) from *frictions* (from P&L).

**Recurring infrastructure (the only real cash cost):**

| Item | Cost |
|---|---|
| Windows VPS (8 GB, runs 7 terminals + Python stack) | **$20–50/mo** (Contabo-class ~$20–25; forex-optimized ~$40–50) |
| MT5 ×7, Exness ×7 + transfers, Telegram bot, FastAPI/SQLite/dashboard | $0 |
| Remote dashboard access (Tailscale free tier) | $0 |

**≈ $20–50/month (~$240–600/year).** Latency is non-critical (pre-placed stop entries, bar-close
management) so a generic cheap Windows VPS works. Exness free VPS won't fit (one instance, needs
~$500+ equity). **Nothing is spent until go-live — Phases A–C build & validate locally for $0.**

**Capital (yours, at risk, not a cost):** $100 shakedown → $1000 → big.

**Frictions (from P&L, partly modeled):** spread/commission/slippage/swaps. Backtest already nets
a stress cost ($0.40/op gold, $18/op BTC). Watch **BTC swaps** on multi-day trailed ops and
**slippage**. At $100, frictions sting disproportionately → another reason to judge on mechanics.

**Your time:** manual Telegram transfers; mitigate with a **min-transfer threshold** (no pings for
tiny moves), automate the PA later.

**Build cost:** $0 software (all free/open-source), no paid APIs, no data purchases.

**Bottom line:** ~$20–50/mo to run, $0 to build/validate, plus chosen trading capital.

---

## Open / future (parked, do not start unprompted)
- Full transfer automation (Exness Personal Area scripting) if semi-manual gets tedious.
- The parked research arcs: *why* the breakout works on gold/BTC but not silver/FX; a
  cross-symbol correlation screen for a 3rd uncorrelated stream.
