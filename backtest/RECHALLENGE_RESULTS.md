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

## Phase 3 PREVIEW — new archetypes ALONE (740 cands, no incumbents) = **12.2× @24%DD**
⚠️ **Below the champion's 57.5×.** Team is 6/6, low-corr, positive extop1R everywhere — but
`f=0.005` (tiny): the aggressive legs are so volatile that DD-budgeting to 24% forces a small
compounding fraction → modest growth despite nbpR up to 333. **High nbpR ≠ high growth-at-DD**
(totR-vs-compounding inversion, again). Conclusion: the new archetypes do NOT win standalone;
any dethroning must come from **complementarity** with the SMOOTH incumbent legs (do they smooth
bad segments enough to lift f?). Decisive test = the FULL-UNION tournament (needs `pool_gen`).
Jackpot filter works: TP3 one-monster gold rows (extop1R −145) correctly excluded.

## Phase 3 FULL UNION — verdict so far (champion 57.5×)
**Gate correction (important):** first union run hit **934×** — a MIRAGE = the GoldS210 pin-jackpot
(nbpR 1012, **1op 87%**) the prior work already flagged. My extop1R-only gate let it back in
(removing just the top op still leaves other monsters). **Restored `oneop ≤ 50` as the PRIMARY
jackpot guard + extop1R secondary.** (oneop caps single-op dominance + guards the float-DD the
weekly realized-R can't see.)

**Controlled comparison (same current engine, same gate, diversity-guarded max_corr=0.7):**
| pool | growth@24%DD |
|---|---|
| incumbent only (control) | **48.4×** |
| full union (+ archetypes) | **55.1×** |
→ **new archetypes ADD +14%** at matched DD. Seats won by new archetypes: **XAU nback5/TP1.0**
(the gold COMPOUNDER the crown lacked — win 41%, extop1R +72, 1op 39%), **BTC nback5/buf0.5**,
**BTC pinprev**. (max_corr=1.0 gives 69.5× but seats correlated BTC-trail twins = false diversification.)

**Caveat:** incumbent-only = 48.4× < champion 57.5× because this is the COARSE `pool_gen` (~230
incumbent cands) vs the champion's DENSE pool (1075). Incumbent side is under-sampled.
**▶ NEXT (definitive crown test): densify the incumbent pool (`pool_dense`) back to championship
strength + densify the live archetype corners (gold nback low-TP, BTC nback/pinprev), re-run union.
+14% archetype lift suggests a densified union clears 57.5×, but must be RUN not extrapolated.
Then Phase 4.5 finalist bootstrap-over-monsters before any re-crown.**

## Phase 4 — DEFINITIVE VERDICT (championship-density pool, R1-R3, robust objective)
**Selection objective fixed:** raw growth@DD is jackpot-inflatable (float-DD-blind mega-stacks) — even
under R1/R2/R3 the greedy grabbed the GoldS210 1op-87% leg → fake 934× (ex-top5 retain **1%**). So the
greedy now maximizes **robust growth = growth@DD after dropping the top-3 weeks** (`promdate.robust_growth`,
`drop_top=3`) = "high CHANCE of high returns", not an in-sample peak. This is the thesis operationalized.

**Same-engine, same-lens comparison (max_corr=0.7):**
| metric | Champion (current crown) | Challenger (robust-selected) |
|---|---|---|
| raw growth@24%DD | 44.0× | 35.9× |
| **robust (ex-top3-wk)** | **4.8×** | **14.3×** |
| ex-top5-wk retention | 6% | 24% |
| bootstrap median / p05 | 10.1× / 1.8× | 9.8× / 2.5× |
| back-loading h2/h1 | 3.5× | 1.8× |

**VERDICT: the current crown is FRAGILE** — 94% of its growth is in 5 weeks; it's a back-loaded in-sample
peak (vindicates the user's "king won't stand"). The **robust-selected team is ~3× more dependable**
(robust 14.3× vs 4.8×) and more diversified: 2 real GOLD geofloor compounders (crown had only a gold
shield) + BTC trail + 2 NEW archetypes (BTC nback15/buf0.5, BTC pinprev). Cost: lower raw peak (36 vs 44).
**Caveat:** neither is bulletproof — both bootstrap to ~10× median; both still lean on the back half.
Forward expectations « headline raw. ▶ NEXT: finalist single-pass reproduce + decide crown (robust team)
vs further densify the archetype low-TP corners; mind the back-loading for live sizing.

## Phase 4b — DENSIFIED + R4, CONVERGED CROWN
After densifying archetype corners, the drop_top=3 objective was GAMED (GoldS210 1op87% snuck back,
ex-top5 retain 3%). Added **R4 (weekly concentration): retain ≥35% of R after dropping the 3 biggest
WEEKS** — the thesis's "occur often enough" on the weeks/growth dimension. Pool 769→109 survivors;
jackpot gone. **CROWNED challenger (max_corr=1.0, 6 legs, all corr_to_rest ≤0.44) = 31.5× raw /
13.5× robust / retain 27% / boot-median 12.3× / p05 2.7× / 5-6 segs.** Roster: 2 GOLD geofloor
compounders (sma7/step1.7/TP3, sma9/slow300/step1.4/TP3) + 2 BTC trails (sma15/slow270/step1.5/tr2.5,
sma15/step1.2/tr2.5) + BTC nback15/buf0.5/step2.0/TP1.0 + BTC pinprev/buf0.4/sma13/TP1.5.
**vs champion (same engine): 44× raw but robust 4.8× / retain 6% / boot-med 10.1 / p05 1.8.**
→ challenger wins the user's metric (chance of high returns) on every robustness measure.
CAVEAT: boot-median ~12×, back-loaded → modest, regime-dependent forward edge.
▶ pending user confirm: crown challenger → PD2_*.set presets + finalist single-pass reproduce.

## Phase 5 — FINALIST REPRODUCE + presets (crown confirmed by user)
Single-pass reproduce of the 6 legs (`_finalist.py`):
- **Quick-exit/trail legs reproduce near-exactly** (gold geofloor-TP3 +0%, BTC trails +1%/−6%).
- **Aggressive deep-STACK legs are path-sensitive +10..+36%** (gold proggeo sma7 +36%, BTC nback +10%,
  BTC pinprev +18%) — known sub-bar tick-ordering jitter on deep stacks. A real fidelity caveat for
  the aggressive archetypes: exact contribution wobbles run-to-run even on the tester.
- **Team reproduced: 24.2× raw (WITH monsters) / 10.8× robust (ex-top3wk) / retain 30% / boot-median
  11.9× / p05 2.5×.** Monsters ≈ **×2.2** the growth (10.8→24.2) = the capped-downside aggression payoff.
- Crown STANDS: even reproduced + softened, beats champion (44× raw but robust 4.8× / retain 6% / med 10.1).
**Presets written: `presets/PD2_*.set`** (GoldGeo_0 proggeo sma7/step1.7/TP3, BtcTrail_1 geofloor
sma15/slow270/tr2.5, BtcNb_2 nback15/buf0.5/step2.0/TP1, GoldGeo_3 geofloor sma9/slow300/TP3, BtcTrail_4
proggeo sma15/step1.2/tr2.5, BtcPin_5 pinprev/buf0.4/sma13/TP1.5). `_finalist.py`, `_gen_presets.py`.
**Deployment: back-loading + aggressive-leg path-jitter → size conservatively (f near bootstrap median, not raw).**
