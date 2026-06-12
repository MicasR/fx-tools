"""
Unified stacking engine — confluence + 50-SMA-bounce adds, gate, margin-level sizing.

Fixes the two omissions that (per the user) invalidated the earlier compound &
bounce tests:
  (1) THE GATE  — a position is only added when its entry is BEYOND the last
      (worst) position's entry: higher for longs, lower for sells.  Strictly
      rising/falling ladder; never average into the worst leg.
  (2) CONFLUENCE MANAGEMENT — same-direction H1 breakout signals that fire while
      an operation is open are no longer ignored; they ADD, and on a confluence
      add the margin (liquidation) price is pinned to the NEW signal's STRUCTURE
      low (long) / high (short).

Operation: H1 V-pattern breakout base, 1R-risk, structure SL = entry∓R, TP3R, NO
trail.  Two add triggers, both gated and only after price >= 0.5R:
  - confluence add  -> size to pin the book's liquidation price to the new
                       signal's structure low/high.
  - 50-SMA bounce   -> size to bring MARGIN LEVEL (equity incl. float / used
                       margin) to a target (swept 150..2000%).
Floor: broker stop-out 0% -> liquidation at equity 0 -> every loss = -1R (the
ops account).  Two-account geometric bankroll: each op stakes 1% of total capital.

Real M1 only (terminal cache ~62d BTC / ~92d XAU): tests the MECHANIC.

Run:  python pyramid_engine.py
"""
import glob
import numpy as np
import pandas as pd
import signals as sg
from book_sim import entry_events

# per-symbol live specs (USD): TR = $ P&L per 1.0 price unit per lot; MPL = margin/lot
SPECS = {
    "BTC": dict(TR=0.01, MPL=1.59, cost=18.0),
    "XAU": dict(TR=1.00, MPL=2.095, cost=0.50),
}
VOL_MIN, VOL_STEP, VOL_MAX = 0.01, 0.01, 200.0


def qfloor(x):
    return np.floor(x / VOL_STEP + 1e-9) * VOL_STEP


def margin_line(pos, dd, E0, TR, MPL):
    """Price where equity hits 0 (liquidation), from the book only."""
    L = sum(l for _, l in pos)
    if L <= 0:
        return None
    we = sum(e * l for e, l in pos) / L
    return we - dd * E0 / (TR * L)


def lot_to_pin(pos, P, S, dd, E0, TR, MPL):
    """Lot to add at price P so the book's liquidation price becomes S (equity-0)."""
    L = sum(l for _, l in pos)
    A = sum(dd * (S - e) * l for e, l in pos)
    denom = TR * dd * (S - P)
    if denom >= 0:
        return 0.0
    x = (-E0 - TR * A) / denom
    return max(0.0, qfloor(min(x, VOL_MAX)))         # per-position cap; total uncapped (volume_limit=0)


def lot_to_mlevel(pos, P, dd, E0, TR, MPL, ml_target):
    """Lot to add at price P so margin level (equity@P / margin) == ml_target."""
    L = sum(l for _, l in pos)
    equity = E0 + sum(dd * (P - e) * l * TR for e, l in pos)
    x = equity / (MPL * ml_target) - L
    return max(0.0, qfloor(min(x, VOL_MAX)))         # per-position cap; total uncapped (volume_limit=0)


def h1_events(sym, m1_start):
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= (m1_start - pd.Timedelta(days=5))].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    t = d["time"].to_numpy()
    evs, H, L, C, n = entry_events(d)
    return [(t[e["ej"]], e["d"], e["entry"], e["sl"], e["rng"]) for e in evs]


