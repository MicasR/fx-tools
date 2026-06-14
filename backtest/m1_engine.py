"""
m1_engine.py — M1-INTRABAR concurrent engine (FIDELITY §3.3, the M1 route).

Goal: reproduce the MQL5 Strategy-Tester (Model 1, NBP-clamped) as a FAST Python
engine, by removing the bar-granularity optimism that made the old `conc_engine`
(management-TF bars) diverge. The decomposition (FIDELITY_FINDINGS) showed the
residual gap is the **entry set** under max_conc=1: the tester exits ops INTRABAR,
frees the single slot sooner, and catches more breakouts. So here:

  * ENTRY  : V-pattern signal on H1 (DERIVED from M1 so tick_volume = ΣM1, per
             DATA PARITY); the breakout fills at the FIRST M1 bar that touches the
             signal bar's high/low within the WAIT window -- gated on a free slot
             AT THAT M1 (this is what frees the slot intrabar).
  * EXITS  : SL / TP / chandelier-trail checked every M1 bar (not once per mgmt bar).
  * GATE   : favourable >= half checked every M1 (running extreme).
  * MGMT   : SMA-bounce arming/adds run on the MANAGEMENT-TF close (M15 gold / H1
             BTC), using that mgmt bar's OHLC/SMA -- same cadence as the EA.

Everything else (sizing rules, margin-line liquidation, the gate, geofloor/proggeo)
is the SAME primitive code as conc_engine/pyramid_engine. Returns run_tf_conc's
6-tuple op format + (tm1, H1, L1, n1) so callers can NBP-clamp / fingerprint.

DATA: consumes ONLY the dumped M1 (m1_data.derive) -> H1 entry frame & mgmt frame
are both aggregated from it. Same data in as the tester's Model 1.
"""
import numpy as np
import pandas as pd
import signals as sg
from m1_data import load_m1, derive
from book_sim import WAIT
from pyramid_engine import (SPECS, VOL_MIN, VOL_STEP, VOL_MAX, qfloor,
                            margin_line, lot_to_pin, _size_add)

_TF_MIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}


def m1_entry_events(sym, tm1, H1, L1):
    """V-pattern breakouts with M1 fill timing. Signal on DERIVED-H1 (tick_volume
    = ΣM1); for each signal bar find the FIRST M1 bar in the WAIT window (the next
    WAIT H1 bars) that touches the signal bar's high (up) or low (down). If a single
    M1 bar touches both -> ambiguous -> skip (matches book_sim.entry_events).
    Returns list of (fill_m1_idx, dir, entry_level, sl, rng), sorted by fill idx."""
    h1 = derive(sym, "H1")
    d = sg.add_features(h1, period=20, mult=2.0)
    sig = sg.volumevpattern_signal(d, method="threshold", rise_pct=0.02)
    Hh, Lh, A = d["high"].to_numpy(), d["low"].to_numpy(), d["atr"].to_numpy()
    th = d["time"].to_numpy()
    nH = len(d)
    idx = np.flatnonzero(sig.to_numpy())
    idx = idx[(idx + 1 < nH) & ~np.isnan(A[idx])]

    evs = []
    for i in idx:
        hi, lo = Hh[i], Lh[i]
        rng = hi - lo
        if rng <= 0:
            continue
        # M1 window = [open of H1 bar i+1, close of H1 bar i+WAIT)
        t0 = th[i + 1]
        j_last = min(i + WAIT, nH - 1)
        t1 = th[j_last] + np.timedelta64(60, "m")            # exclusive end
        a = int(np.searchsorted(tm1, t0, side="left"))
        b = int(np.searchsorted(tm1, t1, side="left"))
        fill = None
        for k in range(a, b):
            up = H1[k] >= hi
            dn = L1[k] <= lo
            if up and dn:
                break                                        # ambiguous bar -> skip signal
            if up:
                fill = (k, 1, hi, lo, rng); break
            if dn:
                fill = (k, -1, lo, hi, rng); break
        if fill is not None:
            evs.append(fill)
    evs.sort(key=lambda e: e[0])
    return evs


