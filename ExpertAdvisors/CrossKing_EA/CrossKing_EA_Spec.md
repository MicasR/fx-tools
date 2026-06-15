# CrossKing_EA — Specification

**One leg of the cross-instrument king portfolio.** A faithful MQL5 port of
`backtest/conc_engine.run_tf_conc` (`max_conc=1`) + `backtest/pyramid_engine`
sizing primitives. **One EA binary, six `.set` presets** (3 gold + 3 BTC). Part of
the live trading **system** (`SYSTEM_PLAN.md`, Phase A).

> Status: built & compiles clean (0 errors / 0 warnings). Phase B ran (Model 1) and
> found a **port bug** — the geometric add-ramp computed off the wrong base lot
> (`lots[0]` is newest-first), collapsing every gold stack to 0.01 (gold legs
> retained only 20–43% of the oracle). **Fixed** (latched `g_base_lot`/`g_add_count`,
> 2026-06-14); re-validation in progress. Full diagnosis: `backtest/FIDELITY_FINDINGS.md`.
> Spread/commission/swap were **ruled out** as the gap (≤0.06 R/op). Remaining residual
> (~the 21% even faithful BtcGF lost) = entry-set + bar-granularity, handled by
> FIDELITY_PLAN §3.2/§3.3.

---

## 1. Model — "EA-dumb / orchestrator-brain"

The EA risks its **whole account balance** on each operation. At op-open
`E0 = AccountBalance`; the base lot pins the broker **equity-0 (liquidation) line
onto the structural stop**, so a full stop-out loses `E0` = **−1R = the whole
account**. All portfolio weighting/pooling lives in *how much cash the orchestrator
funds each account with* — never in this EA. One EA per ops-account.

**Negative-balance protection (NBP) — losses are capped at −1R.** Because the account
*is* 1R, a liquidation that momentarily overshoots equity-0 is zeroed by the broker
(Exness NBP): the realized loss can never exceed the account = **−1R**. The Strategy
Tester, run on a large deposit with `InpFixedE0`, does **not** trigger NBP, so it
*reports* losses of −1.1..−2.0R; those are a tester artifact. **All tester accounting
must clamp each op `max(R, −1)`** to match live (`backtest/tester_truth.py`,
`ck_batch.ps1` → `nbpR`). This clamp also makes tester Model 1 ≡ Model 4.

Leverage **1:2000** on every account (the add free-margin cap assumes it).

**Graceful degradation:** the EA is autonomous — it sizes off its own balance and
exits on its own broker SL/TP/trail orders. If the orchestrator (or telemetry) is
down, trading continues safely; only monitoring/rebalancing pause.

---

## 2. The six presets (`presets/*.set`)

| Preset | Symbol | chart TF | mgmt TF | stack | sizing | smaP | slowP | mult | step | tp_R | trail_R | magic | king-wt |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **GoldGeo17**  | XAUUSDc | **H1** | M15 | yes | proggeo  | 7  | –   | 0.01  | 1.7 | 3.0  | –   | 20260601 | 0.500 |
| **GoldS210**   | XAUUSDc | **H1** | M15 | yes | geofloor | 5  | 210 | 0.015 | 1.7 | 3.0  | –   | 20260602 | 0.375 |
| **GoldShield** | XAUUSDc | **H1** | M15 | no  | –        | –  | –   | –     | –   | 2.0  | –   | 20260603 | 0.125 |
| **BtcGF**      | BTCUSDc | **H1** | H1  | yes | geofloor | 15 | 210 | 0.015 | 1.2 | 0.0  | 2.5 | 20260604 | 0.552 |
| **BtcPG**      | BTCUSDc | **H1** | H1  | yes | proggeo  | 15 | –   | 0.01  | 1.2 | 3.0  | –   | 20260605 | 0.248 |
| **BtcShield**  | BTCUSDc | **H1** | H1  | no  | –        | –  | –   | –     | –   | 1.25 | –   | 20260606 | 0.200 |