def run(sym, triggers=("conf", "bounce"), ml_target=3.0, smaP=50,
        cap0=1000.0, risk_frac=0.01, half=0.5, tp_R=3.0):
    sp = SPECS[sym]; TR, MPL, COST = sp["TR"], sp["MPL"], sp["cost"]
    m1 = pd.read_csv(glob.glob(f"data/*{sym}*_M1.csv")[0], parse_dates=["time"])
    m1["sma"] = m1["close"].rolling(smaP).mean()
    m1 = m1.dropna().reset_index(drop=True)
    tm = m1["time"].to_numpy()
    H, L, C, SMA = (m1[c].to_numpy() for c in ("high", "low", "close", "sma"))
    n = len(m1)

    evs = h1_events(sym, m1["time"].iloc[0])
    ev_at = {}
    for e in evs:
        j = int(np.searchsorted(tm, np.datetime64(e[0])))
        if 0 <= j < n:
            ev_at.setdefault(j, []).append(e)

    ops, curve, capital, op, peak_mtm = [], [], cap0, None, 0.0

    def close(reason, k, xp):
        nonlocal capital, op
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xp - e) * l * TR for e, l in op["pos"])
        cost = sum(COST * TR * l for _, l in op["pos"])
        res = max(floating - cost, -E0)
        capital += res
        ops.append((op["k0"], k, res / E0, len(op["pos"]), reason))
        curve.append(capital); op = None

    def gate_ok(price):
        return (price > op["last"]) if op["dir"] == 1 else (price < op["last"])

    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
            tp = op["e0"] + dd * tp_R * r0
            stop = (L[k] <= ml) if dd == 1 else (H[k] >= ml)
            tph  = (H[k] >= tp) if dd == 1 else (L[k] <= tp)
            if stop:
                close("SL", k, ml)
            elif tph:
                close("TP", k, tp)
            else:
                fav = dd * ((H[k] if dd == 1 else L[k]) - op["e0"]) / r0
                if fav >= half:
                    op["ok"] = True
                # confluence adds (same-dir H1 signals firing this minute)
                if "conf" in triggers:
                    for e in ev_at.get(k, []):
                        if e[1] == dd and op["ok"] and gate_ok(e[2]) \
                                and sum(l for _, l in op["pos"]) < VOL_MAX:
                            x = lot_to_pin(op["pos"], e[2], e[3], dd, op["E0"], TR, MPL)
                            if x >= VOL_STEP:
                                op["pos"].append((e[2], x)); op["last"] = e[2]
                # bounce adds (50-SMA cross-back), sized to margin-level target
                if "bounce" in triggers:
                    wrong = (C[k] < SMA[k]) if dd == 1 else (C[k] > SMA[k])
                    back  = (C[k] >= SMA[k]) if dd == 1 else (C[k] <= SMA[k])
                    if wrong:
                        op["armed"] = True
                    elif back and op["armed"]:
                        op["armed"] = False
                        if op["ok"] and gate_ok(C[k]) \
                                and sum(l for _, l in op["pos"]) < VOL_MAX:
                            x = lot_to_mlevel(op["pos"], C[k], dd, op["E0"], TR, MPL, ml_target)
                            if x >= VOL_STEP:
                                op["pos"].append((C[k], x)); op["last"] = C[k]
                adv = L[k] if dd == 1 else H[k]
                eq = op["E0"] + sum(dd * (adv - e) * l * TR for e, l in op["pos"])
                peak_mtm = max(peak_mtm, (op["E0"] - eq) / op["E0"])

        if op is None:
            for e in ev_at.get(k, []):
                dd, entry, sl, rng = e[1], e[2], e[3], e[4]
                if rng <= 0:
                    continue
                E0 = risk_frac * capital
                lot0 = max(lot_to_pin([], entry, entry - dd * rng, dd, E0, TR, MPL), VOL_MIN)
                op = dict(dir=dd, r0=rng, e0=entry, k0=k, E0=E0, pos=[(entry, min(lot0, VOL_MAX))],
                          armed=False, ok=(half <= 0), last=entry)
                break

    if op is not None:
        close("END", n - 1, C[n - 1])
    return ops, curve, peak_mtm, n


