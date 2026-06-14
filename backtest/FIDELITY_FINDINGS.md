# Fidelity diagnosis — op-by-op attribution (FIDELITY_PLAN §3.1)

**Date:** 2026-06-14   **Method:** parameter-free probes + reconstructing the EA's
actual op streams from the Phase-B tester log, matched 1:1 against the Python shadow
oracle. Tooling: `cost_probe.py`, `out/ealog/*.csv` (parsed from the tester log),
`/tmp` comparison scripts.

## TL;DR
The 20–80% Python↔tester gap is **NOT** spread, commission, swap, or slippage. The
dominant chunk is a **port bug in the EA's geometric add-sizing**: it read the base
lot and the add index off the *live position book* (`ScanBook()[0]` / `ArraySize`),
but MT5 lists positions **newest-first**, so `lots[0]` was the most-recent **0.01
add**, not the original base. The proggeo/geofloor ramp `base*mult*step^k` therefore
computed off ~0.01 and **collapsed to 0.01 on every gold stack** → the big winners
never formed. **Fixed** by latching `g_base_lot` + `g_add_count` at op-open.

## Evidence

### 1. Spread is negligible (H1 falsified)
`cost_probe.py` re-costed every op with the **real per-fill spread** from the CSV
`spread` column (gold 3dp→point 0.001, BTC 2dp→0.01), zero free parameters:
avg spread cost = **0.01–0.06 R per op**. Re-costing barely moved totR. Spread
cannot explain a tester that retains 20% of the oracle. (Commission/swap scale with
lots like spread and would have to be absurdly large; and they'd hit BtcGF too.)

### 2. Where the gap lives — aligned ops vs entry-set differences
Matching EA ops ↔ Python ops by entry price+dir (≈90% align):

| leg | aligned R-gap (PY−EA) | total gap | pyWin→eaLoss | read |
|---|---|---|---|---|
| GoldS210  | **+167.1** | ~216 | 3 | gap is in *matched* ops → smaller EA books |
| GoldGeo17 | **+93.4**  | ~138 | 3 | same |
| GoldShield| +10.9 | ~50 | 4 | mostly in the entry-set (skips) |
| BtcGF     | **+1.4** | ~52 | 0 | matched ops AGREE; gap = different entries |
| BtcPG     | −4.0 | ~43 | 0 | matched ops agree |
| BtcShield | −11.8 | ~30 | 2 | matched ops agree (EA even higher) |

→ Gold **stackers** lose on *matched* trades (book construction). BTC legs +
GoldShield agree on matched trades; their (smaller) gaps are a different entry set.

### 3. Smoking gun — the ramp collapses with base size
GoldGeo17 (`add = base*0.01*1.7^k`), 5 biggest Python winners vs their EA twin:

```
  e0=2627.30 PYbase=0.39 PYadds=[.01,.01,.01,.01,.03,.05] R=+40.7
             EAadds=[.01,.01,.01,.01,.01,.01]             R=-7.7
  e0=2971.16 PYbase=0.46 PYadds=[.01,.01,.01,.02,.03,.06] R=+37.7
             EAadds=[.01,.01,.01,.01,.01,.01]             R=-1.1
  e0=4784.94 PYbase=0.10 PYadds=[.01,.01,.01,.01,.01,.01] R=+5.5
             EAadds=[.01,.01,.01,.01,.01,.01]             R=+4.2   <- agree when base small
```
When the Python base is large the ramp climbs and wins big; the EA stays at 0.01.
When the base is already ~0.10 the ramp is flat anyway and the two agree. That is
exactly the signature of the EA computing the ramp off a ~0.01 base.

### Why BTC was barely affected (retained 79%)
BTC base lot ≈ 1 and its add scale is dominated by the **geofloor pin** to the slow
SMA (order-independent, uses book sums — correct) and tiny geometric terms
(`step=1.2`). So the wrong-base ramp term was immaterial for BTC. Gold's geometric
term *is* the book, so the bug was fatal there.

## Fix (committed)
`CrossKing_EA.mq5`: added `g_base_lot` (= `SumLots` at op-open) and `g_add_count`
(incremented per logical add). `SizeAdd` now uses these instead of `lots[0]` /
`ArraySize(lots)-1`. This also fixes a latent second bug: when an add is split over
the per-order `VOL_MAX`, the book grows by >1 position per add, so `ArraySize-1`
would over-count `k` — `g_add_count` counts *logical* adds, matching Python.

## Validated result (Model 1 re-run, 2026-06-14, same harness)

| leg | before | **after fix** | oracle | retained | matched-op R-gap |
|---|---|---|---|---|---|
| GoldGeo17  | 40.3 | **120.9** | 174.1 | 23%→**69%** | +93.4 → **+5.2** |
| GoldS210   | 51.8 | **153.4** | 259.5 | 20%→**59%** | +167 → **+64.4** |
| GoldShield | 35.4 | 35.4  | 82.7  | unchanged | +10.9 (depth-1) |
| BtcGF      | 189.9| 189.9 | 241.3 | unchanged (faithful) | +1.4 |
| BtcPG      | 39.5 | 39.6  | 82.3  | unchanged | −4.1 |
| BtcShield  | 16.0 | 16.0  | 45.8  | unchanged | −11.8 |

Gold stackers **tripled**; BTC + shields untouched (the fix is surgical). On matched
ops the gold ladders now reproduce Python (GoldGeo17 biggest winner −7.7→**+40.9** vs
PY +40.7). GoldGeo17's aligned gap collapsed to +5.2 → its residual is **entirely the
entry set** (27 EA-only / 9 PY-only entries = gold H5).

## Remaining residual (the next targets, both smaller & plan-addressed)
1. **Entry-set differences** (all legs, ~20–32 EA-only / ~8–24 PY-only entries). For
   gold this is **H5** — the tester reconstructs H1 tick-volume from the M15 chart, so
   the V-pattern fires on a few different bars than the standalone `XAUUSDc_H1.csv`.
   → FIDELITY_PLAN **§3.2** (chart gold on H1, manage on M15; Model 4).
2. **Bar-granularity path sensitivity on big stacks** (GoldS210's +64 is ~49R from a
   *single* op whose late geofloor adds diverge once the M15-bar path ≠ the M1-tick
   path). The ladder tracks faithfully then splits on depth 17↔18. → **§3.3**
   (M1-intrabar Python) / Model-4 tester. This is the same ~21% even faithful BtcGF
   loses — universal, not gold-specific.

**Bottom line:** the dominant, gold-specific gap was a single port bug, now fixed.
What's left is the universal entry/granularity drift (~25–40% on the thin gold
stackers, ~21% on BTC), to be closed by the §3.2/§3.3 engine/chart changes, then
the Model-4 <5% gate.
