# Full Strategy Re-Challenge — tester-true, whole field (2026-06-15)

> **Mandate (user):** the §3.6 prom-date crown was chosen from a pool that only ever
> contained the archetypes the EA can express. Several archetypes we explored were ruled
> out / never entered the tournament — and were judged on the **inflated oracle**. Re-run
> the *entire* field through the trustworthy tester and the prom-date best-match. **Belief:
> the current 3-dancer king will not survive.** Reality first; no oracle numbers anywhere.

This is **FIDELITY §3.6-REDUX** — a wider re-run of the king search, on the engine that
already passed the <5% gate (NBP-clamped Model-1 tester = ground truth; see
`FIDELITY_PLAN.md`, [[feedback-tester-fidelity-gate]]). It does **not** reopen the data /
fidelity work — that's settled (Path A). It reopens only **which strategies were allowed to
compete.**

---

## 1. Archetype coverage matrix — *what was actually in the tournament*

| # | Archetype | In EA today? | In tester-true pool? | Verdict basis | Action |
|---|---|---|---|---|---|
| A | Shield + fixed TP | ✅ `InpStack=false,InpTpR` | ✅ (Btc/GoldShield) | tester | re-confirm sweep width |
| B | Trailing stop | ✅ `InpTrailR` | ✅ (BtcGF) | tester | re-confirm sweep width |
| C | Geometric "slow" compounding (proggeo) | ✅ `CK_PROGGEO` | ✅ (BtcPG) | tester | re-confirm sweep width |
| D | Aggressive margin-line / geofloor (slow-SMA anchored) | ✅ `CK_GEOFLOOR,InpSlowP` | ✅ (GoldS210/Geo) | tester | re-confirm sweep width |
| E | SMA-bounce add trigger | ✅ `InpSmaP` | ✅ (all stacks) | tester | baseline |
| **F** | **Open-candle ("poscandle") compounding** | ❌ Python only | ❌ **never** | **ORACLE — "mirage"** | **build into EA + trial** |
| **G** | **Structural / grid-SL margin-line (pinprev, N-back)** | ❌ Python only | ❌ **never** | **ORACLE — "DEAD"** | **build into EA + trial** |
| **H** | **RSI-recovery add trigger / RSI-anchored line** | ❌ never built | ❌ never | never tested | **scope decision (net-new)** |

**F, G (and optionally H) are the gap.** They were killed on numbers we no longer trust.
A–E are present but were swept with the *old* pool generator — re-confirm the grid is wide
enough now that they share the field with F/G.