def run_m1_conc(sym="XAU", tf="M15", smaP=7, slowP=0, sizing="proggeo", mult=1.0,
                prog_step=1.7, unit="base", tp_R=3.0, lev=2000.0, stack=True,
                max_conc=1, conc_dir="same", cap0=1000.0, risk_frac=0.01,
                half=0.5, buf=0.0, ml_target=3.0, gb=1.0, prev_fb="skip",
                trig="bounce", nback=0, trail_R=0.0):
    sp = SPECS[sym]; TR, MPL0, COST = sp["TR"], sp["MPL"], sp["cost"]
    MPL = MPL0 * 400.0 / lev if lev > 0 else 0.0

    # --- M1 master clock ---
    m1 = load_m1(sym)
    tm1 = m1["time"].to_numpy()
    O1, H1, L1, C1 = (m1[c].to_numpy() for c in ("open", "high", "low", "close"))
    n1 = len(m1)

    # --- management frame (derived from the SAME M1), warmup-trimmed like conc_engine ---
    g = derive(sym, tf)
    if stack:
        g["sma"] = g["close"].rolling(smaP).mean()
    if slowP > 0:
        g["slow"] = g["close"].rolling(slowP).mean()
    g = g.dropna().reset_index(drop=True)
    Og, Hg, Lg, Cg = (g[c].to_numpy() for c in ("open", "high", "low", "close"))
    SMA = g["sma"].to_numpy() if stack else None
    SLOW = g["slow"].to_numpy() if slowP > 0 else None
    gstart = {t: i for i, t in enumerate(g["time"].to_numpy())}

    # map each M1 -> its mgmt-bar index (post-warmup) and flag the mgmt-bar close M1
    per = _TF_MIN[tf]
    mfloor = pd.Series(tm1).dt.floor(f"{per}min").to_numpy()
    gidx = np.array([gstart.get(t, -1) for t in mfloor])
    is_close = np.empty(n1, dtype=bool)
    is_close[-1] = True
    is_close[:-1] = mfloor[1:] != mfloor[:-1]

    # --- entry signal frame: V-pattern on DERIVED H1 (tick_volume = ΣM1) ---
    h1 = derive(sym, "H1")
    d = sg.add_features(h1, period=20, mult=2.0)
    SIG = sg.volumevpattern_signal(d, method="threshold", rise_pct=0.02).to_numpy()
    Hh, Lh = d["high"].to_numpy(), d["low"].to_numpy()
    hmap = {t: i for i, t in enumerate(d["time"].to_numpy())}
    h1floor = pd.Series(tm1).dt.floor("1h").to_numpy()
    h1idx = np.array([hmap.get(t, -1) for t in h1floor])
    is_h1open = np.empty(n1, dtype=bool)
    is_h1open[0] = True
    is_h1open[1:] = h1floor[1:] != h1floor[:-1]
    BREAK_BARS = WAIT   # EA InpBreakBars = 4 H1 bars

    results, ops_open, pend = [], [], None

    def close(op, k, xp, reason):
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xp - e) * l * TR for e, l in op["pos"])
        cost = sum(COST * TR * l for _, l in op["pos"])
        res = max(floating - cost, -E0)
        results.append((op["k0"], k, res / E0, len(op["pos"]), reason,
                        dict(dir=dd, E0=E0, r0=op["r0"], e0=op["e0"], log=list(op["log"]))))

    def do_add(op, P, anchor, r0, ml, k):
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

    def pin_add(op, P, S, k):
        dd = op["dir"]
        x = min(lot_to_pin(op["pos"], P, S, dd, op["E0"], TR, MPL), VOL_MAX)
        if MPL > 0:
            Lb = sum(l for _, l in op["pos"])
            eq = op["E0"] + sum(dd * (P - e) * l * TR for e, l in op["pos"])
            x = min(x, qfloor(max(0.0, eq / MPL - Lb)))
        if x >= VOL_STEP:
            op["pos"].append((P, x)); op["last"] = P
            op["log"].append((k, P, x))

    for k in range(n1):
        # 1. EXITS (every M1 bar) + favourable gate + trail-extreme update
        for op in list(ops_open):
            dd, r0 = op["dir"], op["r0"]
            ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
            if trail_R > 0:
                # chandelier stop set on the LAST mgmt-bar close (op["ext"] frozen
                # between closes); the broker enforces that fixed level every M1.
                trail = op["ext"] - dd * trail_R * r0
                stop = max(ml, trail) if dd == 1 else min(ml, trail)
                if (L1[k] <= stop) if dd == 1 else (H1[k] >= stop):
                    rsn = "TR" if ((trail > ml) if dd == 1 else (trail < ml)) else "SL"
                    close(op, k, stop, rsn); ops_open.remove(op); continue
                if tp_R > 0:
                    tp = op["e0"] + dd * tp_R * r0
                    if (H1[k] >= tp) if dd == 1 else (L1[k] <= tp):
                        close(op, k, tp, "TP"); ops_open.remove(op); continue
            else:
                tp = op["e0"] + dd * tp_R * r0
                if (L1[k] <= ml) if dd == 1 else (H1[k] >= ml):
                    close(op, k, ml, "SL"); ops_open.remove(op); continue
                if (H1[k] >= tp) if dd == 1 else (L1[k] <= tp):
                    close(op, k, tp, "TP"); ops_open.remove(op); continue

        # 2. ENTRY CADENCE (H1 open, flat only): arm/cancel the pending breakout pair.
        #    The EA arms a Buy-Stop@H / Sell-Stop@L pair on a closed-H1 trigger bar
        #    ONLY when flat with no pending; while in-op no breakout is ever armed
        #    (so an intrabar exit can NOT grab a later breakout). Pair expires after
        #    BREAK_BARS H1 bars.
        if is_h1open[k] and not ops_open:
            c = h1idx[k]
            if pend is not None:
                if c - pend["arm_bar"] >= BREAK_BARS:        # stale -> cancel (re-arm next bar)
                    pend = None
            elif c >= 1 and SIG[c - 1]:                      # flat & no pending -> arm on just-closed bar
                hi, lo = Hh[c - 1], Lh[c - 1]
                if hi - lo > 0:
                    pend = dict(hi=hi, lo=lo, r0=hi - lo, arm_bar=c)

        # 3. FILL: pending level touched at this M1 (flat) -> open op at the break level
        if pend is not None and not ops_open:
            buy = H1[k] >= pend["hi"]; sell = L1[k] <= pend["lo"]
            if buy or sell:
                dd = (1 if C1[k] >= O1[k] else -1) if (buy and sell) else (1 if buy else -1)
                entry = pend["hi"] if dd == 1 else pend["lo"]
                rng = pend["r0"]
                E0 = risk_frac * cap0
                lot0 = max(lot_to_pin([], entry, entry - dd * rng, dd, E0, TR, MPL), VOL_MIN)
                if MPL > 0:
                    lot0 = min(lot0, qfloor(E0 / MPL))
                lot0 = min(lot0, VOL_MAX)
                ops_open.append(dict(dir=dd, r0=rng, e0=entry, k0=k, E0=E0,
                                     pos=[(entry, lot0)], ok=(half <= 0), last=entry, ext=entry,
                                     log=[(k, entry, lot0)], arm_b=False, anc_b=None, prev_anc=None))
                pend = None

        # 4. MGMT-TF close: ratchet the chandelier extreme (per mgmt bar, not per M1),
        #    then run SMA-bounce adds (uses the mgmt bar's OHLC/SMA)
        if is_close[k] and gidx[k] >= 0:
            j = gidx[k]
            for op in ops_open:
                dd = op["dir"]
                if trail_R > 0:                              # ratchet chandelier extreme
                    op["ext"] = max(op["ext"], Hg[j]) if dd == 1 else min(op["ext"], Lg[j])
                # favourable gate: checked AT the mgmt-bar close on that bar's extreme
                # (EA ManagementCadence) -- NOT mid-bar, or the first add fires too early
                adv = Hg[j] if dd == 1 else Lg[j]
                if dd * (adv - op["e0"]) / op["r0"] >= half:
                    op["ok"] = True
        if stack and is_close[k] and gidx[k] >= 0:
            j = gidx[k]
            for op in ops_open:
                if not op["ok"]:
                    continue
                dd, r0 = op["dir"], op["r0"]
                ml = margin_line(op["pos"], dd, op["E0"], TR, MPL)
                gated = (Cg[j] > op["last"]) if dd == 1 else (Cg[j] < op["last"])
                nb = (Lg[j - nback] if dd == 1 else Hg[j - nback]) if (nback > 0 and j >= nback) else None
                if trig == "poscandle":
                    confluent = (Cg[j] > Og[j]) if dd == 1 else (Cg[j] < Og[j])
                    if confluent and gated:
                        anc = nb if nb is not None else (SLOW[j] if slowP > 0 else ml)
                        do_add(op, Cg[j], anc, r0, ml, k)
                else:
                    wrong = (Cg[j] < SMA[j]) if dd == 1 else (Cg[j] > SMA[j])
                    back = (Cg[j] >= SMA[j]) if dd == 1 else (Cg[j] <= SMA[j])
                    if wrong:
                        op["arm_b"] = True
                        cur = op.get("anc_b"); ext = Lg[j] if dd == 1 else Hg[j]
                        op["anc_b"] = ext if cur is None else (min(cur, ext) if dd == 1 else max(cur, ext))
                    elif back and op.get("arm_b"):
                        op["arm_b"] = False
                        cur_anc = op.get("anc_b")
                        if gated and sizing == "pinprev":
                            prev = op.get("prev_anc")
                            beyond = prev is not None and ((prev < cur_anc) if dd == 1 else (prev > cur_anc))
                            S = prev if beyond else (cur_anc if prev_fb == "current" else None)
                            if S is not None:
                                pin_add(op, Cg[j], S, k)
                        elif gated:
                            anc = nb if nb is not None else (SLOW[j] if slowP > 0 else (cur_anc if cur_anc is not None else ml))
                            do_add(op, Cg[j], anc, r0, ml, k)
                        if cur_anc is not None:
                            op["prev_anc"] = cur_anc
                        op["anc_b"] = None

    for op in ops_open:
        close(op, n1 - 1, C1[n1 - 1], "END")
    return results, tm1, H1, L1, n1