def _size_add(sizing, pos, P, anchor, dd, E0, TR, MPL, ml_target, gb, r0, ml_now,
              mult=1.0, prog_step=0.0, unit_lot=VOL_MIN, cap_lot=0.0, buf=0.0):
    """Lot for a bounce/candle add under one sizing rule (gate/cap handled by caller).
    minlot/prog/proggeo are expressed in `unit_lot` units (VOL_MIN, or the base lot
    for relative sizing).  buf > 0 (price units) = a minimum BUFFER: the pinned
    liquidation line can never sit closer than `buf` to the current price, so a
    slow SMA hugging price can't demand a margin-maxed lot (caps the pin-family)."""
    cap = lambda x: (min(x, cap_lot) if cap_lot > 0 else x)       # ceiling on a single add
    flr = lambda x: (max(VOL_MIN, qfloor(cap(x))) if x > 0 else 0.0)   # cap, then below-min -> use min
    def floored_anchor(a):                                        # keep line >= buf from price
        return (min(a, P - buf) if dd == 1 else max(a, P + buf)) if buf > 0 else a
    if sizing == "minlot":
        return flr(unit_lot * mult)
    if sizing == "prog":                          # arithmetic: (mult + k*step) x unit, k = add index
        k = len(pos) - 1
        return flr(unit_lot * (mult + k * prog_step))
    if sizing == "proggeo":                       # geometric: mult * step^k x unit
        k = len(pos) - 1
        return flr(unit_lot * mult * (prog_step ** k))
    if sizing == "mlevel":
        return lot_to_mlevel(pos, P, dd, E0, TR, MPL, ml_target)
    if sizing == "pinlast":                       # pin liquidation to last bounce/contrary low/high
        S = max(ml_now, anchor) if dd == 1 else min(ml_now, anchor)
        return lot_to_pin(pos, P, S, dd, E0, TR, MPL)
    if sizing == "pin1R":                         # gb*R below current price
        tgt = P - dd * gb * r0
        S = max(ml_now, tgt) if dd == 1 else min(ml_now, tgt)
        return lot_to_pin(pos, P, S, dd, E0, TR, MPL)
    if sizing == "geopin":                        # geometric ramp, each add capped so the
        k = len(pos) - 1                          # line never crosses the anchor
        g = flr(unit_lot * mult * (prog_step ** k))
        S = floored_anchor(max(ml_now, anchor) if dd == 1 else min(ml_now, anchor))
        return min(g, lot_to_pin(pos, P, S, dd, E0, TR, MPL))
    if sizing == "geofloor":                      # geometric ramp OR pin-to-anchor,
        k = len(pos) - 1                          # whichever is bigger
        g = flr(unit_lot * mult * (prog_step ** k))
        S = floored_anchor(max(ml_now, anchor) if dd == 1 else min(ml_now, anchor))
        return max(g, lot_to_pin(pos, P, S, dd, E0, TR, MPL))
    if sizing == "pinfrac":                       # pin the line gb of the way line -> price
        S = ml_now + gb * (P - ml_now)
        return lot_to_pin(pos, P, S, dd, E0, TR, MPL)
    return 0.0


def _rsi(close, period):
    d = np.diff(close, prepend=close[0])
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1/period, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1/period, adjust=False).mean().to_numpy()
    return 100 - 100 / (1 + up / np.where(dn == 0, 1e-9, dn))


