"""
Compound pyramid — margin-line SL + geometric 1%-of-capital bankroll (BTC).

The current best BTC operation, UNCHANGED (V-pattern trigger, breakout entry,
R = first-signal range, chandelier SL stepped in G with 2.5R give-back, add on
each up-step), with exactly two edits vs the additive pyramid:

  1. TP 3R (not 5R).
  2. SL order  ->  MARGIN LINE.  Each up-step we don't top-up to a fixed -1R; we
     add the *largest* lot that pushes the book's stop-out (margin-call) price up
     to where the chandelier SL currently sits.  That deploys the whole
     operations account, so winning books BALLOON in size while the trade runs.

Two-account capital model (user's "deploying capital"):
  - Total capital starts at $1000.  Main/Bank holds it and never trades.
  - Each operation funds an Operations account with **1% of current total
    capital** (= 1R in cash).  Win -> sweep profit back to Main (capital grows ->
    next stake grows); blow -> lose exactly that 1% (capital shrinks).  So stakes
    compound GEOMETRICALLY across operations; size compounds WITHIN an operation.
  - Stop-out at equity 0 (broker SO_SO = 0%) => a liquidation costs exactly the
    deposit => hard -1R floor per operation, by construction.

Money-space, live BTCUSDc specs (cent account, pulled from the terminal):
  contract 0.01, $0.01 P&L per $1 move per lot, margin ~$1.57/lot (~400:1),
  vol_min/step 0.01, VOL_MAX 200 (the one thing that does NOT scale -> as capital
  compounds the stake's base lots rise toward 200 and throttle the compounding).

Buffer sweep: place the margin line at SO_SO + buffer (0 / 5 / 10%) so a liquidation
leaves a cushion instead of literal zero equity.

Run:  python pyramid_compound.py
"""
import glob
from collections import defaultdict
import numpy as np
import pandas as pd
import signals as sg
from book_sim import entry_events
import pyramid_sim as ps

# ---- live BTCUSDc specs (USD), from MetaTrader5 order_calc_margin / symbol_info ----
TR        = 0.01      # $ P&L per 1.0 price unit, per 1.0 lot (= contract size)
MPL       = 1.5687    # margin per 1.0 lot, USD (156.87 USC) -> effective ~400:1
VOL_MIN   = 0.01
VOL_STEP  = 0.01
VOL_MAX   = 200.0
COST_PX   = 18.0      # round-trip cost in PRICE units (~the $10 spread); matches additive baseline
TRAIL     = 2.5       # chandelier give-back, in R


def _qfloor(lot):
    """Quantize a lot down to the broker volume step."""
    return np.floor(lot / VOL_STEP + 1e-9) * VOL_STEP


def add_to_pin_margin_line(book, P, S, dd, E0, so_frac):
    """Largest lot to add at price P so the book's stop-out price reaches S.

    Solves  E0 + TR*[A + d*(S-P)*x] = so_frac*MPL*(L+x)  for x, where
    A = sum d*(S-entry)*lot over the book (floating at S, in price*lot units).
    Returns a step-quantized lot >= 0 (0 if no room: BE ceiling reached / book full).
    """
    L = sum(lot for _, lot in book)
    A = sum(dd * (S - e) * lot for e, lot in book)
    denom = TR * dd * (S - P) - so_frac * MPL          # < 0 for a valid (S past P) stop
    if denom >= 0:
        return 0.0
    x = (so_frac * MPL * L - E0 - TR * A) / denom
    if x <= 0:
        return 0.0
    x = min(x, VOL_MAX - L)
    return max(0.0, _qfloor(x))


def margin_line_price(book, dd, E0, so_frac):
    """Price at which equity falls to so_frac*margin (the live stop-out / margin line)."""
    L = sum(lot for _, lot in book)
    if L <= 0:
        return None
    we = sum(e * lot for e, lot in book) / L           # weighted entry
    return we + dd * (so_frac * MPL * L - E0) / (TR * L)


