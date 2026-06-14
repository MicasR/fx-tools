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

## §3.2 done — chart on H1, manage on `InpMgmtTF` (2026-06-14)
Added `InpMgmtTF` (gold M15, BTC H1); all six legs now **chart on H1** so entry is
native to the chart (matches live `CopyTickVolume(H1)`). Re-validated Model 1:

| leg | base-fix M1 | **§3.2 M1** | Δ |
|---|---|---|---|
| GoldGeo17 | 120.9 | 119.9 | −1.0 |
| GoldS210  | 153.4 | 152.2 | −1.2 |
| GoldShield| 35.4  | 35.4  | 0 |
| BtcGF/BtcPG/BtcShield | 189.9/39.6/16.0 | **189.9/39.6/16.0** | 0 |

**Finding:** under Model 1 charting gold on H1 changes ~nothing (the tester builds
H1 from M1 regardless of chart TF), so the gold entry-set drift is **NOT** H5 volume
reconstruction — it is **bar-granularity / fill-path**. §3.2 is still correct (zero
regression; matches live; required for a faithful Model-4 run).

## Model 4 (real ticks) ≈ Model 1, and the M1-data blocker (2026-06-14)
Ran the two extreme legs under **Model 4 (every tick, real ticks)** over the full
window — both reproduce Model 1:

| leg | oracle | tester M1 | **tester M4** | M4 retained | M4 minR |
|---|---|---|---|---|---|
| BtcGF    | 241.3 | 189.9 | **188.3** | 78% | −1.11 |
| GoldS210 | 259.5 | 152.2 | **147.4** | 57% | **−2.01** |

**Model 1 ≈ Model 4** (BtcGF 0.8% apart, GoldS210 3.2%), identical op-counts/win% →
the **fast Model-1 headless tester is a faithful full-window proxy for real ticks**;
no need to iterate on slow Model-4 runs. Both are reproducible headless over the whole
2.2 yr (`ck_batch.ps1 -Model 1|4`).

**The residual is the Python oracle being too optimistic, two parts:**
1. **Loss overshoot** — the oracle floors every loss at exactly −1R (equity-0); the
   tester slips/gaps *past* the synthetic margin-line SL, realizing **−1.1 to −2.0R**.
   On a 20%-win leg (~300 losers) an average −0.2R overshoot ≈ −60R. Big.
2. **Bar-path optimism on winners/stacks** — H1/M15 bars can't see the intrabar path,
   so the oracle is too generous about which winners reach TP/trail and how big late
   stacked adds get.

**§3.3 blocker:** an M1-intrabar Python engine needs full-window M1, but the exported
M1 CSVs only cover the last **~2–3 months** (terminal `copy_rates_from_pos` cache:
XAU M1 Mar–Jun 2026, BTC M1 Apr–Jun 2026). The broker *has* full M1 (the Model-1
tester uses it), but exporting it to CSV is non-trivial. → strategic fork (see below).

## Where this leaves the plan (the fork)
Base-fix + §3.2 closed the gold-specific **bug**; the tester (truth) now retains
**57–78%** of the oracle, the rest being the oracle's bar-level optimism (loss
overshoot + path). To get research onto a trustworthy footing:
- **A — tester-as-truth:** use the headless Model-1 tester directly as the engine for
  the §3.6 king re-search (slower per run, but definitive & full-window; Model 1 proven
  ≈ Model 4). Drops the "<5% Python match" sub-goal as impractical given the M1 blocker.
- **B — build §3.3:** re-export full-window M1 (fight the terminal cache), then build the
  M1-intrabar Python engine to match the tester. Highest-fidelity fast engine; two hard
  sub-problems first.
- **C — calibrated correction:** build/validate the M1-intrabar engine on the ~2–3 mo
  where M1 exists, derive a principled loss-overshoot + path correction, apply to the
  full-window bar oracle. Pragmatic; some fudge risk (the plan warns against fudge).

## DECISION — Path A + NBP (2026-06-14, user)
**Chose A (tester-as-truth).** And a key correction from the user on "loss overshoot":
it is **not** real — in live high-leverage trading a liquidation briefly shows e.g.
−1.3R, but the broker's **negative-balance protection** instantly zeroes the account,
so the realized loss is **capped at −1R** (the account *is* 1R in the EA-dumb model).
The tester only shows −2R because it runs on a big deposit (NBP never triggers).

→ **Standard accounting (D5): clamp every op `max(R, −1)`.** Applied, this:
- makes **Model 1 ≡ Model 4** (BtcGF 191.0/190.2, GoldS210 157.4/157.5 — the overshoot
  was their *only* divergence), so the fast Model-1 tester is the definitive engine;
- is the **live** number (totR/DD/RF/segments/growth all use clamped R).

The NBP-clamped tester fingerprints (the *real* king legs — note they're weaker & less
robust than the oracle, which is the whole reason to re-search):

