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
<!-- next: gold nback (G), gold pinprev (G), then BTC archetypes, then baseline re-confirm -->