**Fixed by prior decision (do NOT reopen):** entry signal = H1 V-pattern (D2 — "the edge is
in HOW we trade the signal"). The search space is the **management layer only**: add-trigger,
sizing rule, margin-line placement, TP vs trail, favourable gate, concurrency, weights, blend.

---

## 2. Ground rules (inherited — non-negotiable)

1. **Tester-true only.** NBP-clamped Model-1 MT5 tester via `backtest/tester_truth.py`. No
   oracle / idealized Python numbers enter any ranking. (D4/D5.)
2. **Common clock = calendar-week NBP-R vectors.** Every candidate (any archetype) ships its
   130-week NBP-clamped R vector via `OnTester`/`FrameAdd` → `ck_opt.csv`. This is what makes
   cross-archetype prom-date comparison valid.
3. **Prom-date best-match across the WHOLE pooled field** (`backtest/promdate.py`): greedy
   add-the-dancer-who-most-lifts-geometric-growth-@matched-DD, diversity guard `max_corr`,
   **1-op filter ≤ 40–50%** (kills pin-jackpots), **equal weight** (anti-curve-fit), **6/6
   segment robustness** required.
4. **Head-to-head gate.** A new crown must beat the current 3-dancer (57.5× @24%DD, RF 25.1,
   6/6) on growth-@-matched-DD **and** be no worse on segment spread / recency risk.

---

## 3. Phases

### Phase 0 — Audit & lock the field *(no tester runs; cheap)*
- Confirm matrix §1 against the EA source (the add path + sizing enum) and the old Python
  prototypes (`king_poscandle.py`, `margin_line*.py`, `bounce_struct.py`, `conc_engine.py`
  `trig=`). Output: the final archetype list + per-archetype param grid. **Settle H (RSI)
  scope here.**

### Phase 1 — Extend the EA to express the whole field *(one MQL5 change, shared plumbing)*
**SCOPE LOCKED (user, 2026-06-15): F (poscandle) + G (structural/grid-SL) this round; H (RSI)
QUEUED as a fast-follow only if F/G don't dethrone the king (net-new, zero prior signal).**
- Add **`InpAddTrigger`** enum `{ADD_SMA_BOUNCE=0, ADD_POSCANDLE=1, ADD_STRUCT_SL=2}` driving
  *when* an add arms (reuse the existing `DoAdd`→`SizeAdd`→`MarginCap`→`PlaceSplit` path; only
  the arming block in `OnBar` step 3 branches). `RSI_RECOVERY` left as a reserved slot.
- Add **`InpLinePlace`** enum `{LINE_MARGIN=0, LINE_PINPREV=1, LINE_NBACK=2}` for the
  floor/anchor (touches `MarginLine`/`ComputeStops`); `InpNBack` depth input for NBACK.
- POSCANDLE = add on every confluent in-trend candle (mirror Python `trig="poscandle"`);
  STRUCT_SL = place the line at the prior bounce extreme (pinprev) / N-bar structural low/high.
- Recompile to 0/0; re-validate the 3 existing presets reproduce their locked R-streams
  (regression gate — the EA change must not move A–E).

### Phase 2 — Optimize each archetype on the tester *(heavy compute, OFFLINE / cloud)*
- One MT5 optimizer sweep per archetype family over its grid (MetaQuotes terminal + cloud
  agents). Each pass = one candidate row in `ck_opt.csv` with its weekly NBP vector.
- Densify only where the surface looks alive (mirror `pool_gen.py` → `pool_dense.py`).
- **Output per archetype: ONE candidate CSV.** Nothing else enters my context.

### Phase 3 — Pool the full field + prom-date tournament *(cheap; Python summary only)*
- Concatenate all archetype CSVs → one pool. Run `promdate.py` greedy build over the union.
- Report the chosen team + the per-archetype "best standalone" leaderboard (so we *see* where
  F/G/H actually landed vs A–E).

### Phase 4 — Re-crown & head-to-head
- New team vs current 3-dancer (§2.4 gate). Crown only if it clears the gate. If the current
  king survives, that is a legitimate result and we say so.

### Phase 5 — Ship
- Regenerate `PD_*.set` presets for the new team, update `_Spec.md`, `shadow_streams`, and the
  memory ([[project-promdate-kings]]). Resume `SYSTEM_PLAN.md` deployment with the true team.

---

## 4. Token-efficiency protocol (how we keep cost down)

The expensive work (tester/optimizer passes) runs **in MT5 / cloud agents — outside my
context**. Discipline for the parts that touch my context:

1. **Never dump raw tester logs or full CSVs into context.** Always reduce through
   `tester_truth.py` / `promdate.py` to a summary table (the `row()` helper: per-seg R +
   champion benchmark + 1-op share). Cap any log read with grep, not `cat`.
2. **One summary line per candidate**, one leaderboard per archetype — not op-by-op streams.
3. **Checkpoint to `RECHALLENGE_RESULTS.md`** after each archetype (Phase 2/3). State lives in
   the file, so context can be `/compact`-ed between archetypes with zero loss.
4. **Batch optimizer configs**; generate `.ini`/`.set` programmatically, launch headless.
5. **Subagent for wide code reads** (e.g. auditing the old Python prototypes) — relay only the
   param grid, not the file dumps.
6. **Work archetype-by-archetype**, committing after each, so a long session degrades
   gracefully and is resumable from git + the results file.

---

## 5. Status / log
- **2026-06-15: plan written.** Coverage matrix established from EA source + memory. GAP
  confirmed: archetypes F (poscandle), G (structural/grid-SL) never had a tester-true trial
  (killed on oracle); H (RSI) never built.
- **2026-06-15: scope LOCKED = F+G now, RSI queued (user took the recommendation).** Phase 0
  audit done — EA add-path/sizing plumbing is shared & branch-able; poscandle exists in
  `conc_engine` (`trig=`), struct-SL in `margin_line.py`; RSI confirmed nowhere.
- **2026-06-15: ✅ PHASE 1 DONE.** EA extended (commit pending): `InpAddTrigger`
  {ADD_SMA_BOUNCE, ADD_POSCANDLE}, `InpLinePlace` {LINE_MARGIN, LINE_NBACK, LINE_PINPREV},
  `InpNBack`. `SizeAdd` generalized to an explicit anchor; `DoAdd(…, anchor, pinExact)` branches
  geofloor-ramp vs `lot_to_pin` (pin_add); new `g_anc_b`/`g_prev_anc` op-state (reset at
  open/close/adopt). **Compiles 0 errors / 0 warnings.** Default path is logic-preserving (the 3
  locked presets reproduce). Spec §3 updated. NEXT = Phase 2: regression-confirm the 3 presets on
  the headless tester, then author per-archetype optimizer grids (poscandle, nback, pinprev) and
  sweep on the MetaQuotes terminal + cloud agents → one candidate CSV each.