def run_tf(sym, tf="M15", triggers=("bounce",), sizing="mlevel", ml_target=3.0,
           smaP=50, slowP=0, gb=1.0, conf=False, mult=1.0, prog_step=2.0, unit="min",
           cap=0.0, grid_R=0.5, rsiP=14, rsi_os=30.0, rsi_ob=70.0, cap0=1000.0,
           risk_frac=0.01, half=0.5, tp_R=3.0, lev=400.0, buf=0.0):
    """General stacking engine on a chosen intrabar timeframe (M1/M5/M15).
    Base = H1 breakout (1R, TP3R, no trail).  Add triggers (any of):
      'bounce'  -> SMA(close) cross-back, anchor = wrong-side extreme;
      'candle'  -> confluent candle after a contrary candle, anchor = contrary extreme.
    'conf' (separate flag) -> same-dir H1 breakout adds, pinned to its structure.
    All adds gated: beyond the last/worst leg AND price >= half*R.  Sizing per
    `sizing` (minlot/mlevel/pinlast/pin1R/geopin/pinfrac).  slowP > 0 -> a slow
    SMA replaces the trigger anchor for pin-family sizing (dual-SMA: fast = when
    to add, slow = where the margin line goes).  Floor: equity-0 stop-out = -1R.
    lev = account leverage; SPECS margins were measured at ~1:400, so the free-
    margin check scales by 400/lev.  lev=0 -> unlimited (check disabled)."""
    sp = SPECS[sym]; TR, MPL, COST = sp["TR"], sp["MPL"], sp["cost"]
    MPL = MPL * 400.0 / lev if lev > 0 else 0.0
    m = pd.read_csv(glob.glob(f"data/*{sym}*_{tf}.csv")[0], parse_dates=["time"])
    if "bounce" in triggers:
        m["sma"] = m["close"].rolling(smaP).mean()
    if slowP > 0:
        m["slow"] = m["close"].rolling(slowP).mean()
    m = m.dropna().reset_index(drop=True)
    tm = m["time"].to_numpy()
    O, H, L, C = (m[c].to_numpy() for c in ("open", "high", "low", "close"))
    SMA = m["sma"].to_numpy() if "bounce" in triggers else None
    SLOW = m["slow"].to_numpy() if slowP > 0 else None
    RSI = _rsi(C, rsiP) if "rsi" in triggers else None
    n = len(m)

    evs = h1_events(sym, m["time"].iloc[0])
    ev_at = {}
    for e in evs:
        j = int(np.searchsorted(tm, np.datetime64(e[0])))
        if 0 <= j < n:
            ev_at.setdefault(j, []).append(e)

    ops, curve, capital, op, peak = [], [], cap0, None, 0.0

    def close(reason, k, xp):
        nonlocal capital, op
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xp - e) * l * TR for e, l in op["pos"])
        cost = sum(COST * TR * l for _, l in op["pos"])
        res = max(floating - cost, -E0)
        capital += res
        ops.append((op["k0"], k, res / E0, len(op["pos"]), reason,
                    dict(dir=dd, E0=E0, r0=op["r0"], e0=op["e0"], log=list(op["log"]))))
        curve.append(capital); op = None

    def gate(price):
        return (price > op["last"]) if op["dir"] == 1 else (price < op["last"])

    def add(P, anchor, r0, ml):
        base = op["pos"][0][1]
        ulot = VOL_MIN if unit == "min" else base                 # base-lot-relative if unit='base'
        clot = cap * base if cap > 0 else 0.0                     # ceiling = cap fraction of base lot
        x = _size_add(sizing, op["pos"], P, anchor, op["dir"], op["E0"], TR, MPL,
                      ml_target, gb, r0, ml, mult, prog_step, ulot, clot, buf)
        x = min(x, VOL_MAX)                                       # per-position cap (each add = own position)
        # broker check: the add's margin must fit in free margin (equity incl. float
        # minus used margin) or the order is rejected
        if MPL > 0:
            Lb = sum(l for _, l in op["pos"])
            eq = op["E0"] + sum(op["dir"] * (P - e) * l * TR for e, l in op["pos"])
            x = min(x, qfloor(max(0.0, eq / MPL - Lb)))
        if x >= VOL_STEP:
            op["pos"].append((P, x)); op["last"] = P
            op["log"].append((k, P, x))

    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
            tp = op["e0"] + dd * tp_R * r0
            if (L[k] <= ml) if dd == 1 else (H[k] >= ml):
                close("SL", k, ml)
            elif (H[k] >= tp) if dd == 1 else (L[k] <= tp):
                close("TP", k, tp)
            else:
                fav = dd * ((H[k] if dd == 1 else L[k]) - op["e0"]) / r0
                if fav >= half:
                    op["ok"] = True
                if conf or "conf" in triggers:
                    for e in ev_at.get(k, []):
                        if e[1] == dd and op["ok"] and gate(e[2]):
                            if "conf" in triggers:
                                add(e[2], e[3], r0, ml)            # schedule-sized
                            else:
                                x = lot_to_pin(op["pos"], e[2], e[3], dd, op["E0"], TR, MPL)
                                if x >= VOL_STEP:
                                    op["pos"].append((e[2], x)); op["last"] = e[2]
                if "bounce" in triggers and op["ok"]:
                    wrong = (C[k] < SMA[k]) if dd == 1 else (C[k] > SMA[k])
                    back  = (C[k] >= SMA[k]) if dd == 1 else (C[k] <= SMA[k])
                    if wrong:
                        op["arm_b"] = True
                        cur = op.get("anc_b")
                        ext = L[k] if dd == 1 else H[k]
                        op["anc_b"] = ext if cur is None else (min(cur, ext) if dd == 1 else max(cur, ext))
                    elif back and op.get("arm_b"):
                        op["arm_b"] = False
                        if gate(C[k]):
                            anc = SLOW[k] if slowP > 0 else op.get("anc_b", ml)
                            add(C[k], anc, r0, ml)
                        op["anc_b"] = None
                if "candle" in triggers and op["ok"]:
                    contrary  = (C[k] < O[k]) if dd == 1 else (C[k] > O[k])
                    confluent = (C[k] > O[k]) if dd == 1 else (C[k] < O[k])
                    if contrary:
                        op["arm_c"] = True
                        op["anc_c"] = L[k] if dd == 1 else H[k]
                    elif confluent and op.get("arm_c"):
                        op["arm_c"] = False
                        if gate(C[k]):
                            ml2 = margin_line(op["pos"], dd, op["E0"], TR, MPL)
                            add(C[k], op.get("anc_c", ml2), r0, ml2)
                if "grid" in triggers and op["ok"]:           # add every grid_R of favorable move
                    lvl = int(fav / grid_R + 1e-9)
                    if lvl > op.get("grid_n", 0):
                        pl = op["e0"] + dd * lvl * grid_R * r0
                        if gate(pl):
                            add(pl, ml, r0, ml)
                        op["grid_n"] = lvl
                if "rsi" in triggers and op["ok"]:            # add on exit from oversold/overbought
                    rv = RSI[k]
                    if dd == 1:
                        if rv < rsi_os:
                            op["arm_r"] = True
                        elif rv >= rsi_os and op.get("arm_r"):
                            op["arm_r"] = False
                            if gate(C[k]):
                                add(C[k], ml, r0, ml)
                    else:
                        if rv > rsi_ob:
                            op["arm_r"] = True
                        elif rv <= rsi_ob and op.get("arm_r"):
                            op["arm_r"] = False
                            if gate(C[k]):
                                add(C[k], ml, r0, ml)
                adv = L[k] if dd == 1 else H[k]
                eq = op["E0"] + sum(dd * (adv - e) * l * TR for e, l in op["pos"])
                peak = max(peak, (op["E0"] - eq) / op["E0"])

        if op is None:
            for e in ev_at.get(k, []):
                dd, entry, sl, rng = e[1], e[2], e[3], e[4]
                if rng <= 0:
                    continue
                E0 = risk_frac * cap0
                lot0 = max(lot_to_pin([], entry, entry - dd * rng, dd, E0, TR, MPL), VOL_MIN)
                if MPL > 0:                                   # margin must fit the deposit
                    lot0 = min(lot0, qfloor(E0 / MPL))
                lot0 = min(lot0, VOL_MAX)
                op = dict(dir=dd, r0=rng, e0=entry, k0=k, E0=E0, pos=[(entry, lot0)],
                          ok=(half <= 0), last=entry, log=[(k, entry, lot0)])
                break

    if op is not None:
        close("END", n - 1, C[n - 1])
    return ops, curve, peak, n


