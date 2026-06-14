# Python ↔ MQL5 Fidelity Plan — **THE priority** (2026-06-14)

> **Mandate (user, 2026-06-14):** the gap between our Python backtests and the MQL5
> Strategy-Tester results must be **< 5%**, and the fix must be **strategy- and
> instrument-agnostic**. Model whatever reality requires — **spread, swap,
> commission, slippage/latency** — pulling real data directly from MQL5. *We used
> Python results to make every research decision; if the tester is off, we can't
> trust what we have.* Only after the engine is trustworthy do we **re-challenge the
> kings** (strategies, sets, weights, expert combinations — intuition says the
> current ones are NOT optimal), verifying **6-segment robustness**, and **then**
> return to the deployment phase.

This **supersedes** the deployment arc (`SYSTEM_PLAN.md`) as the active priority.
The deployment work (EA, presets, orchestrator) is **paused** until fidelity is won.

---

## 0. Ground rules (the new contract)

1. **MQL5 real-tick tester = GROUND TRUTH.** Run **Model 4 ("every tick based on real
   ticks")**, real spread, swaps enabled, commission set, leverage 1:2000. Whatever
   it reports is reality.
2. **Python must MATCH reality, not the other way round.** Upgrade the Python engine
   to model real frictions until per-leg results agree with the tester within 5%.
   Python stays the *fast research engine*; the tester stays the *truth oracle*.
3. **< 5% gate, agnostic.** The agreement must hold on **per-leg totR** AND the
   **6-segment fingerprint** (sign + rough magnitude per segment), for **all 6 legs**
   and ideally an arbitrary new strategy/instrument — no per-leg fudge factors.
4. **No research decisions on the old (idealized) numbers.** The `cross_kings`/king
   results stand as *suspect* until reproduced on the corrected engine.

---

## 1. Phase B evidence (the gap we must close)

Tester (Model 1, 1:2000, fixed-E0 validation) vs the `out/shadow` oracle:

| leg | tester totR | oracle totR | retained | ops t/o | win% t/o |
|---|---|---|---|---|---|
| BtcGF (fat trail, wt .55) | 189.9 | 241.3 | **79%** | 261/256 | 23.4/25.8 |
| BtcPG | 39.5 | 82.3 | 48% | 269/250 | 28.6/33.2 |
| BtcShield | 16.0 | 45.8 | 35% | 407/396 | 46.4/50.3 |
| GoldShield | 35.4 | 82.7 | 43% | 357/344 | 37.5/42.2 |
| GoldGeo17 | 40.3 | 174.1 | 23% | 312/304 | 28.5/31.9 |
| GoldS210 | 51.8 | 259.5 | 20% | 381/360 | 20.7/23.6 |

**Read:** op-counts match within 3–8% and win-rates within 3–5 pts on EVERY leg →
entry + base-exit logic is faithfully ported (not a structural bug). The shortfall is
in **win magnitude** and scales with **edge-thinness / stack-size** → it's **real
execution cost** the Python engine omits, plus (gold) a tester data artifact.

---

## 2. Root-cause hypotheses (confirm by op-by-op diagnosis first)

| # | Suspect | Why | Fix |
|---|---|---|---|
| H1 | **Spread** (per fill, every position incl. each add) | Python bakes only a flat stress ($18 BTC / $0.40 gold); reality charges bid/ask on entry+exit of every leg | model real per-bar spread (the CSVs already carry a `spread` column) on every fill |
| H2 | **Commission** per lot | Exness c-symbols may charge commission; big-lot gold-geofloor stacks pay most → explains gold-stacker worst-hit | read per-symbol commission; charge per lot per side |
| H3 | **Swap** (overnight) | multi-day trailed BTC + long gold stacks accrue swap; Python ignores it | per-symbol swap-rate × nights × lots |
| H4 | **Slippage / latency** | stop & market fills slip vs the modeled level | calibrate a slippage model from observed tester fills |
| H5 | **Gold H1 tick-volume RECONSTRUCTION** (tester-only?) | gold charts M15 but entry reads H1; the tester rebuilds H1 volume from M15 → different V-patterns than the real `XAUUSDc_H1.csv` Python used. **May NOT exist live** (live `CopyTickVolume(H1)` reads real H1 bars) → a tester artifact to neutralize | decouple management TF from chart TF (see §3.2) and chart gold on **H1** so entry volume is native |

The op-by-op diagnosis (§3.1) **attributes** the 20–80% gap across H1–H5 before we
spend effort fixing the wrong thing. BtcGF (native H1, same geofloor code) keeps 79%
→ the stacking code is fine; gold's extra gap points hard at H5.

---

## 3. Plan

### 3.1 Diagnose op-by-op (attribute the gap) — FIRST
- Make the EA **dump its op stream to CSV** mirroring `out/shadow/<leg>.csv` (entry/exit
  time, dir, R, #pos, reason, add ladder) — it already logs `OP OPEN/ADD/CLOSE`; add a
  file writer (or parse the tester log).
- Match tester ops ↔ Python ops by time on **GoldS210** + **BtcGF**; quantify how much
  of each op's R-gap is spread vs commission vs swap vs slippage vs a different entry.
- Output: a per-leg attribution of the gap → tells us which of H1–H5 dominate.

### 3.2 Architectural fix — chart on H1, manage on M15 (DECIDED: change the EA)
- **Always chart the EA on H1** so entry detection is **native to the chart** (`_Period`
  = H1 = the broker's real H1 bars live; real-tick-derived in the tester) — matching live
  exactly, no cross-TF volume reconstruction. Add **`InpMgmtTF`** (the management/add
  timeframe: **M15** for gold, **H1** for BTC) and run management (SMA bounce, adds,
  margin-line, trail) off `InpMgmtTF` instead of `_Period`. Requires the M1-granular
  tester (Model 1/4) so M15 is available under an H1 chart. Instrument-agnostic.
- User's call (accuracy first): *"just release an EA on the H1 chart and add positions on
  M15."* This + a **Model-4 (real-tick)** validation makes the tester a faithful referee
  for gold (live `CopyTickVolume(H1)` reads real H1 bars). Re-validate all legs after.

### 3.3 Realistic friction model in Python (agnostic)
- Extend `pyramid_engine`/`conc_engine` accounting (`close`, the add path) with a
  per-symbol **cost model**: spread (from the CSV `spread` column, per fill),
  commission/lot, swap/night/lot, slippage. Keyed by `SPECS[sym]` so it generalizes to
  any instrument; applied to **every position** (base + each add), not a flat per-op
  stress. Pull the real rates from MQL5 (see §3.5).

### 3.4 Re-validate < 5% (the gate)
- Tester **Model 4** (real ticks) for all 6 legs over the full window; compare per-leg
  totR + 6-seg fingerprint to the corrected Python. Iterate §3.3 until **every leg < 5%**.
  Confirm agnosticism on a held-out strategy/instrument.

### 3.5 Data bridge (pull real cost data from MQL5)
- An MQL5 utility (script/EA) or tester export that dumps the broker's real
  **spread series, swap rates, commission, contract specs** per symbol → CSV for the
  Python cost model. "We can pull data directly from MQL5."

### 3.6 Re-challenge the kings (only after the gate passes)
- Re-run the king search on the **corrected** engine: re-pick legs, sets, weights,
  expert combinations, gold:BTC split — the old choices were made on the untrustworthy
  engine, and the user suspects they're **not optimal**. Enforce **6-segment robustness**
  throughout. Produce the *true* kings + a fresh `cross_kings`-style portfolio result.
- **Scope (DECIDED): stay within the current family — V-pattern breakout, gold + BTC.**
  Do **not** hunt for new signals: *"our edge is in HOW we trade the signal, not the
  signal itself — these triggers are basic, maybe no better than an MA cross."* So the
  search space is the **trade-management** layer: stacking geometry (proggeo/geofloor,
  mult/step), the margin-line floor, TP vs trail, the favourable gate, concurrency, the
  leg weights, and the cross-instrument blend — NOT the entry.

### 3.7 Return to deployment
- Regenerate `shadow_streams` from the corrected engine; re-validate the EA; resume
  `SYSTEM_PLAN.md` (orchestrator → $100 shakedown) with **trustworthy** numbers.

---

## 4. Resolved decisions (2026-06-14)
- **D4 — REOPENED (2026-06-14): pursue the M1 route to make PYTHON match the tester;
  Path A (tester-as-truth) is the FALLBACK.** The op-by-op decomposition (FINDINGS) showed
  Python's **per-op physics already match** the tester (matched ops agree within ±12R on
  5/6 legs); the residual is the **entry set** — an intrabar (M1) entry/exit-timing effect
  of `max_conc=1`, i.e. a **data** gap, not a modeling gap. So:
  - **Primary:** extract full-window **M1** (`Scripts/DumpHistory.mq5` — an in-terminal
    MQL5 CSV dumper, the user's idea, bypassing the Python `copy_rates_from_pos` ~90k cap)
    → build an **M1-intrabar Python engine** → verify Python ≈ NBP-tester (`tester_truth.py`).
    If it matches, Python is the **fast** trustworthy engine and §3.6 runs in Python.
  - **Fallback (if M1 can't be extracted):** **Path A** — the MQL5 tester *is* the research
    engine (proven **Model 1 ≡ Model 4** under NBP; read via `tester_truth.py`); run §3.6
    through `out/ck_batch.ps1`. Slower but definitive. Aligns with *tester = ground truth*.
  - The "<5% Python match" is no longer a blocker to fear — it's now the **target** of the
    M1 route (and moot under the fallback).
- **D5 — NBP is the standard accounting.** Each ops-account is funded with exactly **1R**
  (EA-dumb model), so the broker's **negative-balance protection** caps any loss at **-1R**
  (the tester, run on a big deposit, *reports* -1.1..-2.0R overshoot; the live account
  zeroes it). **Every op's realized R is clamped `max(R, -1)`** in all downstream accounting
  (totR/DD/RF/segments/growth). This clamp also makes Model 1 ≡ Model 4 (overshoot was their
  only divergence). Implemented in `tester_truth.py` (canonical reader) and `ck_batch.ps1`
  (reports `nbpR`).
- **D1 — gap metric/bar: `totR`** *(superseded by D4 as a Python↔tester gate; totR remains
  the headline metric, now read NBP-clamped off the tester).* Was: per-leg totR within 5%
  vs the Model-4 tester; 6-segment fingerprint as robustness.
- **D2 — re-research scope: STAY in the current family** — V-pattern breakout, gold + BTC.
  The edge is the **trade management**, not the signal → optimize management/weights/combos,
  not the trigger. (No new signals/instruments.)
- **D3 — chart/management TF: change the EA → chart on H1, manage on M15** (`InpMgmtTF`),
  validate under Model 4. Accuracy over convenience (user's explicit preference). The
  Python engine goes **M1-driven intrabar** if bar-level can't hit <5% (we have M1 data).

---

## 5. Status / artifacts
- **§3.1 DIAGNOSIS DONE (2026-06-14) — see `backtest/FIDELITY_FINDINGS.md`.** Op-by-op
  attribution (reconstructed the EA's op streams from the tester log, matched 1:1 to the
  shadow oracle) found the dominant gap was **NOT** spread/commission/swap (all ≤0.06
  R/op — H1 **falsified** via the param-free `cost_probe.py`). It was a **port bug**: the
  EA's geometric add-ramp read the base lot off `ScanBook()[0]`, but MT5 lists positions
  **newest-first**, so the ramp computed off the latest 0.01 add and **collapsed** on
  every gold stack. **FIXED** (latched `g_base_lot`/`g_add_count`). Re-validation (Model
  1): GoldGeo17 40.3→**120.9** (23%→69%), GoldS210 51.8→**153.4** (20%→59%); BTC + shields
  unchanged; matched gold ops now reproduce Python.
- **Residual now = §3.2 + §3.3 work:** (a) entry-set drift (gold H5: reconstructed H1
  volume → chart gold on H1) and (b) bar-granularity path sensitivity on big stacks
  (→ M1-intrabar Python / Model-4 tester). This is the same ~21% even faithful BtcGF loses.
- **§3.2 DONE (commit 8757179):** `InpMgmtTF` added, all legs chart on H1. Model-1 re-run:
  gold ~unchanged (120.9/152.2), BTC identical → zero regression. Proved **H5 is not the
  gap** (under Model 1 the tester builds H1 from M1 regardless of chart TF); the residual is
  bar-granularity / fill-path.
- **§3.4 DONE → PATH A (commit 9afc99b + the NBP work):** **Model 4 ≈ Model 1** (BtcGF
  188.3 vs 189.9; GoldS210 147.4 vs 152.2), and **identical under NBP** (BtcGF 190/191,
  GoldS210 157.4/157.5). So the **NBP-clamped Model-1 tester is the trustworthy full-window
  engine** (D4/D5). `tester_truth.py` is the canonical reader. The Python oracle is retired
  as the research engine; **§3.3 (M1-intrabar Python) is dropped** (also blocked: exported
  M1 only covers ~2–3 months). The *real* king legs on the trustworthy engine are **weaker
  & less robust** than the oracle claimed (e.g. GoldS210 nbpR 157 vs oracle 259, segs 3/6,
  1op 57%) — confirming the kings need re-challenging (§3.6).
- **▶ RESUME HERE (next session, 2026-06-14 — paused on credits):**
  0. **DATA PARITY is the rule** (user): Python and the tester must consume identical
     inputs. The tester's Model 1 builds *everything* from M1 → so dump **M1** and **derive
     H1 & M15 from it** (H1 `tick_volume` = SUM of M1 tick_vols); do NOT read the old
     separately-pulled H1 CSV (its tick_volume likely differs → a prime suspect for the
     entry-set gap). Compare Python to tester **Model 1** (same M1 source). See FINDINGS
     "DATA PARITY".
  1. **Extract M1** (user must launch the live terminal). `Scripts/DumpHistory.mq5`
     (compiles 0/0; modes **BARS**/**TICKS**) — junction into `MQL5/Scripts` per
     [[reference_mt5_junction_setup]] or drop beside the EA; set Max-bars-in-chart→Unlimited;
     run **mode=BARS, TF=M1** for XAUUSDc + BTCUSDc over 2024-02→2026-06. Copy
     `MQL5/Files/*_M1_dump.csv` → `backtest/data/<SYM>USDc_M1.csv`. Confirm full-window
     coverage (today only ~2–3 mo) AND that M1→H1 `tick_volume` reconciles. **Fallback:**
     **mode=TICKS** (CopyTicksRange, day-chunked) for exact Model-4 parity if M1 falls short.
  2. **If full M1 obtained → build the M1-intrabar Python engine**: derive H1 (entry, incl.
     tick_volume=ΣM1) and M15 (management) from the dumped M1; management cadence on M15/H1,
     but **exit-check + entry-fill stepped at M1**. Prototype on the recent ~2–3 mo of M1
     first (where it already exists), confirm it reproduces tester Model 1 there, then run
     full-window. Goal: Python ≈ NBP-tester (`tester_truth.py`) per-leg → the fast engine.
  3. **If M1 can't be extracted → Path A fallback:** §3.6 king re-search **through the
     tester** (`ck_batch.ps1`, NBP-scored via `tester_truth.py`).
  4. **Then §3.6** (either engine): re-search the trade-management layer (stacking geometry,
     margin-floor, TP/trail, gate, concurrency, weights, blend), enforcing **real** 6-seg
     robustness (the trustworthy fingerprints are weaker: GoldS210 3/6, 1op 57%) → the
     *true* kings → resume deployment (§3.7).
- Phase A (EA + oracle + presets) and Phase B (validation run) are **done & committed**
  (`1b7efda`, `7b769fa`, `5d75115`). The management/sizing core is now faithful on matched
  ops; the gap is entry-set + granularity, not the port logic.
- Tooling: `backtest/shadow_streams.py` (oracle), `backtest/out/ck_batch.ps1`
  (headless batch runner), `ExpertAdvisors/CrossKing_EA/run_test.ps1`.
- Headless tester recipe (it's fiddly): live Exness terminal holds the data-dir lock
  → close it; `ShutdownTerminal=1` is unreliable → kill-launch-wait-parse-kill; parse
  `OP CLOSE R=` from `Tester/logs/<date>.log`. Account leverage = 1:2000. Validation
  config: `InpFixedE0=10`, `InpMPLOverride=0.318 BTC / 0.419 gold`, `InpTROverride=0`,
  deposit 100000. **Real TR = 0.01 BTC, 1.0 gold** (gold is NOT a 100× contract).
