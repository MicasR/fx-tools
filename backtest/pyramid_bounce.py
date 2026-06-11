"""
[!] SUPERSEDED by pyramid_engine.py (2026-06-11).  This file's ORIGINAL results
were INVALID: the operation-open logic opened a stale QUEUED breakout at its old
entry price after a trade closed (look-ahead phantom profit), inflating the no-add
baseline ~7x (BTC 78.8R -> 10.7R).  That bug is fixed below (open only while flat,
never re-open stale events).  The validated engine + the correct management
(confluence adds + the gate) live in pyramid_engine.py.  Kept for the audit trail.

Bounce-add compound pyramid — M1 50/20-SMA bounce as the ADD trigger.

Question this answers (user's reframe): *what add-trigger lets us stack the MOST
positions SAFELY, so winning operations compound more R?*  Safety is structural:
the operations account holds exactly 1R, so the broker liquidation floors every
loss at -1R no matter how many positions we stack.  The only open question is
whether the extra positions CAPTURE profit -- the last test failed because
trail-step adds entered late near the top.  Here adds are timed to PULLBACKS (a
50-SMA bounce on M1), so they enter cheap.

Mechanic (both gold & BTC), built on the H1 champion with edits:
  - Base entry: H1 V-pattern breakout (unchanged).  R = trigger range.  TP = 3R.
  - NO chandelier trail.  Stop = the book's MARGIN LINE (equity-0 / liquidation).
  - Margin line trails to **1R below the current price**, ratcheting up only; each
    add re-pins the aggregate stop-out there (funded by earlier legs' float).  So
    a ~1R pullback from the running high liquidates the ops account = -1R.
  - ADDS: once price >= 0.5R in profit, every M1 50-SMA(close) BOUNCE in the op's
    direction (close on the wrong side of the SMA, then close back across) adds a
    position, sized margin-line-max to the (ratcheted) 1R-below line, cap vol 200.
  - Two-account geometric bankroll: each op funds 1% of running total capital.

Data: real M1 (terminal cache, ~62d BTC / ~92d XAU) -- short, one regime; this
phase tests the MECHANIC (does it stack positions profitably & hold the floor?),
not long-run robustness.  Compared head-to-head vs adds-OFF on the same window.

Run:  python pyramid_bounce.py
"""
import glob
import numpy as np
import pandas as pd
import signals as sg
from book_sim import entry_events
from pyramid_compound import TR, MPL, VOL_MIN, VOL_STEP, VOL_MAX, COST_PX, \
    add_to_pin_margin_line, margin_line_price


def h1_events(sym, m1_start):
    """H1 V-pattern breakout events as (t_entry, dir, entry, sl, rng), within window."""
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= (m1_start - pd.Timedelta(days=5))].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    t = d["time"].to_numpy()
    evs, H, L, C, n = entry_events(d)
    out = []
    for e in evs:
        te = t[e["ej"]]
        if te >= np.datetime64(m1_start):
            out.append((te, e["d"], e["entry"], e["sl"], e["rng"]))
    out.sort(key=lambda x: x[0])
    return out


