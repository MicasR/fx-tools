"""
conc_engine.py — CONCURRENT operations engine (2026-06-12).

Current run_tf is one-operation-at-a-time: a new H1 breakout that fires while an
op is open is DROPPED.  Here, new breakouts open NEW operations on fresh accounts
(up to max_conc, per a direction policy) while existing ops keep stacking and
running.  Each op = own 1R stake, own -1R floor, own TP/SL.  This tests harvesting
the dropped-signal stream via concurrency.

  stack    : True  -> base + SMA-bounce stacking (geo1.7 / s210);
             False -> shield mode (single position, no adds).
  max_conc : max simultaneously-open ops (1 == run_tf one-at-a-time).
  conc_dir : 'same' / 'opp' / 'both' -- a new op may open only if its direction
             is same-as / opposite-to / either, relative to the most-recently
             opened still-open op (flat -> always allowed).

Reuses all of pyramid_engine's primitives.  Returns ops in run_tf's 6-tuple
format + the frame arrays (tm,H,L) so callers can compute stress gaps.
"""
import glob
import numpy as np
import pandas as pd
from pyramid_engine import (SPECS, VOL_MIN, VOL_STEP, VOL_MAX, qfloor,
                            margin_line, lot_to_pin, _size_add, h1_events)


def run_tf_conc(sym="XAU", tf="M15", smaP=7, slowP=0, sizing="proggeo", mult=1.0,
                prog_step=1.7, unit="base", tp_R=3.0, lev=2000.0, stack=True,
                max_conc=1, conc_dir="same", cap0=1000.0, risk_frac=0.01,
                half=0.5, buf=0.0, ml_target=3.0, gb=1.0):
    sp = SPECS[sym]; TR, MPL0, COST = sp["TR"], sp["MPL"], sp["cost"]
    MPL = MPL0 * 400.0 / lev if lev > 0 else 0.0
    m = pd.read_csv(glob.glob(f"data/*{sym}*_{tf}.csv")[0], parse_dates=["time"])
    if stack:
        m["sma"] = m["close"].rolling(smaP).mean()
    if slowP > 0:
        m["slow"] = m["close"].rolling(slowP).mean()
    m = m.dropna().reset_index(drop=True)
    tm = m["time"].to_numpy()
    O, H, L, C = (m[c].to_numpy() for c in ("open", "high", "low", "close"))
    SMA = m["sma"].to_numpy() if stack else None
    SLOW = m["slow"].to_numpy() if slowP > 0 else None
    n = len(m)

    evs = h1_events(sym, m["time"].iloc[0])
    ev_at = {}
    for e in evs:
        j = int(np.searchsorted(tm, np.datetime64(e[0])))
        if 0 <= j < n:
            ev_at.setdefault(j, []).append(e)

    results, ops_open = [], []

    def close(op, k, xp, reason):
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xp - e) * l * TR for e, l in op["pos"])
        cost = sum(COST * TR * l for _, l in op["pos"])
        res = max(floating - cost, -E0)
        results.append((op["k0"], k, res / E0, len(op["pos"]), reason,
                        dict(dir=dd, E0=E0, r0=op["r0"], e0=op["e0"], log=list(op["log"]))))

    def do_add(op, k, P, anchor, r0, ml):
        base = op["pos"][0][1]
        ulot = VOL_MIN if unit == "min" else base
        x = _size_add(sizing, op["pos"], P, anchor, op["dir"], op["E0"], TR, MPL,
                      ml_target, gb, r0, ml, mult, prog_step, ulot, 0.0, buf)
        x = min(x, VOL_MAX)
        if MPL > 0:
            Lb = sum(l for _, l in op["pos"])
            eq = op["E0"] + sum(op["dir"] * (P - e) * l * TR for e, l in op["pos"])
            x = min(x, qfloor(max(0.0, eq / MPL - Lb)))
        if x >= VOL_STEP:
            op["pos"].append((P, x)); op["last"] = P
            op["log"].append((k, P, x))

    for k in range(n):
        # 1. existing ops: exits first, then bounce-stacking adds
        for op in list(ops_open):
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
            tp = op["e0"] + dd * tp_R * r0
            if (L[k] <= ml) if dd == 1 else (H[k] >= ml):
                close(op, k, ml, "SL"); ops_open.remove(op); continue
            if (H[k] >= tp) if dd == 1 else (L[k] <= tp):
                close(op, k, tp, "TP"); ops_open.remove(op); continue
            fav = dd * ((H[k] if dd == 1 else L[k]) - op["e0"]) / r0
            if fav >= half:
                op["ok"] = True
            if stack and op["ok"]:
                wrong = (C[k] < SMA[k]) if dd == 1 else (C[k] > SMA[k])
                back  = (C[k] >= SMA[k]) if dd == 1 else (C[k] <= SMA[k])
                if wrong:
                    op["arm_b"] = True
                    cur = op.get("anc_b"); ext = L[k] if dd == 1 else H[k]
                    op["anc_b"] = ext if cur is None else (min(cur, ext) if dd == 1 else max(cur, ext))
                elif back and op.get("arm_b"):
                    op["arm_b"] = False
                    if (C[k] > op["last"]) if dd == 1 else (C[k] < op["last"]):
                        anc = SLOW[k] if slowP > 0 else op.get("anc_b", ml)
                        do_add(op, k, C[k], anc, r0, ml)
                    op["anc_b"] = None
        # 2. new H1 breakouts open NEW ops (cap + direction policy)
        for e in ev_at.get(k, []):
            if len(ops_open) >= max_conc:
                break
            d, entry, sl, rng = e[1], e[2], e[3], e[4]
            if rng <= 0:
                continue
            ref = ops_open[-1]["dir"] if ops_open else None
            if ref is not None:
                if conc_dir == "same" and d != ref:
                    continue
                if conc_dir == "opp" and d == ref:
                    continue
            E0 = risk_frac * cap0
            lot0 = max(lot_to_pin([], entry, entry - d * rng, d, E0, TR, MPL), VOL_MIN)
            if MPL > 0:
                lot0 = min(lot0, qfloor(E0 / MPL))
            lot0 = min(lot0, VOL_MAX)
            ops_open.append(dict(dir=d, r0=rng, e0=entry, k0=k, E0=E0,
                                 pos=[(entry, lot0)], ok=(half <= 0), last=entry,
                                 log=[(k, entry, lot0)], arm_b=False, anc_b=None))

    for op in ops_open:
        close(op, n - 1, C[n - 1], "END")
    return results, tm, H, L, n