def run_op_stream(d, G, tp_R, so_frac, cap0=1000.0, risk_frac=0.01, trail=TRAIL):
    """Walk the bars once; run sequential compound operations on a geometric
    1%-of-capital bankroll.  `trail` = chandelier give-back in R (when adds start).
    Returns (ops, capital_curve).
    ops item: (entry_bar, exit_bar, result_R, n_positions, reason, deposit$)."""
    evs, H, L, C, n = entry_events(d)
    by_bar = defaultdict(list)
    for e in evs:
        by_bar[e["ej"]].append(e)

    ops, curve = [], []
    capital = cap0
    op = None

    def close(reason, k, xprice):
        nonlocal capital, op
        dd, E0 = op["dir"], op["E0"]
        floating = sum(dd * (xprice - e) * lot * TR for e, lot in op["pos"])
        cost = sum(COST_PX * TR * lot for _, lot in op["pos"])
        res_cash = floating - cost
        res_cash = max(res_cash, -E0)                  # hard floor: can't lose > the deposit
        capital += res_cash
        ops.append((op["ebar"], k, res_cash / E0, len(op["pos"]), reason, E0))
        curve.append(capital)
        op = None

    for k in range(n):
        if op is not None:
            dd, r0 = op["dir"], op["r0"]
            gb, step = trail * r0, G * r0
            mline = margin_line_price(op["pos"], dd, op["E0"], so_frac)
            tp_price = op["e0"] + dd * tp_R * r0

            stop_hit = (L[k] <= mline) if dd == 1 else (H[k] >= mline)
            tp_hit   = (H[k] >= tp_price) if dd == 1 else (L[k] <= tp_price)
            if stop_hit:
                close("SL", k, mline)
            elif tp_hit:
                close("TP", k, tp_price)
            else:                                       # ---- extend chandelier, add on each step ----
                if dd == 1:
                    op["ext"] = max(op["ext"], H[k]); chand = op["ext"] - gb
                    while op["sl"] + step <= chand and sum(l for _, l in op["pos"]) < VOL_MAX:
                        op["sl"] += step
                        Padd = op["sl"] + gb
                        x = add_to_pin_margin_line(op["pos"], Padd, op["sl"], dd, op["E0"], so_frac)
                        if x < VOL_STEP:
                            break
                        op["pos"].append((Padd, x))
                else:
                    op["ext"] = min(op["ext"], L[k]); chand = op["ext"] + gb
                    while op["sl"] - step >= chand and sum(l for _, l in op["pos"]) < VOL_MAX:
                        op["sl"] -= step
                        Padd = op["sl"] - gb
                        x = add_to_pin_margin_line(op["pos"], Padd, op["sl"], dd, op["E0"], so_frac)
                        if x < VOL_STEP:
                            break
                        op["pos"].append((Padd, x))

        if op is None:                                  # flat -> open next signal
            for e in by_bar.get(k, []):
                if e["rng"] <= 0:
                    continue
                E0 = risk_frac * capital
                lot0 = add_to_pin_margin_line([], e["entry"], e["sl"], e["d"], E0, so_frac)
                lot0 = max(lot0, VOL_MIN)               # always take at least the min lot
                lot0 = min(lot0, VOL_MAX)
                op = dict(dir=e["d"], r0=e["rng"], ebar=k, e0=e["entry"], ext=e["entry"],
                          sl=e["sl"], E0=E0, pos=[(e["entry"], lot0)])
                break

    if op is not None:
        close("END", n - 1, C[n - 1])
    return ops, curve, cap0