def run(sym, smaP, add_on=True, cap0=1000.0, risk_frac=0.01, half_gate=0.5, tp_R=3.0, gb=1.0):
    m1 = pd.read_csv(glob.glob(f"data/*{sym}*_M1.csv")[0], parse_dates=["time"])
    m1["sma"] = m1["close"].rolling(smaP).mean()
    m1 = m1.dropna().reset_index(drop=True)
    t   = m1["time"].to_numpy()
    H, L, C, S = (m1[c].to_numpy() for c in ("high", "low", "close", "sma"))
    n = len(m1)
    evs = h1_events(sym, m1["time"].iloc[0])

    ops, curve, capital = [], [], cap0
    op = None
    ei = 0                                   # event pointer
    peak_riskR = 0.0

    def close(reason, k, xprice):
        nonlocal capital, op
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xprice - e) * lot * TR for e, lot in op["pos"])
        cost = sum(COST_PX * TR * lot for _, lot in op["pos"])
        res = max(floating - cost, -E0)
        capital += res
        ops.append((op["k0"], k, res / E0, len(op["pos"]), reason))
        curve.append(capital); op = None

    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line_price(op["pos"], dd, op["E0"], 0.0)
            tp = op["e0"] + dd * tp_R * r0

            stop_hit = (L[k] <= ml) if dd == 1 else (H[k] >= ml)
            tp_hit   = (H[k] >= tp) if dd == 1 else (L[k] <= tp)
            if stop_hit:
                close("SL", k, ml)
            elif tp_hit:
                close("TP", k, tp)
            else:
                fav = dd * (H[k] - op["e0"]) / r0 if dd == 1 else dd * (L[k] - op["e0"]) / r0
                if fav >= half_gate:
                    op["armed_ok"] = True
                # --- 50-SMA bounce state machine (only while armed past 0.5R) ---
                wrong = (C[k] < S[k]) if dd == 1 else (C[k] > S[k])
                back  = (C[k] >= S[k]) if dd == 1 else (C[k] <= S[k])
                if wrong:
                    op["armed_bounce"] = True
                elif back and op["armed_bounce"] and op.get("armed_ok") and add_on:
                    op["armed_bounce"] = False
                    P = C[k]
                    target = P - dd * gb * r0                  # gb*R below current price
                    eff_S = max(ml, target) if dd == 1 else min(ml, target)   # ratchet only
                    if sum(l for _, l in op["pos"]) < VOL_MAX:
                        x = add_to_pin_margin_line(op["pos"], P, eff_S, dd, op["E0"], 0.0)
                        if x >= VOL_STEP:
                            op["pos"].append((P, x))
                # true MTM drawdown: worst intrabar floating loss vs deposit, in R
                adverse = L[k] if dd == 1 else H[k]
                eq_adv = op["E0"] + sum(dd * (adverse - e) * lot * TR for e, lot in op["pos"])
                peak_riskR = max(peak_riskR, (op["E0"] - eq_adv) / op["E0"])

        # consume every H1 event that has fired by this bar; open one ONLY while
        # flat (events firing during a trade are skipped, never re-opened stale).
        # [BUGFIX 2026-06-11] the old code opened the oldest QUEUED event at its
        # stale entry price after a trade closed -> look-ahead phantom profit.
        while ei < len(evs) and evs[ei][0] <= t[k]:
            te, dd, entry, sl, rng = evs[ei]; ei += 1
            if op is None and rng > 0:
                E0 = risk_frac * capital
                lot0 = min(max(add_to_pin_margin_line([], entry, entry - dd * rng,
                                                       dd, E0, 0.0), VOL_MIN), VOL_MAX)
                op = dict(dir=dd, r0=rng, e0=entry, k0=k, E0=E0, pos=[(entry, lot0)],
                          armed_bounce=False, armed_ok=(half_gate <= 0))

    if op is not None:
        close("END", n - 1, C[n - 1])
    return ops, curve, peak_riskR, n


def stat(ops, curve, peak_riskR, cap0=1000.0):
    R = np.array([o[2] for o in ops]) if ops else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    npos = [o[3] for o in ops]
    return dict(n=len(R), totR=R.sum(), avgR=R.mean(), pf=(w / l if l > 0 else 9.99),
                maxdd=dd, win=100*np.mean(R > 0), minR=R.min(),
                avgpos=np.mean(npos) if npos else 0, maxpos=max(npos) if npos else 0,
                final=curve[-1] if curve else cap0, riskR=peak_riskR)


def show(sym):
    m1 = pd.read_csv(glob.glob(f"data/*{sym}*_M1.csv")[0], parse_dates=["time"])
    days = (m1["time"].iloc[-1] - m1["time"].iloc[0]).days
    print(f"\n================ {sym}  bounce-add (real M1, {days}d, {len(m1):,} bars) ============")
    print(f"  {'variant':<16}{'ops':>4}{'totR':>8}{'avgR':>7}{'PF':>6}{'maxDD':>7}{'win%':>6}"
          f"{'avgPos':>7}{'mxPos':>6}{'minR':>7}{'pkRisk':>7}{'final$':>9}")
    for lbl, on, P in [("no-add (base)", False, 50), ("bounce SMA50", True, 50),
                       ("bounce SMA20", True, 20)]:
        ops, curve, pr, n = run(sym, P, add_on=on)
        s = stat(ops, curve, pr)
        print(f"  {lbl:<16}{s['n']:>4}{s['totR']:>8.1f}{s['avgR']:>7.2f}{s['pf']:>6.2f}"
              f"{s['maxdd']:>7.1f}{s['win']:>6.1f}{s['avgpos']:>7.1f}{s['maxpos']:>6.0f}"
              f"{s['minR']:>7.2f}{s['riskR']:>7.2f}{s['final']:>9.0f}")


if __name__ == "__main__":
    show("BTC")
    show("XAU")
