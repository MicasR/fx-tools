# Engine Architectural Review — CrossKing live system

_2026-06-22. Scope: the telemetry + capital pipeline (EA ⇄ orchestrator ⇄ dashboard/Telegram ⇄
human transfers). Written after a shakedown session where "I made a transfer and the dashboard
didn't update" exposed a cluster of transport bugs. Grounded in the as-built code, not the plan._

> **UPDATE 2026-06-22 (later): F1 + F2 RESOLVED.** Root cause of the dead telemetry was found to be
> MT5/WinINet failing to retry POST on a stale keep-alive connection (`err=5203`), while GET self-heals.
> Telemetry/op_close/control switched to **GET + cache-buster**; heartbeat moved to **`OnTimer`** (F1);
> all `WebRequest` outcomes now logged (F2). Verified live: all 7 legs report every 30s, balances
> correct, transfers reconcile. Remaining items below (durability F7, op_close idempotency F8, setup
> automation F3) are still open.

## 1. System map (as-built)

```
 7 MT5 terminals (6 ops = USC cent accts, 1 Main = USD)
   each: CrossKing_EA, InpLegName = leg id
        │  POST /telemetry  (balance/equity/op-state)   ← OnTick heartbeat, 30s throttle
        │  GET  /control/<leg> (halt flag, fail-open)    ← same OnTick heartbeat
        │  POST /op_close   (realized R)                 ← on op close
        ▼
 Orchestrator (FastAPI, :8800)
   in-memory ACCT  +  SQLite (accounts/telemetry/ops/transfers/events)
   brain: T=Σequity → targets W·f·T → breaker(DD) → plan_transfers (event-driven, flat legs only)
        │  /status (dashboard JSON)        │  /halt /resume
        ▼                                   ▼
 Dashboard (static HTML, 3s poll)     Telegram bot (5s poll: alerts + commands)
                                            │  "move $X Y→Z"
                                            ▼
                                      HUMAN executes transfer in Exness (instant, free)
                                            │  next balance heartbeat
                                            ▼
                                      orchestrator reconciles → confirms pending transfer
```

## 2. What is sound — keep it

- **The brain (`capital.py`).** Pure, deterministic, unit-tested (10/10). Single-budget model
  `target_i = W_i·f·T`, Main = reserve, event-driven rebalance on flat legs only, open-op lock.
  No reason to touch the math.
- **Audit-first SQLite.** Append-only telemetry/ops/transfers/events. Right call for a money system.
- **Decoupled Telegram bot.** Pure HTTP client of `/status` + `/halt|/resume`. Clean boundary.
- **Fail-open control.** EA keeps trading if the orchestrator is down; control is advisory. Correct
  safety posture — the orchestrator is a supervisor, never in the trade-execution path.
- **Manual-transfer-with-reconcile.** Exness has no public transfer API, so human-in-the-loop is
  forced; the design (instruct → execute → confirm by balance delta) is the right shape. It was
  just never wired (see F5).

## 3. Failure-mode analysis — where the fragility is

**It is entirely in the transport layer, not the brain.** Every painful bug this session lived here.

- **F1 — Tick-driven heartbeat (ROOT CAUSE).** `Heartbeat()` runs inside `OnTick()`, so balance
  reporting only happens when the *symbol ticks*. Evidence: every leg's most recent telemetry was
  ~500s old with 2–4 rows _ever_, despite `InpHeartbeatSec=30`. Consequences cascade:
  - balances lag minutes / stall when a market is quiet or closed (gold) → "transfer didn't update";
  - **T is computed off stale equity** → the circuit breaker can act on stale data;
  - the 5s synchronous `WebRequest` blocks the *trading* thread (OnTick) on every failure.
- **F2 — Silent transport failures.** `PollControl` ignores all WebRequest errors; `PushJson` logs
  only `code == -1`. A bad whitelist (`err=4014`) or a rejected body (the 422 truncation bug) looked
  like "alive but quiet." Hours were lost to invisible failures. There is no per-leg telemetry-age
  or last-error surfaced anywhere.
- **F3 — Manual, 7× setup surface.** Per-terminal GUI: login + "Allow WebRequest" + Algo + preset
  load + EA reload. One wrong character → silent dead leg. Nothing is templated/scripted.
- **F4 — Liveness vs data-freshness (fixed this session, note the lesson).** `/control` updating
  `last_hb` made the `warm` guard treat a live-but-data-stale leg as fresh. Now split into
  `last_ctrl` (proof-of-life) and `last_hb` (real balance). The lesson: "alive" ≠ "has fresh data";
  the breaker/transfer math must key on data freshness only.
