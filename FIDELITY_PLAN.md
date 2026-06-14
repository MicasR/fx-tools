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

### 3.2 Architectural fix — decouple management TF from chart TF
- Add `InpMgmtTF` (default = chart `_Period`). The EA already separates **entry TF**
  (H1) from chart; do the same for **management**. Then chart **gold on H1** (native
  H1 entry volume, no reconstruction = kills H5) while managing on **M15** via
  `InpMgmtTF`. Instrument-agnostic. Re-validate gold legs after.

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
  engine. Enforce **6-segment robustness** throughout. Possibly reconsider the strategy/
  instrument universe (see open decisions). Produce the *true* kings + a fresh
  `cross_kings`-style portfolio result.

### 3.7 Return to deployment
- Regenerate `shadow_streams` from the corrected engine; re-validate the EA; resume
  `SYSTEM_PLAN.md` (orchestrator → $100 shakedown) with **trustworthy** numbers.

---

## 4. Open decisions (confirm at the start of the new session)
- **D1 — gap metric/bar:** target = per-leg totR within 5% vs **Model 4** tester, AND
  6-segment fingerprint match? (assumed yes.)
- **D2 — re-research scope:** when re-challenging the kings, stay within the current
  family (V-pattern breakout, gold + BTC) and re-optimize sets/weights/combos — or
  also re-open the **strategy and instrument universe**? (user hinted "strategies" and
  "experts" plural.)
- **D3 — engine resolution:** if bar-level Python can't hit <5% because intrabar SL/TP
  ordering matters, do we move the Python engine to **M1-driven** intrabar (we have M1
  data) to mirror the tester? (assumed: escalate only if needed.)

---

## 5. Status / artifacts
- Phase A (EA + oracle + presets) and Phase B (validation run) are **done & committed**
  (`1b7efda`, `7b769fa`, `5d75115`). The EA is faithful in structure; the gap is the
  cost model + gold data artifact, not the port logic.
- Tooling: `backtest/shadow_streams.py` (oracle), `backtest/out/ck_batch.ps1`
  (headless batch runner), `ExpertAdvisors/CrossKing_EA/run_test.ps1`.
- Headless tester recipe (it's fiddly): live Exness terminal holds the data-dir lock
  → close it; `ShutdownTerminal=1` is unreliable → kill-launch-wait-parse-kill; parse
  `OP CLOSE R=` from `Tester/logs/<date>.log`. Account leverage = 1:2000. Validation
  config: `InpFixedE0=10`, `InpMPLOverride=0.318 BTC / 0.419 gold`, `InpTROverride=0`,
  deposit 100000. **Real TR = 0.01 BTC, 1.0 gold** (gold is NOT a 100× contract).
