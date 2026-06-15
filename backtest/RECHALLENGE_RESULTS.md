# Re-Challenge Results Log (FIDELITY §3.6-REDUX)

Checkpoint file (token protocol §4): one summary block per archetype so context can be
compacted without losing state. Tester-true (MetaQuotes terminal, Model 1, NBP). Raw
per-pass CSVs in `out/opt/<tag>.csv`.

Champion to beat: prom-date 3-dancer **57.5× @24%DD**, RF 25.1, 6/6 (the current crown).

---

## Archetype F — poscandle (open-candle compounding) — GOLD — ✅ ALIVE
`out/opt/gold_poscandle.csv` (240 passes, geofloor, sweep step×buffer×slowP×TP).
- **103/240 positive nbpR.** Two regimes:
  - **Jackpot trap (TP 2.5–3):** nbpR up to 1155 but `segpos 1/6`, `oneop>112%`,
    **`extop1R ≈ −145`** → all from one lucky monster stack → REJECTED by the aggressive gate.
    (Confirms why raw-nbpR ranking is a trap; the extop1R metric catches it.)
  - **Genuine low-TP edge (TP 1.5):** e.g. `step2.0/TP1.5/buffer0.25/slowP150` →
    `extop1R **+37**`, `segpos **4/6**`, `win **25%**`, `oneop 57%`, `nmonster 14`.
    Dropping TP 3→1.5 ~doubles win rate and turns the jackpot into a recurring edge.
    **User's TP insight vindicated by data.** Viable corner = low step-ish + buffer ~0.25 + TP 1–2R.
- **Verdict:** enters the prom-date tournament as an aggressive gold candidate. Densify the
  low-TP corner (TP 1.0–2.0, buffer 0.1–0.4, step 1.7–2.3) IF it makes the team.

---
## Archetype G — structural / grid-SL — GOLD — ✅ ALIVE & ROBUST
### nback (geofloor anchored N bars back) — `out/opt/gold_nback.csv` (320 passes, 56 positive)
- ⭐ **`nback5 / TP1.0 / buffer0`**: `nbpR 117.8`, `segpos **5/6**`, `RF **5.87**`, `extop1R **+71.9**`,
  `win **40.7%**`, `nmonster 11`, `oneop 39%`. Low TP + tight structural anchor → high-win, very
  smooth, edge NOT one-op-dependent. **Best gold candidate of the redux so far.**
- `nback20 / TP3 / buffer0`: nbpR ~135, segpos 5/6, extop1R +5, win 14% (lower-win backup).
- step is ~irrelevant here (nback pin dominates the ramp).
### pinprev (pin to prior bounce extreme) — `out/opt/gold_pinprev.csv` (228 positive)
- Best: `buffer0.4 / TP3 / smaP7` → `nbpR 108`, `segpos 5/6`, `extop1R +64`, `nmonster 25`. Robust.
- (Grid logged 900 rows — `step` swept but pinprev ignores it → harmless dup near-twins; tighten on BTC.)

**Pattern (all 3 gold archetypes):** deployable configs = **positive extop1R + segpos 5/6 + LOW TP**
(user's TP insight, confirmed 3×). These robust gold candidates were ABSENT from the old pool.
Incumbent ref on same engine: GoldS210 nbpR 157 but segpos **3/6** → the new nback5 is far smoother.

---
## BTC archetypes F + G — ✅ STRONGLY ALIVE (`out/opt/btc_*.csv`)
- **poscandle** (182/240 pos): `step2.0/TP3/slowP210` → `nbpR **333**`, segpos 4/6, `extop1R **+114**`,
  nmonster 13 (high-return, repeatable); `step1.4/TP3` → nbpR 128, **segpos 6/6**, win 21% (robust).
- **nback** (292/320 pos, 91%): `nback5/TP3` → nbpR 169, segpos 3/6, `extop1R +47`, win 19%;
  `nback20/TP2.5` → nbpR 71, segpos 4/6, extop1R +32, win 25%. (step swept but irrelevant at nback5.)
- **pinprev** (261/300 pos): `buffer0/TP2/smaP11/half1.0` → nbpR 70, **segpos 6/6**, `extop1R +34`,
  **win 32%**, RF 3.85 (fully robust); `buffer0/TP3` → nbpR 106, segpos 5/6, extop1R +38.
- ✅ `_val` ||N fix VALIDATED: btc_pinprev = exactly 300 rows (was 900 pre-fix).

## Phase 2 takeaways
- ALL six new-archetype sweeps (gold+BTC × poscandle/nback/pinprev) produced **robust,
  positive-extop1R, non-jackpot** candidates absent from the old pool — strongest on the gold side
  (the crown's weak point: it had only a gold *shield*).
- LOW TP consistently improves the aggressive tier (win-rate + segpos); confirmed 6×.
- The aggressive gate's `extop1R` cleanly separates genuine edges from TP3 one-monster jackpots.

---
## Phase 3 (next): pool ALL candidates (new archetype CSVs + old incumbent `pool_*.csv`) →
extend `promdate.load_pool` (new cols + the refined aggressive gate: accept if segpos≥5 OR
extop1R>floor & nmonster≥3) → run the greedy tournament → re-crown → head-to-head vs the
current 3-dancer (57.5× @24%DD). Then finalist bootstrap-over-monsters + ship (Phase 5).
<!-- candidate CSVs ready: gold_{poscandle,nback,pinprev}, btc_{poscandle,nback,pinprev} -->