Entry detection is **identical across all six** (H1 V-pattern volume-threshold,
MA20 + 2.0·popStd, rise ≥ 2%, 4-bar breakout window), **always read from H1**
(`InpEntryTF`). **Chart every preset on H1** so entry is *native to the chart*
(matches live `CopyTickVolume(H1)`; no cross-TF reconstruction — FIDELITY_PLAN §3.2);
management (bounce/add/trail cadence + the bounce SMA) runs off **`InpMgmtTF`** (gold
**M15**, BTC **H1**). The king-weight is the orchestrator's capital allocation —
**not an EA input**.

Attach all six to an **H1 chart** of their symbol (XAUUSDc / BTCUSDc), one preset per
ops-account; the gold presets set `InpMgmtTF=M15`, the BTC presets `InpMgmtTF=H1`.

---

## 3. Mechanics (port mapping to `conc_engine.run_tf_conc`, `max_conc=1`)

### Entry — H1 V-pattern breakout (`EntryCadence`, on each closed H1 bar, flat only)
Detection block is **reused from `VolumeSpikeBreakOut_Book_EA`** (`TriggerFired` /
`ThresholdAt` / `VolMA` / `VolStd`), run on `InpEntryTF=H1`:
- threshold line `s = MA(20) + 2.0·popStdDev(20)` of H1 tick volume;
- V-pattern: `s[i-2] > s[i-1]` and `s[i] > s[i-1]` and `(s[i]−s[i-1])/|s[i-1]| ≥ 0.02`;
- on a trigger H1 bar (bar 1), arm an **OCO pair**: Buy Stop @ H1 high, Sell Stop @
  H1 low. First fill starts the op (sibling cancelled); **stale-cancel after 4 H1
  bars** (`iBarShift`, gap-immune). `R` = H1 trigger-bar range; `e0` = the filled
  level; structural SL = the opposite extreme. **No new op while one is open**
  (`max_conc=1`).

### Base size (`ArmStop`)
`lot0 = qfloor(E0 / (TR·R))`, ≥ broker min, capped by `qfloor(E0/MPL)` (must fit the
deposit) and broker max. This is exactly `lot_to_pin([], entry, entry−d·R) =
E0/(TR·R)`: one position of this size makes `margin_line = entry − d·R` = the
structural SL.

