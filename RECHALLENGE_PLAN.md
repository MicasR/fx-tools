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

## 1b. CHAMPIONSHIP QUALIFICATION (user, 2026-06-15 — Option B)

**Thesis (user):** high-compound trades whose downside is **capped at −1R** by NBP can yield
phenomenal results *if they recur often enough*. The research question = *what system of EAs gives
the highest chance of truly high returns at reasonable DD?* → **the most aggressive techniques MUST
compete** (no `oneop` cap). A leg/preset qualifies for the championship iff:
- **R1 Robustness:** `segpos ≥ 4` (≥4/6 segments positive).
- **R2 Low single-trade dependency:** still `≥4/6` positive **after removing the 3 biggest winning
  ops** (`segpos_ex3 ≥ 4`). Principled replacement for the oneop cut — admits aggression, rejects
  edges carried by ≤3 trades.
- **R3 Anti-recency (added):** positive in **both halves** of the window (`h1R>0 & h2R>0`) — guards
  the known back-loading/recent-regime deployment risk; closest in-sample proxy for out-of-sample.
- **Team backstop:** `team_robustness` — growth@DD must survive dropping the biggest weeks +
  bootstrap-over-weeks (the team can't hinge on a few lucky weeks; team analogue of R2).

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

### Phase 4.5 — Aggression: tiers + the aggressive-strategy gate (the hard part)
**Why this matters:** aggressive pin/geofloor stacks blow up the 1R ops-account often but can
return **+100R in one trade (~quarterly on gold)**. NBP caps each blow-up at **−1R**, so an
aggressive leg = a stream of mostly `−1R` with rare monsters — a *bounded-cost asymmetric bet*,
not ruin. The metric is fine; the old **selection filters discriminate against it**: the blunt
`oneop ≤ 40–50%` cut can't tell a recurring monster edge from a one-shot curve-fit jackpot, and
the **6/6 segment-positivity** gate structurally rejects lumpy returns. Gold is where this bites.

**Aggression is a continuous dial → sweep it, don't pick it.** Controlled by `InpLineBuffer`
(→0 = aggressive, line hugs price, lots maxed), `InpProgStep`, geofloor anchor distance
(`InpSlowP`), and `InpHalf`. Every archetype is swept across **conservative / mild / aggressive**
bands; **all three tiers compete as separate dancers** (tagged by tier — never pre-collapsed).

**Refined acceptance (replaces the blunt 1-op cut), per candidate:**
- **Smooth path:** accept if `segpos ≥ 5` (the old robustness, for non-aggressive legs).
- **Aggressive path:** accept a lumpy leg if it proves *recurrence, not luck* —
  `extop1R > min_floor` (totR **ex the single best op** stays clearly positive) **AND**
  `nmonster ≥ 3` (≥3 ops ≥ `CK_MONSTER_R`=5R) **AND** those monsters span **≥2 segments**.
  One-segment / one-monster wonders (the pin-jackpot) are still rejected.
- **Finalist bootstrap:** resample which monster ops "landed"; the team must beat the champion
  in most resamples (drop-any-1-monster survival). This is the statistically-correct robustness
  test for ~8 monster opportunities — it *replaces* segment-positivity for the aggressive tier.
- (EA now ships `extop1R`, `nmonster` per pass; `promdate.load_pool` META + filter to be
  extended in Phase 3, and `validate_finalists.py` gets the bootstrap.)
- **Soft tiebreaker (deployment-aware):** between equal-growth tiers, prefer **fewer blow-ups**
  (refund-latency drag under the semi-manual Telegram model); flag any leg whose blow-up rate
  outpaces a realistic refund cadence (backtest assumes instant re-seed; reality doesn't).

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

## 5. Staged optimizer grids (Phase 2 — sweep on MetaQuotes terminal + cloud)

Common to all: chart **H1**; `InpMgmtTF` = M15 (gold XAUUSDc) / H1 (BTC BTCUSDc); `InpStack=true`;
entry knobs fixed (V-pattern). Validation sizing `InpFixedE0=10`, real `TR`/`MPL` overrides per
[[reference-mt5-junction-setup]] / FIDELITY §5. Score = NBP `OnTester`. Each pass → one `ck_opt.csv`
row (now carrying `extop1R`,`nmonster`,`addtrig`,`lineplace`,`nback`,`buffer`).

**Aggression tier = (buffer × step × anchor) band** (the dial, not a free axis):

| tier | `InpLineBuffer` (R) | `InpProgStep` | `InpSlowP` (geofloor) | `InpTpR` |
|---|---|---|---|---|
| aggressive   | 0.0       | 1.7, 2.0 | 150, 180 (tight = big lots) | **1.0, 1.5, 2.0, 3.0** |
| mild         | 0.25, 0.5 | 1.4, 1.5 | 210 | 2.0, 3.0 |
| conservative | 0.75, 1.0 | 1.1, 1.2 | 270, 330 | 3.0 (or trail) |

**TP × aggression interaction (user, 2026-06-15):** an aggressive stack pins huge lots against a
close line → *fragile but explosive*. A high TP often never lands before the stack blows up; a
**lower TP banks the monster lots while in profit**, converting −1R blow-ups into wins. So the
aggressive band **sweeps `InpTpR` low** (1.0–2.0R) as well as 3R — TP height is part of the
aggression search, not a fixed exit.

**Archetype F — poscandle compounding:** `InpAddTrigger=ADD_POSCANDLE`,
`InpSizing ∈ {CK_PROGGEO, CK_GEOFLOOR}`, `InpLinePlace ∈ {LINE_MARGIN, LINE_NBACK}`,
`InpSmaP ∈ {5,7,11}` (gold) / `{12,15,18}` (BTC), `InpHalf ∈ {0,0.5,1.0}`, exit `TpR=3` or
`TrailR ∈ {2.5,3.5}` × the 3 tiers.

**Archetype G — structural / grid-SL line placement:** `InpAddTrigger=ADD_SMA_BOUNCE`,
`InpSizing=CK_GEOFLOOR`, two flavors:
- `InpLinePlace=LINE_NBACK`, `InpNBack ∈ {5,10,20}` (structural low/high N back), × tiers;
- `InpLinePlace=LINE_PINPREV` (pin to prior bounce extreme), × buffer (`{0,0.25,0.5,0.75}`).

**Baseline (re-confirm A–E width):** re-run the existing geofloor/proggeo/shield/trail grid
(old `pool_gen.py`) so the incumbent family competes on the SAME corrected engine + filter.

Densify (`pool_dense.py`-style) only where the surface is alive. Keep gold & BTC pools separate
files; prom-date pools the union. **Estimated passes are large → cloud agents; results reduce to
one summary leaderboard per archetype (token protocol §4).**

## 6. Status / log
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
  locked presets reproduce). Spec §3 updated.
- **2026-06-15: ✅ AGGRESSION + BUFFER added (user requirements).** EA: `InpLineBuffer` (R units,
  the aggression dial — 0=aggressive/line hugs price, >0 caps the pin family; `FloorAnchor` applied
  to geofloor + pinprev anchors, mirrors `conc_engine` `floored_anchor`). `OnTester` now also ships
  **`extop1R`** (totR ex the single best op) and **`nmonster`** (#ops ≥ 5R) for the aggressive gate,
  plus the new identifying params (`addtrig`,`lineplace`,`nback`,`buffer`) — `ck_opt.csv` header +
  `OnTesterPass` extended; `CK_NMETA=23`. Compiles 0/0. **Methodology for optimizing aggressive
  (blow-up-prone, monster-return) strategies = new §4.5** (tier-sweep the aggression dial; replace
  the blunt 1-op cut with an ex-top-1 + monster-recurrence + bootstrap gate; prom-date marginal
  selection unchanged). **Tiered grids staged in §5.** NOTE (correction): RSI exists as an OLD
  single-stream `pyramid_engine.run_tf` prototype (`_rsi`), never in the concurrent engine/EA/tester
  — so the "RSI queued" call stands.
- **▶ NEXT = Phase 2 (needs MT5 terminal):** (a) regression-confirm the 3 locked presets reproduce
  on the headless tester; (b) launch the §5 archetype sweeps on the MetaQuotes terminal + cloud
  agents → one candidate CSV per archetype. Then Phase 3 (extend `promdate.load_pool` META/filter +
  pool the union), Phase 4/4.5 (re-crown + aggressive gate + head-to-head), Phase 5 (ship).