| leg | nbpR | win% | maxDD | RF | segs | 1op | vs oracle |
|---|---|---|---|---|---|---|---|
| BtcGF      | 191.0 | 23.4 | 18.8 | 10.2 | 5/6 | 50% | 0.79 |
| BtcPG      |  40.6 | 28.6 | 25.9 |  1.6 | 4/6 |  8% | 0.49 |
| BtcShield  |  16.5 | 46.4 | 20.3 |  0.8 | 3/6 |  8% | 0.36 |
| GoldGeo17  | 124.3 | 27.7 | 19.9 |  6.3 | 5/6 | 33% | 0.71 |
| GoldS210   | 157.4 | 20.6 | 33.4 |  4.7 | 3/6 | 57% | 0.61 |
| GoldShield |  37.7 | 37.6 | 16.0 |  2.4 | 4/6 |  5% | 0.46 |

**Tooling now standard:** `tester_truth.py` (canonical NBP reader/fingerprint),
`ck_batch.ps1 -Model 1` (the research engine; reports `nbpR`).

## CAN PYTHON MATCH THE TESTER? — decomposition says "yes, it's a DATA problem" (2026-06-14)
User reopened the question. Decomposed each leg's oracle−tester gap (NBP on both,
post-base-fix) into matched-op R diff vs entry-set differences (`/tmp/decomp.py`):

| leg | gap | **matched-op diff** | tester's extra ops (R) | winners tester missed (R) |
|---|---|---|---|---|
| GoldGeo17  | 53.7 | **0.9**  | +36 = −32 | 19 = +21 |
| BtcGF      | 51.6 | **0.3**  | +40 = +30 | 35 = +81 |
| GoldShield | 47.9 | **3.2**  | +56 = −14 | 46 = +30 |
| BtcShield  | 29.4 | **−12.3**| +42 = −24 | 31 = +18 |
| BtcPG      | 41.7 | **−4.7** | +66 = −38 | 47 = +9  |
| GoldS210   | 110.7| **59.5** | +39 = −39 | 16 = +12 |

**For 5 of 6 legs the matched ops agree within ±12R — Python's per-op physics already
match the tester.** The gap is overwhelmingly the **entry set**: with `max_conc=1`, the
tester closes ops intrabar, frees the single slot sooner, and catches 5–23 *more*
breakouts per leg (which are net losers), while the two engines catch different trends.
Only **GoldS210** has a real per-op disagreement (+59.5R, its big geofloor stacks
realize less on the intrabar path). So the residual is **intrabar entry/exit timing**,
needing **M1** resolution — a *data* gap, not a *modeling* gap. The broker has full M1;
our export just capped at ~2–3 months.

→ **Reopened plan (the M1 route, primary; Path A = fallback):**
1. **Extract full-window M1** via `Scripts/DumpHistory.mq5` (user's idea: an in-terminal
   MQL5 dumper writes CSV, bypassing the Python `copy_rates_from_pos` cap; CopyRates by
   date range forces the download). Pull XAUUSDc + BTCUSDc M1 for the full 2.2yr.
2. **Build the M1-intrabar Python engine** (management cadence on M15/H1, but exit-check
   /entry-fill stepped at M1) — prototype it first on the ~2–3 mo of M1 we already have,
   confirm it reproduces the tester there, then run full-window.
3. **Verify Python ≈ tester** (NBP, per `tester_truth.py`). If yes → Python is the FAST
   trustworthy engine again; do §3.6 in Python. If M1 truly can't be extracted → fall
   back to **Path A** (tester-as-truth, already standardized).

**NBP (D5) stands regardless** — it's the correct live accounting and what Python must be
compared against.

## DATA PARITY — the rule for the M1 route (user, 2026-06-14)
Any Python-vs-tester comparison is only valid if **both consume identical input series**;
otherwise we'd be measuring data mismatch, not engine fidelity. In the tester's **Model 1**
*everything* is built from **M1**: the H1 bars (incl. their `tick_volume`, which drives the
V-pattern ENTRY), the M15 management bars, and the simulated intrabar path. Therefore:
- **Dump M1 as the single source of truth** (`DumpHistory.mq5` mode=BARS, TF=M1) and in
  Python **derive H1 & M15 from that M1 by aggregation** — H1 `tick_volume` = **sum of the
  M1 tick_volumes**. **Do NOT** keep reading a separately-pulled `XAUUSDc_H1.csv`: its
  `tick_volume` can differ from the M1-sum the tester uses → different V-pattern triggers →
  different entry set. *This is a prime suspect for the current entry-set gap* (the gap is
  ~entirely the entry set, and even native-H1 BTC's entries differ) — verify by aggregating
  dumped M1→H1 and diffing `tick_volume` vs the old H1 CSV.
- **Intrabar exit/entry stepped at M1** (each M1 bar's H/L vs SL/TP). Within one minute both
  SL and TP are ~never hit together, so MT5's exact M1→tick ordering rarely matters; M1-bar
  resolution captures essentially all the intrabar path that drives the entry-set gap.
- **Fallback — ticks (`DumpHistory.mq5` mode=TICKS)** for exact **Model-4** parity if M1
  proves insufficient. From ticks, H1 `tick_volume` = real tick count/hour (= Model 4).
  Bigger/slower; only if needed.

So the build order next session: dump M1 → **derive H1/M15 from it** → confirm M1 spans the
full window AND M1→H1 `tick_volume` reconciles → build the M1-intrabar engine on this shared
data → compare to tester **Model 1** (same M1 source) under NBP. Same data in, same ops out.