def run_h1(sym, conf=True, gate=True, geo=False, cap0=1000.0, risk_frac=0.01,
           half=0.5, tp_R=3.0):
    """Full-history H1 test: base breakout + structure-pinned same-dir CONFLUENCE
    adds (the only stackable trigger without M1).  geo=False keeps E0 constant so
    totR is directly comparable to the R-space additive champion."""
    from collections import defaultdict
    sp = SPECS[sym]; TR, MPL, COST = sp["TR"], sp["MPL"], sp["cost"]
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= pd.Timestamp("2024-03-26")].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    evs, H, L, C, n = entry_events(d)
    by = defaultdict(list)
    for e in evs:
        by[e["ej"]].append(e)

    ops, curve, capital, op, peak = [], [], cap0, None, 0.0

    def close(reason, k, xp):
        nonlocal capital, op
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xp - e) * l * TR for e, l in op["pos"])
        cost = sum(COST * TR * l for _, l in op["pos"])
        res = max(floating - cost, -E0)
        capital += res
        ops.append((op["k0"], k, res / E0, len(op["pos"]), reason))
        curve.append(capital); op = None

    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
            tp = op["e0"] + dd * tp_R * r0
            if (L[k] <= ml) if dd == 1 else (H[k] >= ml):
                close("SL", k, ml)
            elif (H[k] >= tp) if dd == 1 else (L[k] <= tp):
                close("TP", k, tp)
            else:
                fav = dd * ((H[k] if dd == 1 else L[k]) - op["e0"]) / r0
                if fav >= half:
                    op["ok"] = True
                adv = L[k] if dd == 1 else H[k]
                eq = op["E0"] + sum(dd * (adv - e) * l * TR for e, l in op["pos"])
                peak = max(peak, (op["E0"] - eq) / op["E0"])

        for e in by.get(k, []):
            if op is None:
                E0 = risk_frac * (capital if geo else cap0)
                lot0 = max(lot_to_pin([], e["entry"], e["entry"] - e["d"] * e["rng"],
                                      e["d"], E0, TR, MPL), VOL_MIN)
                op = dict(dir=e["d"], r0=e["rng"], e0=e["entry"], k0=k, E0=E0,
                          pos=[(e["entry"], min(lot0, VOL_MAX))], ok=(half <= 0), last=e["entry"])
            elif conf and e["d"] == op["dir"] and op["ok"] \
                    and (not gate or ((e["entry"] > op["last"]) if op["dir"] == 1 else (e["entry"] < op["last"]))) \
                    and sum(l for _, l in op["pos"]) < VOL_MAX:
                x = lot_to_pin(op["pos"], e["entry"], e["sl"], op["dir"], op["E0"], TR, MPL)
                if x >= VOL_STEP:
                    op["pos"].append((e["entry"], x)); op["last"] = e["entry"]

    if op is not None:
        close("END", n - 1, C[n - 1])
    return ops, curve, peak, n