def stat(ops, curve, cap0):
    R = np.array([o[2] for o in ops]) if ops else np.array([0.0])
    w, l = R[R > 0].sum(), -R[R <= 0].sum()
    # drawdown in R-space (realized) and in % of the compounding capital curve
    cum = peak = ddR = 0.0
    for _, _, r, _, _, _ in sorted(ops, key=lambda o: o[1]):
        cum += r; peak = max(peak, cum); ddR = max(ddR, peak - cum)
    eq = np.array([cap0] + curve)
    pk = np.maximum.accumulate(eq)
    ddPct = float(np.max((pk - eq) / pk) * 100) if len(eq) else 0.0
    npos = [o[3] for o in ops]
    return dict(n=len(R), totR=R.sum(), avgR=R.mean(), pf=(w / l if l > 0 else 9.99),
                ddR=ddR, ddPct=ddPct, win=100 * np.mean(R > 0), final=curve[-1] if curve else cap0,
                avgpos=np.mean(npos) if npos else 0, maxpos=max(npos) if npos else 0)


def seg_robust(ops, n):
    q = n // 6
    seg = [sum(r for eb, xb, r, *_ in ops if k*q <= eb < (n if k == 5 else (k+1)*q)) for k in range(6)]
    return sum(1 for t in seg if t > 0), seg


def run(sym="BTC"):
    raw = pd.read_csv(glob.glob(f"data/*{sym}*_H1.csv")[0], parse_dates=["time"])
    raw = raw[raw["time"] >= pd.Timestamp("2024-03-26")].reset_index(drop=True)
    d = sg.add_features(raw, period=20, mult=2.0)
    n = len(d)

    def add_stat(ops):                                  # additive baseline: ops are (eb,xb,R,npos,reason)
        R = np.array([o[2] for o in ops])
        w, l = R[R > 0].sum(), -R[R <= 0].sum()
        cum = peak = dd = 0.0
        for o in sorted(ops, key=lambda o: o[1]):
            cum += o[2]; peak = max(peak, cum); dd = max(dd, peak - cum)
        return R.sum(), (w / l if l > 0 else 9.99), dd, 100*np.mean(R > 0), np.mean([o[3] for o in ops])

    print(f"\n================ {sym}  COMPOUND (margin-line SL, 1%/op bankroll, $1000 start) ============")
    print("additive baselines (R-space, pyramid_sim) for reference:")
    for G, tp in [(0.25, 5), (0.25, 3), (1.0, 3)]:
        ops = ps.run_sym(d, COST_PX, G, tp_R=tp)
        totR, pf, dd, win, avgp = add_stat(ops)
        ap, _ = seg_robust([(o[0], o[1], o[2]) for o in ops], n)
        print(f"  additive TP{tp}R G{G:<5} totR {totR:6.1f}  PF {pf:.2f}  "
              f"maxDD {dd:5.1f}R  win {win:4.1f}%  avgPos {avgp:4.1f}  ({ap}/6)")

    for buf, blbl in [(0.00, "0%"), (0.05, "5%"), (0.10, "10%")]:
        print(f"\n  --- margin buffer {blbl} ---")
        print(f"  {'step G':<9}{'ops':>4}{'totR':>8}{'avgR':>7}{'PF':>6}{'maxDD_R':>8}"
              f"{'DD%':>6}{'win%':>6}{'final$':>9}{'avgPos':>7}{'mxPos':>6}  segs")
        for G, lbl in [(0.25, "0.25R"), (0.50, "0.50R"), (1.0, "1.00R")]:
            ops, curve, c0 = run_op_stream(d, G, tp_R=3, so_frac=buf)
            s = stat(ops, curve, c0)
            rob, _ = seg_robust(ops, n)
            print(f"  {lbl:<9}{s['n']:>4}{s['totR']:>8.1f}{s['avgR']:>7.2f}{s['pf']:>6.2f}"
                  f"{s['ddR']:>8.1f}{s['ddPct']:>6.1f}{s['win']:>6.1f}{s['final']:>9.0f}"
                  f"{s['avgpos']:>7.1f}{s['maxpos']:>6.0f}   {rob}/6")


if __name__ == "__main__":
    run("BTC")