### Management (`ManagementCadence`, on each closed chart bar) — order matches the engine
1. **Running extreme** `ext` updated with the just-closed bar's high/low (for the trail).
2. **Favourable gate**: `fav = d·((H or L) − e0)/R`; once `fav ≥ InpHalf` (0.5), latch `ok`.
3. **Add trigger** (stack presets, `ok` only) — selected by **`InpAddTrigger`**
   (FIDELITY §3.6-REDUX, `RECHALLENGE_PLAN.md`):
   - **`ADD_SMA_BOUNCE`** (default): close goes **wrong side** of `SMA(smaP)` then
     **back**; on the back-cross, if **gated** (`close` beyond the ladder extreme), add.
   - **`ADD_POSCANDLE`**: add on **every confluent in-trend candle** (`close > open` long
     / `close < open` short) while gated — mirrors `conc_engine` `trig="poscandle"`.

   The add lot is then sized (gated case):
   - **proggeo**: `lot = max(0.01, qfloor(base·mult·step^k))`, where `base = g_base_lot`
     and `k = g_add_count` — **both latched op-state, NOT read from the live book**.
     `g_base_lot` = the base-position volume captured at op-open; `g_add_count` = the
     number of logical adds placed so far (= Python's `len(pos)-1`). *This is a fixed
     port bug:* MT5 lists positions newest-first, so the old `base = lots[0]` /
     `k = ArraySize(lots)-1` read the most-recent **0.01 add** as the base and the ramp
     collapsed to 0.01 on every gold stack (see `backtest/FIDELITY_FINDINGS.md`).
     `g_add_count` (logical adds) also stays correct when one add is split over
     `VOL_MAX` into several positions.
   - **geofloor**: `max(proggeo lot, lot_to_pin(book, close, S))`,
     `S = max(margin_line, anchor)` (long) / `min(...)` (short). The pin term reads
     the live book (order-independent sums) and was always correct. The **anchor** is
     chosen by **`InpLinePlace`**: `LINE_MARGIN` → `SMA(slowP)` (the original geofloor);
     `LINE_NBACK` → the structural low/high **`InpNBack`** candles back. (FIDELITY
     §3.6-REDUX archetype **G**.)
   - **pinprev** (`InpLinePlace = LINE_PINPREV`, SMA-bounce only): instead of the
     ramp/geofloor lot, pin the book's liquidation **exactly** to the **prior bounce
     extreme** (`g_prev_anc`) when price has pushed beyond it, else the current bounce
     extreme — `lot = lot_to_pin(book, close, S)` (no `max` with the geometric ramp),
     mirroring `conc_engine` `pin_add`. Uses the tracked `g_anc_b`/`g_prev_anc` state.
   - **`InpLineBuffer`** (R units, the **aggression dial**): the pin target `S` is floored so
     the liquidation line can never sit closer than `InpLineBuffer·R` to current price
     (`FloorAnchor`, mirrors `conc_engine` `floored_anchor`). `0` = aggressive (line may hug
     price → margin-maxed lot → frequent −1R blow-ups but monster upside); larger = conservative
     (caps the pin family). Applied to **both** geofloor and pinprev anchors. (FIDELITY
     §3.6-REDUX; sweeps the conservative/mild/aggressive bands.)
   - then the **free-margin cap** `lot ≤ qfloor(eq/MPL − openLots)`, `eq = E0 +
     floating`.
   - **per-order split** (`PlaceSplit`): the broker rejects any single order above
     `SYMBOL_VOLUME_MAX`, so a margin-capped add larger than the per-order ceiling
     (`min(VOL_MAX=200, broker max)`) is placed as **multiple positions**, e.g.
     `250 → 200 + 50` — the full desired volume goes on, each chunk its own position
     (all ≤ the per-position cap). The backtest *caps a single add at 200 and drops the
     rest*; the EA instead places the remainder, so they agree exactly whenever an add
     is ≤ 200 (the faithful/fixed-E0 regime — the cap only binds under runaway
     compounding). `LotToPin`/`MarginCap` therefore no longer clamp at `VOL_MAX`; that
     ceiling now lives solely in `PlaceSplit`.
4. **Re-sync** the shared stop/TP to the (possibly enlarged) book.

### Exit — broker orders written to every position (`ComputeStops` + `ApplyStopAll`)
- **SL** = `margin_line(book)` (equity-0). Trail presets: `max(margin_line, ext −
  d·trail_R·R)`, ratcheting.
- **TP** = `e0 + d·tp_R·R` (fixed; `0` = none → trail leg).
All positions carry the **same** SL/TP price → the whole book exits together at the
−1R floor or the target. Exits are **resting broker orders** (tick-granular,
survive EA/VPS hiccups), unlike the engine's bar-close check — a deliberate
robustness gain (see §6 drift).

`g_anc_b` (the wrong-side bounce extreme) and `g_prev_anc` are used **only** by
`LINE_PINPREV` (archetype G). The 6 *locked* legs use `LINE_MARGIN`/proggeo, where the
anchor is the slow SMA or ignored, so those legs are unaffected by this state — the
defaults (`ADD_SMA_BOUNCE`, `LINE_MARGIN`, `InpNBack=0`) reproduce the pre-redux EA
exactly (logic-preserving; confirmed by re-running the 3 presets in Phase 2).

---

## 4. Telemetry (`InpTelemetryURL`; auto-off in tester / when empty)
POSTs JSON to the orchestrator (Phase C). Whitelist the URL in the terminal
(Tools ▸ Options ▸ Expert Advisors ▸ Allow WebRequest). Events:
- **heartbeat** (throttled `InpHeartbeatSec`): leg, symbol, ver, ts, balance,
  equity, open?, depth.
- **op** (`open` / `add`): dir, e0, R, E0, depth, total lots, margin_line, equity.
- **op close**: realized R (from balance delta / E0), dir, E0, open/close ts, balance.

`WebRequest` is disabled in the Strategy Tester, so telemetry is a no-op there
(Phase B runs without it).

---

## 5. Phase B — validation procedure (the go/no-go gate)

For **each** preset:
1. Strategy Tester ▸ select `CrossKing_EA`, load the preset `.set`, set the symbol
   and **chart TF** per §2, model = **Every tick based on real ticks** (or 1-min OHLC
   as a first pass), leverage **1:2000**, deposit = a round 1R (e.g. $1000), window =
   the backtest window (gold from 2024-03-26, BTC from 2024-02-26).
2. Export the tester's deal/op list.
3. Compare against `backtest/out/shadow/<leg>.csv`: **leg totR / win% / maxDD /
   6-segment fingerprint**, and ideally **op-by-op** (entry/exit time, R, #positions,
   reason, add ladder) within tolerance.
4. **Go** if all six reproduce their leg within tolerance ⇒ the port is trustworthy.

Expected per-leg fingerprints (stress baked, from `shadow_streams.py`):

| leg | ops | totR | win% | maxDD | RF | segs |
|---|---|---|---|---|---|---|
| GoldGeo17  | 304 | 174.1 | 31.9 | 12.9 | 13.4 | 6/6 |
| GoldS210   | 360 | 259.5 | 23.6 | 24.0 | 10.8 | 6/6 |
| GoldShield | 344 |  82.7 | 42.2 | 11.2 |  7.4 | 6/6 |
| BtcGF      | 256 | 241.3 | 25.8 | 15.5 | 15.6 | 5/6 |
| BtcPG      | 250 |  82.3 | 33.2 | 13.0 |  6.3 | 5/6 |
| BtcShield  | 396 |  45.8 | 50.3 | 15.8 |  2.9 | 5/6 |

(Weighted blend reconciles to the documented king: GOLD 194.7R / BTC 162.8R.)

---

## 6. Known/expected drift (tester vs shadow — small, not bugs)
- **Spread/slippage**: base & adds are stop/market orders → fills differ from the
  engine's exact `entry`/`close` levels. The shadow stream already bakes a spread
  stress (a near-liquidation winner flipped to −1R); minor extra drift is expected.
- **Exit timing**: engine checks SL/TP at bar close; the EA uses resting broker
  orders (tick-granular). Same level, finer timing.
- **Margin model**: `TR`/`MPL` are read **live** from the symbol (overridable via
  `InpTROverride`/`InpMPLOverride` to pin them to the backtest's `SPECS` and isolate
  port-logic from broker-calibration drift). The add free-margin cap rarely binds at
  small balances; if a leg diverges, pin the overrides first.
- **Entry fill location**: the engine opens at the M15 bar aligned to the breakout
  H1 bar; the EA fills the resting stop at the actual intrabar cross — same price,
  near-same time.
- **H1 tick-volume reconstruction (gold)**: *addressed by §3.2* — all legs now chart
  on H1 so entry volume is native (`InpMgmtTF` carries M15 for gold's management). NB:
  under **Model 1** this changed nothing (the tester builds H1 from M1 regardless of
  chart TF — GoldGeo17 120.9→119.9, GoldS210 153.4→152.2, BTC identical), so the
  residual gold entry-set drift is **not** volume reconstruction but bar-granularity /
  fill-path. Charting on H1 still matters for **live** fidelity and the **Model-4**
  (real-tick) gate, where the intrabar path is exact.
- **Bar-granularity / fill-path (the live residual, all legs)**: the shadow oracle
  manages on M15/H1 *bars* and is blind to the intrabar path, so it is optimistic
  about which of SL/TP a bar hits and where late stacked adds land. This is the ~21%
  even faithful BtcGF loses and the bulk of GoldS210's leftover (one big op's late
  geofloor adds diverge once M15-bar path ≠ M1-tick path). Closing it needs **Model 4**
  on the tester side + an **M1-intrabar** Python engine (FIDELITY_PLAN §3.3).

**Large** divergence (totR, segment signs, win% off by a lot) = a port bug to fix,
not drift.

---

## 8. OnTester scoring + optimization frames (FIDELITY §3.6 king re-search)
The EA self-scores so the MT5 optimizer can re-search the management knobs on the
*trustworthy tester* (Path A), and ships each pass's data back for the "prom date"
team selector (`backtest/promdate.py`).
- **`OnTester()`** — NBP-clamps the op R-stream (`g_opR`, every op capped at −1R, the
  live accounting), returns the **robustness-weighted score `nbpR × (positive-6-seg/6)`**
  (criterion = Custom max). Rewards magnitude AND 6-segment robustness → surfaces durable
  kings, not 1-op pin-jackpots.
- **Weekly performance vector** — `g_week[CK_NWEEK]` accumulates NBP-clamped R into
  calendar weeks (epoch 2024-02-26) = the common clock to align different EAs by time
  (op index can't align across EAs). The "prom date" selector picks a TEAM whose members
  lift each other on bad weeks (time-decorrelation), generalizing shield/sword to N members.
- **Frame collection** — `OnTester` ships metrics + params + the weekly vector via
  `FrameAdd`; `OnTesterInit/Pass/Deinit` (terminal side) write every pass (local **and**
  MQL5-Cloud agents) to `MQL5/Files/ck_opt.csv`. Harness: `backtest/opt_run.py`,
  `pool_gen.py`/`pool_dense.py`, `promdate.py`. Runs on the **MetaQuotes** terminal
  (Exness account + cloud agents), NOT the EXNESS terminal.
- **`ck_opt.csv` columns** (`CK_NMETA`=26 leading + `w0..w129` weekly): `pass, score, nbpR,
  segpos, rf, oneop, ops, win, sizing, smaP, slowP, mult, step, tpR, trailR, half, mgmtTF,
  stack,` `extop1R, nmonster, addtrig, lineplace, nback, buffer,` **`segpos_ex3, h1R, h2R`**.
  `addtrig/lineplace/nback/buffer` identify the archetype + aggression tier;
  `extop1R`/`nmonster` are aggressive diagnostics.
- **CHAMPIONSHIP QUALIFICATION (user, 2026-06-15 — Option B: aggression ADMITTED, no oneop cap;
  the capped −1R downside makes high-compound aggression a bounded-cost asymmetric bet that must
  compete):** a candidate qualifies iff
  - **R1** `segpos ≥ 4` (≥4/6 segments positive);
  - **R2** `segpos_ex3 ≥ 4` — still ≥4/6 positive **after removing the 3 biggest winning ops**
    (low single-trade dependency; the principled replacement for the oneop cut);
  - **R3** `h1R > 0 AND h2R > 0` — positive in **both halves** of the window (anti-recency).
  Team-level backstop: `promdate.team_robustness` (growth@DD after dropping the biggest weeks +
  a bootstrap-over-weeks). See `RECHALLENGE_PLAN.md` + `backtest/RECHALLENGE_RESULTS.md`.

## 9. PROM-DATE 3-dancer team (LOCKED 2026-06-15 — replaces the oracle kings)
Tester-true (NBP, $1000, growth@24%DD = **57.5×**, PF 1.49, RF 25.1, 6/6, win 34%,
payoff 2.87). ~3× the old oracle cross-king's *real* number (19.2× on the same tester).
**Equal weight** (weights are a fine-tune; equal = anti-curve-fit). Presets `presets/PD_*.set`:
| preset | sym | mgmt | stack | sizing | smaP | slowP | step | tpR | trailR | role |
|---|---|---|---|---|---|---|---|---|---|---|
| PD_BtcGF | BTCUSDc | H1 | geofloor | 1 | 18 | 270 | 1.1 | 0 | 2.5 | trend-trail |
| PD_GoldShield | XAUUSDc | M15 | shield | 0 | 7 | 0 | — | 2.0 | 0 | gold smooth |
| PD_BtcPG | BTCUSDc | H1 | proggeo | 0 | 12 | 0 | 1.5 | 2.0 | 0 | BTC complement |
Caveat: back-loaded (S6 ≈ 53% of profit = recent BTC trend) — recency risk the live
shakedown will test. The six old `*.set` (oracle kings) are retired but kept for history.

## 7. Files
- `CrossKing_EA.mq5` — the EA (this spec's subject).
- `presets/*.set` — the six retired oracle-king presets + `PD_*.set` (the live 3-dancer team).
- `backtest/shadow_streams.py` → `backtest/out/shadow/<leg>.csv` — the validation oracle.