def show_h1(sym):
    print(f"\n================ {sym}  H1 confluence stacking (full 2.2yr) ============")
    print(f"  {'variant':<16}{'ops':>5}{'totR':>8}{'PF':>6}{'maxDD':>7}{'RF':>6}{'win%':>6}"
          f"{'TP#':>5}{'avgPos':>7}{'mxPos':>6}{'minR':>7}{'mtmDD':>7}{'segs':>6}")
    for lbl, conf, gate in [("no-add", False, True), ("conf+gate", True, True),
                            ("conf no-gate", True, False)]:
        ops, curve, pm, n = run_h1(sym, conf=conf, gate=gate)
        s = st(ops, curve, pm); q = n // 6
        seg = [sum(o[2] for o in ops if k*q <= o[0] < (n if k == 5 else (k+1)*q)) for k in range(6)]
        rob = sum(1 for t in seg if t > 0)
        rf = s["totR"] / s["maxdd"] if s["maxdd"] > 0 else 0
        print(f"  {lbl:<16}{s['n']:>5}{s['totR']:>8.1f}{s['pf']:>6.2f}{s['maxdd']:>7.1f}{rf:>6.1f}"
              f"{s['win']:>6.1f}{s['tp']:>5}{s['avgpos']:>7.1f}{s['maxpos']:>6.0f}{s['minR']:>7.2f}"
              f"{s['mtm']:>7.2f}   {rob}/6")


def st(ops, curve, pm, cap0=1000.0):
    R = np.array([o[2] for o in ops]) if ops else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    cum = peak = dd = 0.0
    for o in sorted(ops, key=lambda o: o[1]):
        cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
    npos = [o[3] for o in ops]
    tp = sum(1 for o in ops if o[4] == "TP")
    return dict(n=len(R), totR=R.sum(), pf=(w / l if l > 0 else 9.99), maxdd=dd,
                win=100*np.mean(R > 0), tp=tp, minR=R.min(), mtm=pm,
                avgpos=np.mean(npos) if npos else 0, maxpos=max(npos) if npos else 0,
                final=curve[-1] if curve else cap0)


def show(sym):
    m1 = pd.read_csv(glob.glob(f"data/*{sym}*_M1.csv")[0], parse_dates=["time"])
    days = (m1["time"].iloc[-1] - m1["time"].iloc[0]).days
    print(f"\n================ {sym}  unified engine (real M1, {days}d) ============")
    hdr = (f"  {'variant':<22}{'totR':>8}{'PF':>6}{'maxDD':>7}{'win%':>6}{'TP#':>5}"
           f"{'avgPos':>7}{'mxPos':>6}{'minR':>7}{'mtmDD':>7}{'final$':>8}")
    print(hdr)
    def row(lbl, ops, curve, pm):
        s = st(ops, curve, pm)
        print(f"  {lbl:<22}{s['totR']:>8.1f}{s['pf']:>6.2f}{s['maxdd']:>7.1f}{s['win']:>6.1f}"
              f"{s['tp']:>5}{s['avgpos']:>7.1f}{s['maxpos']:>6.0f}{s['minR']:>7.2f}"
              f"{s['mtm']:>7.2f}{s['final']:>8.0f}")
    row("no-add", *run(sym, triggers=())[:3])
    row("conf-only", *run(sym, triggers=("conf",))[:3])
    for ml in [1.5, 2, 3, 5, 8, 12, 20]:
        row(f"bounce ML{int(ml*100)}%", *run(sym, triggers=("bounce",), ml_target=ml)[:3])
    for ml in [2, 3, 5, 8, 20]:
        row(f"both ML{int(ml*100)}%", *run(sym, triggers=("conf", "bounce"), ml_target=ml)[:3])


if __name__ == "__main__":
    show("BTC")
    show("XAU")