- **F5 — Reconciliation was missing (fixed this session).** `confirm_transfer()` existed but was
  never called — pending transfers never cleared and the dedup blocked re-emission. Now `_rebalance`
  confirms a pending transfer once its leg is back within `min_transfer` of target. Residual gaps:
  no before/after balance captured at confirm (audit), and no manual override for cases auto-match
  can't resolve (partial fills, multi-step moves).
- **F6 — Unit handling (fixed this session).** Cent (USC) legs were summed with USD Main (T=1050 vs
  60). Now normalized at ingest via `Config.to_usd`. Residual: pre-fix DB rows are raw, so a
  warm-start can briefly show a wrong-unit balance until the first new telemetry.
- **F7 — Orchestrator lifecycle.** No durable boot-persistent service yet; the auto-restart wrapper
  doesn't survive a detached launch here, and we hit dual-instance / stale-log confusion. Single
  process, no health endpoint beyond `/status`.
- **F8 — `op_close` is not idempotent.** Every POST appends an ops row; an EA retry would duplicate
  R-stream points. No dedup key (e.g. account+close_time).

## 4. Options & recommendations (per concern)

| Concern | Options | Recommendation |
|---|---|---|
| **Heartbeat cadence (F1)** | (a) keep OnTick; (b) `EventSetTimer(InpHeartbeatSec)` + `OnTimer()` for the heartbeat; (c) external balance poller | **(b).** Move the periodic heartbeat (SendState + PollControl) to `OnTimer`; keep op-open/close transitions + per-tick stop safety in `OnTick`. Reliable wall-clock reporting independent of ticks, and isolates the blocking WebRequest from the trade thread. Single highest-leverage change. |
| **Observability (F2)** | log all WebRequest outcomes; expose telemetry-age + last-error in `/status`; dashboard/bot surface it | Do all three. Make a dead leg loud within one heartbeat. |
| **Setup surface (F3)** | template WebRequest whitelist + stored login + startup `.ini`; or accept manual | Template what MT5 allows (startup config, whitelist file); script the EA+preset deploy (already done). Keep one-time GUI login if the build won't store creds. |
| **Reconciliation (F5)** | balance-delta auto-confirm (done); + capture before/after; + manual `/confirm` | Add before/after balances to the transfers row at confirm; add a Telegram `/confirm <id>` override. |
| **Lifecycle (F7)** | scheduled task (elevated); NSSM; container | Scheduled task at boot + restart-on-fail (the `install_services.ps1` path), run once elevated. Add a `/health` route. |
| **op_close idempotency (F8)** | dedup key | Unique (account, close_time) or an EA-supplied op id; ignore duplicates. |
| **Topology** | 7 terminals is the broker reality (1 acct/terminal) | Out of scope of the engine; note that each account multiplies operational surface. Main is reporter-only — fine as a tiny EA. |
| **Transfers** | manual (now); portal automation later (plan §E) | Stay manual + reconcile for shakedown. Revisit automation only after mechanics are boring. |

## 5. Do NOT change
`capital.py` math, the SQLite audit model, the decoupled bot, fail-open control, and the
manual-transfer-with-reconcile flow. These are correct and/or tested. Resist rewriting them.

## 6. Risk register before scaling to $1000 (plan phase E)
- **P0** Tick-driven heartbeat → stale T → breaker/transfers on stale data. (F1)
- **P0** Silent transport failures → operational blindness on a money system. (F2)
- **P1** No durable orchestrator service → restart gaps, dual-instance confusion. (F7)
- **P1** `op_close` duplication corrupts the live R-stream / reconciliation. (F8)
- **P1** Manual setup error → silent dead leg → missed rebalances. (F3)
- **P2** Warm-start unit hygiene; transfer audit completeness; breaker policy when a leg is dark.

## 7. Suggested remediation order (no code yet — for decision)
1. **P0 transport reliability:** OnTimer heartbeat + log every WebRequest outcome + expose
   per-leg telemetry-age/last-error in `/status` & dashboard. (EA recompile + redeploy to 7.)
2. **P0/P1 durability:** orchestrator as a boot service (elevated) + `/health`.
3. **P1 integrity:** `op_close` idempotency; transfer before/after audit + `/confirm` override.
4. **P1 setup:** template whitelist/login/startup to kill the `err=4014` class.
5. **P2:** warm-start unit stamp; breaker-on-partial-data policy; (later) transfer automation.

_Open question for the owner: should the breaker act on the legs it CAN see when one leg is dark
(fail-cautious) or refuse to compute (current `warm`=all-fresh, fail-blind)? This is a money-safety
policy call, not a code detail._
